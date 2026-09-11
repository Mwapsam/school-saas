"""
DRF Serializers that leverage services for business logic
"""
from .base import ServiceSerializerMixin
from .student_serializers import (
    StudentSerializer, StudentListSerializer, StudentDetailSerializer,
    StudentBulkCreateSerializer, StudentSearchSerializer, GuardianSerializer
)
from .user_serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    UserProfileSerializer, PasswordChangeSerializer
)
from .academic_serializers import (
    BatchSerializer, CourseSerializer, SubjectSerializer,
    BatchStudentSerializer, BatchListSerializer, AcademicReportSerializer,
    BatchTransferSerializer
)
from .admission_serializers import (
    AdmissionApplicationSerializer, AdmissionApplicationListSerializer,
    AdmissionApprovalSerializer, AdmissionInterviewSerializer,
    AdmissionBulkApprovalSerializer, AdmissionReportSerializer,
    AdmissionSearchSerializer
)

# Import services for use in serializers
from core.services import (
    StudentService, UserService, AcademicService, AttendanceService,
    TimetableService, ReportingService, EmployeeService
)

__all__ = [
    'ServiceSerializerMixin',
    # Student serializers
    'StudentSerializer',
    'StudentListSerializer', 
    'StudentDetailSerializer',
    'StudentBulkCreateSerializer',
    'StudentSearchSerializer',
    'GuardianSerializer',
    # User serializers
    'UserSerializer',
    'UserCreateSerializer',
    'UserUpdateSerializer',
    'UserProfileSerializer',
    'PasswordChangeSerializer',
    # Academic serializers
    'BatchSerializer',
    'CourseSerializer',
    'SubjectSerializer',
    'BatchStudentSerializer',
    'BatchListSerializer',
    'AcademicReportSerializer',
    'BatchTransferSerializer',
    # Admission serializers
    'AdmissionApplicationSerializer',
    'AdmissionApplicationListSerializer',
    'AdmissionApprovalSerializer',
    'AdmissionInterviewSerializer',
    'AdmissionBulkApprovalSerializer',
    'AdmissionReportSerializer',
    'AdmissionSearchSerializer',
    # Services
    'StudentService',
    'UserService',
    'AcademicService',
    'AttendanceService',
    'TimetableService',
    'ReportingService',
    'EmployeeService',
]
