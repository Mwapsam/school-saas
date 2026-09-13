"""
Bootstrap endpoint — the tenant-configuration contract between Django and Next.js.

GET /api/v1/bootstrap/ returns:
- Tenant identity (name, logo, branding)
- Current user info (name, role)
- Capabilities (permission list for UI gating)
- Terminology overrides (what to call things in this school)
- Enabled modules (which product areas are active)

The Next.js BFF calls this once per session (or on route change) to populate the UI state
with tenant-specific branding and capabilities, enabling the frontend to:
1. Show/hide features based on module enablement
2. Apply per-tenant branding (colors, logo, name)
3. Use school-specific terminology (e.g., "Guardians" vs "Parents")
4. Gate UI elements based on capability list (not role names)

This is the single source of truth for frontend access control and configuration.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.core.files.storage import default_storage

from core.models import SchoolModule, TerminologyOverride
from core.authz.access import get_permission_set
from core.modules import MODULES


@extend_schema(
    summary="Bootstrap tenant configuration",
    description="Returns tenant branding, user info, capabilities, terminology, and enabled modules. "
                "Called by Next.js on app load to populate UI state.",
    responses={
        200: {
            "type": "object",
            "properties": {
                "tenant": {"type": "object"},
                "user": {"type": "object"},
                "capabilities": {"type": "array"},
                "terminology": {"type": "object"},
                "modules": {"type": "object"},
            },
        }
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bootstrap(request):
    """
    Bootstrap endpoint — load tenant config, user info, capabilities, and enabled modules.

    Returns:
    {
        "tenant": {
            "id": "uuid",
            "name": "School Name",
            "logo_url": "https://...",
            "primary_color": "#5a9e2f",
            "footer_quote": "...",
            "address": "...",
            "phone": "...",
            "email": "...",
        },
        "user": {
            "id": "uuid",
            "username": "john.doe",
            "full_name": "John Doe",
            "email": "john@school.com",
        },
        "capabilities": [
            "students.view",
            "students.manage",
            "finance.invoices.view",
            ...
        ],
        "terminology": {
            "guardian": "Guardian",
            "student": "Student",
            ...
        },
        "modules": {
            "academics": True,
            "finance": True,
            "hr": True,
            "hostel": False,
            "transport": False,
            ...
        },
    }
    """
    tenant = request.tenant
    user = request.user

    # Tenant branding
    tenant_data = {
        "id": str(tenant.id),
        "name": tenant.name,
        "code": tenant.code,
        "logo_url": tenant.logo_url,
        "logo_secondary_url": tenant.logo_secondary.url if tenant.logo_secondary else None,
        "report_title": tenant.report_title,
        "footer_quote": tenant.footer_quote,
        "address_line1": tenant.address_line1,
        "address_line2": tenant.address_line2,
        "city": tenant.city,
        "state": tenant.state,
        "pin_code": tenant.pin_code,
        "phone": tenant.phone,
        "email": tenant.email,
        "website": tenant.website,
    }

    # User info
    user_data = {
        "id": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_admin": getattr(user, 'is_admin', False),
    }

    # Capabilities (permission strings for UI gating)
    capabilities = list(get_permission_set(user, tenant, request=request))

    # Terminology overrides (if any)
    terminology_dict = {}
    try:
        overrides = TerminologyOverride.objects.filter(tenant=tenant)
        for override in overrides:
            terminology_dict[override.key] = override.value
    except Exception:
        pass

    # Module enablement state
    modules_enabled = {}
    try:
        school_modules = SchoolModule.objects.filter(school=tenant)
        for sm in school_modules:
            modules_enabled[sm.module] = sm.enabled
    except Exception:
        # If SchoolModule doesn't exist yet, default all to enabled
        for module_key in MODULES.keys():
            modules_enabled[module_key] = True

    return Response({
        "tenant": tenant_data,
        "user": user_data,
        "capabilities": capabilities,
        "terminology": terminology_dict,
        "modules": modules_enabled,
    })
