from typing import Any, Dict, Optional

from django.db import transaction

from core.models import SchoolSignature
from .base import TenantAwareService
from .exceptions import ValidationException
from .logging_service import ServiceLogger, logged_operation


class SchoolSignatureService(TenantAwareService):
    """CRUD for the tenant's named report-card signatures (e.g. Lower Primary Head,
    Secondary Head). Exactly one row per tenant may be the default (enforced by a DB
    constraint) — that default is what report templates fall back to when they don't
    pick a signature of their own.
    """

    def __init__(self, tenant):
        super().__init__(SchoolSignature, tenant)
        self.logger = ServiceLogger('school_signature', tenant)

    def list(self):
        return self.get_base_queryset()  # Meta.ordering already sorts default-first

    @logged_operation(action='create', resource_type='school_signature', log_result=True)
    def create(self, user=None, image=None, **data: Dict[str, Any]) -> SchoolSignature:
        if not data.get('name', '').strip():
            raise ValidationException("Signature name is required")

        instance = SchoolSignature(tenant=self.tenant, **data)
        if image is not None:
            instance.image = image
        if not self.exists():
            # First signature for this tenant becomes the default automatically,
            # so a school never ends up with signatures but no default.
            instance.is_default = True
        instance.full_clean()
        instance.save()
        return instance

    @logged_operation(action='update', resource_type='school_signature', log_result=True)
    def update(self, obj_id: Any, user=None, image=None, remove_image: bool = False,
               **data: Dict[str, Any]) -> SchoolSignature:
        instance = self.get_by_id(obj_id)
        for field, value in data.items():
            setattr(instance, field, value)

        if remove_image and instance.image:
            instance.image.delete(save=False)
            instance.image = None
        elif image is not None:
            if instance.image:
                instance.image.delete(save=False)
            instance.image = image

        instance.full_clean()
        instance.save()
        return instance

    @logged_operation(action='set_default', resource_type='school_signature')
    @transaction.atomic
    def set_default(self, obj_id: Any, user=None) -> SchoolSignature:
        instance = self.get_by_id(obj_id)
        SchoolSignature.objects.filter(tenant=self.tenant).exclude(id=obj_id).update(is_default=False)
        instance.is_default = True
        instance.save(update_fields=['is_default'])
        return instance

    @logged_operation(action='delete', resource_type='school_signature')
    @transaction.atomic
    def delete(self, obj_id: Any, user=None) -> bool:
        instance = self.get_by_id(obj_id)
        was_default = instance.is_default

        if instance.image:
            instance.image.delete(save=False)
        instance.delete()

        if was_default:
            # A tenant with zero default signatures silently blanks the signature
            # block on every report template that hasn't picked one explicitly, so
            # promote another signature (if any remain) rather than leaving a gap.
            next_signature = SchoolSignature.objects.filter(tenant=self.tenant).first()
            if next_signature:
                next_signature.is_default = True
                next_signature.save(update_fields=['is_default'])

        return True
