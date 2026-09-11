import json
import requests
import base64
import secrets
import string
from urllib.parse import urlencode
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import time
import logging


class AuthClientError(Exception):
    pass


class AuthServerError(Exception):
    pass


class InvalidRequestError(Exception):
    pass


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuickBooksAuth(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: str
    environment: str = "sandbox"

    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    realm_id: Optional[str] = None
    token_expires_at: Optional[float] = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def base_url(self) -> str:
        return "https://oauth.platform.intuit.com"

    @property
    def discovery_url(self) -> str:
        if self.environment == "production":
            return "https://quickbooks.api.intuit.com"
        return "https://sandbox-quickbooks.api.intuit.com"

    def _generate_state(self) -> str:
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(30))

    def get_authorization_url(self, scopes: List[str] = None) -> str:
        if scopes is None:
            scopes = ["com.intuit.quickbooks.accounting"]

        try:
            state = self._generate_state()
            
            params = {
                'client_id': self.client_id,
                'response_type': 'code',
                'scope': ' '.join(scopes),
                'redirect_uri': self.redirect_uri,
                'state': state
            }
            
            base_auth_url = "https://appcenter.intuit.com/connect/oauth2"
            url = f"{base_auth_url}?{urlencode(params)}"
            
            logger.info(f"Generated authorization URL: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to get authorization URL: {e}")
            raise AuthClientError(f"Failed to generate authorization URL: {str(e)}")

    def get_bearer_token(self, auth_code: str, realm_id: str) -> Dict[str, Any]:
        try:
            logger.debug(
                f"Exchanging auth code for tokens: auth_code={auth_code}, realm_id={realm_id}"
            )

            token_response = self._exchange_code_for_tokens(auth_code)

            if not isinstance(token_response, dict):
                logger.error(f"Invalid token response type: {type(token_response)}")
                raise AuthClientError(
                    f"Invalid token response type: {type(token_response)}, value: {token_response}"
                )

            if (
                "access_token" not in token_response
                or "refresh_token" not in token_response
            ):
                logger.error(
                    f"Missing required keys in token response: {list(token_response.keys())}"
                )
                raise AuthClientError(
                    f"Invalid token response: missing access_token or refresh_token. Got keys: {list(token_response.keys())}"
                )

            self.access_token = token_response.get("access_token")
            self.refresh_token = token_response.get("refresh_token")
            self.realm_id = realm_id

            expires_in = token_response.get("expires_in", 3600)
            self.token_expires_at = time.time() + expires_in

            logger.info("Successfully obtained bearer token")
            return token_response

        except AuthClientError:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in get_bearer_token: {str(e)}, type: {type(e)}"
            )
            raise AuthClientError(f"Unexpected error during token exchange: {str(e)}")

    def _exchange_code_for_tokens(self, auth_code: str) -> Dict[str, Any]:
        try:
            token_url = f"{self.base_url}/oauth2/v1/tokens/bearer"

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {self._get_basic_auth_header()}",
            }

            data = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": self.redirect_uri,
            }

            logger.info(f"Making token exchange request to {token_url}")
            logger.debug(f"Request data: grant_type=authorization_code, redirect_uri={self.redirect_uri}")
            
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            
            logger.debug(f"Token exchange response status: {response.status_code}")
            logger.debug(f"Token exchange response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    token_data = response.json()
                    logger.info("Successfully exchanged authorization code for tokens")
                    return token_data
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse token response as JSON: {response.text}")
                    raise AuthClientError("Invalid JSON response from QuickBooks API")
            
            try:
                error_data = response.json()
                error = error_data.get("error", "unknown_error")
                error_description = error_data.get("error_description", "Unknown error occurred")
                
                logger.error(f"Token exchange failed: {error} - {error_description}")
                
                if error == "invalid_grant":
                    raise AuthClientError("Authorization code is invalid or expired")
                elif error == "invalid_client":
                    raise AuthClientError("Invalid client ID or secret")
                elif error == "redirect_uri_mismatch":
                    raise AuthClientError("Redirect URI does not match QuickBooks app settings")
                else:
                    raise AuthClientError(f"QuickBooks API error: {error} - {error_description}")
                    
            except json.JSONDecodeError:
                logger.error(f"Non-JSON error response: {response.text}")
                raise AuthClientError(f"QuickBooks API returned status {response.status_code}: {response.text}")

        except requests.RequestException as e:
            logger.error(f"Network error during token exchange: {str(e)}")
            raise AuthClientError(f"Network error during token exchange: {str(e)}")
        except AuthClientError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token exchange: {str(e)}")
            raise AuthClientError(f"Unexpected error during token exchange: {str(e)}")

    def _get_basic_auth_header(self) -> str:
        import base64

        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return encoded_credentials

    def refresh_access_token(self) -> Dict[str, Any]:
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        try:
            token_url = f"{self.base_url}/oauth2/v1/tokens/bearer"

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {self._get_basic_auth_header()}",
            }

            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            }

            logger.info("Refreshing access token")
            response = requests.post(token_url, headers=headers, data=data, timeout=30)

            if response.status_code == 200:
                try:
                    token_data = response.json()
                    
                    self.access_token = token_data.get("access_token")
                    if "refresh_token" in token_data:
                        self.refresh_token = token_data.get("refresh_token")

                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expires_at = time.time() + expires_in

                    logger.info("Successfully refreshed access token")
                    return token_data
                    
                except json.JSONDecodeError:
                    raise AuthClientError("Invalid JSON response when refreshing token")
            else:
                try:
                    error_data = response.json()
                    error = error_data.get("error", "unknown_error")
                    error_description = error_data.get("error_description", "Unknown error")
                    raise AuthClientError(f"Token refresh failed: {error} - {error_description}")
                except json.JSONDecodeError:
                    raise AuthClientError(f"Token refresh failed with status {response.status_code}")

        except requests.RequestException as e:
            logger.error(f"Network error during token refresh: {str(e)}")
            raise AuthClientError(f"Network error during token refresh: {str(e)}")
        except AuthClientError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {str(e)}")
            raise AuthClientError(f"Unexpected error during token refresh: {str(e)}")

    def is_token_expired(self, buffer_seconds: int = 300) -> bool:
        """
        Check if token is expired or will expire soon.
        
        Args:
            buffer_seconds: Seconds before expiration to consider token expired (default: 5 minutes)
        """
        if not self.token_expires_at:
            return True

        return time.time() >= (self.token_expires_at - buffer_seconds)
    
    def time_until_expiry(self) -> int:
        """Get seconds remaining until token expires"""
        if not self.token_expires_at:
            return 0
        return max(0, int(self.token_expires_at - time.time()))

    def ensure_valid_token(self) -> str:
        if not self.access_token:
            raise ValueError("No access token available. Please authenticate first.")

        if self.is_token_expired():
            logger.info("Token is expired, attempting to refresh")
            self.refresh_access_token()

        return self.access_token

    def get_auth_headers(self) -> Dict[str, str]:
        token = self.ensure_valid_token()
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def revoke_token(self) -> bool:
        if not self.refresh_token:
            logger.warning("No refresh token to revoke")
            return False

        try:
            revoke_url = f"{self.base_url}/oauth2/v1/tokens/revoke"

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {self._get_basic_auth_header()}",
            }

            data = {
                "token": self.refresh_token,
            }

            logger.info("Revoking refresh token")
            response = requests.post(revoke_url, headers=headers, data=data, timeout=30)

            if response.status_code == 200:
                self.access_token = None
                self.refresh_token = None
                self.realm_id = None
                self.token_expires_at = None

                logger.info("Successfully revoked token")
                return True
            else:
                logger.warning(f"Token revocation returned status {response.status_code}")
                self.access_token = None
                self.refresh_token = None
                self.realm_id = None
                self.token_expires_at = None
                return True

        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            self.access_token = None
            self.refresh_token = None
            self.realm_id = None
            self.token_expires_at = None
            return False
