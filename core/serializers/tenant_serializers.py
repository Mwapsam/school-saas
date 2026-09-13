"""
Serializers for tenant/school management and demo requests.
"""

from rest_framework import serializers
from core.models import School, DemoRequest


class SchoolSerializer(serializers.ModelSerializer):
    """Serializer for School (tenant) CRUD operations.

    Used for superuser provisioning of new schools.
    """

    class Meta:
        model = School
        fields = [
            'id',
            'name',
            'code',
            'description',
            'logo',
            'logo_secondary',
            'primary_color',
            'secondary_color',
            'email',
            'phone',
            'address_line1',
            'address_line2',
            'city',
            'state',
            'pin_code',
            'country',
            'website',
            'is_active',
            'admission_enabled',
            'admission_heading',
            'admission_cta_text',
            'admission_description',
            'admission_email',
            'social_links',
            'features',
            'timezone',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SchoolListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing schools."""

    logo_url = serializers.CharField(source='logo_url', read_only=True)

    class Meta:
        model = School
        fields = [
            'id',
            'name',
            'code',
            'email',
            'is_active',
            'logo_url',
            'admission_enabled',
            'created_at',
        ]
        read_only_fields = fields


class DemoRequestSerializer(serializers.ModelSerializer):
    """Serializer for demo booking requests (public)."""

    class Meta:
        model = DemoRequest
        fields = [
            'id',
            'full_name',
            'email',
            'phone',
            'school_name',
            'message',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'status', 'created_at']


class DemoRequestAdminSerializer(serializers.ModelSerializer):
    """Admin-only serializer with notes field."""

    class Meta:
        model = DemoRequest
        fields = [
            'id',
            'full_name',
            'email',
            'phone',
            'school_name',
            'message',
            'status',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
