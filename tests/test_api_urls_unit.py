"""
Unit tests for API URLs that don't require database access
"""
import pytest
from unittest.mock import Mock, patch
from django.test import RequestFactory
from django.urls import reverse, resolve
from django.contrib.auth.models import AnonymousUser
import json


class TestAPIURLConfiguration:
    """Test that API URLs are configured correctly without database"""
    
    def setup_method(self):
        self.factory = RequestFactory()
        self.mock_tenant = Mock()
        self.mock_tenant.id = "test-tenant-id"
        self.mock_tenant.name = "Test School"
    
    def test_quick_stats_api_url_resolves(self):
        """Test quick stats API URL resolves"""
        from core.views import quick_stats_api
        url = reverse('core:quick_stats_api')
        resolved = resolve(url)
        assert resolved.func == quick_stats_api
    
    def test_dashboard_stats_api_url_resolves(self):
        """Test dashboard stats API URL resolves"""
        from core.views import dashboard_stats_api
        url = reverse('core:dashboard_stats_api')
        resolved = resolve(url)
        assert resolved.func == dashboard_stats_api
    
    def test_service_health_api_url_resolves(self):
        """Test service health API URL resolves"""
        from core.views import service_health_api
        url = reverse('core:service_health_api')
        resolved = resolve(url)
        assert resolved.func == service_health_api
    
    def test_enrollment_trends_api_url_resolves(self):
        """Test enrollment trends API URL resolves"""
        from core.views import enrollment_trends_api
        url = reverse('core:enrollment_trends_api')
        resolved = resolve(url)
        assert resolved.func == enrollment_trends_api
    
    def test_subjects_api_url_resolves(self):
        """Test subjects API URL resolves"""
        from core.views import subjects_api
        url = reverse('core:subjects_api')
        resolved = resolve(url)
        assert resolved.func == subjects_api
    
    def test_timetable_api_url_resolves(self):
        """Test timetable API URL resolves"""
        from core.views import timetable_crud_api
        url = reverse('core:timetable_api')
        resolved = resolve(url)
        assert resolved.func == timetable_crud_api
    
    def test_attendance_summary_api_url_resolves(self):
        """Test attendance summary API URL resolves"""
        from core.views import attendance_summary_api
        url = reverse('core:attendance_summary_api')
        resolved = resolve(url)
        assert resolved.func == attendance_summary_api


