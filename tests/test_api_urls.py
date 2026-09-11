"""
Test that all API URLs are properly configured and use services
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import RequestFactory
from django.urls import reverse, resolve

from core.views import (
    quick_stats_api, dashboard_stats_api, service_health_api,
    enrollment_trends_api, subjects_api, timetable_crud_api, attendance_summary_api
)


@pytest.mark.django_db(transaction=True)
class TestAPIURLs:
    """Test that API URLs are configured correctly"""

    def setup_method(self):
        self.factory = RequestFactory()
        self.mock_tenant = Mock()
        self.mock_tenant.id = "test-tenant-id"
        self.mock_tenant.name = "Test School"

    def test_quick_stats_api_url_resolves(self):
        """Test quick stats API URL resolves"""
        url = reverse('core:quick_stats_api')
        resolved = resolve(url)
        assert resolved.func == quick_stats_api

    def test_dashboard_stats_api_url_resolves(self):
        """Test dashboard stats API URL resolves"""
        url = reverse('core:dashboard_stats_api')
        resolved = resolve(url)
        assert resolved.func == dashboard_stats_api

    def test_service_health_api_url_resolves(self):
        """Test service health API URL resolves"""
        url = reverse('core:service_health_api')
        resolved = resolve(url)
        assert resolved.func == service_health_api

    def test_enrollment_trends_api_url_resolves(self):
        """Test enrollment trends API URL resolves"""
        url = reverse('core:enrollment_trends_api')
        resolved = resolve(url)
        assert resolved.func == enrollment_trends_api

    def test_subjects_api_url_resolves(self):
        """Test subjects API URL resolves"""
        url = reverse('core:subjects_api')
        resolved = resolve(url)
        assert resolved.func == subjects_api

    def test_timetable_api_url_resolves(self):
        """Test timetable API URL resolves"""
        url = reverse('core:timetable_api')
        resolved = resolve(url)
        assert resolved.func == timetable_crud_api

    def test_attendance_summary_api_url_resolves(self):
        """Test attendance summary API URL resolves"""
        url = reverse('core:attendance_summary_api')
        resolved = resolve(url)
        assert resolved.func == attendance_summary_api


@pytest.mark.django_db(transaction=True)
class TestAPIEndpoints:
    """Test that API endpoints work with the service architecture.

    The service classes are imported into ``core.views``; patch the names where
    they are *used* (``core.views.*``), not where they are defined, otherwise
    the view keeps its original reference and the mock is never exercised.
    The views return ``django.http.JsonResponse`` (no ``.json()`` helper), so
    the body is parsed with ``json.loads(response.content)``.
    """

    def setup_method(self):
        self.factory = RequestFactory()
        self.mock_tenant = Mock()
        self.mock_tenant.id = "test-tenant"
        self.mock_tenant.name = "Test School"

        # Create mock user
        self.mock_user = Mock()
        self.mock_user.id = "test-user-id"
        self.mock_user.username = "testuser"
        self.mock_user.is_authenticated = True

    def _build_request(self, path, tenant="__default__"):
        request = self.factory.get(path)
        request.tenant = self.mock_tenant if tenant == "__default__" else tenant
        request.user = self.mock_user
        return request

    @patch('core.views.AttendanceService')
    @patch('core.views.AcademicService')
    @patch('core.views.StudentService')
    def test_quick_stats_api_uses_services(
        self, mock_student, mock_academic, mock_attendance
    ):
        """quick_stats_api aggregates StudentService/AcademicService/AttendanceService."""
        mock_student.return_value.count.return_value = 100
        mock_academic.return_value.count_batches.return_value = 10
        mock_attendance.return_value.get_daily_attendance_summary.return_value = {
            'present_count': 80,
            'absent_count': 20,
        }

        response = quick_stats_api(self._build_request('/api/stats/quick/'))

        assert response.status_code == 200
        mock_student.assert_called_once_with(self.mock_tenant)
        mock_academic.assert_called_once_with(self.mock_tenant)
        mock_attendance.assert_called_once_with(self.mock_tenant)

    @patch('core.views.ReportingService')
    def test_dashboard_stats_api_uses_reporting_service(self, mock_reporting_service):
        """dashboard_stats_api delegates to ReportingService."""
        mock_service_instance = mock_reporting_service.return_value
        mock_service_instance.get_dashboard_stats.return_value = {
            'students': {'total_active': 100},
            'employees': {'total_active': 25},
            'academic': {'active_batches': 10}
        }

        response = dashboard_stats_api(self._build_request('/api/stats/dashboard/'))

        assert response.status_code == 200
        mock_reporting_service.assert_called_once_with(self.mock_tenant)
        mock_service_instance.get_dashboard_stats.assert_called_once()

    def test_service_health_api_checks_all_services(self):
        """service_health_api reports the health of every service."""
        with patch('core.views.StudentService') as mock_student, \
             patch('core.views.EmployeeService') as mock_employee, \
             patch('core.views.AcademicService') as mock_academic, \
             patch('core.views.AttendanceService') as mock_attendance, \
             patch('core.views.TimetableService') as mock_timetable, \
             patch('core.views.ReportingService'):

            # Mock all service instances
            mock_student.return_value.count_active_students.return_value = 100
            mock_employee.return_value.count_active_employees.return_value = 25
            mock_academic.return_value.count_courses.return_value = 5
            mock_academic.return_value.count_batches.return_value = 10
            mock_attendance.return_value.count.return_value = 500
            mock_timetable.return_value.count.return_value = 50

            response = service_health_api(self._build_request('/api/health/'))

            assert response.status_code == 200
            response_data = json.loads(response.content.decode('utf-8'))
            assert response_data['overall_status'] == 'healthy'
            assert 'student_service' in response_data['services']
            assert 'employee_service' in response_data['services']
            assert 'academic_service' in response_data['services']

    def test_api_handles_missing_tenant(self):
        """APIs return a 400 when no tenant is resolved."""
        response = quick_stats_api(self._build_request('/api/stats/quick/', tenant=None))

        assert response.status_code == 400
        response_data = json.loads(response.content.decode('utf-8'))
        assert 'error' in response_data
        assert response_data['error'] == 'Tenant not found'
