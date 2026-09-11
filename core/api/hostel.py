"""
Hostel domain API — dormitory/boarding house management.

Covers:
- Room management (individual room data, capacity, occupancy)
- Hostel fees (charges for hostel accommodation)

Note: Full hostel block management requires additional models for future implementation.

Reuses existing services: See core/services/
"""

from rest_framework import viewsets, serializers
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import HostelRoom, HostelFee, Student
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class HostelRoomSerializer(serializers.ModelSerializer):
    """Serializer for HostelRoom — individual rooms."""
    class Meta:
        model = HostelRoom
        fields = [
            'id', 'room_number', 'floor', 'capacity', 'occupancy',
            'room_type', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class HostelFeeSerializer(serializers.ModelSerializer):
    """Serializer for HostelFee — hostel charges."""
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model = HostelFee
        fields = [
            'id', 'student', 'student_name', 'room', 'fee_amount',
            'fee_type', 'due_date', 'is_paid', 'paid_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class HostelRoomViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['room_type', 'floor', 'is_active']
    search_fields = ['room_number']
    ordering_fields = ['room_number', 'floor', 'capacity']
    ordering = ['floor', 'room_number']


class HostelFeeViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['student', 'room', 'fee_type', 'is_paid']
    search_fields = ['student__full_name']
    ordering_fields = ['due_date', 'fee_amount', 'created_at']
    ordering = ['-due_date']

    def get_queryset(self):
        return super().get_queryset().select_related('student', 'room')
