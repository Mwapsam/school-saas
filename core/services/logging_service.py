import logging
import time
from typing import Any, Dict
from datetime import datetime, timezone
from functools import wraps
from django.contrib.auth import get_user_model
from django.db import models
from django.http import HttpRequest

User = get_user_model()


class ServiceLogger:
    def __init__(self, service_name: str, tenant: models.Model = None):
        self.service_name = service_name
        self.tenant = tenant
        self.logger = logging.getLogger(f"services.{service_name}")
        
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
    
    def _get_base_context(self, user: User = None, request: HttpRequest = None) -> Dict[str, Any]:
        context = {
            'service': self.service_name,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'tenant_id': self.tenant.id if self.tenant else None,
            'tenant_name': self.tenant.name if hasattr(self.tenant, 'name') else None,
        }
        
        if user:
            context.update({
                'user_id': str(user.id),
                'username': user.username,
                'user_full_name': getattr(user, 'full_name', f"{user.first_name} {user.last_name}")
            })
        
        if request:
            context.update({
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'request_method': request.method,
                'request_path': request.path
            })
        
        return context
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def log_action(
        self, 
        action: str, 
        resource_type: str,
        resource_id: str = None,
        user: User = None,
        request: HttpRequest = None,
        details: Dict[str, Any] = None,
        level: str = 'INFO'
    ):
        context = self._get_base_context(user, request)
        context.update({
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'level': level
        })
        
        if details:
            context['details'] = details
        
        message = f"{action.upper()} {resource_type}"
        if resource_id:
            message += f" (ID: {resource_id})"
        
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, extra=context)
    
    def log_create(
        self, 
        resource_type: str, 
        resource_id: str, 
        user: User = None,
        request: HttpRequest = None,
        details: Dict[str, Any] = None
    ):
        self.log_action(
            action='create',
            resource_type=resource_type,
            resource_id=resource_id,
            user=user,
            request=request,
            details=details,
            level='INFO'
        )
    
    def log_read(
        self, 
        resource_type: str, 
        resource_id: str = None,
        user: User = None,
        request: HttpRequest = None,
        query_details: Dict[str, Any] = None
    ):
        details = query_details or {}
        self.log_action(
            action='read',
            resource_type=resource_type,
            resource_id=resource_id,
            user=user,
            request=request,
            details=details,
            level='DEBUG'
        )
    
    def log_update(
        self, 
        resource_type: str, 
        resource_id: str,
        user: User = None,
        request: HttpRequest = None,
        changed_fields: Dict[str, Any] = None
    ):
        details = {}
        if changed_fields:
            details['changed_fields'] = list(changed_fields.keys())
            details['changes'] = changed_fields
        
        self.log_action(
            action='update',
            resource_type=resource_type,
            resource_id=resource_id,
            user=user,
            request=request,
            details=details,
            level='INFO'
        )
    
    def log_delete(
        self, 
        resource_type: str, 
        resource_id: str,
        user: User = None,
        request: HttpRequest = None,
        soft_delete: bool = True
    ):
        details = {'soft_delete': soft_delete}
        self.log_action(
            action='delete',
            resource_type=resource_type,
            resource_id=resource_id,
            user=user,
            request=request,
            details=details,
            level='WARNING'
        )
    
    def _add_service_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Add service context to logging extra data"""
        context = {
            'service': self.service_name,
            'tenant_id': self.tenant.id if self.tenant else None,
        }
        context.update(extra or {})
        return context
    
    def error(self, message: str, **extra):
        """Log error message with service context"""
        self.logger.error(message, extra=self._add_service_context(extra))
    
    def info(self, message: str, **extra):
        """Log info message with service context"""
        self.logger.info(message, extra=self._add_service_context(extra))
    
    def debug(self, message: str, **extra):
        """Log debug message with service context"""
        self.logger.debug(message, extra=self._add_service_context(extra))
    
    def warning(self, message: str, **extra):
        """Log warning message with service context"""
        self.logger.warning(message, extra=self._add_service_context(extra))
    
    def log_error(
        self, 
        error: Exception,
        action: str = None,
        resource_type: str = None,
        user: User = None,
        request: HttpRequest = None
    ):
        """Log error with full context"""
        details = {
            'error_type': error.__class__.__name__,
            'error_message': str(error),
        }
        
        if action and resource_type:
            self.log_action(
                action=action,
                resource_type=resource_type,
                user=user,
                request=request,
                details=details,
                level='ERROR'
            )
        else:
            self.error(f"Error in {self.service_name}: {str(error)}", **details)
    
    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        resource_type: str = None,
        user: User = None,
        **extra
    ):
        """Log performance metrics"""
        details = {
            'operation': operation,
            'duration_ms': round(duration_ms, 2),
            'resource_type': resource_type,
        }
        details.update(extra)
        
        self.info(f"Performance: {operation} took {duration_ms:.2f}ms", **details)
    
    def log_error(
        self, 
        error: Exception,
        action: str = None,
        resource_type: str = None,
        resource_id: str = None,
        user: User = None,
        request: HttpRequest = None,
        additional_context: Dict[str, Any] = None
    ):
        context = self._get_base_context(user, request)
        
        context.update({
            'level': 'ERROR',
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id
        })
        
        if hasattr(error, 'details'):
            context['error_details'] = error.details
        
        if hasattr(error, 'error_code'):
            context['error_code'] = error.error_code
        
        if additional_context:
            context['additional_context'] = additional_context
        
        message = f"ERROR in {self.service_name}"
        if action and resource_type:
            message += f" during {action} {resource_type}"
        message += f": {str(error)}"
        
        self.logger.error(message, extra=context, exc_info=True)
    
    def log_performance(
        self, 
        operation: str,
        duration_ms: float,
        resource_type: str = None,
        resource_count: int = None,
        user: User = None,
        additional_metrics: Dict[str, Any] = None
    ):
        context = self._get_base_context(user)
        context.update({
            'operation': operation,
            'duration_ms': duration_ms,
            'resource_type': resource_type,
            'resource_count': resource_count,
            'level': 'INFO',
            'metric_type': 'performance'
        })
        
        if additional_metrics:
            context['metrics'] = additional_metrics
        
        message = f"PERFORMANCE: {operation} completed in {duration_ms:.2f}ms"
        if resource_count:
            message += f" ({resource_count} items)"
        
        self.logger.info(message, extra=context)
    
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        user: User = None,
        request: HttpRequest = None,
        details: Dict[str, Any] = None
    ):
        context = self._get_base_context(user, request)
        context.update({
            'event_type': 'security',
            'security_event_type': event_type,
            'severity': severity,
            'level': 'WARNING' if severity in ['LOW', 'MEDIUM'] else 'ERROR'
        })
        
        if details:
            context['security_details'] = details
        
        message = f"SECURITY EVENT: {event_type} (Severity: {severity})"
        
        log_method = self.logger.warning if severity in ['LOW', 'MEDIUM'] else self.logger.error
        log_method(message, extra=context)


def logged_operation(
    action: str = None,
    resource_type: str = None,
    log_performance: bool = False,
    log_result: bool = False
):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'logger') or not isinstance(self.logger, ServiceLogger):
                return func(self, *args, **kwargs)
            
            operation_action = action or func.__name__
            operation_resource = resource_type or getattr(self, 'model_class', self.__class__).__name__.lower().replace('service', '')
            
            user = kwargs.get('user') or getattr(self, 'current_user', None)
            request = kwargs.get('request') or getattr(self, 'current_request', None)
            
            start_time = time.time()
            
            try:
                result = func(self, *args, **kwargs)
                
                if log_result and result:
                    details = {}
                    if hasattr(result, 'id'):
                        details['result_id'] = str(result.id)
                    if hasattr(result, '__len__'):
                        details['result_count'] = len(result)
                    
                    self.logger.log_action(
                        action=operation_action,
                        resource_type=operation_resource,
                        user=user,
                        request=request,
                        details=details
                    )
                
                if log_performance:
                    duration = (time.time() - start_time) * 1000
                    self.logger.log_performance(
                        operation=f"{operation_action}_{operation_resource}",
                        duration_ms=duration,
                        resource_type=operation_resource,
                        user=user
                    )
                
                return result
                
            except Exception as e:
                self.logger.log_error(
                    error=e,
                    action=operation_action,
                    resource_type=operation_resource,
                    user=user,
                    request=request
                )
                raise
        
        return wrapper
    return decorator


def get_service_logger(service_name: str, tenant: models.Model = None) -> ServiceLogger:
    return ServiceLogger(service_name, tenant)