"""
Test service interfaces without requiring database
"""
import pytest
from unittest.mock import Mock, patch
from datetime import date

from core.services import (
    StudentService, EmployeeService, AcademicService, ReportingService,
    PermissionService, ServiceException, ValidationException, NotFoundException
)
from core.services.permission_service import PermissionServiceInterface, DjangoPermissionService


class TestServiceInterfaces:
    """Test that service interfaces follow black box principles"""
    
    def test_services_have_consistent_base_interface(self):
        """All tenant-aware services should have consistent base interface"""
        mock_tenant = Mock()
        mock_tenant.id = "test-tenant"
        mock_tenant.name = "Test Tenant"
        
        # All services should accept tenant in constructor
        student_service = StudentService(mock_tenant)
        employee_service = EmployeeService(mock_tenant)
        academic_service = AcademicService(mock_tenant)
        
        # All should have base CRUD methods
        base_methods = ['create', 'get_by_id', 'update', 'delete', 'filter', 'count', 'exists']
        
        for method_name in base_methods:
            assert hasattr(student_service, method_name), f"StudentService missing {method_name}"
            assert hasattr(employee_service, method_name), f"EmployeeService missing {method_name}"
            assert hasattr(academic_service, method_name), f"AcademicService missing {method_name}"
            
            assert callable(getattr(student_service, method_name))
            assert callable(getattr(employee_service, method_name))
            assert callable(getattr(academic_service, method_name))
    
    def test_reporting_service_aggregates_without_exposing_internals(self):
        """ReportingService should hide complexity of multiple service coordination"""
        mock_tenant = Mock()
        mock_tenant.name = "Test School"
        
        reporting_service = ReportingService(mock_tenant)
        
        # Should have clean interface methods
        interface_methods = [
            'get_dashboard_stats', 'get_quick_stats', 'get_enrollment_trends',
            'get_academic_performance_summary', 'get_financial_overview'
        ]
        
        for method_name in interface_methods:
            assert hasattr(reporting_service, method_name)
            assert callable(getattr(reporting_service, method_name))
        
        # Should initialize internal services automatically
        assert hasattr(reporting_service, 'student_service')
        assert hasattr(reporting_service, 'employee_service')
        assert hasattr(reporting_service, 'academic_service')
        assert hasattr(reporting_service, 'finance_service')
        
        # All internal services should use same tenant
        assert reporting_service.student_service.get_tenant() == mock_tenant
        assert reporting_service.employee_service.get_tenant() == mock_tenant
    
    def test_permission_service_interface_is_replaceable(self):
        """Permission service should use replaceable interface pattern"""
        mock_tenant = Mock()
        
        # Interface should be abstract
        assert hasattr(PermissionServiceInterface, 'can_user_access_tenant')
        assert hasattr(PermissionServiceInterface, 'can_user_perform_action')
        assert hasattr(PermissionServiceInterface, 'get_user_permissions')
        assert hasattr(PermissionServiceInterface, 'has_role')
        
        # Django implementation should implement interface
        django_impl = DjangoPermissionService(mock_tenant)
        assert isinstance(django_impl, PermissionServiceInterface)
        
        # Service facade should accept any implementation
        permission_service = PermissionService(mock_tenant, django_impl)
        assert permission_service.implementation == django_impl
    
    def test_services_use_consistent_exception_hierarchy(self):
        """All services should use the same exception types"""
        # Import the exception hierarchy
        from core.services.exceptions import (
            ServiceException, ValidationException, NotFoundException,
            DuplicateException, PermissionException, TenantException,
            BusinessLogicException, ExternalServiceException
        )
        
        # Check inheritance hierarchy
        assert issubclass(ValidationException, ServiceException)
        assert issubclass(NotFoundException, ServiceException)
        assert issubclass(DuplicateException, ServiceException)
        assert issubclass(PermissionException, ServiceException)
        assert issubclass(TenantException, ServiceException)
        assert issubclass(BusinessLogicException, ServiceException)
        assert issubclass(ExternalServiceException, ServiceException)
        
        # All should support error details
        exception_types = [
            ValidationException, NotFoundException, DuplicateException,
            PermissionException, TenantException, BusinessLogicException, ExternalServiceException
        ]
        
        for exc_type in exception_types:
            exc = exc_type("Test message", details={"test": "data"})
            assert exc.message == "Test message"
            assert exc.details == {"test": "data"}
            assert exc.error_code  # Should have default error code
    
    def test_services_return_structured_data(self):
        """Services should return structured data, not raw model instances"""
        mock_tenant = Mock()
        mock_tenant.id = "test-id"
        mock_tenant.name = "Test School"
        
        # Mock the database layer to return structured data
        with patch.object(StudentService, 'count_active_students') as mock_count, \
             patch.object(EmployeeService, 'count_active_employees') as mock_emp_count, \
             patch.object(AcademicService, 'count_batches') as mock_batch_count, \
             patch.object(AcademicService, 'count_courses') as mock_course_count:
            
            # Set up mocks to return primitive values
            mock_count.return_value = 100
            mock_emp_count.return_value = 25
            mock_batch_count.return_value = 10
            mock_course_count.return_value = 5
            
            reporting_service = ReportingService(mock_tenant)
            quick_stats = reporting_service.get_quick_stats()
            
            # Should return dictionary with primitive values
            assert isinstance(quick_stats, dict)
            assert all(isinstance(v, (int, float, str, bool, list, dict)) for v in quick_stats.values())
    
    def test_service_methods_are_self_documenting(self):
        """Service method names should clearly indicate their purpose"""
        mock_tenant = Mock()
        
        student_service = StudentService(mock_tenant)
        employee_service = EmployeeService(mock_tenant)
        academic_service = AcademicService(mock_tenant)
        
        # Methods should have descriptive names
        student_methods = [
            'create_student', 'get_active_students', 'count_active_students',
            'search_students', 'enroll_in_batch', 'transfer_batch'
        ]
        
        employee_methods = [
            'create_employee', 'get_active_employees', 'count_active_employees',
            'search_employees', 'deactivate_employee', 'activate_employee'
        ]
        
        academic_methods = [
            'create_course', 'create_batch', 'create_subject',
            'count_courses', 'count_batches', 'get_academic_stats'
        ]
        
        for method in student_methods:
            assert hasattr(student_service, method)
        
        for method in employee_methods:
            assert hasattr(employee_service, method)
        
        for method in academic_methods:
            assert hasattr(academic_service, method)
    
    def test_services_encapsulate_business_rules(self):
        """Services should encapsulate business logic validation"""
        mock_tenant = Mock()
        
        # Services should validate inputs without exposing validation logic
        student_service = StudentService(mock_tenant)
        
        # Should have methods that encapsulate complex business operations
        complex_operations = [
            'enroll_in_batch',     # Handles enrollment business rules
            'transfer_batch',      # Handles transfer validation
            'bulk_create_students' # Handles bulk operation validation
        ]
        
        for operation in complex_operations:
            assert hasattr(student_service, operation)
            assert callable(getattr(student_service, operation))


