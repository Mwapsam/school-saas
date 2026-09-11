from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone

from .base import TenantAwareService
from .student_service import StudentService
from .employee_service import EmployeeService
from .academic_service import AcademicService
from .finance_service import FinanceService
from .exceptions import ServiceException
from .logging_service import ServiceLogger, logged_operation


class ReportingService(TenantAwareService):
    """Black box service for all reporting and analytics operations"""
    
    def __init__(self, tenant):
        # ReportingService doesn't manage a specific model, so we pass None
        super().__init__(None, tenant)
        self.logger = ServiceLogger('reporting', tenant)
        
        # Initialize domain services
        self.student_service = StudentService(tenant)
        self.employee_service = EmployeeService(tenant)
        self.academic_service = AcademicService(tenant)
        self.finance_service = FinanceService(tenant)
    
    @logged_operation(action='generate', resource_type='dashboard_stats')
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        try:
            # Get stats from each domain service
            student_stats = self.student_service.get_student_stats()
            employee_stats = self.employee_service.get_employee_stats()
            academic_stats = self.academic_service.get_academic_stats()
            
            return {
                "students": {
                    "total_active": student_stats.get("total_active", 0),
                    "total_inactive": student_stats.get("total_inactive", 0),
                    "recent_admissions": student_stats.get("recent_students", [])[:5]
                },
                "employees": {
                    "total_active": employee_stats.get("total_active", 0),
                    "total_inactive": employee_stats.get("total_inactive", 0),
                    "by_department": employee_stats.get("by_department", {})
                },
                "academic": {
                    "total_courses": academic_stats.get("total_courses", 0),
                    "total_batches": academic_stats.get("total_batches", 0),
                    "active_batches": academic_stats.get("active_batches", 0)
                },
                "summary": {
                    "last_updated": timezone.now().isoformat(),
                    "tenant": self.tenant.name if hasattr(self.tenant, 'name') else str(self.tenant)
                }
            }
        except Exception as e:
            # Fallback stats if any service fails
            self.logger.error(f"Failed to get dashboard stats: {str(e)}")
            return {
                "students": {"total_active": 0, "total_inactive": 0, "recent_admissions": []},
                "employees": {"total_active": 0, "total_inactive": 0, "by_department": {}},
                "academic": {"total_courses": 0, "total_batches": 0, "active_batches": 0},
                "summary": {"last_updated": timezone.now().isoformat(), "error": "Stats unavailable"}
            }
    
    @logged_operation(action='generate', resource_type='quick_stats')
    def get_quick_stats(self) -> Dict[str, int]:
        """Get quick overview statistics"""
        return {
            "total_students": self.student_service.count_active_students(),
            "total_employees": self.employee_service.count_active_employees(),
            "total_batches": self.academic_service.count_batches(active_only=True),
            "total_courses": self.academic_service.count_courses()
        }
    
    def get_enrollment_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get student enrollment trends over time"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get daily enrollment data
        enrollments = (
            self.student_service
            .filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
            .extra(select={'date': 'date(created_at)'})
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        return {
            "period": {"start": start_date, "end": end_date, "days": days},
            "data": list(enrollments),
            "total": sum(item['count'] for item in enrollments)
        }
    
    def get_academic_performance_summary(self) -> Dict[str, Any]:
        """Get academic performance summary across all batches"""
        try:
            return {
                "batch_performance": self.academic_service.get_batch_performance_summary(),
                "subject_performance": self.academic_service.get_subject_performance_summary(),
                "attendance_summary": self.get_attendance_summary()
            }
        except Exception as e:
            self.logger.error(f"Failed to get academic performance summary: {str(e)}")
            return {"error": "Academic performance data unavailable"}
    
    def get_attendance_summary(self) -> Dict[str, Any]:
        """Get attendance summary statistics"""
        # This would typically use an AttendanceService
        # For now, return a placeholder structure
        return {
            "overall_rate": 0,
            "by_batch": {},
            "trend": "stable"
        }
    
    def get_financial_overview(self) -> Dict[str, Any]:
        """Get financial overview from finance service"""
        try:
            return self.finance_service.get_financial_overview()
        except Exception as e:
            self.logger.error(f"Failed to get financial overview: {str(e)}")
            return {"error": "Financial data unavailable"}
    
    def generate_monthly_report(self, year: int, month: int) -> Dict[str, Any]:
        """Generate comprehensive monthly report"""
        return {
            "period": {"year": year, "month": month},
            "students": self.student_service.get_monthly_student_report(year, month),
            "employees": self.employee_service.get_employee_stats(),
            "academic": self.academic_service.get_academic_stats(),
            "generated_at": timezone.now().isoformat()
        }
    
    def export_data(self, data_type: str, format: str = 'json') -> Dict[str, Any]:
        """Export data in various formats"""
        if data_type == 'dashboard':
            data = self.get_dashboard_stats()
        elif data_type == 'students':
            data = self.student_service.get_student_stats()
        elif data_type == 'employees':
            data = self.employee_service.get_employee_stats()
        else:
            raise ServiceException(f"Unknown data type: {data_type}")
        
        return {
            "data": data,
            "format": format,
            "exported_at": timezone.now().isoformat(),
            "tenant": str(self.tenant)
        }