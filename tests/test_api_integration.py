"""
Test API views to ensure they work with the new service architecture
"""
import json
import pytest
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from core.views import quick_stats_api

User = get_user_model()


class APIViewTest(TestCase):
    """Test that API views work with the service layer"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.mock_tenant = Mock()
        self.mock_tenant.id = "test-tenant-id"
        self.mock_tenant.name = "Test School"
        self.mock_user = Mock()
        self.mock_user.is_authenticated = True
        self.mock_user.is_staff = True
    
    @patch('core.views.AttendanceService')
    @patch('core.views.AcademicService')
    @patch('core.views.StudentService')
    def test_quick_stats_api_uses_services(self, mock_student_service, mock_academic_service, mock_attendance_service):
        """Test that quick_stats_api uses the service layer"""
        request = self.factory.get('/api/stats/quick/')
        request.tenant = self.mock_tenant
        request.user = self.mock_user

        mock_student_service.return_value.count.return_value = 100
        mock_academic_service.return_value.count_batches.return_value = 10
        mock_attendance_service.return_value.get_daily_attendance_summary.return_value = {
            'present_count': 80,
            'absent_count': 20,
        }

        response = quick_stats_api(request)

        self.assertEqual(response.status_code, 200)
        mock_student_service.assert_called_once_with(self.mock_tenant)
    
    def test_quick_stats_api_handles_no_tenant(self):
        """Test that API gracefully handles missing tenant"""
        request = self.factory.get('/api/stats/quick/')
        request.tenant = None
        request.user = self.mock_user
        
        response = quick_stats_api(request)
        
        self.assertEqual(response.status_code, 400)
        # Should return JSON error response
        self.assertIn('error', json.loads(response.content))
    
    @patch('core.views.AttendanceService')
    @patch('core.views.ReportingService')
    def test_quick_stats_api_handles_service_exceptions(self, mock_reporting_service, mock_attendance_service):
        """Test that API handles service exceptions gracefully"""
        request = self.factory.get('/api/stats/quick/')
        request.tenant = self.mock_tenant
        request.user = self.mock_user
        
        # Mock ReportingService to raise an exception
        mock_reporting_service.side_effect = Exception("Service initialization failed")
        
        response = quick_stats_api(request)
        
        # Should handle the exception gracefully
        self.assertEqual(response.status_code, 400)