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

from rest_framework import viewsets, serializers
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import time

from core.models import (
    TransportRoute, TransportRouteStop, TransportStaff, TransportFee
)
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class TransportRouteStopSerializer(serializers.ModelSerializer):
    """Serializer for TransportRouteStop — stops on a route."""
    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = TransportRouteStop
        fields = [
            'id', 'route', 'route_name', 'stop_name', 'stop_order',
            'arrival_time', 'departure_time', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransportRouteSerializer(serializers.ModelSerializer):
    """Serializer for TransportRoute — daily routes."""
    class Meta:
        model = TransportRoute
        fields = [
            'id', 'name', 'route_code', 'from_location', 'to_location',
            'distance_km', 'duration_minutes', 'departure_time', 'arrival_time',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransportStaffSerializer(serializers.ModelSerializer):
    """Serializer for TransportStaff — drivers, conductors, etc."""
    class Meta:
        model = TransportStaff
        fields = [
            'id', 'name', 'staff_type', 'license_number', 'license_expiry',
            'phone', 'email', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransportFeeSerializer(serializers.ModelSerializer):
    """Serializer for TransportFee — transport charges."""
    class Meta:
        model = TransportFee
        fields = [
            'id', 'route', 'student_category', 'monthly_fee', 'annual_fee',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class TransportRouteViewSet(viewsets.ModelViewSet):
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
    search_fields = ['name', 'route_code']
    ordering_fields = ['name', 'departure_time', 'created_at']
    ordering = ['name']


class TransportRouteStopViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['route', 'is_active']
    search_fields = ['stop_name']
    ordering_fields = ['stop_order', 'arrival_time', 'created_at']
    ordering = ['stop_order']

    def get_queryset(self):
        return super().get_queryset().select_related('route')


class TransportStaffViewSet(viewsets.ModelViewSet):
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
    search_fields = ['name', 'license_number']
    ordering_fields = ['name', 'staff_type', 'created_at']
    ordering = ['name']


class TransportFeeViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['route', 'student_category', 'is_active']
    search_fields = ['route__name']
    ordering_fields = ['monthly_fee', 'annual_fee', 'created_at']
    ordering = ['route__name']

    def get_queryset(self):
        return super().get_queryset().select_related('route')
