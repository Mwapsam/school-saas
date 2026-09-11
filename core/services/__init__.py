"""
Core services package for the Pinewood School Management System.

This package provides business logic services following clean architecture principles:
- Single Responsibility: Each service handles one domain
- Tenant Awareness: All operations respect school boundaries
- Dependency Injection: Services accept dependencies for testability
- Error Handling: Consistent exception handling
- Idempotency: Safe to call operations multiple times
- Stateless: No instance state between calls
"""

from .exceptions import (
    ServiceException,
    ValidationException,
    NotFoundException,
    DuplicateException,
    PermissionException,
    TenantException,
    BusinessLogicException,
    ExternalServiceException,
    handle_service_exceptions
)

from .base import BaseService, TenantAwareService
from .logging_service import ServiceLogger, logged_operation, get_service_logger
from .student_service import StudentService
from .employee_service import EmployeeService
from .academic_service import AcademicService
from .finance_service import FinanceService
from .fee_collection_service import FeeCollectionService
from .library_service import LibraryService
from .user_service import UserService
from .attendance_service import AttendanceService
from .exam_service import ExamService
from .communication_service import CommunicationService
from .reporting_service import ReportingService
from .permission_service import PermissionService, PermissionServiceInterface, DjangoPermissionService
from .timetable_service import TimetableService
from .report_generation_service import ReportGenerationService
from .class_teacher_assignment_service import ClassTeacherAssignmentService
from .transport_service import TransportService, TransportSettingsService

__all__ = [
    # Exception classes
    'ServiceException',
    'ValidationException', 
    'NotFoundException',
    'DuplicateException',
    'PermissionException',
    'TenantException',
    'BusinessLogicException',
    'ExternalServiceException',
    'handle_service_exceptions',
    
    # Base service classes
    'BaseService',
    'TenantAwareService',
    
    # Logging utilities
    'ServiceLogger',
    'logged_operation',
    'get_service_logger',
    
    # Domain services
    'StudentService',
    'EmployeeService',
    'AcademicService',
    'FinanceService',
    'FeeCollectionService',
    'TransportService',
    'TransportSettingsService',
    'LibraryService',
    'UserService',
    'AttendanceService',
    'ExamService',
    'CommunicationService',
    'ReportingService',
    'PermissionService',
    'PermissionServiceInterface',
    'DjangoPermissionService',
    'TimetableService',
    'ReportGenerationService',
    'ClassTeacherAssignmentService',
]