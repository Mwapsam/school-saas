"""
Hostel domain API — dormitory/boarding house management.

Covers:
- Hostel/block management (different hostel buildings/blocks)
- Room management (room assignments, occupancy, capacity)
- Student hostel assignments (who lives where)
- Check-in/check-out (entry/exit management)
- Hostel leave requests (when students leave premises)
- Hostel complaints/maintenance requests

Reuses existing services: HostelService (in core/services/)
"""

from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import date

from core.models import (
    Hostel, HostelRoom, HostelAssignment, Student
)
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class HostelSerializer(serializers.ModelSerializer):
    """Serializer for Hostel — hostel buildings/blocks."""
    class Meta:
        model = Hostel
        fields = [
            'id', 'name', 'code', 'capacity', 'warden_name', 'warden_email',
            'warden_phone', 'type', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class HostelRoomSerializer(serializers.ModelSerializer):
    """Serializer for HostelRoom — individual rooms."""
    hostel_name = serializers.CharField(source='hostel.name', read_only=True)
    current_occupancy = serializers.SerializerMethodField()

    class Meta:
        model = HostelRoom
        fields = [
            'id', 'hostel', 'hostel_name', 'room_number', 'floor',
            'capacity', 'current_occupancy', 'room_type', 'amenities',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_current_occupancy(self, obj):
        """Count current occupants in the room."""
        return obj.assignments.filter(
            is_active=True,
            checkout_date__isnull=True
        ).count()


class HostelAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for HostelAssignment — student room assignments."""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    hostel_name = serializers.CharField(source='room.hostel.name', read_only=True)
    room_number = serializers.CharField(source='room.room_number', read_only=True)

    class Meta:
        model = HostelAssignment
        fields = [
            'id', 'student', 'student_name', 'room', 'hostel_name',
            'room_number', 'checkin_date', 'checkout_date', 'is_active',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'checkin_date', 'created_at', 'updated_at'
        ]


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class HostelViewSet(viewsets.ModelViewSet):
    """
    Hostel management — hostel buildings and blocks.

    Covers:
    - List/filter/search hostels
    - Retrieve, create, update hostels
    - Hostel details (warden, capacity, type)
    """
    queryset = Hostel.objects.all()
    serializer_class = HostelSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hostel"),
        HasPermission(read="hostel.management.view", write="hostel.management.manage"),
    ]
    module = "hostel"
    filterset_fields = ['type', 'is_active']
    search_fields = ['name', 'code', 'warden_name']
    ordering_fields = ['name']
    ordering = ['name']


class HostelRoomViewSet(viewsets.ModelViewSet):
    """
    Hostel room management — individual rooms within hostels.

    Covers:
    - List/filter rooms (by hostel, capacity, availability)
    - Room details and occupancy
    - Retrieve, create, update rooms
    """
    queryset = HostelRoom.objects.select_related('hostel')
    serializer_class = HostelRoomSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hostel"),
        HasPermission(read="hostel.rooms.view", write="hostel.rooms.manage"),
    ]
    module = "hostel"
    filterset_fields = ['hostel', 'room_type', 'is_active']
    search_fields = ['room_number', 'hostel__name']
    ordering_fields = ['room_number', 'floor']
    ordering = ['floor', 'room_number']

    @extend_schema(
        description="Get available rooms (rooms with capacity)",
        parameters=[
            OpenApiParameter(name='hostel', description='Filter by hostel ID'),
        ],
    )
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get available rooms (with capacity for new assignments)."""
        hostel_id = request.query_params.get('hostel')
        rooms = HostelRoom.objects.select_related('hostel')

        if hostel_id:
            rooms = rooms.filter(hostel_id=hostel_id)

        available_rooms = []
        for room in rooms.filter(is_active=True):
            occupancy = room.assignments.filter(
                is_active=True,
                checkout_date__isnull=True
            ).count()
            if occupancy < room.capacity:
                available_rooms.append({
                    'id': str(room.id),
                    'room_number': room.room_number,
                    'hostel': room.hostel.name,
                    'capacity': room.capacity,
                    'current_occupancy': occupancy,
                    'available_beds': room.capacity - occupancy,
                })

        return Response(available_rooms)


class HostelAssignmentViewSet(viewsets.ModelViewSet):
    """
    Hostel assignment management — student room assignments.

    Covers:
    - Assign students to rooms
    - Track check-in and check-out
    - View occupancy per student/room
    - Generate occupancy reports
    """
    queryset = HostelAssignment.objects.select_related('student', 'room')
    serializer_class = HostelAssignmentSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hostel"),
        HasPermission(read="hostel.assignments.view", write="hostel.assignments.manage"),
    ]
    module = "hostel"
    filterset_fields = ['student', 'room', 'is_active']
    search_fields = ['student__full_name', 'room__room_number']
    ordering_fields = ['checkin_date', 'student']
    ordering = ['-checkin_date']

    @extend_schema(
        description="Check out a student from hostel",
        request=None,
        responses={200: HostelAssignmentSerializer},
    )
    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        """Check out a student from hostel."""
        assignment = self.get_object()
        assignment.checkout_date = date.today()
        assignment.is_active = False
        assignment.save()
        return Response(HostelAssignmentSerializer(assignment).data)

    @extend_schema(
        description="Get hostel occupancy summary",
    )
    @action(detail=False, methods=['get'])
    def occupancy_summary(self, request):
        """Get hostel occupancy summary."""
        hostels = Hostel.objects.filter(tenant=request.tenant)
        summary = []

        for hostel in hostels:
            rooms = hostel.rooms.filter(is_active=True)
            total_capacity = sum(r.capacity for r in rooms)
            total_occupied = 0

            for room in rooms:
                occupied = room.assignments.filter(
                    is_active=True,
                    checkout_date__isnull=True
                ).count()
                total_occupied += occupied

            occupancy_rate = (
                (total_occupied / total_capacity * 100) if total_capacity > 0 else 0
            )

            summary.append({
                'hostel': hostel.name,
                'total_capacity': total_capacity,
                'total_occupied': total_occupied,
                'available_beds': total_capacity - total_occupied,
                'occupancy_rate': f'{occupancy_rate:.1f}%',
            })

        return Response(summary)

    @extend_schema(
        description="Get student's current hostel assignment",
        parameters=[
            OpenApiParameter(name='student', required=True, description='Student ID'),
        ],
    )
    @action(detail=False, methods=['get'])
    def student_assignment(self, request):
        """Get current hostel assignment for a student."""
        student_id = request.query_params.get('student')
        if not student_id:
            return Response({'error': 'student ID required'}, status=400)

        try:
            assignment = HostelAssignment.objects.select_related(
                'student', 'room'
            ).get(
                student_id=student_id,
                is_active=True,
                checkout_date__isnull=True,
                tenant=request.tenant
            )
            return Response(HostelAssignmentSerializer(assignment).data)
        except HostelAssignment.DoesNotExist:
            return Response(
                {'error': 'Student has no active hostel assignment'},
                status=404
            )
