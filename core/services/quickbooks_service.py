import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.urls import reverse

from django_tenants.utils import schema_context

from core.services.base import TenantAwareService
from core.services.exceptions import ValidationException, NotFoundException, BusinessLogicException
from django.core.exceptions import ValidationError as DjangoValidationError
from core.models import QuickBooksIntegration, QuickBooksRealmMapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from quickbooks.base import QuickBooksAuth
except ImportError:
    QuickBooksAuth = None


class QuickBooksService(TenantAwareService):
    def __init__(self, tenant):
        super().__init__(QuickBooksIntegration, tenant)

    def get_integration(self) -> Optional[QuickBooksIntegration]:
        return self.get_base_queryset().first()

    def get_or_create_integration(self, **kwargs) -> QuickBooksIntegration:
        integration = self.get_integration()
        if not integration:
            if 'redirect_uri' not in kwargs:
                base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
                kwargs['redirect_uri'] = base_url + reverse('core:quickbooks_callback')

            integration = self.create(**kwargs)
        return integration

    def update_credentials(self, client_id: str, client_secret: str, environment: str = 'sandbox') -> QuickBooksIntegration:
        if not client_id or not client_secret:
            raise ValidationException("Client ID and Client Secret are required")

        try:
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            redirect_uri = base_url + reverse('core:quickbooks_callback')

            integration = self.get_integration()
            if not integration:
                integration = self.create(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                    environment=environment
                )
            else:
                integration.client_id = client_id
                integration.client_secret = client_secret
                integration.environment = environment
                # Keep the stored redirect_uri in step with the current
                # BASE_URL - a stale value (e.g. sandbox host) makes the OAuth
                # handshake fail with redirect_uri_mismatch.
                integration.redirect_uri = redirect_uri
                integration.save()

            return integration

        except DjangoValidationError as e:
            raise ValidationException(f"Validation failed: {str(e)}")
        except Exception as e:
            raise BusinessLogicException(f"Failed to update credentials: {str(e)}")

    def get_auth_client(self) -> 'QuickBooksAuth':
        if QuickBooksAuth is None:
            raise ValidationException("QuickBooks integration not available - missing dependencies")

        integration = self.get_integration()
        if not integration:
            raise NotFoundException("QuickBooks integration not configured")

        if not integration.client_id or not integration.client_secret:
            raise ValidationException("QuickBooks credentials not configured")

        auth_client = QuickBooksAuth(
            client_id=integration.client_id,
            client_secret=integration.client_secret,
            redirect_uri=integration.redirect_uri,
            environment=integration.environment
        )
        
        # Load tokens from database if available
        if integration.access_token:
            auth_client.access_token = integration.access_token
        if integration.refresh_token:
            auth_client.refresh_token = integration.refresh_token
        if integration.realm_id:
            auth_client.realm_id = integration.realm_id
            
        return auth_client

    def get_authorization_url(self) -> str:
        auth_client = self.get_auth_client()
        return auth_client.get_authorization_url()


    def connect(self, auth_code: str, realm_id: str) -> QuickBooksIntegration:
        if not auth_code or not realm_id:
            raise ValidationException("Authorization code and realm ID are required")

        integration = self.get_integration()
        if not integration:
            raise NotFoundException("QuickBooks integration not configured")

        try:
            auth_client = self.get_auth_client()
            logger.debug(
                f"Attempting to get bearer token with auth_code: {auth_code}, realm_id: {realm_id}"
            )
            token_response = auth_client.get_bearer_token(auth_code, realm_id)

            if token_response is None:
                logger.error(
                    f"Token response is None for auth_code: {auth_code}, realm_id: {realm_id}"
                )
                raise BusinessLogicException(
                    "Failed to obtain tokens from QuickBooks: No response received"
                )

            if not isinstance(token_response, dict) or "access_token" not in token_response:
                logger.error(f"Invalid token response: {token_response}")
                raise BusinessLogicException(
                    f"Invalid token response from QuickBooks: {token_response}"
                )

            integration.access_token = token_response.get("access_token")
            integration.refresh_token = token_response.get("refresh_token")
            integration.realm_id = realm_id
            integration.is_connected = True

            expires_in = token_response.get("expires_in", 3600)
            integration.token_expires_at = timezone.now() + timedelta(seconds=expires_in)

            integration.save()
            self._update_company_info(integration)
            self._sync_realm_mapping(realm_id)

            # Trigger automatic student sync after successful authentication
            self._trigger_automatic_student_sync(integration)

            return integration

        except Exception as e:
            logger.error(f"Failed to connect to QuickBooks: {str(e)}")
            raise BusinessLogicException(f"Failed to connect to QuickBooks: {str(e)}")

    def disconnect(self) -> bool:
        integration = self.get_integration()
        if not integration or not integration.is_connected:
            return True

        try:
            if integration.refresh_token:
                auth_client = self.get_auth_client()
                auth_client.refresh_token = integration.refresh_token
                auth_client.revoke_token()
        except Exception:
            pass

        old_realm_id = integration.realm_id

        integration.access_token = None
        integration.refresh_token = None
        integration.realm_id = None
        integration.token_expires_at = None
        integration.is_connected = False
        integration.last_sync = None
        integration.company_name = None
        integration.company_country = None
        integration.save()

        if old_realm_id:
            self._remove_realm_mapping(old_realm_id)

        return True

    def _sync_realm_mapping(self, realm_id: str) -> None:
        """Upsert the public-schema realm_id -> tenant lookup used by the
        QuickBooks webhook handler to resolve which tenant an event is for.
        """
        try:
            with schema_context('public'):
                QuickBooksRealmMapping.objects.update_or_create(
                    realm_id=realm_id, defaults={'tenant': self.tenant},
                )
        except Exception as e:
            logger.error(f"Failed to record QuickBooks realm mapping for tenant {self.tenant.id}: {e}")

    def _remove_realm_mapping(self, realm_id: str) -> None:
        try:
            with schema_context('public'):
                QuickBooksRealmMapping.objects.filter(realm_id=realm_id, tenant=self.tenant).delete()
        except Exception as e:
            logger.error(f"Failed to remove QuickBooks realm mapping for tenant {self.tenant.id}: {e}")

    def refresh_token(self, max_retries: int = 3) -> QuickBooksIntegration:
        """
        Refresh the QuickBooks access token with retry logic.
        
        Args:
            max_retries: Maximum number of retry attempts
        """
        integration = self.get_integration()
        if not integration or not integration.refresh_token:
            raise ValidationException("No refresh token available")

        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting token refresh for tenant {self.tenant.name} (attempt {attempt + 1}/{max_retries})")
                
                auth_client = self.get_auth_client()
                auth_client.refresh_token = integration.refresh_token
                auth_client.access_token = integration.access_token

                token_response = auth_client.refresh_access_token()

                # Validate token response
                if not token_response.get('access_token'):
                    raise BusinessLogicException("No access token in refresh response")

                # Update integration with new tokens
                integration.access_token = token_response.get('access_token')
                if 'refresh_token' in token_response:
                    integration.refresh_token = token_response.get('refresh_token')

                expires_in = token_response.get('expires_in', 3600)
                integration.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
                
                # Ensure connection remains active
                integration.is_connected = True
                integration.last_sync = timezone.now()
                integration.save()
                
                logger.info(f"Successfully refreshed token for tenant {self.tenant.name}")
                return integration

            except Exception as e:
                last_error = e
                logger.warning(f"Token refresh attempt {attempt + 1} failed for tenant {self.tenant.name}: {str(e)}")
                
                # If this was the last attempt or it's an unrecoverable error, break
                if attempt == max_retries - 1 or self._is_unrecoverable_error(e):
                    break
                    
                # Brief delay before retry
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
        
        # All attempts failed
        logger.error(f"All token refresh attempts failed for tenant {self.tenant.name}: {str(last_error)}")
        
        # Only mark as disconnected if it's a refresh token issue
        if self._is_refresh_token_invalid(last_error):
            integration.is_connected = False
            integration.access_token = None
            integration.refresh_token = None
            integration.token_expires_at = None
            integration.save()
            logger.warning(f"Marked QuickBooks as disconnected for tenant {self.tenant.name} due to invalid refresh token")
        
        raise BusinessLogicException(f"Failed to refresh QuickBooks token after {max_retries} attempts: {str(last_error)}")
    
    def _is_unrecoverable_error(self, error: Exception) -> bool:
        """Check if an error is unrecoverable and should not be retried"""
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in [
            'invalid_grant', 'invalid_client', 'unauthorized_client',
            'refresh token is invalid', 'refresh token expired'
        ])
    
    def _is_refresh_token_invalid(self, error: Exception) -> bool:
        """Check if the error indicates the refresh token is invalid"""
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in [
            'invalid_grant', 'refresh token is invalid', 'refresh token expired',
            'unauthorized_client'
        ])

    def ensure_valid_token(self) -> str:
        """
        Ensure we have a valid access token, refreshing if necessary.
        
        This method includes basic thread safety to prevent concurrent refresh attempts.
        """
        from django.db import transaction
        import threading
        
        # Use a class-level lock to prevent concurrent token refreshes for the same tenant
        lock_key = f"qb_refresh_{self.tenant.id}"
        if not hasattr(self.__class__, '_refresh_locks'):
            self.__class__._refresh_locks = {}
        if lock_key not in self.__class__._refresh_locks:
            self.__class__._refresh_locks[lock_key] = threading.Lock()
        
        with self.__class__._refresh_locks[lock_key]:
            # Re-fetch integration inside the lock to get latest state
            with transaction.atomic():
                integration = self.get_integration()
                if not integration or not integration.is_connected:
                    raise ValidationException("QuickBooks is not connected")

                # Check if token needs refresh
                if integration.is_token_expired():
                    logger.info(f"Token expired for tenant {self.tenant.name}, refreshing...")
                    try:
                        integration = self.refresh_token()
                    except BusinessLogicException as e:
                        # Log the refresh failure but don't immediately mark as disconnected
                        # unless it's a permanent failure
                        if self._is_refresh_token_invalid(e):
                            logger.error(f"Refresh token invalid for tenant {self.tenant.name}, marking as disconnected")
                            raise ValidationException("QuickBooks authentication expired. Please reconnect.")
                        else:
                            # Temporary failure - still try to use existing token if not fully expired
                            if integration.token_expires_at and timezone.now() < integration.token_expires_at:
                                logger.warning(f"Token refresh failed but token not yet fully expired, continuing with existing token")
                                return integration.access_token
                            else:
                                raise ValidationException(f"Token refresh failed and token is expired: {str(e)}")

                return integration.access_token

    def get_connection_status(self) -> Dict[str, Any]:
        if QuickBooksAuth is None:
            return {
                'connected': False,
                'configured': False,
                'status': 'dependencies_missing',
                'message': 'QuickBooks integration not available - missing dependencies'
            }

        integration = self.get_integration()

        if not integration:
            return {
                'connected': False,
                'configured': False,
                'status': 'not_configured',
                'message': 'QuickBooks integration not configured'
            }

        if not integration.client_id or not integration.client_secret:
            return {
                'connected': False,
                'configured': False,
                'status': 'credentials_missing',
                'message': 'QuickBooks API credentials not configured'
            }

        if not integration.is_connected:
            return {
                'connected': False,
                'configured': True,
                'status': 'not_connected',
                'message': 'QuickBooks is not connected. Click Connect to authorize.',
                'auth_url': self.get_authorization_url()
            }

        if integration.is_token_expired():
            return {
                'connected': False,
                'configured': True,
                'status': 'token_expired',
                'message': 'QuickBooks connection expired. Please reconnect.'
            }

        return {
            'connected': True,
            'configured': True,
            'status': 'connected',
            'message': f'Connected to {integration.company_name or "QuickBooks"}',
            'company_name': integration.company_name,
            'environment': integration.environment,
            'last_sync': integration.last_sync,
            'sync_enabled': integration.sync_enabled
        }

    def config_warnings(self) -> List[str]:
        """Environment/config problems that don't stop a connection but will
        bite in production (stale redirect_uri, missing webhook verifier token,
        missing realm mapping). Surfaced on the settings page and by the
        quickbooks_preflight command."""
        warnings: List[str] = []
        integration = self.get_integration()
        if not integration:
            return warnings

        base_url = getattr(settings, 'BASE_URL', '')
        expected_redirect = base_url + reverse('core:quickbooks_callback')
        if integration.redirect_uri and integration.redirect_uri != expected_redirect:
            warnings.append(
                f"Stored redirect_uri ({integration.redirect_uri}) does not match "
                f"the current BASE_URL ({expected_redirect}); re-save credentials."
            )

        if integration.environment == 'production':
            if not getattr(settings, 'QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN', ''):
                warnings.append(
                    "QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN is not set - inbound QuickBooks "
                    "webhook notifications will be rejected."
                )
            if integration.is_connected and integration.realm_id:
                with schema_context('public'):
                    mapped = QuickBooksRealmMapping.objects.filter(
                        realm_id=integration.realm_id
                    ).exists()
                if not mapped:
                    warnings.append(
                        "No QuickBooksRealmMapping for this realm - inbound webhooks "
                        "cannot be routed. Run: manage.py backfill_quickbooks_realm_mappings"
                    )
        return warnings

    def _update_company_info(self, integration: QuickBooksIntegration):
        integration.last_sync = timezone.now()
        integration.save()
    
    def _trigger_automatic_student_sync(self, integration: QuickBooksIntegration):  # pylint: disable=unused-argument
        """Trigger automatic student sync after QuickBooks authentication"""
        try:
            # Import here to avoid circular imports
            from core.utils.quickbooks_sync_utils import QuickBooksSyncManager
            
            logger.info(f"Triggering automatic student sync for tenant {self.tenant.name} after QuickBooks authentication")
            
            # Start async sync task for this tenant
            result = QuickBooksSyncManager.sync_tenant_students(
                tenant_id=str(self.tenant.id),
                limit=100,  # Limit initial sync to 100 students
                force_resync=False,  # Don't re-sync already synced students
                run_async=True  # Run asynchronously
            )
            
            if result.get('success'):
                logger.info(f"Automatic student sync task started for tenant {self.tenant.name}: Task ID {result.get('task_id')}")
            else:
                logger.warning(f"Failed to start automatic student sync for tenant {self.tenant.name}: {result.get('error')}")
                
        except Exception as e:
            # Don't let sync failure affect the authentication process
            logger.error(f"Error triggering automatic student sync for tenant {self.tenant.name}: {str(e)}")
            logger.info("QuickBooks authentication was successful, but automatic sync failed")

    def test_connection(self) -> Dict[str, Any]:
        try:
            self.ensure_valid_token()
            return {
                'success': True,
                'message': 'QuickBooks connection is working properly'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }
