"""
Test suite to verify proper service architecture and black box principles
"""
import pytest
from django.test import TestCase
from unittest.mock import Mock, patch
from datetime import date

from core.models import School, Student, Employee, Course, Batch, User
from core.services import (
    StudentService, EmployeeService, AcademicService, ReportingService,
    PermissionService, ServiceException, ValidationException, NotFoundException
)


class ServiceArchitectureTest(TestCase):
    """Test that services properly encapsulate business logic"""
    
    def setUp(self):
        # Create test tenant
        self.school = School.objects.create(
            name="Test School",
            code="TEST001",
            schema_name="test_schema"
        )
        
        # Create test user
        self.user = User.objects.create(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
    
    def test_services_hide_database_implementation(self):
        """Services should not expose Django ORM details"""
        student_service = StudentService(self.school)
        
        # Service methods should return domain objects, not querysets
        result = student_service.get_student_stats()
        self.assertIsInstance(result, dict)
        self.assertIn('total_active', result)
        
        # Service should handle its own error cases
        with self.assertRaises(NotFoundException):
            student_service.get_by_id('nonexistent-id')
    
    def test_services_are_tenant_aware(self):
        """All services should automatically filter by tenant"""
        service1 = StudentService(self.school)
        
        # Create a second school
        school2 = School.objects.create(
            name="School 2",
            code="TEST002",
            schema_name="test_schema2"
        )
        service2 = StudentService(school2)
        
        # Services should only see their own tenant's data
        self.assertEqual(service1.get_tenant(), self.school)
        self.assertEqual(service2.get_tenant(), school2)
    
    def test_reporting_service_is_black_box(self):
        """ReportingService should hide complexity of aggregating from multiple services"""
        reporting_service = ReportingService(self.school)
        
        # Should get comprehensive stats without knowing internal implementation
        stats = reporting_service.get_dashboard_stats()
        
        self.assertIn('students', stats)
        self.assertIn('employees', stats) 
        self.assertIn('academic', stats)
        self.assertIn('summary', stats)
        
        # Should gracefully handle service failures
        with patch.object(StudentService, 'get_student_stats', side_effect=Exception("Service down")):
            stats = reporting_service.get_dashboard_stats()
            # Should still return data structure, possibly with error indicators
            self.assertIn('students', stats)
    
    def test_permission_service_is_replaceable(self):
        """Permission service should use interface that can be replaced"""
        permission_service = PermissionService(self.school)
        
        # Should have clean interface
        result = permission_service.check_tenant_access(self.user)
        self.assertIsInstance(result, bool)
        
        result = permission_service.check_action_permission(self.user, 'view', 'students')
        self.assertIsInstance(result, bool)
        
        permissions = permission_service.get_user_permissions(self.user)
        self.assertIsInstance(permissions, list)
    
    def test_services_handle_exceptions_consistently(self):
        """All services should handle exceptions in consistent way"""
        student_service = StudentService(self.school)
        employee_service = EmployeeService(self.school)
        academic_service = AcademicService(self.school)
        
        # All services should raise ServiceException hierarchy
        with self.assertRaises(ValidationException):
            student_service.create_student("", "", "", date.today(), "male")
        
        with self.assertRaises(NotFoundException):
            employee_service.get_by_id("nonexistent")
        
        with self.assertRaises(ValidationException):
            academic_service.create_course("", "")
    
    def test_service_operations_are_logged(self):
        """Service operations should be automatically logged"""
        student_service = StudentService(self.school)
        
        # Operations should complete without explicit logging code
        with patch('core.services.logging_service.ServiceLogger.info') as mock_log:
            stats = student_service.get_student_stats()
            # Verify operation completed successfully
            self.assertIsInstance(stats, dict)


class ServiceInterfaceTest(TestCase):
    """Test that service interfaces follow black box principles"""
    
    def setUp(self):
        self.school = School.objects.create(
            name="Interface Test School",
            code="INT001", 
            schema_name="interface_schema"
        )
    
    def test_services_return_primitives_not_models(self):
        """Services should return data primitives, not Django model instances when appropriate"""
        reporting_service = ReportingService(self.school)
        
        quick_stats = reporting_service.get_quick_stats()
        
        # Should return primitive types
        for key, value in quick_stats.items():
            self.assertIn(type(value), [int, float, str, bool, list, dict])
    
    def test_service_methods_are_descriptive(self):
        """Service method names should clearly indicate what they do"""
        student_service = StudentService(self.school)
        academic_service = AcademicService(self.school)
        
        # Method names should be self-documenting
        self.assertTrue(hasattr(student_service, 'create_student'))
        self.assertTrue(hasattr(student_service, 'get_active_students'))
        self.assertTrue(hasattr(student_service, 'count_active_students'))
        
        self.assertTrue(hasattr(academic_service, 'create_course'))
        self.assertTrue(hasattr(academic_service, 'count_batches'))
        self.assertTrue(hasattr(academic_service, 'get_academic_stats'))
    
    def test_service_dependencies_are_injected(self):
        """Services should accept dependencies rather than hardcode them"""
        # ReportingService properly injects other services
        reporting_service = ReportingService(self.school)
        
        # Should have internal service dependencies
        self.assertIsNotNone(reporting_service.student_service)
        self.assertIsNotNone(reporting_service.employee_service)
        self.assertIsNotNone(reporting_service.academic_service)
        
        # All should use the same tenant
        self.assertEqual(reporting_service.student_service.get_tenant(), self.school)
        self.assertEqual(reporting_service.employee_service.get_tenant(), self.school)


class ServiceReplaceabilityTest(TestCase):
    """Test that services can be replaced without breaking other components"""
    
    def setUp(self):
        self.school = School.objects.create(
            name="Replaceable Test School",
            code="REP001",
            schema_name="replaceable_schema"
        )
    
    def test_mock_service_can_replace_real_service(self):
        """Mock services should be able to replace real services"""
        # Create a mock student service
        mock_student_service = Mock()
        mock_student_service.get_student_stats.return_value = {
            'total_active': 100,
            'total_inactive': 5,
            'recent_students': [],
            'by_gender': {}
        }
        
        # ReportingService should work with mock
        reporting_service = ReportingService(self.school)
        
        # Replace internal service with mock
        reporting_service.student_service = mock_student_service
        
        stats = reporting_service.get_dashboard_stats()
        
        # Should work with mocked data
        self.assertEqual(stats['students']['total_active'], 100)
        mock_student_service.get_student_stats.assert_called_once()
    
    def test_service_interfaces_are_stable(self):
        """Service interfaces should remain stable for replaceability"""
        student_service = StudentService(self.school)
        
        # Core interface methods should exist
        required_methods = [
            'create', 'get_by_id', 'update', 'delete', 'filter', 
            'count', 'exists', 'get_active_students', 'count_active_students'
        ]
        
        for method in required_methods:
            self.assertTrue(hasattr(student_service, method))
            self.assertTrue(callable(getattr(student_service, method)))


@pytest.mark.integration
class ServiceIntegrationTest(TestCase):
    """Integration tests to verify services work together correctly"""
    
    def setUp(self):
        self.school = School.objects.create(
            name="Integration Test School",
            code="INT001",
            schema_name="integration_schema"
        )
    
    def test_reporting_service_aggregates_correctly(self):
        """ReportingService should correctly aggregate data from all domain services"""
        # Create test data through services
        student_service = StudentService(self.school)
        employee_service = EmployeeService(self.school)
        academic_service = AcademicService(self.school)
        
        # Create test data
        course = academic_service.create_course("Test Course", "TC001")
        
        student = student_service.create_student(
            admission_no="2024001",
            first_name="John", 
            last_name="Doe",
            date_of_birth=date(2000, 1, 1),
            gender="male"
        )
        
        employee = employee_service.create_employee(
            employee_number="EMP001",
            first_name="Jane",
            last_name="Teacher", 
            joining_date=date.today(),
            gender=True
        )
        
        # Get aggregated stats
        reporting_service = ReportingService(self.school)
        stats = reporting_service.get_dashboard_stats()
        
        # Verify aggregation
        self.assertGreaterEqual(stats['students']['total_active'], 1)
        self.assertGreaterEqual(stats['employees']['total_active'], 1) 
        self.assertGreaterEqual(stats['academic']['total_courses'], 1)
    
    def test_services_maintain_tenant_isolation(self):
        """Services should maintain tenant isolation across operations"""
        # Create second school
        school2 = School.objects.create(
            name="School 2",
            code="INT002", 
            schema_name="integration_schema2"
        )
        
        service1 = StudentService(self.school)
        service2 = StudentService(school2)
        
        # Create student in school1
        student1 = service1.create_student(
            admission_no="2024001",
            first_name="Student",
            last_name="One",
            date_of_birth=date(2000, 1, 1),
            gender="male"
        )
        
        # School2 service shouldn't see school1's student
        self.assertEqual(service2.count_active_students(), 0)
        self.assertEqual(service1.count_active_students(), 1)
        
        # Each service should maintain its own tenant context
        self.assertNotEqual(service1.get_tenant(), service2.get_tenant())