from typing import Dict, Any
from datetime import date, datetime
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from core.models import Course, Batch, Subject, ElectiveGroup, Employee
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException,
    BusinessLogicException
)
from .logging_service import ServiceLogger, logged_operation


class AcademicService(TenantAwareService[Course]):    
    def __init__(self, tenant):
        super().__init__(Course, tenant)
        self.logger = ServiceLogger('academic', tenant)

    @logged_operation(action='create', resource_type='course', log_result=True)
    def create_course(
        self,
        course_name: str,
        code: str,
        section_name: str = None,
        grading_type: str = None,
        max_hours_day: int = None,
        max_hours_week: int = None,
        user=None,
        **additional_data
    ) -> Course:
        if self.exists(code=code):
            raise DuplicateException(
                f"Course with code '{code}' already exists",
                details={"code": code}
            )

        course_data = {
            "course_name": course_name,
            "code": code,
            "section_name": section_name,
            "grading_type": grading_type,
            "max_hours_day": max_hours_day,
            "max_hours_week": max_hours_week,
            **additional_data
        }

        course = self.create(**course_data)

        self.logger.log_create(
            resource_type='course',
            resource_id=str(course.id),
            user=user,
            details={
                'course_name': course_name,
                'code': code,
                'section_name': section_name,
                'grading_type': grading_type
            }
        )

        return course

    def get_course_by_code(self, code: str) -> Course:
        course = self.get_or_none(code=code, is_deleted=False)
        if course is None:
            raise NotFoundException(
                f"Course with code '{code}' not found",
                details={"code": code}
            )
        return course

    def get_active_courses(self) -> QuerySet[Course]:
        return self.filter(is_deleted=False)

    def archive_course(self, course_id: str) -> Course:
        if self._has_active_batches(course_id):
            raise BusinessLogicException(
                "Cannot archive course with active batches",
                details={"course_id": course_id}
            )

        return self.update(course_id, is_deleted=True)

    def _has_active_batches(self, course_id: str) -> bool:
        return Batch.objects.filter(
            course_id=course_id, tenant=self.tenant, is_active=True, is_deleted=False
        ).exists()

    @logged_operation(action='create', resource_type='batch', log_result=True)
    @transaction.atomic
    def create_batch(
        self,
        name: str,
        course_id: str,
        start_date: datetime,
        end_date: datetime,
        employee_id: str = None,
        grading_type: str = None,
        user=None,
        **additional_data
    ) -> Batch:
        course = self.get_by_id(course_id)

        if start_date >= end_date:
            raise ValidationException(
                "Batch start date must be before end date",
                details={"start_date": start_date, "end_date": end_date}
            )

        employee = None
        if employee_id:
            employee = self._get_employee_by_id(employee_id)

        overlapping = Batch.objects.filter(
            course=course,
            name=name,
            tenant=self.tenant,
            is_deleted=False
        ).filter(
            Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
        )

        if overlapping.exists():
            raise BusinessLogicException(
                f"Batch '{name}' overlaps with existing batch for this course",
                details={"name": name, "course_id": course_id}
            )

        # Handle academic year if provided
        academic_year = None
        if 'academic_year_id' in additional_data:
            from ..models import AcademicYear
            try:
                academic_year = AcademicYear.objects.get(
                    id=additional_data.pop('academic_year_id'),
                    tenant=self.tenant,
                    is_active=True
                )
            except AcademicYear.DoesNotExist:
                raise ValidationException(
                    "Academic year not found",
                    details={"academic_year_id": additional_data.get('academic_year_id')}
                )

        batch_data = {
            "name": name,
            "course": course,
            "academic_year": academic_year,
            "start_date": start_date,
            "end_date": end_date,
            "employee": employee,
            "grading_type": grading_type or course.grading_type,
            "tenant": self.tenant,
            **additional_data
        }

        batch = Batch.objects.create(**batch_data)

        self.logger.log_create(
            resource_type='batch',
            resource_id=str(batch.id),
            user=user,
            details={
                'name': name,
                'course': course.course_name,
                'start_date': str(start_date.date()),
                'end_date': str(end_date.date()),
                'employee': employee.first_name + ' ' + employee.last_name if employee else None
            }
        )

        return batch

    @logged_operation(action='update', resource_type='batch', log_result=True)
    @transaction.atomic
    def update_batch(self, batch_id: str, user=None, **fields) -> Batch:
        """
        Update an existing batch. Accepts both id-style keys (``course_id``,
        ``employee_id``, ``academic_year_id``) and resolved model instances
        (``course``, ``employee``) so it can be driven by either the DRF
        serializer or plain view code.
        """
        batch = self.get_batch_by_id(batch_id)

        # Resolve related objects (may arrive as instances or ids)
        if 'course' in fields:
            course = fields.pop('course')
            batch.course = course if isinstance(course, Course) else self.get_by_id(str(course))
        if 'course_id' in fields:
            batch.course = self.get_by_id(str(fields.pop('course_id')))

        if 'employee' in fields:
            employee = fields.pop('employee')
            batch.employee = (
                employee if (employee is None or isinstance(employee, Employee))
                else self._get_employee_by_id(str(employee))
            )
        if 'employee_id' in fields:
            emp_id = fields.pop('employee_id')
            batch.employee = self._get_employee_by_id(str(emp_id)) if emp_id else None

        if 'academic_year_id' in fields:
            from ..models import AcademicYear
            ay_id = fields.pop('academic_year_id')
            if ay_id:
                try:
                    batch.academic_year = AcademicYear.objects.get(id=ay_id, tenant=self.tenant)
                except AcademicYear.DoesNotExist:
                    raise ValidationException(
                        "Academic year not found",
                        details={"academic_year_id": ay_id}
                    )

        # Scalar fields
        for field in ('name', 'start_date', 'end_date', 'is_active', 'grading_type'):
            if field in fields:
                setattr(batch, field, fields.pop(field))

        if batch.start_date and batch.end_date and batch.start_date >= batch.end_date:
            raise ValidationException(
                "Batch start date must be before end date",
                details={"start_date": batch.start_date, "end_date": batch.end_date}
            )

        overlapping = Batch.objects.filter(
            course=batch.course,
            name=batch.name,
            tenant=self.tenant,
            is_deleted=False
        ).filter(
            Q(start_date__lte=batch.end_date) & Q(end_date__gte=batch.start_date)
        ).exclude(id=batch.id)

        if overlapping.exists():
            raise BusinessLogicException(
                f"Batch '{batch.name}' overlaps with existing batch for this course",
                details={"name": batch.name, "course_id": str(batch.course.id)}
            )

        batch.save()

        self.logger.log_update(
            resource_type='batch',
            resource_id=str(batch.id),
            user=user,
            changed_fields={'name': batch.name}
        )

        return batch

    @logged_operation(action='update', resource_type='batch', log_result=True)
    @transaction.atomic
    def set_class_teachers(self, batch_id: str, employee_ids: list, user=None) -> Batch:
        """
        Replace the set of class teachers for a batch. The legacy single
        `employee` field is kept in sync with the first teacher (or cleared)
        so existing reads of `batch.employee` stay meaningful.
        """
        batch = self.get_batch_by_id(batch_id)

        employees = []
        for emp_id in (employee_ids or []):
            if emp_id:
                employees.append(self._get_employee_by_id(str(emp_id)))

        batch.class_teachers.set(employees)
        batch.employee = employees[0] if employees else None
        batch.save(update_fields=['employee'])

        self.logger.log_update(
            resource_type='batch',
            resource_id=str(batch.id),
            user=user,
            changed_fields={'class_teachers': [str(e.id) for e in employees]}
        )

        return batch

    def get_batch_by_id(self, batch_id: str) -> Batch:
        try:
            return Batch.objects.get(
                id=batch_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except Batch.DoesNotExist:
            raise NotFoundException(
                f"Batch with id {batch_id} not found",
                details={"batch_id": batch_id}
            )

    def get_batches_by_course(self, course_id: str, active_only: bool = True) -> QuerySet[Batch]:
        query = Q(course_id=course_id, tenant=self.tenant, is_deleted=False)

        if active_only:
            query &= Q(is_active=True)

        return Batch.objects.filter(query)

    def get_current_batches(self, reference_date: date = None) -> QuerySet[Batch]:
        if reference_date is None:
            reference_date = timezone.now().date()

        return Batch.objects.filter(
            tenant=self.tenant,
            is_active=True,
            is_deleted=False,
            start_date__lte=reference_date,
            end_date__gte=reference_date
        )

    @transaction.atomic
    def close_batch(self, batch_id: str, reason: str = None) -> Batch:
        batch = self.get_batch_by_id(batch_id)
        batch.is_active = False
        batch.save()

        Subject.objects.filter(
            batch=batch,
            tenant=self.tenant
        ).update(is_deleted=True)

        return batch

    @transaction.atomic
    def create_subject(
        self,
        name: str,
        code: str,
        batch_id: str,
        no_exams: bool = False,
        max_weekly_classes: int = None,
        elective_group_id: str = None,
        language: bool = False,
        credit_hours: float = None,
        prefer_consecutive: bool = False,
        amount: float = None,
        **additional_data
    ) -> Subject:
        batch = self.get_batch_by_id(batch_id)

        if Subject.objects.filter(
            name__iexact=name,
            batch=batch,
            tenant=self.tenant,
            is_deleted=False
        ).exists():
            raise DuplicateException(
                f"Subject with name '{name}' already exists in batch '{batch.name}'",
                details={"name": name, "batch_id": batch_id}
            )

        if Subject.objects.filter(
            code__iexact=code,
            batch=batch,
            tenant=self.tenant,
            is_deleted=False
        ).exists():
            raise DuplicateException(
                f"Subject with code '{code}' already exists in batch '{batch.name}'",
                details={"code": code, "batch_id": batch_id}
            )

        elective_group = None
        if elective_group_id:
            elective_group = self._get_elective_group_by_id(elective_group_id)
            if elective_group.batch != batch:
                raise ValidationException(
                    "Elective group must belong to the same batch",
                    details={"elective_group_id": elective_group_id, "batch_id": batch_id}
                )

        subject_data = {
            "name": name,
            "code": code,
            "batch": batch,
            "no_exams": no_exams,
            "max_weekly_classes": max_weekly_classes,
            "elective_group": elective_group,
            "language": language,
            "credit_hours": credit_hours,
            "prefer_consecutive": prefer_consecutive,
            "amount": amount,
            "tenant": self.tenant,
            **additional_data
        }

        subject = Subject.objects.create(**subject_data)
        return subject

    def get_subject_by_id(self, subject_id: str) -> Subject:
        try:
            return Subject.objects.get(
                id=subject_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except Subject.DoesNotExist:
            raise NotFoundException(
                f"Subject with id {subject_id} not found",
                details={"subject_id": subject_id}
            )

    @logged_operation(action='update', resource_type='subject', log_result=True)
    @transaction.atomic
    def update_subject(self, subject_id: str, user=None, **fields) -> Subject:
        """Update a subject (name, code, assigned teacher, etc.)."""
        subject = self.get_subject_by_id(subject_id)

        if 'batch' in fields:
            batch = fields.pop('batch')
            subject.batch = batch if isinstance(batch, Batch) else self.get_batch_by_id(str(batch))
        if 'batch_id' in fields:
            subject.batch = self.get_batch_by_id(str(fields.pop('batch_id')))

        if 'employee' in fields:
            employee = fields.pop('employee')
            subject.employee = (
                employee if (employee is None or isinstance(employee, Employee))
                else self._get_employee_by_id(str(employee))
            )
        if 'employee_id' in fields:
            emp_id = fields.pop('employee_id')
            subject.employee = self._get_employee_by_id(str(emp_id)) if emp_id else None

        if 'name' in fields:
            new_name = fields.pop('name')
            if Subject.objects.filter(
                name__iexact=new_name,
                batch=subject.batch,
                tenant=self.tenant,
                is_deleted=False
            ).exclude(id=subject.id).exists():
                raise DuplicateException(
                    f"Subject with name '{new_name}' already exists in batch '{subject.batch.name}'",
                    details={"name": new_name}
                )
            subject.name = new_name

        if 'code' in fields:
            new_code = fields.pop('code')
            if Subject.objects.filter(
                code__iexact=new_code,
                batch=subject.batch,
                tenant=self.tenant,
                is_deleted=False
            ).exclude(id=subject.id).exists():
                raise DuplicateException(
                    f"Subject with code '{new_code}' already exists in batch '{subject.batch.name}'",
                    details={"code": new_code}
                )
            subject.code = new_code

        for field in ('no_exams', 'max_weekly_classes', 'language',
                      'credit_hours', 'prefer_consecutive', 'amount'):
            if field in fields:
                setattr(subject, field, fields.pop(field))

        subject.save()

        self.logger.log_update(
            resource_type='subject',
            resource_id=str(subject.id),
            user=user
        )

        return subject

    @logged_operation(action='assign_subjects', resource_type='employee', log_result=True)
    @transaction.atomic
    def assign_subjects_to_employee(self, employee_id: str, subject_ids: list, user=None) -> QuerySet[Subject]:
        """Bulk-set which subjects (across all batches) this employee teaches.

        Subject.employee is a single FK per subject-row, so "assign an
        employee to one or more subjects" is just bulk-setting that FK for
        the selected subjects and clearing it for any subject previously
        assigned to this employee that got deselected. Scoped strictly to
        this employee — never touches subjects assigned to other teachers.
        """
        employee = self._get_employee_by_id(str(employee_id))
        subject_ids = [str(sid) for sid in subject_ids]

        Subject.objects.filter(
            tenant=self.tenant, is_deleted=False, id__in=subject_ids
        ).update(employee=employee)

        Subject.objects.filter(
            tenant=self.tenant, is_deleted=False, employee=employee
        ).exclude(id__in=subject_ids).update(employee=None)

        return Subject.objects.filter(tenant=self.tenant, is_deleted=False, employee=employee)

    def get_subjects_by_batch(self, batch_id: str, active_only: bool = True) -> QuerySet[Subject]:
        query = Q(batch_id=batch_id, tenant=self.tenant)

        if active_only:
            query &= Q(is_deleted=False)

        return Subject.objects.filter(query)

    def get_elective_subjects(self, batch_id: str) -> QuerySet[Subject]:
        return Subject.objects.filter(
            batch_id=batch_id,
            tenant=self.tenant,
            is_deleted=False,
            elective_group__isnull=False
        )

    def get_mandatory_subjects(self, batch_id: str) -> QuerySet[Subject]:
        return Subject.objects.filter(
            batch_id=batch_id,
            tenant=self.tenant,
            is_deleted=False,
            elective_group__isnull=True
        )

    @transaction.atomic
    def create_elective_group(
        self,
        name: str,
        batch_id: str,
        **additional_data
    ) -> ElectiveGroup:
        batch = self.get_batch_by_id(batch_id)

        if ElectiveGroup.objects.filter(
            name=name,
            batch=batch,
            tenant=self.tenant,
            is_deleted=False
        ).exists():
            raise DuplicateException(
                f"Elective group '{name}' already exists in batch '{batch.name}'",
                details={"name": name, "batch_id": batch_id}
            )

        elective_group_data = {
            "name": name,
            "batch": batch,
            "tenant": self.tenant,
            **additional_data
        }

        elective_group = ElectiveGroup.objects.create(**elective_group_data)
        return elective_group

    def _get_elective_group_by_id(self, elective_group_id: str) -> ElectiveGroup:
        try:
            return ElectiveGroup.objects.get(
                id=elective_group_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except ElectiveGroup.DoesNotExist:
            raise NotFoundException(
                f"Elective group with id {elective_group_id} not found",
                details={"elective_group_id": elective_group_id}
            )

    def _get_employee_by_id(self, employee_id: str) -> Employee:
        try:
            return Employee.objects.get(
                id=employee_id,
                tenant=self.tenant,
                status=True
            )
        except Employee.DoesNotExist:
            raise NotFoundException(
                f"Employee with id {employee_id} not found",
                details={"employee_id": employee_id}
            )

    def get_academic_statistics(self) -> Dict[str, Any]:
        stats = {}

        stats['total_courses'] = self.count(is_deleted=False)
        stats['active_courses'] = self.count(is_deleted=False)

        total_batches = Batch.objects.filter(
            tenant=self.tenant,
            is_deleted=False
        ).count()

        active_batches = Batch.objects.filter(
            tenant=self.tenant,
            is_active=True,
            is_deleted=False
        ).count()

        stats['total_batches'] = total_batches
        stats['active_batches'] = active_batches

        total_subjects = Subject.objects.filter(
            tenant=self.tenant,
            is_deleted=False
        ).count()

        elective_subjects = Subject.objects.filter(
            tenant=self.tenant,
            is_deleted=False,
            elective_group__isnull=False
        ).count()

        stats['total_subjects'] = total_subjects
        stats['mandatory_subjects'] = total_subjects - elective_subjects
        stats['elective_subjects'] = elective_subjects

        return stats

    def count_batches(self, active_only: bool = True) -> int:
        """Count batches, optionally filtering for active ones only."""
        query = Q(tenant=self.tenant, is_deleted=False)
        if active_only:
            query &= Q(is_active=True)
        return Batch.objects.filter(query).count()

    def get_active_batches(self) -> QuerySet[Batch]:
        """Get all active batches from the active academic year."""
        active_year = self.get_active_academic_year()
        if not active_year:
            return Batch.objects.none()

        return Batch.objects.filter(
            tenant=self.tenant,
            is_active=True,
            is_deleted=False,
            academic_year=active_year
        ).select_related('course', 'employee')

    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        super()._validate_create_data(data)

        required_fields = ['course_name', 'code']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationException(
                    f"Required field '{field}' is missing or empty",
                    details={"field": field}
                )

        max_hours_day = data.get('max_hours_day')
        max_hours_week = data.get('max_hours_week')

        if max_hours_day is not None and max_hours_day <= 0:
            raise ValidationException(
                "Maximum hours per day must be positive",
                details={"max_hours_day": max_hours_day}
            )

        if max_hours_week is not None and max_hours_week <= 0:
            raise ValidationException(
                "Maximum hours per week must be positive",
                details={"max_hours_week": max_hours_week}
            )

        if (max_hours_day is not None and max_hours_week is not None and
            max_hours_day * 7 < max_hours_week):
            raise ValidationException(
                "Weekly hours cannot exceed daily hours × 7",
                details={"max_hours_day": max_hours_day, "max_hours_week": max_hours_week}
            )

    def count_batches(self, active_only: bool = False) -> int:
        """Count batches"""
        if active_only:
            return Batch.objects.filter(tenant=self.tenant, is_active=True, is_deleted=False).count()
        return Batch.objects.filter(tenant=self.tenant, is_deleted=False).count()

    def count_courses(self) -> int:
        """Count courses"""
        return self.count(is_deleted=False)

    def get_academic_stats(self) -> Dict[str, Any]:
        """Get academic statistics"""
        from core.models import Batch, Subject

        return {
            "total_courses": self.count_courses(),
            "total_batches": self.count_batches(),
            "active_batches": self.count_batches(active_only=True),
            "total_subjects": Subject.objects.filter(
                tenant=self.tenant, 
                is_deleted=False
            ).count()
        }

    def get_batch_performance_summary(self) -> Dict[str, Any]:
        """Get batch performance summary - placeholder for future implementation"""
        return {
            "total_batches": self.count_batches(active_only=True),
            "performance_data": "Not implemented yet"
        }

    def get_subject_performance_summary(self) -> Dict[str, Any]:
        """Get subject performance summary - placeholder for future implementation"""
        return {
            "total_subjects": Subject.objects.filter(
                tenant=self.tenant, 
                is_deleted=False
            ).count(),
            "performance_data": "Not implemented yet"
        }

    def get_active_academic_year(self):
        """Get the currently active academic year"""
        from core.models import AcademicYear
        return AcademicYear.objects.filter(
            tenant=self.tenant, 
            is_active=True
        ).first()

    def get_active_batches_deprecated(self):
        """Deprecated: Use the first get_active_batches method instead"""
        from core.models import Batch
        return Batch.objects.filter(
            tenant=self.tenant,
            is_active=True,
            is_deleted=False
        )

    def get_all_batches(self):
        """Get all batches including inactive ones"""
        from core.models import Batch
        from django.db.models import Count, Q
        return Batch.objects.filter(
            tenant=self.tenant, 
            is_deleted=False
        ).select_related('course', 'employee').annotate(
            student_count=Count('batch_students', filter=Q(batch_students__is_active=True))
        )

    def search_batches(self, query: str):
        """Search batches by name or course"""
        from django.db.models import Q
        batches = self.get_all_batches()
        if query:
            batches = batches.filter(
                Q(name__icontains=query) |
                Q(course__course_name__icontains=query)
            )
        return batches

    def get_all_subjects(self):
        """Get all subjects"""
        from core.models import Subject
        return Subject.objects.filter(tenant=self.tenant, is_deleted=False)

    def search_subjects(self, query: str = None, batch_id: str = None):
        """Search subjects with filters"""
        from django.db.models import Q
        queryset = self.get_all_subjects()

        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(code__icontains=query) |
                Q(batch__name__icontains=query)
            )

        return queryset.select_related('batch', 'elective_group')

    def get_all_academic_years(self):
        """Get all academic years"""
        from core.models import AcademicYear
        return AcademicYear.objects.filter(tenant=self.tenant)

    def get_active_courses(self):
        """Get all active courses"""
        return self.filter(is_deleted=False).prefetch_related('batches')

    def search_courses(self, query: str):
        """Search courses by name or code"""
        from django.db.models import Q
        courses = self.get_active_courses()
        if query:
            courses = courses.filter(
                Q(course_name__icontains=query) |
                Q(code__icontains=query)
            )
        return courses

    def get_all_courses(self):
        """Get all courses (for compatibility)"""
        return self.get_active_courses()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def generate_course_summary(self) -> Dict[str, Any]:
        """Per-course batch counts for the academic 'course_summary' report."""
        courses = Course.objects.filter(tenant=self.tenant, is_deleted=False)
        rows = []
        for course in courses:
            batches = Batch.objects.filter(tenant=self.tenant, course=course)
            rows.append({
                "course_id": str(course.id),
                "course_name": course.course_name,
                "code": course.code,
                "batch_count": batches.count(),
                "active_batch_count": batches.filter(is_active=True).count(),
            })
        return {
            "report_type": "course_summary",
            "total_courses": courses.count(),
            "courses": rows,
        }

    def generate_batch_enrollment_report(self, course_id: str) -> Dict[str, Any]:
        """Per-batch active enrolment counts for a single course."""
        from core.models import BatchStudent

        try:
            course = Course.objects.get(id=course_id, tenant=self.tenant)
        except Course.DoesNotExist:
            raise NotFoundException(
                f"Course with id {course_id} not found",
                details={"course_id": course_id},
            )

        batches = Batch.objects.filter(tenant=self.tenant, course=course)
        rows = [
            {
                "batch_id": str(batch.id),
                "batch_name": batch.name,
                "enrolled_students": BatchStudent.objects.filter(
                    tenant=self.tenant, batch=batch, is_active=True
                ).count(),
            }
            for batch in batches
        ]
        return {
            "report_type": "batch_enrollment",
            "course_id": str(course.id),
            "course_name": course.course_name,
            "total_batches": batches.count(),
            "batches": rows,
        }

    def generate_subject_distribution_report(self) -> Dict[str, Any]:
        """Count of subjects grouped by batch."""
        subjects = Subject.objects.filter(
            tenant=self.tenant, is_deleted=False
        ).select_related("batch")
        distribution: Dict[str, int] = {}
        for subject in subjects:
            batch_name = subject.batch.name if subject.batch else "Unassigned"
            distribution[batch_name] = distribution.get(batch_name, 0) + 1
        return {
            "report_type": "subject_distribution",
            "total_subjects": subjects.count(),
            "distribution_by_batch": distribution,
        }
