"""
Transport domain serializers — routes, stops, staff, and fees.

Pattern: All serializers inherit from TenantAwareSerializer + ServiceSerializerMixin.
This ensures:
1. Tenant context is properly passed to services
2. Service exceptions are translated to DRF errors
3. Validation logic is centralized in the service layer
"""

from rest_framework import serializers
from core.models import (
    TransportRoute, TransportRouteStop, TransportStaff, TransportFee
)
from core.serializers.base import TenantAwareSerializer, ServiceSerializerMixin


class TransportRouteStopSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for TransportRouteStop — stops along a transport route.

    Includes read-only nested route name and stop name for context.
    Tracks pickup/dropoff times for each stop.

    Pattern:
    - Read: List/retrieve route stops with context
    - Create: Via service
    - Update: Via service
    - Delete: Remove stop from route
    """
    service_class = None  # Will use TransportService when available
    route_name = serializers.CharField(source='route.route_name', read_only=True)
    stop_name = serializers.CharField(source='stop.name', read_only=True)

    class Meta:
        model = TransportRouteStop
        fields = [
            'id', 'route', 'route_name', 'stop', 'stop_name', 'order',
            'pickup_time', 'dropoff_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = TransportRouteStop.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class TransportRouteSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for TransportRoute — daily transportation routes.

    Includes nested driver and attendant names. Tracks vehicle assignment,
    fare, and estimated duration.

    Pattern:
    - Read: List/retrieve routes with staff context
    - Create: Via service
    - Update: Via service
    - Delete: Deactivate or remove route
    """
    service_class = None  # Will use TransportService when available
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    attendant_name = serializers.CharField(source='attendant.full_name', read_only=True)

    class Meta:
        model = TransportRoute
        fields = [
            'id', 'route_name', 'code', 'fare', 'description', 'vehicle',
            'driver', 'driver_name', 'attendant', 'attendant_name',
            'estimated_duration_minutes',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = TransportRoute.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class TransportStaffSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for TransportStaff — drivers, conductors, helpers, and support staff.

    Tracks staff type, license information, contact details, and emergency contacts.

    Pattern:
    - Read: List/retrieve transport staff
    - Create: Via service
    - Update: Via service
    - Delete: Deactivate or remove staff
    """
    service_class = None  # Will use TransportService when available

    class Meta:
        model = TransportStaff
        fields = [
            'id', 'full_name', 'staff_type', 'license_number', 'license_expiry',
            'phone', 'alt_phone', 'email', 'national_id',
            'emergency_contact_name', 'emergency_contact_phone', 'employee',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = TransportStaff.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class TransportFeeSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for TransportFee — transport charges per student per route.

    **DEPRECATED:** This serializer represents historical rows only. Modern transport
    fees are managed through the Finance module as StudentFee records. This endpoint
    is read-only for backward compatibility.

    Pattern:
    - Read: List/retrieve historical transport fees
    - Create: Not exposed (use Finance module instead)
    - Update: Not exposed (use Finance module instead)
    - Delete: Not exposed
    """
    service_class = None
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    route_name = serializers.CharField(source='route.route_name', read_only=True)

    class Meta:
        model = TransportFee
        fields = [
            'id', 'student', 'student_name', 'route', 'route_name',
            'start_date', 'end_date', 'total_amount',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'student', 'route', 'start_date', 'end_date', 'total_amount',
            'created_at', 'updated_at'
        ]

    def _service_create(self, service, validated_data):
        raise NotImplementedError("TransportFee is deprecated. Use Finance module for new fees.")

    def _service_update(self, service, instance, validated_data):
        raise NotImplementedError("TransportFee is deprecated. Use Finance module for updates.")
