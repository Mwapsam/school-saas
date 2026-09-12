"""
Students domain API — UNUSED / BROKEN reference sketch, do not wire up as-is.

Found 2026-09-12: nothing imports this module (core/api_urls.py registers the
real, working Student/Course/Batch/Subject ViewSets from core/api_views.py
instead). This file's serializers reference model fields that don't exist on
the real Student model (`admission_number`, a plain `full_name`, direct
`batch`/`course` FKs) — the actual model has `admission_no`, computed
first/last name, and a many-to-many batch relation via BatchStudent. Using
this ViewSet as registered would raise a DRF AssertionError on first request.

The permission-enforcement PATTERN here (ModuleEnabled + HasPermission +
drf-spectacular decorators) is still the right one to copy for new domains —
core/api_views.py's StudentViewSet now uses that same pattern with correct
field mappings. Fix this file's serializers to match the real model before
ever registering it, or delete it.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import Student, Batch, Course, Subject
from core.authz.drf import ModuleEnabled, HasPermission
from core.services import StudentService


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

from rest_framework import serializers


class StudentSerializer(serializers.ModelSerializer):
    """Serializer for Student model — handles CRUD + nested course/batch info."""
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'admission_number', 'full_name', 'first_name', 'last_name',
            'date_of_birth', 'batch', 'batch_name', 'course', 'course_name',
            'gender', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BatchSerializer(serializers.ModelSerializer):
    """Serializer for Batch model — student cohorts."""
    course_name = serializers.CharField(source='course.name', read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = [
            'id', 'name', 'code', 'course', 'course_name', 'start_date', 'end_date',
            'student_count', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_student_count(self, obj):
        """Return count of students in this batch."""
        return obj.students.count()


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model — academic programs."""
    class Meta:
        model = Course
        fields = [
            'id', 'name', 'code', 'description', 'section_name',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for Subject model — courses/subjects taught."""
    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'description',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class StudentViewSet(viewsets.ModelViewSet):
    """
    Student management API.

    Covers:
    - List all students in current school
    - Retrieve, create, update, delete individual students
    - Filter by batch, course, active status
    - Search by admission number or name

    Permission model:
    - ModuleEnabled: entire endpoint disabled if academics module off
    - IsAuthenticated: user must be logged in
    - HasPermission("students.view" / "students.manage"): capability-based access control
    """
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="students.view", write="students.manage"),
    ]
    module = "academics"  # Required for ModuleEnabled permission
    filterset_fields = ['batch', 'course', 'is_active']
    search_fields = ['admission_number', 'full_name', 'first_name', 'last_name']
    ordering_fields = ['full_name', 'admission_number', 'created_at']
    ordering = ['full_name']

    def get_queryset(self):
        """Automatically filtered to current tenant (via django-tenants)."""
        return super().get_queryset().select_related('batch', 'course')

    @extend_schema(
        description="Retrieve a student by ID",
        responses=StudentSerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single student."""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        description="List all students (paginated, filterable)",
        parameters=[
            OpenApiParameter(name='batch', description='Filter by batch ID'),
            OpenApiParameter(name='course', description='Filter by course ID'),
            OpenApiParameter(name='search', description='Search by name/admission number'),
        ],
    )
    def list(self, request, *args, **kwargs):
        """List students with filtering and search."""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        description="Create a new student",
        request=StudentSerializer,
        responses={201: StudentSerializer},
    )
    def create(self, request, *args, **kwargs):
        """Create a new student."""
        return super().create(request, *args, **kwargs)

    @extend_schema(
        description="Update an existing student",
        request=StudentSerializer,
        responses=StudentSerializer,
    )
    def update(self, request, *args, **kwargs):
        """Update a student (full or partial)."""
        return super().update(request, *args, **kwargs)

    @extend_schema(
        description="Delete a student",
        responses={204: None},
    )
    def destroy(self, request, *args, **kwargs):
        """Delete a student."""
        return super().destroy(request, *args, **kwargs)


class BatchViewSet(viewsets.ModelViewSet):
    """
    Batch (cohort) management API.

    Covers:
    - List all batches for current school
    - Retrieve, create, update, delete batches
    - Filter by course, active status
    - Get student count per batch
    """
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="academics.batches.view", write="academics.batches.manage"),
    ]
    module = "academics"
    filterset_fields = ['course', 'is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'start_date']
    ordering = ['name']

    def get_queryset(self):
        """Automatically filtered to current tenant."""
        return super().get_queryset().select_related('course').prefetch_related('students')


class CourseViewSet(viewsets.ModelViewSet):
    """
    Course (academic program) management API.

    Covers:
    - List all courses for current school
    - Retrieve, create, update, delete courses
    - Filter by active status
    """
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="academics.courses.view", write="academics.courses.manage"),
    ]
    module = "academics"
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name']
    ordering = ['name']


class SubjectViewSet(viewsets.ModelViewSet):
    """
    Subject (course content) management API.

    Covers:
    - List all subjects for current school
    - Retrieve, create, update, delete subjects
    - Filter by active status
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="academics.subjects.view", write="academics.subjects.manage"),
    ]
    module = "academics"
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name']
    ordering = ['name']