class TestAPIServiceIntegration:
    """Test that API endpoints integrate with service architecture"""

    def setup_method(self):
        self.factory = RequestFactory()
        self.mock_tenant = Mock()
        self.mock_tenant.id = "test-tenant"
        self.mock_tenant.name = "Test School"
        self.mock_user = Mock()
        self.mock_user.is_authenticated = True
        self.mock_user.is_staff = True
    
    @patch('core.views.AttendanceService')
    @patch('core.views.AcademicService')
    @patch('core.views.StudentService')
    def test_quick_stats_api_uses_services(self, mock_student_service, mock_academic_service, mock_attendance_service):
        """quick_stats_api aggregates Student, Academic and Attendance services."""
        from core.views import quick_stats_api

        mock_student_service.return_value.count.return_value = 100
        mock_academic_service.return_value.count_batches.return_value = 10
        mock_attendance_service.return_value.get_daily_attendance_summary.return_value = {
            'present_count': 80,
            'absent_count': 20,
        }

        request = self.factory.get('/api/stats/quick/')
        request.tenant = self.mock_tenant
        request.user = self.mock_user

        response = quick_stats_api(request)

        assert response.status_code == 200
        mock_student_service.assert_called_once_with(self.mock_tenant)
        mock_academic_service.assert_called_once_with(self.mock_tenant)
    
    @patch('core.views.ReportingService')
    def test_dashboard_stats_api_uses_reporting_service(self, mock_reporting_service):
        """Test that dashboard stats API uses ReportingService"""
        from core.views import dashboard_stats_api
        
        mock_service_instance = mock_reporting_service.return_value
        mock_service_instance.get_dashboard_stats.return_value = {
            'students': {'total_active': 100},
            'employees': {'total_active': 25},
            'academic': {'active_batches': 10}
        }
        
        request = self.factory.get('/api/stats/dashboard/')
        request.tenant = self.mock_tenant
        request.user = self.mock_user
        
        response = dashboard_stats_api(request)
        
        assert response.status_code == 200
        mock_reporting_service.assert_called_once_with(self.mock_tenant)
        mock_service_instance.get_dashboard_stats.assert_called_once()
    
    def test_service_health_api_checks_services(self):
        """Test that service health API checks all services"""
        from core.views import service_health_api
        
        with patch('core.views.StudentService') as mock_student, \
             patch('core.views.EmployeeService') as mock_employee, \
             patch('core.views.AcademicService') as mock_academic, \
             patch('core.views.AttendanceService') as mock_attendance, \
             patch('core.views.TimetableService') as mock_timetable:
            
            # Mock all service instances
            mock_student.return_value.count_active_students.return_value = 100
            mock_employee.return_value.count_active_employees.return_value = 25
            mock_academic.return_value.count_courses.return_value = 5
            mock_academic.return_value.count_batches.return_value = 10
            mock_attendance.return_value.count.return_value = 500
            mock_timetable.return_value.count.return_value = 50
            
            request = self.factory.get('/api/health/')
            request.tenant = self.mock_tenant
            request.user = self.mock_user
            
            response = service_health_api(request)
            
            assert response.status_code == 200
            response_data = json.loads(response.content.decode('utf-8'))
            assert response_data['overall_status'] == 'healthy'
            assert 'student_service' in response_data['services']
            assert 'employee_service' in response_data['services']
            assert 'academic_service' in response_data['services']
    
    def test_api_handles_missing_tenant(self):
        """Test that APIs handle missing tenant gracefully"""
        from core.views import quick_stats_api
        
        request = self.factory.get('/api/stats/quick/')
        request.tenant = None
        request.user = self.mock_user
        
        response = quick_stats_api(request)
        
        assert response.status_code == 400
        response_data = json.loads(response.content.decode('utf-8'))
        assert 'error' in response_data
        assert response_data['error'] == 'Tenant not found'
    
    @patch('core.views.AcademicService')
    def test_subjects_api_uses_academic_service(self, mock_academic_service):
        """Test that subjects API uses AcademicService"""
        from core.views import subjects_api
        
        # The view iterates queryset.select_related('batch')[:50] and reads model
        # attributes, so the service must return a queryset-like object yielding
        # subject-like objects with JSON-serializable attributes.
        mock_subject = Mock()
        mock_subject.id = 'sub-1'
        mock_subject.name = 'Mathematics'
        mock_subject.code = 'MATH101'
        mock_subject.batch.id = 'batch-1'
        mock_subject.batch.name = 'Batch A'

        mock_service_instance = mock_academic_service.return_value
        mock_service_instance.search_subjects.return_value.select_related.return_value = [mock_subject]

        request = self.factory.get('/api/subjects/')
        request.tenant = self.mock_tenant
        request.user = self.mock_user

        response = subjects_api(request)

        assert response.status_code == 200, response.content
        mock_academic_service.assert_called_once_with(self.mock_tenant)
        mock_service_instance.search_subjects.assert_called_once()
    
    @patch('core.views.TimetableService')
    def test_timetable_api_uses_timetable_service(self, mock_timetable_service):
        """Test that timetable API uses TimetableService"""
        from core.views import timetable_crud_api

        # The view iterates timetable entries and reads related model fields, so
        # build a entry-like Mock with JSON-serializable attribute values.
        entry = Mock()
        entry.weekday.weekday = 'Monday'
        entry.id = 'tt-1'
        entry.class_timing.start_time.strftime.return_value = '09:00'
        entry.class_timing.end_time.strftime.return_value = '10:00'
        entry.class_timing.name = 'Period 1'
        entry.class_timing.is_break = False
        entry.subject.name = 'Math'
        entry.employee.first_name = 'Jane'
        entry.employee.last_name = 'Doe'

        mock_service_instance = mock_timetable_service.return_value
        mock_service_instance.get_timetables.return_value = [entry]

        # timetable_crud_api requires a batch_id query parameter for GET requests.
        request = self.factory.get('/api/timetable/', {'batch_id': 'batch-1'})
        request.tenant = self.mock_tenant
        request.user = self.mock_user

        response = timetable_crud_api(request)

        assert response.status_code == 200, response.content
        mock_timetable_service.assert_called_once_with(self.mock_tenant)
        mock_service_instance.get_timetables.assert_called_once()