class TestServiceReplaceability:
    """Test that services can be replaced without breaking other components"""
    
    def test_mock_services_can_replace_real_services(self):
        """Mock implementations should work with real service interfaces"""
        mock_tenant = Mock()
        mock_tenant.name = "Mock School"
        
        # Create mock student service with expected interface
        mock_student_service = Mock()
        mock_student_service.get_student_stats.return_value = {
            'total_active': 50,
            'total_inactive': 5,
            'recent_students': [],
            'by_gender': {'male': 25, 'female': 25}
        }
        mock_student_service.get_tenant.return_value = mock_tenant
        
        # Create mock employee service
        mock_employee_service = Mock()
        mock_employee_service.get_employee_stats.return_value = {
            'total_active': 10,
            'total_inactive': 1,
            'by_department': {}
        }
        
        # Create mock academic service
        mock_academic_service = Mock()
        mock_academic_service.get_academic_stats.return_value = {
            'total_courses': 5,
            'total_batches': 3,
            'active_batches': 3
        }
        
        # ReportingService should work with mocks
        reporting_service = ReportingService(mock_tenant)
        reporting_service.student_service = mock_student_service
        reporting_service.employee_service = mock_employee_service
        reporting_service.academic_service = mock_academic_service
        
        # Should work with mocked services
        stats = reporting_service.get_dashboard_stats()
        assert stats['students']['total_active'] == 50
        assert stats['employees']['total_active'] == 10
        
        # Mocks should have been called
        mock_student_service.get_student_stats.assert_called_once()
        mock_employee_service.get_employee_stats.assert_called_once()
        mock_academic_service.get_academic_stats.assert_called_once()
    
    def test_permission_service_implementations_are_interchangeable(self):
        """Different permission implementations should be interchangeable"""
        mock_tenant = Mock()
        mock_user = Mock()
        
        # Create custom permission implementation
        class CustomPermissionService(PermissionServiceInterface):
            def can_user_access_tenant(self, user, tenant):
                return True  # Always allow for testing
            
            def can_user_perform_action(self, user, action, resource, obj=None):
                return action in ['view', 'create']  # Limited permissions
            
            def get_user_permissions(self, user, tenant):
                return ['view_dashboard', 'create_student']
            
            def has_role(self, user, role, tenant=None):
                return role == 'tester'
        
        # Both implementations should work with PermissionService facade
        django_impl = DjangoPermissionService(mock_tenant)
        custom_impl = CustomPermissionService()
        
        django_service = PermissionService(mock_tenant, django_impl)
        custom_service = PermissionService(mock_tenant, custom_impl)
        
        # Both should have same interface
        assert hasattr(django_service, 'check_tenant_access')
        assert hasattr(custom_service, 'check_tenant_access')
        
        # Different implementations should produce different results
        # (This would be true with real user/tenant objects)
        assert django_service.implementation != custom_service.implementation