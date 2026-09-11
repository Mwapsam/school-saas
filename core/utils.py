"""
Tenant-aware utility functions for caching and common operations
"""
from django.core.cache import cache
from django_tenants.utils import get_tenant_model
from django.db import connection
import logging

logger = logging.getLogger(__name__)


def get_cache_key(key, tenant=None):
    if not tenant:
        if hasattr(connection, 'tenant') and connection.tenant:
            tenant = connection.tenant
        else:
            # Fallback to getting tenant from model if available
            try:
                tenant = get_tenant_model().get_current()
            except:
                # If no tenant context, use 'public' schema
                return f"public:{key}"
    
    return f"{tenant.schema_name}:{key}"


def tenant_cache_get(key, default=None, tenant=None):
    cache_key = get_cache_key(key, tenant)
    return cache.get(cache_key, default)


def tenant_cache_set(key, value, timeout=None, tenant=None):
    cache_key = get_cache_key(key, tenant)
    return cache.set(cache_key, value, timeout)


def tenant_cache_delete(key, tenant=None):
    cache_key = get_cache_key(key, tenant)
    return cache.delete(cache_key)


def get_current_tenant():
    if hasattr(connection, 'tenant') and connection.tenant:
        return connection.tenant
    return None


def log_with_tenant(message, level='info', tenant=None):
    if not tenant:
        tenant = get_current_tenant()
    
    tenant_info = f"[{tenant.schema_name}]" if tenant else "[no_tenant]"
    full_message = f"{tenant_info} {message}"
    
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(full_message)


def validate_tenant_access(user, tenant):
    from django.core.exceptions import PermissionDenied
    
    if not hasattr(user, 'has_tenant_access'):
        raise PermissionDenied("User model does not support tenant access checking")
    
    if not user.has_tenant_access(tenant):
        log_with_tenant(
            f"Access denied for user {user.username} to tenant {tenant.schema_name}",
            level='warning',
            tenant=tenant
        )
        raise PermissionDenied(f"User does not have access to tenant {tenant.schema_name}")
    
    return True