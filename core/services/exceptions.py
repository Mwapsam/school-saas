from typing import Any, Dict
from django.core.exceptions import ValidationError


class ServiceException(Exception):
    def __init__(
        self,
        message: str,
        error_code: str = None,
        details: Dict[str, Any] = None,
        original_exception: Exception = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.original_exception = original_exception
        super().__init__(self.message)


class ValidationException(ServiceException):
    pass


class NotFoundException(ServiceException):
    pass


class DuplicateException(ServiceException):
    pass


class PermissionException(ServiceException):
    pass


class TenantException(ServiceException):
    pass


class BusinessLogicException(ServiceException):
    pass


class ExternalServiceException(ServiceException):
    pass


def handle_service_exceptions(func):
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceException:
            raise
        except ValidationError as e:
            raise ValidationException(
                message="Data validation failed",
                details={"validation_errors": e.messages if hasattr(e, 'messages') else str(e)},
                original_exception=e
            )
        except Exception as e:
            raise ServiceException(
                message=f"Unexpected error in {func.__name__}: {str(e)}",
                error_code="UNEXPECTED_ERROR",
                original_exception=e
            )
    
    return wrapper