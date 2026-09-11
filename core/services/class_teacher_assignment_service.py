import logging
from typing import Optional, List, Dict, Set
from django.db import transaction
from django.utils import timezone

from core.models import ClassTeacherAssignment, Batch, Employee, Student, BatchStudent
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    BusinessLogicException
)
from .logging_service import ServiceLogger, logged_operation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ClassTeacherAssignmentService(TenantAwareService[ClassTeacherAssignment]):
    """Service for managing per-student class teacher assignments within batches.

    Handles:
    - Single and bulk student-to-teacher assignments
    - Validation against the batch's teacher pool
    - Soft-deactivation pattern for reassignments (historical preservation)
    - Sole-teacher fallback for single-teacher batches
    - Per-teacher student roster narrowing
    """

    def __init__(self, tenant=None):
        super().__init__(ClassTeacherAssignment, tenant)
        self.logger = ServiceLogger('class_teacher_assignment', tenant)

    @transaction.atomic
    @logged_operation('assign_class_teacher')
    def assign(
        self,
        student_id: str,
        batch_id: str,
        employee_id: str,
        *,
        user=None,
        reason: str = ""
    ) -> ClassTeacherAssignment:
        """Assign a student to a class teacher within a batch.

        Validates that employee_id is in the batch's teacher pool
        (batch.employee or batch.class_teachers). Deactivates any prior active
        assignment for (student, batch) and creates a new one. No-op if the
        prior active row already points at the same employee.

        Args:
            student_id: UUID of the student
            batch_id: UUID of the batch
            employee_id: UUID of the teacher
            user: User performing the assignment (for audit trail)
            reason: Reason for the assignment (e.g., "admin reassignment", "backfill:auto")

        Returns:
            The newly created ClassTeacherAssignment

        Raises:
            ValidationException: If employee is not in batch's teacher pool
            NotFoundException: If student, batch, or employee not found
        """
        # Fetch and validate batch
        try:
            batch = Batch.objects.get(id=batch_id, tenant=self.tenant)
        except Batch.DoesNotExist:
            raise NotFoundException(f"Batch {batch_id} not found")

        # Fetch and validate employee
        try:
            employee = Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {employee_id} not found")

        # Fetch and validate student
        try:
            student = Student.objects.get(id=student_id, tenant=self.tenant)
        except Student.DoesNotExist:
            raise NotFoundException(f"Student {student_id} not found")

        # Validate employee is in batch's teacher pool
        is_primary = batch.employee_id and str(batch.employee_id) == str(employee_id)
        is_in_pool = batch.class_teachers.filter(id=employee_id).exists()

        if not (is_primary or is_in_pool):
            raise ValidationException(
                f"Employee {employee.full_name} is not a class teacher for batch {batch.name}",
                details={"batch_id": str(batch_id), "employee_id": str(employee_id)}
            )

        # Check for existing active assignment
        existing = ClassTeacherAssignment.objects.filter(
            tenant=self.tenant,
            student_id=student_id,
            batch_id=batch_id,
            is_active=True
        ).first()

        # No-op if already assigned to the same employee
        if existing and str(existing.employee_id) == str(employee_id):
            self.logger.info(f"Assignment unchanged: {student} → {employee} in {batch}")
            return existing

        # Deactivate prior assignment if it exists
        if existing:
            existing.is_active = False
            existing.deactivated_at = timezone.now()
            existing.deactivated_by = user
            existing.save(update_fields=['is_active', 'deactivated_at', 'deactivated_by', 'updated_at'])
            self.logger.info(f"Deactivated prior assignment: {existing}")

        # Create new assignment
        new_assignment = ClassTeacherAssignment.objects.create(
            tenant=self.tenant,
            student_id=student_id,
            batch_id=batch_id,
            employee_id=employee_id,
            academic_year=batch.academic_year,
            is_active=True,
            assigned_by=user,
            reason=reason,
        )

        self.logger.info(
            f"New assignment created: {student} → {employee} in {batch}",
            extra={"assignment_id": str(new_assignment.id), "reason": reason}
        )

        return new_assignment

    @transaction.atomic
    @logged_operation('bulk_assign_class_teachers')
    def bulk_assign(
        self,
        batch_id: str,
        assignments: List[Dict],
        *,
        user=None
    ) -> List[ClassTeacherAssignment]:
        """Bulk assign multiple students to teachers within a batch.

        Args:
            batch_id: UUID of the batch
            assignments: List of dicts: [{"student_id": "...", "employee_id": "..."}, ...]
            user: User performing the assignments

        Returns:
            List of created/updated ClassTeacherAssignment records
        """
        results = []
        for assignment_data in assignments:
            result = self.assign(
                student_id=assignment_data['student_id'],
                batch_id=batch_id,
                employee_id=assignment_data['employee_id'],
                user=user,
                reason=assignment_data.get('reason', '')
            )
            results.append(result)

        self.logger.info(f"Bulk assigned {len(results)} students in batch {batch_id}")
        return results

    @transaction.atomic
    @logged_operation('deactivate_student_assignment')
    def deactivate_all_for_student_in_batch(
        self,
        student_id: str,
        batch_id: str,
        *,
        user=None,
        reason: str = ""
    ) -> int:
        """Deactivate all active assignments for a student in a batch.

        Called by StudentService.transfer_batch when a student leaves a batch,
        ensuring stale assignments don't linger.

        Args:
            student_id: UUID of the student
            batch_id: UUID of the batch
            user: User performing the deactivation
            reason: Reason for deactivation (e.g., "batch transfer")

        Returns:
            Number of rows deactivated
        """
        deactivated_count = ClassTeacherAssignment.objects.filter(
            tenant=self.tenant,
            student_id=student_id,
            batch_id=batch_id,
            is_active=True
        ).update(
            is_active=False,
            deactivated_at=timezone.now(),
            deactivated_by=user,
            reason=reason,
            updated_at=timezone.now()
        )

        if deactivated_count > 0:
            self.logger.info(
                f"Deactivated {deactivated_count} assignments for student {student_id} "
                f"in batch {batch_id}",
                extra={"reason": reason}
            )

        return deactivated_count

    def get_active_assignment(
        self,
        student_id: str,
        batch: Batch
    ) -> Optional[ClassTeacherAssignment]:
        """Get the active assignment for a student in a batch, if any."""
        return ClassTeacherAssignment.objects.filter(
            tenant=self.tenant,
            student_id=student_id,
            batch_id=batch.id,
            is_active=True
        ).first()

    @staticmethod
    def _sole_teacher(batch: Batch) -> Optional[Employee]:
        """The one teacher who covers a single-teacher batch without needing
        explicit per-student assignments, or None if the batch is genuinely
        multi-teacher (or has no teacher at all). A pool of exactly one
        class_teachers member counts even if batch.employee wasn't also set —
        callers must not require both to agree."""
        pool = list(batch.class_teachers.all())
        if len(pool) == 1:
            return pool[0]
        if not pool and batch.employee:
            return batch.employee
        return None

    def get_assigned_employee(
        self,
        student_id: str,
        batch: Batch
    ) -> Optional[Employee]:
        """Resolve the teacher responsible for a student.

        Returns:
        1. The employee from an active assignment, if one exists
        2. The sole batch teacher (see _sole_teacher) if no assignment row
           exists (safety net for newly-enrolled students in single-teacher
           batches that haven't been backfilled yet)
        3. None if genuinely multi-teacher and unassigned

        This fallback pattern ensures single-teacher batches work seamlessly without
        requiring backfill assignments for every student.
        """
        assignment = self.get_active_assignment(student_id, batch)
        if assignment:
            return assignment.employee
        return self._sole_teacher(batch)

    def assigned_student_ids(self, batch: Batch, employee: Employee) -> Set[str]:
        """Get the set of student IDs assigned to an employee in a batch.

        Includes both:
        - Explicitly assigned students (via ClassTeacherAssignment rows)
        - Fallback coverage for newly-enrolled unassigned students in single-teacher
          batches (where employee is the sole batch teacher)

        Returns:
            Set of student ID strings (UUIDs)
        """
        # Get explicitly assigned students
        assigned_ids = set(
            ClassTeacherAssignment.objects
            .filter(
                tenant=self.tenant,
                batch_id=batch.id,
                employee_id=employee.id,
                is_active=True
            )
            .values_list('student_id', flat=True)
        )

        # Add fallback coverage if this is the sole/legacy teacher
        sole_teacher = self._sole_teacher(batch)
        if sole_teacher and sole_teacher.id == employee.id:
            # In single-teacher batches, include all active batch members without
            # an assignment row yet (newly enrolled students awaiting backfill)
            all_active_students = set(
                BatchStudent.objects
                .filter(tenant=self.tenant, batch_id=batch.id, is_active=True)
                .values_list('student_id', flat=True)
            )
            assigned_ids.update(all_active_students)

        return {str(sid) for sid in assigned_ids}

    def batch_assignment_overview(self, batch: Batch) -> List[Dict]:
        """Get a per-student overview of assignments for admin views.

        Returns one row per active BatchStudent, including:
        - Student info
        - Assigned employee (or None if unassigned)
        - ClassTeacherAssignment record (or None)
        - needs_review flag (True if backfill:needs_review)

        Used by the Admin Portal students tab (§4.2) to render the
        assignment overview table.

        Returns:
            List of dicts: [{student, employee, assignment, needs_review}, ...]
        """
        batch_students = BatchStudent.objects.filter(
            tenant=self.tenant,
            batch_id=batch.id,
            is_active=True
        ).select_related('student').order_by(
            'student__first_name', 'student__middle_name', 'student__last_name'
        )

        results = []
        for bs in batch_students:
            assignment = ClassTeacherAssignment.objects.filter(
                tenant=self.tenant,
                student_id=bs.student_id,
                batch_id=batch.id,
                is_active=True
            ).first()

            needs_review = (
                assignment and
                assignment.reason and
                'needs_review' in assignment.reason
            )

            results.append({
                'student': bs.student,
                'employee': assignment.employee if assignment else None,
                'assignment': assignment,
                'needs_review': needs_review,
            })

        return results
