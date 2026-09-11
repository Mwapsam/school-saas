"""DRF exception handler that maps core service-layer exceptions to HTTP responses.

The viewsets call into services that raise the rich exception hierarchy in
``core.services.exceptions``. DRF's default handler only understands its own
``APIException`` subclasses, so without this handler a ``NotFoundException`` or
``ValidationException`` raised from a view (e.g. inside ``get_object``) surfaces
as an unhandled 500. This handler keeps DRF's native behaviour and adds a thin
mapping layer for our service exceptions.
"""
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status

from core.services.exceptions import (
    ServiceException,
    ValidationException,
    NotFoundException,
    DuplicateException,
    PermissionException,
    TenantException,
    BusinessLogicException,
)


def service_exception_handler(exc, context):
    """Map service exceptions to responses, deferring to DRF for everything else."""
    # Let DRF handle framework-native exceptions (Http404, PermissionDenied,
    # APIException, serializer ValidationError, ...) exactly as before.
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    # Subclasses must be checked before the ServiceException base class.
    if isinstance(exc, NotFoundException):
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, DuplicateException):
        return Response(
            {"detail": str(exc), "errors": getattr(exc, "details", {})},
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, (PermissionException, TenantException)):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, (ValidationException, BusinessLogicException)):
        return Response(
            {"detail": str(exc), "errors": getattr(exc, "details", {})},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, ServiceException):
        return Response(
            {"detail": "An error occurred processing your request"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Not ours and not DRF's — let Django produce the default 500.
    return None
