"""HR Settings portal API — mounted under /api/portal/hr/settings/.

Thin DRF wrappers over :class:`core.services.hr_settings_service.HRSettingsService`
and :class:`~core.services.hr_settings_service.WorkingDaySettingsService`. These
expose the simple HR lookup tables (employee category / position / department /
grade, leave type) plus the working-day settings to the Next.js HR portal so the
HR Manager no longer needs the classic Django admin screens.

Gate: ``hr.settings.manage`` for writes, ``hr.employee.view`` for reads (any HR
user can *see* the lookups — they populate directory filters and dropdowns).
"""
from __future__ import annotations

import json

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.exceptions import NotFoundException
from core.services.hr_settings_service import (
    HRSettingsService, WorkingDaySettingsService,
)

from .hr_views import _forbidden, _held, _tenant
from .permissions import HasHRPermission, IsHR

# ConfigStore key holding the JSON list of document-type labels every active
# employee is expected to have on file. Consumed by
# ``hr_selectors.documents_missing`` to drive the dashboard alert.
REQUIRED_DOC_TYPES_KEY = "hr.required_document_types"
DEFAULT_REQUIRED_DOC_TYPES = [
    "NRC/Passport", "CV", "Academic Certificate", "Employment Contract",
    "Police Clearance",
]


def required_document_types(tenant):
    from core.models import ConfigStore

    raw = ConfigStore(tenant).get(REQUIRED_DOC_TYPES_KEY)
    if not raw:
        return list(DEFAULT_REQUIRED_DOC_TYPES)
    try:
        value = json.loads(raw)
        return [str(x) for x in value] if isinstance(value, list) else list(DEFAULT_REQUIRED_DOC_TYPES)
    except (ValueError, TypeError):
        return list(DEFAULT_REQUIRED_DOC_TYPES)

# key in the URL -> service lookup key + the writable/serialised field names
_LOOKUPS = {
    "category": ("category", ("name", "prefix", "status")),
    "position": ("position", ("name", "employee_category_id", "status")),
    "department": ("department", ("code", "name", "status")),
    "grade": ("grade", ("name", "priority", "status", "max_hours_day", "max_hours_week")),
    "leave-type": ("leave_type", ("name", "code", "default_annual_days", "is_paid", "status")),
}


def _serialise(instance, fields):
    out = {"id": str(instance.id)}
    for f in fields:
        out[f] = getattr(instance, f, None)
    return out


class HRLookupListView(APIView):
    permission_classes = [
        IsAuthenticated, IsHR,
        HasHRPermission("hr.settings.manage", read="hr.employee.view"),
    ]

    def _resolve(self, url_key):
        if url_key not in _LOOKUPS:
            raise NotFoundException(f"Unknown HR lookup '{url_key}'")
        return _LOOKUPS[url_key]

    def get(self, request, lookup_key):
        service_key, fields = self._resolve(lookup_key)
        service = HRSettingsService(_tenant(request))
        rows = service.list(service_key, search=request.query_params.get("q"))
        return Response([_serialise(r, fields) for r in rows])

    def post(self, request, lookup_key):
        if "hr.settings.manage" not in _held(request):
            return _forbidden("hr.settings.manage")
        service_key, fields = self._resolve(lookup_key)
        data = {k: v for k, v in request.data.items() if k in fields}
        service = HRSettingsService(_tenant(request))
        instance = service.create(service_key, user=request.user, **data)
        return Response(_serialise(instance, fields), status=status.HTTP_201_CREATED)


class HRLookupDetailView(APIView):
    permission_classes = [
        IsAuthenticated, IsHR,
        HasHRPermission("hr.settings.manage", read="hr.employee.view"),
    ]

    def _resolve(self, url_key):
        if url_key not in _LOOKUPS:
            raise NotFoundException(f"Unknown HR lookup '{url_key}'")
        return _LOOKUPS[url_key]

    def patch(self, request, lookup_key, pk):
        if "hr.settings.manage" not in _held(request):
            return _forbidden("hr.settings.manage")
        service_key, fields = self._resolve(lookup_key)
        data = {k: v for k, v in request.data.items() if k in fields}
        service = HRSettingsService(_tenant(request))
        instance = service.update(service_key, pk, user=request.user, **data)
        return Response(_serialise(instance, fields))

    def delete(self, request, lookup_key, pk):
        if "hr.settings.manage" not in _held(request):
            return _forbidden("hr.settings.manage")
        service_key, _fields = self._resolve(lookup_key)
        service = HRSettingsService(_tenant(request))
        service.delete(service_key, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


_WORKING_DAY_FIELDS = ("working_days", "default_daily_hours", "half_day_hours_threshold")


class HRWorkingDaySettingsView(APIView):
    permission_classes = [
        IsAuthenticated, IsHR,
        HasHRPermission("hr.settings.manage", read="hr.employee.view"),
    ]

    def get(self, request):
        settings = WorkingDaySettingsService(_tenant(request)).get_settings()
        return Response(_serialise(settings, _WORKING_DAY_FIELDS))

    def patch(self, request):
        if "hr.settings.manage" not in _held(request):
            return _forbidden("hr.settings.manage")
        data = {k: v for k, v in request.data.items() if k in _WORKING_DAY_FIELDS}
        settings = WorkingDaySettingsService(_tenant(request)).update_settings(
            user=request.user, **data
        )
        return Response(_serialise(settings, _WORKING_DAY_FIELDS))


class HRDocumentTypesView(APIView):
    """The tenant's required-document-type list (JSON array of labels)."""

    permission_classes = [
        IsAuthenticated, IsHR,
        HasHRPermission("hr.settings.manage", read="hr.employee.view"),
    ]

    def get(self, request):
        return Response({"required_document_types": required_document_types(_tenant(request))})

    def put(self, request):
        if "hr.settings.manage" not in _held(request):
            return _forbidden("hr.settings.manage")
        from core.models import ConfigStore

        values = request.data.get("required_document_types", [])
        if not isinstance(values, list):
            return Response(
                {"detail": "required_document_types must be a list of labels."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        clean = [str(v).strip() for v in values if str(v).strip()]
        ConfigStore(_tenant(request)).set(REQUIRED_DOC_TYPES_KEY, json.dumps(clean))
        return Response({"required_document_types": clean})
