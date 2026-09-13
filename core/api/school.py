"""
Public school configuration endpoint — /api/school/config/

This endpoint returns public information about the school (branding, features, contact info).
It is unauthenticated so the frontend can fetch it before the user logs in.

The response is tenant-scoped: the tenant is determined by the Host header
(django-tenants middleware sets this via the Host/X-Forwarded-Host).
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache


@api_view(['GET'])
@permission_classes([AllowAny])
def school_config(request):
    """
    Return public school configuration.

    This endpoint:
    - Is unauthenticated (anyone can call it)
    - Is tenant-scoped (returns config for the current tenant)
    - Is cached for 1 hour to reduce database queries
    - Returns sensible defaults if the School doesn't exist yet

    Response:
    {
      "name": "Pinewood Preparatory School",
      "code": "pinewood",
      "description": "A leading preparatory school in Zambia",
      "logo_url": "https://cdn.../logo.png",
      "primary_color": "#1a7a3c",
      "secondary_color": "#f5f5f5",
      "contact_email": "office@pinewoodschoolzambia.com",
      "contact_phone": "+260211291167",
      "admission_enabled": true,
      "admission_heading": "Apply for a place at Pinewood Preparatory School",
      "admission_cta_text": "Start Your Application",
      "admission_description": "We welcome applications...",
      "admission_email": "admissions@pinewoodschoolzambia.com",
      "website_url": "https://pinewoodschoolzambia.com",
      "social_links": {
        "twitter": "https://twitter.com/pinewood",
        "facebook": "https://facebook.com/pinewood"
      },
      "features": {
        "parent_portal": true,
        "teacher_portal": true,
        "librarian_portal": true,
        "hr_portal": true,
        "admission_portal": true
      }
    }
    """
    from django.core.cache import cache
    from core.models import School

    # Get the current tenant
    tenant = getattr(request, 'tenant', None)

    if not tenant:
        # Not in a tenanted request (shouldn't happen in normal operation)
        return Response(
            {
                "name": "School Portal",
                "code": "unknown",
                "admission_enabled": False,
                "features": {
                    "parent_portal": True,
                    "teacher_portal": True,
                    "librarian_portal": True,
                    "hr_portal": True,
                    "admission_portal": False,
                },
            },
            status=status.HTTP_200_OK,
        )

    # Try to get from cache first
    cache_key = f"school_config:{tenant.schema_name}"
    cached_config = cache.get(cache_key)
    if cached_config:
        return Response(cached_config, status=status.HTTP_200_OK)

    try:
        # Build the response from the School model
        config = {
            "name": tenant.name,
            "code": tenant.code,
            "description": getattr(tenant, 'description', None),
            "primary_color": getattr(tenant, 'primary_color', None),
            "secondary_color": getattr(tenant, 'secondary_color', None),
            "contact_email": getattr(tenant, 'contact_email', None),
            "contact_phone": getattr(tenant, 'contact_phone', None),
            "admission_enabled": getattr(tenant, 'admission_enabled', False),
            "admission_heading": getattr(tenant, 'admission_heading', None),
            "admission_cta_text": getattr(tenant, 'admission_cta_text', None),
            "admission_description": getattr(tenant, 'admission_description', None),
            "admission_email": getattr(tenant, 'admission_email', None),
            "website_url": getattr(tenant, 'website_url', None),
            "social_links": getattr(tenant, 'social_links', None) or {},
            "features": getattr(tenant, 'features', None) or {
                "parent_portal": True,
                "teacher_portal": True,
                "librarian_portal": True,
                "hr_portal": True,
                "admission_portal": getattr(tenant, 'admission_enabled', False),
            },
        }

        # Remove None values to keep response clean
        config = {k: v for k, v in config.items() if v is not None}

        # Cache for 1 hour
        cache.set(cache_key, config, 60 * 60)

        return Response(config, status=status.HTTP_200_OK)

    except Exception as e:
        # Log but don't fail — return a default response
        import logging
        logger = logging.getLogger("core.api.school")
        logger.error(f"Error loading school config for tenant {tenant.schema_name}: {e}")

        # Return sensible defaults
        return Response(
            {
                "name": tenant.name or "School Portal",
                "code": tenant.code or "unknown",
                "admission_enabled": False,
                "features": {
                    "parent_portal": True,
                    "teacher_portal": True,
                    "librarian_portal": True,
                    "hr_portal": True,
                    "admission_portal": False,
                },
            },
            status=status.HTTP_200_OK,
        )
