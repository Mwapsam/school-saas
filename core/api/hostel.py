"""
Hostel domain API — dormitory/boarding house management.

Covers:
- Room management (individual room data, capacity, occupancy)
- Hostel fees (charges for hostel accommodation)

Note: Full hostel block management requires additional models for future implementation.

Reuses existing services: See core/services/
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import HostelRoom, HostelFee, Student
from core.authz.drf import ModuleEnabled, HasPermission
from core.api.base import TenantAwareViewSet
from core.serializers.hostel_serializers import HostelRoomSerializer, HostelFeeSerializer


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class HostelRoomViewSet(TenantAwareViewSet):
    """
    Hostel room management — manage hostel rooms.

    Covers:
    - List/create/update/delete rooms
    - Filter by room type, floor, or occupancy status
    - Track room capacity and occupancy
    """
    queryset = HostelRoom.objects.all()
    serializer_class = HostelRoomSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hostel.rooms.view", write="hostel.rooms.manage"),
    ]
    module = "hostel"
    filterset_fields = ['room_type']
    search_fields = ['room_number']
    ordering_fields = ['room_number', 'capacity', 'rent']
    ordering = ['room_number']


class HostelFeeViewSet(TenantAwareViewSet):
    """
    Hostel fee management — manage hostel charges.

    Covers:
    - List/create/update/delete hostel fees
    - Filter by student, room, or payment status
    - Track hostel fee payments
    """
    queryset = HostelFee.objects.all()
    serializer_class = HostelFeeSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hostel.fees.view", write="hostel.fees.manage"),
    ]
    module = "hostel"
    filterset_fields = ['student', 'room']
    search_fields = ['student__first_name', 'student__last_name']
    ordering_fields = ['start_date', 'end_date', 'total_amount', 'created_at']
    ordering = ['-start_date']

    def get_queryset(self):
        return super().get_queryset().select_related('student', 'room')
