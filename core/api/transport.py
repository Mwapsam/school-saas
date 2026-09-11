"""
Transport domain API — school transportation and routing management.

Covers:
- Transport routes (daily routes, pickup/dropoff schedule)
- Vehicles (buses, vans, condition tracking)
- Route stops (locations where vehicle stops)
- Transport staff (drivers, conductors, helpers)
- Student assignments (which students on which routes)
- Trip tracking (actual vs. scheduled)

Reuses existing services: TransportService (in core/services/transport_service.py)
"""

from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import date, time

from core.models import (
    TransportRoute, TransportRouteStop, TransportVehicle, TransportStaff,
    TransportAssignment, Student, Employee
)
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class TransportVehicleSerializer(serializers.ModelSerializer):
    """Serializer for TransportVehicle — buses, vans, etc."""
    class Meta:
        model = TransportVehicle
        fields = [
            'id', 'registration_number', 'vehicle_type', 'capacity',
            'make_model', 'year', 'color', 'insurance_expiry',
            'last_service_date', 'condition', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransportRouteStopSerializer(serializers.ModelSerializer):
    """Serializer for TransportRouteStop — pickup/dropoff locations."""
    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = TransportRouteStop
        fields = [
            'id', 'route', 'route_name', 'stop_name', 'location',
            'latitude', 'longitude', 'arrival_time', 'departure_time',
            'stop_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransportRouteSerializer(serializers.ModelSerializer):
    """Serializer for TransportRoute — daily routes."""
    vehicle_name = serializers.CharField(source='vehicle.registration_number', read_only=True)
    stops = TransportRouteStopSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = TransportRoute
        fields = [
            'id', 'name', 'code', 'vehicle', 'vehicle_name', 'route_type',
            'start_time', 'end_time', 'distance_km', 'stops',
            'student_count', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_student_count(self, obj):
        """Count students assigned to this route."""
        return obj.assignments.filter(is_active=True).count()


class TransportStaffSerializer(serializers.ModelSerializer):
    """Serializer for TransportStaff — drivers, conductors, helpers."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = TransportStaff
        fields = [
            'id', 'employee', 'employee_name', 'route', 'route_name',
            'role', 'license_number', 'license_expiry', 'emergency_contact',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransportAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for TransportAssignment — student assignments to routes."""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = TransportAssignment
        fields = [
            'id', 'student', 'student_name', 'route', 'route_name',
            'daily_allowance', 'is_active', 'assignment_date',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'assignment_date', 'created_at', 'updated_at'
        ]


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class TransportVehicleViewSet(viewsets.ModelViewSet):
    """
    Vehicle management — buses, vans, and transport equipment.

    Covers:
    - List/filter/search vehicles
    - Vehicle details (capacity, condition, maintenance)
    - Retrieve, create, update vehicles
    """
    queryset = TransportVehicle.objects.all()
    serializer_class = TransportVehicleSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("transport"),
        HasPermission(read="transport.fleet.view", write="transport.fleet.manage"),
    ]
    module = "transport"
    filterset_fields = ['vehicle_type', 'condition', 'is_active']
    search_fields = ['registration_number', 'make_model']
    ordering_fields = ['registration_number']
    ordering = ['registration_number']

    @extend_schema(
        description="Get vehicle maintenance report",
        parameters=[
            OpenApiParameter(name='vehicle_id', required=True, description='Vehicle ID'),
        ],
    )
    @action(detail=False, methods=['get'])
    def maintenance_report(self, request):
        """Get maintenance report for a vehicle."""
        vehicle_id = request.query_params.get('vehicle_id')
        if not vehicle_id:
            return Response({'error': 'vehicle_id required'}, status=400)

        try:
            vehicle = TransportVehicle.objects.get(id=vehicle_id, tenant=request.tenant)
        except TransportVehicle.DoesNotExist:
            return Response({'error': 'Vehicle not found'}, status=404)

        return Response({
            'vehicle': vehicle.registration_number,
            'last_service': vehicle.last_service_date,
            'insurance_expiry': vehicle.insurance_expiry,
            'condition': vehicle.condition,
            'status': 'good' if vehicle.condition in ['good', 'excellent'] else 'needs_attention',
        })


class TransportRouteViewSet(viewsets.ModelViewSet):
    """
    Route management — daily transportation routes.

    Covers:
    - List/filter routes (morning, afternoon, custom)
    - Route details with stops
    - Student count per route
    - Retrieve, create, update routes
    """
    queryset = TransportRoute.objects.prefetch_related('stops').select_related('vehicle')
    serializer_class = TransportRouteSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("transport"),
        HasPermission(read="transport.routes.view", write="transport.routes.manage"),
    ]
    module = "transport"
    filterset_fields = ['route_type', 'vehicle', 'is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['start_time', 'name']
    ordering = ['start_time']

    @extend_schema(description="Get routes summary by type")
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get routes summary grouped by type."""
        routes = TransportRoute.objects.filter(
            is_active=True,
            tenant=request.tenant
        )

        summary = {}
        for route_type in ['morning', 'afternoon', 'custom']:
            type_routes = routes.filter(route_type=route_type)
            total_capacity = sum(r.vehicle.capacity for r in type_routes if r.vehicle)
            total_students = sum(
                r.assignments.filter(is_active=True).count() for r in type_routes
            )

            summary[route_type] = {
                'total_routes': type_routes.count(),
                'total_capacity': total_capacity,
                'total_students': total_students,
                'utilization': (
                    f'{(total_students / total_capacity * 100):.1f}%'
                    if total_capacity > 0 else '0%'
                ),
            }

        return Response(summary)


class TransportRouteStopViewSet(viewsets.ModelViewSet):
    """
    Route stop management — pickup and dropoff locations.

    Covers:
    - List/filter stops (by route)
    - Stop details (time, location, coordinates)
    - Retrieve, create, update stops
    """
    queryset = TransportRouteStop.objects.select_related('route')
    serializer_class = TransportRouteStopSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("transport"),
        HasPermission(read="transport.routes.view", write="transport.routes.manage"),
    ]
    module = "transport"
    filterset_fields = ['route', 'stop_order']
    search_fields = ['stop_name', 'location']
    ordering_fields = ['stop_order', 'arrival_time']
    ordering = ['stop_order']


class TransportStaffViewSet(viewsets.ModelViewSet):
    """
    Transport staff management — drivers, conductors, helpers.

    Covers:
    - List/filter staff (by route, role)
    - Staff details (license, emergency contact)
    - Retrieve, create, update staff assignments
    """
    queryset = TransportStaff.objects.select_related('employee', 'route')
    serializer_class = TransportStaffSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("transport"),
        HasPermission(read="transport.staff.view", write="transport.staff.manage"),
    ]
    module = "transport"
    filterset_fields = ['route', 'role', 'is_active']
    search_fields = ['employee__full_name', 'license_number']
    ordering_fields = ['employee__full_name', 'role']
    ordering = ['role', 'employee__full_name']

    @extend_schema(
        description="Get staff assigned to a route",
        parameters=[
            OpenApiParameter(name='route', required=True, description='Route ID'),
        ],
    )
    @action(detail=False, methods=['get'])
    def by_route(self, request):
        """Get all staff assigned to a specific route."""
        route_id = request.query_params.get('route')
        if not route_id:
            return Response({'error': 'route ID required'}, status=400)

        staff = TransportStaff.objects.filter(
            route_id=route_id,
            is_active=True,
            tenant=request.tenant
        ).select_related('employee')

        return Response(TransportStaffSerializer(staff, many=True).data)


class TransportAssignmentViewSet(viewsets.ModelViewSet):
    """
    Student transport assignment management.

    Covers:
    - Assign students to routes
    - List/filter assignments (by student, route)
    - Track assignment history
    - Daily allowance management
    """
    queryset = TransportAssignment.objects.select_related('student', 'route')
    serializer_class = TransportAssignmentSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("transport"),
        HasPermission(read="transport.assignments.view", write="transport.assignments.manage"),
    ]
    module = "transport"
    filterset_fields = ['student', 'route', 'is_active']
    search_fields = ['student__full_name', 'route__name']
    ordering_fields = ['assignment_date', 'student__full_name']
    ordering = ['-assignment_date']

    @extend_schema(
        description="Get current transport assignment for a student",
        parameters=[
            OpenApiParameter(name='student', required=True, description='Student ID'),
        ],
    )
    @action(detail=False, methods=['get'])
    def student_route(self, request):
        """Get current route assignment for a student."""
        student_id = request.query_params.get('student')
        if not student_id:
            return Response({'error': 'student ID required'}, status=400)

        try:
            assignment = TransportAssignment.objects.select_related(
                'student', 'route'
            ).get(
                student_id=student_id,
                is_active=True,
                tenant=request.tenant
            )
            return Response(TransportAssignmentSerializer(assignment).data)
        except TransportAssignment.DoesNotExist:
            return Response(
                {'error': 'Student has no active transport assignment'},
                status=404
            )

    @extend_schema(
        description="Get all students assigned to a route",
        parameters=[
            OpenApiParameter(name='route', required=True, description='Route ID'),
        ],
    )
    @action(detail=False, methods=['get'])
    def route_students(self, request):
        """Get all students assigned to a specific route."""
        route_id = request.query_params.get('route')
        if not route_id:
            return Response({'error': 'route ID required'}, status=400)

        assignments = TransportAssignment.objects.filter(
            route_id=route_id,
            is_active=True,
            tenant=request.tenant
        ).select_related('student')

        return Response(TransportAssignmentSerializer(assignments, many=True).data)
