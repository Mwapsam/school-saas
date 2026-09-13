"""
Transport domain API — school transportation and routing management.

Covers:
- Transport routes (daily routes, pickup/dropoff schedule)
- Route stops (locations where vehicle stops)
- Transport staff (drivers, conductors, helpers)
- Transport fees (charges for transport services)

Note: Vehicle management requires additional models for future implementation.

Reuses existing services: See core/services/
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import time

from core.models import (
    TransportRoute, TransportRouteStop, TransportStaff, TransportFee
)
from core.authz.drf import ModuleEnabled, HasPermission
from core.api.base import TenantAwareViewSet
from core.serializers.transport_serializers import (
    TransportRouteStopSerializer, TransportRouteSerializer, TransportStaffSerializer, TransportFeeSerializer
)


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class TransportRouteViewSet(TenantAwareViewSet):
    """
    Transport route management — manage transportation routes.

    Covers:
    - List/create/update/delete routes
    - Filter by active status
    - Search by route name or code
    """
    queryset = TransportRoute.objects.all()
    serializer_class = TransportRouteSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="transport.routes.view", write="transport.routes.manage"),
    ]
    module = "transport"
    filterset_fields = ['is_active']
    search_fields = ['route_name', 'code']
    ordering_fields = ['route_name', 'fare', 'created_at']
    ordering = ['route_name']


class TransportRouteStopViewSet(TenantAwareViewSet):
    """
    Transport route stop management — manage stops on routes.

    Covers:
    - List/create/update/delete stops
    - Filter by route or active status
    - Manage stop sequence and timings
    """
    queryset = TransportRouteStop.objects.all()
    serializer_class = TransportRouteStopSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="transport.stops.view", write="transport.stops.manage"),
    ]
    module = "transport"
    filterset_fields = ['route']
    search_fields = ['stop__name']
    ordering_fields = ['order', 'pickup_time', 'created_at']
    ordering = ['order']

    def get_queryset(self):
        return super().get_queryset().select_related('route', 'stop')


class TransportStaffViewSet(TenantAwareViewSet):
    """
    Transport staff management — manage drivers, conductors, helpers.

    Covers:
    - List/create/update/delete staff
    - Filter by staff type or license expiry
    - Search by name or license number
    """
    queryset = TransportStaff.objects.all()
    serializer_class = TransportStaffSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="transport.staff.view", write="transport.staff.manage"),
    ]
    module = "transport"
    filterset_fields = ['staff_type', 'is_active']
    search_fields = ['full_name', 'license_number']
    ordering_fields = ['full_name', 'staff_type', 'created_at']
    ordering = ['full_name']


class TransportFeeViewSet(TenantAwareViewSet):
    """
    Transport fee management — manage transport charges.

    Covers:
    - List/create/update/delete transport fees
    - Filter by route or student category
    - Manage monthly and annual fees
    """
    queryset = TransportFee.objects.all()
    serializer_class = TransportFeeSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="transport.fees.view", write="transport.fees.manage"),
    ]
    module = "transport"
    filterset_fields = ['route', 'student']
    search_fields = ['route__route_name', 'student__first_name', 'student__last_name']
    ordering_fields = ['total_amount', 'start_date', 'end_date', 'created_at']
    ordering = ['-start_date']

    def get_queryset(self):
        return super().get_queryset().select_related('route', 'student')
