"""
Hostel domain serializers — rooms and fees.

Pattern: All serializers inherit from TenantAwareSerializer + ServiceSerializerMixin.
This ensures:
1. Tenant context is properly passed to services
2. Service exceptions are translated to DRF errors
3. Validation logic is centralized in the service layer
"""

from rest_framework import serializers
from core.models import HostelRoom, HostelFee
from core.serializers.base import TenantAwareSerializer, ServiceSerializerMixin


class HostelRoomSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for HostelRoom — individual dormitory rooms.

    Tracks room type, capacity, and rental cost. Used for room management
    and occupancy tracking.

    Pattern:
    - Read: List/retrieve rooms
    - Create: Via service
    - Update: Via service
    - Delete: Remove room from inventory
    """
    service_class = None  # Will use HostelService when available

    class Meta:
        model = HostelRoom
        fields = [
            'id', 'room_number', 'room_type', 'capacity', 'rent',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = HostelRoom.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class HostelFeeSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for HostelFee — hostel accommodation charges.

    Tracks student hostel fees by room and billing period. Includes
    read-only nested student name for context.

    Pattern:
    - Read: List/retrieve hostel fees
    - Create: Via service
    - Update: Via service
    - Delete: Remove fee record
    """
    service_class = None  # Will use HostelService when available
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model = HostelFee
        fields = [
            'id', 'student', 'student_name', 'room', 'start_date',
            'end_date', 'total_amount',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = HostelFee.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
