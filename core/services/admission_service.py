import logging
from typing import Dict, Any
from datetime import date
from django.db import transaction
from django.db.models import Q, QuerySet

from core.models import AdmissionApplication, Course, Student
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException,
    BusinessLogicException
)
from .logging_service import ServiceLogger, logged_operation

logger = logging.getLogger(__name__)


class AdmissionService(TenantAwareService[AdmissionApplication]):
    def __init__(self, tenant):
        super().__init__(AdmissionApplication, tenant)
        self.logger = ServiceLogger('admission', tenant)
    
    def _find_existing_application(
        self,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        guardian_phone: str,
    ) -> AdmissionApplication:
        """
        Locate a prior application for the same applicant so resubmits (double
        click, retry, back-button) don't create a duplicate row. Matching on
        name + DOB + guardian phone keeps siblings with the same name from
        being conflated.
        """
        return self.get_base_queryset().filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name,
            date_of_birth=date_of_birth,
            guardian_phone=guardian_phone,
        ).order_by('-application_date').first()

    @logged_operation(action='create', resource_type='admission_application', log_result=True)
    def create_application(
        self,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        gender: str,
        course_id: str,
        guardian_name: str,
        guardian_phone: str,
        address: str,
        middle_name: str = None,
        guardian_email: str = None,
        user=None,
        **additional_data
    ) -> AdmissionApplication:
        existing = self._find_existing_application(
            first_name, last_name, date_of_birth, guardian_phone
        )
        if existing:
            return existing

        try:
            course = Course.objects.get(id=course_id, tenant=self.tenant, is_deleted=False)
        except Course.DoesNotExist:
            raise NotFoundException(
                f"Course with id {course_id} not found",
                details={"course_id": course_id}
            )

        application_number = self._generate_application_number()
        
        application_data = {
            "application_number": application_number,
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "date_of_birth": date_of_birth,
            "gender": gender,
            "course_applied": course,
            "guardian_name": guardian_name,
            "guardian_phone": guardian_phone,
            "guardian_email": guardian_email,
            "address": address,
            "status": "pending",
            "tenant": self.tenant,
            **additional_data
        }
        
        application = AdmissionApplication.objects.create(**application_data)
        
        self.logger.log_create(
            resource_type='admission_application',
            resource_id=str(application.id),
            user=user,
            details={
                'application_number': application_number,
                'student_name': f"{first_name} {last_name}",
                'course': course.course_name,
                'guardian': guardian_name
            }
        )
        
        return application
    
    def get_application_by_number(self, application_number: str) -> AdmissionApplication:
        try:
            return self.get_base_queryset().get(application_number=application_number)
        except AdmissionApplication.DoesNotExist:
            raise NotFoundException(
                f"Admission application with number '{application_number}' not found",
                details={"application_number": application_number}
            )
    
    def get_pending_applications(self) -> QuerySet[AdmissionApplication]:
        return self.filter(status='pending').order_by('-application_date')
    
    def get_approved_applications(self) -> QuerySet[AdmissionApplication]:
        return self.filter(status='approved').order_by('-application_date')
    
    def get_rejected_applications(self) -> QuerySet[AdmissionApplication]:
        return self.filter(status='rejected').order_by('-application_date')
    
    def get_all(self) -> QuerySet[AdmissionApplication]:
        """Get all admission applications for the tenant"""
        return self.get_base_queryset().select_related('course_applied')
    
    @logged_operation(action='approve', resource_type='admission_application', log_result=True)
    @transaction.atomic
    def approve_application(
        self, 
        application_id: str, 
        admission_no: str = None,
        admission_date: date = None,
        remarks: str = None,
        user=None
    ) -> Dict[str, Any]:
        application = self.get_by_id(application_id)
        
        if application.status != 'pending':
            raise BusinessLogicException(
                f"Cannot approve application with status '{application.status}'",
                details={"current_status": application.status}
            )
        
        if not admission_no:
            admission_no = self._generate_admission_number()
        
        if Student.objects.filter(admission_no=admission_no, tenant=self.tenant).exists():
            raise DuplicateException(
                f"Student with admission number '{admission_no}' already exists",
                details={"admission_no": admission_no}
            )
        
        if not admission_date:
            admission_date = date.today()
        
        from .student_service import StudentService
        student_service = StudentService(self.tenant)
        
        student = student_service.create_student(
            admission_no=admission_no,
            first_name=application.first_name,
            middle_name=application.middle_name,
            last_name=application.last_name,
            date_of_birth=application.date_of_birth,
            gender=application.gender,
            admission_date=admission_date,
            address_line1=application.address,  
            phone1=application.guardian_phone,
            email=application.guardian_email
        )
        
        application.status = 'approved'
        application.remarks = remarks or f"Approved and enrolled as student {admission_no}"
        application.save()
        
        self.logger.log_update(
            resource_type='admission_application',
            resource_id=str(application.id),
            user=user,
            details={
                'action': 'approved',
                'student_id': str(student.id),
                'admission_no': admission_no,
                'remarks': remarks
            }
        )
        
        return {
            'application': application,
            'student': student,
            'admission_no': admission_no
        }
    
    @logged_operation(action='reject', resource_type='admission_application', log_result=True)
    def reject_application(
        self, 
        application_id: str, 
        reason: str,
        user=None
    ) -> AdmissionApplication:
        application = self.get_by_id(application_id)
        
        if application.status != 'pending':
            raise BusinessLogicException(
                f"Cannot reject application with status '{application.status}'",
                details={"current_status": application.status}
            )
        
        application.status = 'rejected'
        application.remarks = reason
        application.save()
        
        self.logger.log_update(
            resource_type='admission_application',
            resource_id=str(application.id),
            user=user,
            details={
                'action': 'rejected',
                'reason': reason
            }
        )
        
        return application
    
    def search_applications(
        self, 
        query: str, 
        status: str = None,
        limit: int = None
    ) -> QuerySet[AdmissionApplication]:
        search_filter = (
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(application_number__icontains=query) |
            Q(guardian_name__icontains=query)
        )
        
        if status:
            search_filter &= Q(status=status)
        
        queryset = self.filter(search_filter).order_by('-application_date')
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    def get_admission_statistics(self) -> Dict[str, Any]:
        stats = {
            'total_applications': self.count(),
            'pending_applications': self.count(status='pending'),
            'approved_applications': self.count(status='approved'),
            'rejected_applications': self.count(status='rejected'),
        }
        
        total = stats['total_applications']
        if total > 0:
            stats['approval_rate'] = round((stats['approved_applications'] / total) * 100, 2)
        else:
            stats['approval_rate'] = 0
        
        return stats
    
    def _generate_application_number(self) -> str:
        year = date.today().year
        base_number = f"APP{year}"
        
        existing = AdmissionApplication.objects.filter(
            tenant=self.tenant,
            application_number__startswith=base_number
        ).count()
        
        return f"{base_number}{existing + 1:04d}"
    
    def _generate_admission_number(self) -> str:
        year = date.today().year
        base_number = f"ADM{year}"
        
        existing = Student.objects.filter(
            tenant=self.tenant,
            admission_no__startswith=base_number
        ).count()
        
        return f"{base_number}{existing + 1:04d}"
    
    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        super()._validate_create_data(data)
        
        required_fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 
                          'course_applied', 'guardian_name', 'guardian_phone', 'address']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationException(
                    f"Required field '{field}' is missing or empty",
                    details={"field": field}
                )
        
        valid_genders = ['male', 'female', 'other']
        if data.get('gender') not in valid_genders:
            raise ValidationException(
                f"Invalid gender. Must be one of: {valid_genders}",
                details={"gender": data.get('gender'), "valid_choices": valid_genders}
            )
        
        if data.get('date_of_birth') and data['date_of_birth'] >= date.today():
            raise ValidationException(
                "Date of birth must be in the past",
                details={"date_of_birth": data['date_of_birth']}
            )

    def generate_admission_report(
        self,
        report_type: str,
        date_from: date = None,
        date_to: date = None,
        status_filter: str = 'all',
    ) -> Dict[str, Any]:
        """Aggregate admission applications for the admission reports endpoint.

        Returns counts by status (optionally filtered by date range / status) for
        the 'applications_summary', 'approval_statistics', 'interview_schedule'
        and 'pending_applications' report types.
        """
        applications = AdmissionApplication.objects.filter(tenant=self.tenant)

        if date_from:
            applications = applications.filter(application_date__gte=date_from)
        if date_to:
            applications = applications.filter(application_date__lte=date_to)
        if status_filter and status_filter != 'all':
            applications = applications.filter(status=status_filter)

        by_status = {
            'pending': applications.filter(status='pending').count(),
            'approved': applications.filter(status='approved').count(),
            'rejected': applications.filter(status='rejected').count(),
        }

        return {
            'report_type': report_type,
            'total_applications': applications.count(),
            'by_status': by_status,
            'date_from': date_from.isoformat() if date_from else None,
            'date_to': date_to.isoformat() if date_to else None,
            'status_filter': status_filter,
        }