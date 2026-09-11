import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from django.db import transaction
from django.db.models import Q, QuerySet, Count
from django.utils import timezone

from core.models import Student, Batch, BatchStudent, Country, StudentCategory, Guardian, StudentGuardianRelation
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException,
    BusinessLogicException
)
from .logging_service import ServiceLogger, logged_operation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class StudentService(TenantAwareService[Student]):    
    def __init__(self, tenant):
        super().__init__(Student, tenant)
        self.logger = ServiceLogger('student', tenant)
    
    def create_student(
        self,
        admission_no: str,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        gender: str,
        admission_date: date = None,
        middle_name: str = None,
        **additional_data
    ) -> Student:
        if admission_date is None:
            admission_date = date.today()
        
        if self.exists(admission_no=admission_no):
            raise DuplicateException(
                f"Student with admission number '{admission_no}' already exists",
                details={"admission_no": admission_no}
            )
        
        student_data = {
            "admission_no": admission_no,
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": date_of_birth,
            "gender": gender,
            "admission_date": admission_date,
            "middle_name": middle_name,
            **additional_data
        }
        
        return self.create(**student_data)
    
    def get_by_admission_number(self, admission_no: str) -> Student:
        student = self.get_or_none(admission_no=admission_no)
        if student is None:
            raise NotFoundException(
                f"Student with admission number '{admission_no}' not found",
                details={"admission_no": admission_no}
            )
        return student
    
    def update_student(
        self, 
        student_id: str, 
        **update_data
    ) -> Student:
        if 'admission_no' in update_data:
            existing_student = self.get_or_none(admission_no=update_data['admission_no'])
            if existing_student and str(existing_student.id) != str(student_id):
                raise DuplicateException(
                    f"Student with admission number '{update_data['admission_no']}' already exists",
                    details={"admission_no": update_data['admission_no']}
                )
        
        return self.update(student_id, **update_data)
    
    def calculate_age(self, student_id: str, reference_date: date = None) -> int:
        student = self.get_by_id(student_id)
        if reference_date is None:
            reference_date = date.today()
        
        age = reference_date.year - student.date_of_birth.year
        
        if (reference_date.month, reference_date.day) < (
            student.date_of_birth.month, 
            student.date_of_birth.day
        ):
            age -= 1
        
        return age
    
    @transaction.atomic
    def enroll_in_batch(
        self, 
        student_id: str, 
        batch_id: str, 
        roll_number: str = None
    ) -> BatchStudent:
        from .academic_service import AcademicService
        
        student = self.get_by_id(student_id)
        
        academic_service = AcademicService(self.tenant)
        batch = academic_service.get_batch_by_id(batch_id)
        
        existing_enrollment = BatchStudent.objects.filter(
            student=student,
            batch=batch,
            tenant=self.tenant
        ).first()
        
        if existing_enrollment:
            if existing_enrollment.is_active:
                raise DuplicateException(
                    f"Student is already enrolled in batch '{batch.name}'",
                    details={"student_id": student_id, "batch_id": batch_id}
                )
        
        enrollment = BatchStudent.objects.create(
            student=student,
            batch=batch,
            roll_number=roll_number,
            tenant=self.tenant
        )
        
        return enrollment
    
    @transaction.atomic
    def transfer_batch(
        self, 
        student_id: str, 
        from_batch_id: str, 
        to_batch_id: str,
        roll_number: str = None
    ) -> BatchStudent:
        current_enrollment = BatchStudent.objects.filter(
            student_id=student_id,
            batch_id=from_batch_id,
            tenant=self.tenant,
            is_active=True
        ).first()
        
        if not current_enrollment:
            raise NotFoundException(
                "Active enrollment not found for student in specified batch",
                details={"student_id": student_id, "batch_id": from_batch_id}
            )
        
        current_enrollment.is_active = False
        current_enrollment.save()

        # Deactivate class teacher assignments in the old batch
        from .class_teacher_assignment_service import ClassTeacherAssignmentService
        ClassTeacherAssignmentService(self.tenant).deactivate_all_for_student_in_batch(
            student_id, from_batch_id, reason="batch transfer"
        )

        return self.enroll_in_batch(student_id, to_batch_id, roll_number)
    
    def get_students_by_batch(self, batch_id: str, active_only: bool = True) -> QuerySet[Student]:
        # All conditions on the `student_batches` relation must sit in a single
        # .filter() call so they match the SAME enrollment row. Splitting them
        # across calls creates independent joins, which would wrongly keep a
        # student who is inactive in THIS batch but active in another batch.
        link_filters = {
            'student_batches__batch_id': batch_id,
            'student_batches__batch__tenant': self.tenant,
        }
        if active_only:
            link_filters['student_batches__is_active'] = True

        queryset = self.get_base_queryset().filter(**link_filters)

        if active_only:
            queryset = queryset.filter(is_active=True)

        return queryset.distinct()
    
    def get_enrollment_conflicts(self) -> List[Dict[str, Any]]:
        """Find students enrolled in more than one class within the SAME academic year.

        A student may legitimately appear in classes of different academic years
        (their progression history); a conflict is two or more *active* batch
        enrolments sharing one academic year. Returns one entry per
        (student, academic_year) conflict with the competing enrolments.
        """
        # (student, year) pairs that have more than one active enrolment.
        conflict_keys = (
            BatchStudent.objects
            .filter(tenant=self.tenant, is_active=True, student__is_active=True)
            .values('student_id', 'batch__academic_year_id')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
        )
        if not conflict_keys:
            return []

        student_ids = {row['student_id'] for row in conflict_keys}

        # All active enrolments for those students, with the data we need to render.
        links = (
            BatchStudent.objects
            .filter(tenant=self.tenant, is_active=True, student_id__in=student_ids)
            .select_related('student', 'batch', 'batch__course', 'batch__academic_year')
        )

        # Bucket by (student, academic_year); keep only buckets that are conflicts.
        wanted = {(row['student_id'], row['batch__academic_year_id']) for row in conflict_keys}
        buckets: Dict[Any, Dict[str, Any]] = {}
        for link in links:
            key = (link.student_id, link.batch.academic_year_id)
            if key not in wanted:
                continue
            bucket = buckets.get(key)
            if bucket is None:
                bucket = {
                    'student': link.student,
                    'academic_year': link.batch.academic_year,
                    'enrollments': [],
                }
                buckets[key] = bucket
            bucket['enrollments'].append(link)

        results = list(buckets.values())
        results.sort(key=lambda b: (
            b['student'].first_name or '', b['student'].last_name or '',
        ))
        return results

    def get_enrollment_conflict_count(self) -> int:
        """Number of (student, academic_year) enrolment conflicts. Cheap-ish; used
        for notification badges."""
        return (
            BatchStudent.objects
            .filter(tenant=self.tenant, is_active=True, student__is_active=True)
            .values('student_id', 'batch__academic_year_id')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
            .count()
        )

    @transaction.atomic
    def resolve_enrollment_conflict(self, student_id: str, academic_year_id: str,
                                    keep_batch_id: str, user=None) -> int:
        """Resolve a conflict by keeping the chosen class and deactivating the
        student's other active enrolments in the same academic year. Returns the
        number of enrolments deactivated."""
        others = BatchStudent.objects.filter(
            tenant=self.tenant,
            student_id=student_id,
            is_active=True,
            batch__academic_year_id=academic_year_id,
        ).exclude(batch_id=keep_batch_id)

        deactivated = 0
        for link in others:
            link.is_active = False
            link.save(update_fields=['is_active'])
            deactivated += 1
        return deactivated

    def deactivate_student(self, student_id: str, reason: str = None) -> Student:
        update_data = {"is_active": False}
        if reason:
            update_data["status_description"] = reason
        
        return self.update(student_id, **update_data)
    
    def reactivate_student(self, student_id: str) -> Student:
        return self.update(student_id, is_active=True, status_description=None)
    
    def get_active_students(self) -> QuerySet[Student]:
        return self.filter(is_active=True)
    
    def get_inactive_students(self) -> QuerySet[Student]:
        return self.filter(is_active=False)
    
    def search_students(
        self, 
        query: str, 
        active_only: bool = True,
        limit: int = None
    ) -> QuerySet[Student]:
        search_filter = (
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(admission_no__icontains=query)
        )
        
        if active_only:
            search_filter &= Q(is_active=True)
        
        queryset = self.get_base_queryset().filter(search_filter)
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        super()._validate_create_data(data)
        
        required_fields = ['admission_no', 'first_name', 'last_name', 'date_of_birth', 'gender']
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
        
        if data.get('date_of_birth') and data['date_of_birth'] > date.today():
            raise ValidationException(
                "Date of birth cannot be in the future",
                details={"date_of_birth": data['date_of_birth']}
            )
    
    def _validate_update_data(self, instance: Student, data: Dict[str, Any]) -> None:
        super()._validate_update_data(instance, data)
        
        if 'gender' in data:
            valid_genders = ['male', 'female', 'other']
            if data['gender'] not in valid_genders:
                raise ValidationException(
                    f"Invalid gender. Must be one of: {valid_genders}",
                    details={"gender": data['gender'], "valid_choices": valid_genders}
                )
        
        if 'date_of_birth' in data and data['date_of_birth'] and data['date_of_birth'] > date.today():
            raise ValidationException(
                "Date of birth cannot be in the future",
                details={"date_of_birth": data['date_of_birth']}
            )


    @transaction.atomic
    def add_guardian(self, student_id: str, guardian_data: Dict[str, Any]) -> StudentGuardianRelation:
        student = self.get_by_id(student_id)
        guardian = Guardian.objects.create(tenant=self.tenant, **guardian_data)
        relation = StudentGuardianRelation.objects.create(
            student=student,
            guardian=guardian,
            relationship=guardian_data.get('relationship', 'Parent'),
            tenant=self.tenant
        )
        logger.info(f"Added guardian {guardian.id} for student {student.admission_no}")
        return relation

    @logged_operation(action='set_primary_contact', resource_type='guardian', log_result=True)
    @transaction.atomic
    def set_primary_contact(self, student_id: str, guardian_id: str, is_primary: bool) -> Dict[str, Any]:
        """Set or unset a guardian as the primary contact for a student.

        Args:
            student_id: UUID of the student
            guardian_id: UUID of the guardian
            is_primary: True to set as primary, False to unset

        Returns:
            dict with keys:
            - 'was_changed': bool indicating if state changed
            - 'guardian': Guardian instance
            - 'is_primary': the requested is_primary value

        Raises:
            NotFoundException: if student or guardian not found
            BusinessLogicException: if guardian is not linked to student
        """
        student = self.get_by_id(student_id)

        guardian = Guardian.objects.filter(id=guardian_id, tenant=self.tenant).first()
        if guardian is None:
            raise NotFoundException(
                f"Guardian with id {guardian_id} not found",
                details={"guardian_id": guardian_id}
            )

        relation = StudentGuardianRelation.objects.filter(
            tenant=self.tenant, student=student, guardian=guardian
        ).first()

        if relation is None:
            raise BusinessLogicException(
                f"Guardian {guardian_id} is not linked to student {student_id}",
                details={"student_id": student_id, "guardian_id": guardian_id}
            )

        was_changed = False

        if is_primary:
            # Clear immediate_contact flag on all other relations
            StudentGuardianRelation.objects.filter(
                tenant=self.tenant, student=student, is_immediate_contact=True
            ).exclude(id=relation.id).update(is_immediate_contact=False)

            # Set this one as immediate
            if not relation.is_immediate_contact:
                relation.is_immediate_contact = True
                relation.save(update_fields=['is_immediate_contact'])
                was_changed = True

            # Also update the student's immediate_contact pointer
            if student.immediate_contact != guardian:
                student.immediate_contact = guardian
                student.save(update_fields=['immediate_contact'])
                was_changed = True
        else:
            # Only unset if this relation is actually the primary contact
            if relation.is_immediate_contact:
                relation.is_immediate_contact = False
                relation.save(update_fields=['is_immediate_contact'])

                student.immediate_contact = None
                student.save(update_fields=['immediate_contact'])
                was_changed = True

        logger.info(
            f"Updated primary contact for student {student.admission_no}: "
            f"guardian {guardian.id} is_primary={is_primary}, changed={was_changed}"
        )

        return {
            'was_changed': was_changed,
            'guardian': guardian,
            'is_primary': is_primary
        }

    @logged_operation(action='remove_guardian', resource_type='guardian', log_result=True)
    @transaction.atomic
    def remove_guardian(self, student_id: str, guardian_id: str, delete_guardian_record: bool = False) -> Dict[str, Any]:
        """Remove a guardian from a student.

        Args:
            student_id: UUID of the student
            guardian_id: UUID of the guardian to remove
            delete_guardian_record: if True and guardian has no other linked students,
                delete the Guardian record and its linked User

        Returns:
            dict with keys:
            - 'guardian_deleted': bool, True if guardian record was deleted
            - 'has_other_relations': bool, True if guardian still linked to other students
            - 'guardian': Guardian instance

        Raises:
            NotFoundException: if student or guardian not found
            BusinessLogicException: if guardian is not linked to student
            ProtectedError: if guardian has protected foreign key constraints (e.g. invoices)
        """
        from django.db.models import ProtectedError

        student = self.get_by_id(student_id)

        guardian = Guardian.objects.filter(id=guardian_id, tenant=self.tenant).first()
        if guardian is None:
            raise NotFoundException(
                f"Guardian with id {guardian_id} not found",
                details={"guardian_id": guardian_id}
            )

        relation = StudentGuardianRelation.objects.filter(
            tenant=self.tenant, student=student, guardian=guardian
        ).first()

        if relation is None:
            raise BusinessLogicException(
                f"Guardian {guardian_id} is not linked to student {student_id}",
                details={"student_id": student_id, "guardian_id": guardian_id}
            )

        # If this was the immediate contact, clear it before deleting the relation
        if relation.is_immediate_contact:
            student.immediate_contact = None
            student.save(update_fields=['immediate_contact'])

        relation.delete()

        # Check if guardian has any other linked students
        has_other_relations = StudentGuardianRelation.objects.filter(
            tenant=self.tenant, guardian=guardian
        ).exists()

        guardian_deleted = False

        # Optionally delete the guardian if they have no other relations
        if not has_other_relations and delete_guardian_record:
            login_user = guardian.user
            # Both deletions must succeed within same transaction to maintain consistency
            # ProtectedError (e.g. linked invoices) will propagate and trigger rollback
            guardian.delete()
            if login_user is not None:
                # user.delete() is blocked by django-tenant-users unless routed
                # through this helper — see UserService.hard_delete_user_record.
                from .user_service import UserService
                UserService.hard_delete_user_record(login_user)
            guardian_deleted = True
            logger.info(f"Deleted guardian {guardian_id} and linked user (no other relations)")
        else:
            logger.info(f"Removed guardian {guardian_id} from student {student.admission_no}")

        return {
            'guardian_deleted': guardian_deleted,
            'has_other_relations': has_other_relations,
            'guardian': guardian
        }

    def export_emis_report(self, active_only: bool = True) -> str:
        try:
            students = self.get_active_students() if active_only else self.get_base_queryset()
            if not students.exists():
                raise NotFoundException(
                    "No students found for EMIS report",
                    error_code="NO_STUDENTS_FOUND"
                )
            data = [
                {
                    'admission_no': s.admission_no,
                    'first_name': s.first_name,
                    'last_name': s.last_name,
                    'gender': s.gender,
                    'date_of_birth': s.date_of_birth,
                    'batch': s.batch.name if s.batch else ''
                } for s in students
            ]
            # Return CSV data as string (pandas import would be needed for DataFrame)
            csv_data = "admission_no,first_name,last_name,gender,date_of_birth,batch\\n"
            for item in data:
                csv_data += f"{item['admission_no']},{item['first_name']},{item['last_name']},{item['gender']},{item['date_of_birth']},{item['batch']}\\n"
            return csv_data
        except Exception as e:
            raise BusinessLogicException(
                f"Failed to generate EMIS report: {str(e)}",
                error_code="EMIS_EXPORT_ERROR",
                original_exception=e
            )

    @transaction.atomic
    def bulk_create_students(self, students_data: List[Dict[str, Any]], batch_id: Optional[str] = None) -> List[Student]:
        instances = []
        for data in students_data:
            if self.exists(admission_no=data.get('admission_no')):
                raise DuplicateException(
                    f"Student with admission number {data['admission_no']} already exists",
                    error_code="DUPLICATE_ADMISSION_NO",
                    details={"admission_no": data['admission_no']}
                )
            instances.append(self.create(**data))
        if batch_id:
            batch = Batch.objects.get(id=batch_id, tenant=self.tenant)
            # Individual .create() calls (not bulk_create) so the
            # post_save(BatchStudent) signal fires per student — it syncs
            # FinanceFee obligations against already-open fee collections
            # for this batch, which bulk_create silently skips.
            for student in instances:
                BatchStudent.objects.create(student=student, batch=batch, tenant=self.tenant)
        logger.info(f"Bulk created {len(instances)} students for tenant {self.tenant.name}")
        return instances
    
    def get_active_students(self) -> QuerySet[Student]:
        """Get all active students"""
        return self.filter(is_active=True)
    
    def count_active_students(self) -> int:
        """Count active students"""
        return self.count(is_active=True)
    
    def get_student_stats(self) -> Dict[str, Any]:
        """Get comprehensive student statistics"""
        return {
            "total_active": self.count_active_students(),
            "total_inactive": self.count(is_active=False),
            "recent_students": list(
                self.get_active_students()
                .order_by('-created_at')[:10]
                .values('id', 'first_name', 'last_name', 'admission_no', 'created_at')
            ),
            "by_gender": dict(
                self.get_active_students()
                .values('gender')
                .annotate(count=Count('id'))
                .values_list('gender', 'count')
            )
        }
    
    def get_monthly_student_report(self, year: int, month: int) -> Dict[str, Any]:
        """Get monthly student report"""
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month + 1, 1).date()
        
        new_students = self.filter(
            created_at__date__gte=start_date,
            created_at__date__lt=end_date
        ).count()
        
        return {
            "period": {"year": year, "month": month},
            "new_students": new_students,
            "total_active": self.count_active_students()
        }