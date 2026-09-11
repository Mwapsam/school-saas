"""Tests for ClassTeacherAssignmentService.

Coverage: per-student assignment creation/reassignment, pool validation,
sole-teacher fallback, roster narrowing, soft-deactivation pattern.
"""

import pytest
from django.db import IntegrityError
from django.utils import timezone
from uuid import uuid4

from core.models import (
    ClassTeacherAssignment, Batch, Student, Employee, BatchStudent,
    Course, AcademicYear, User
)
from core.services import ClassTeacherAssignmentService
from core.services.exceptions import ValidationException, NotFoundException


@pytest.fixture
def employee_a(db, school):
    """Create test employee - mirrors conftest pattern."""
    u = User(
        username=f"teacher_a_{uuid4().hex[:6]}",
        email=f"teacher_a_{uuid4().hex[:6]}@test.local",
        first_name="Alice",
        last_name="Teacher",
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    return Employee.objects.create(
        tenant=school,
        employee_number=f"E{uuid4().hex[:6].upper()}",
        joining_date="2020-01-01",
        first_name="Alice",
        last_name="Teacher",
        gender=True,
        is_teaching_staff=True,
        user=u
    )


@pytest.fixture
def employee_b(db, school):
    """Create second test employee."""
    u = User(
        username=f"teacher_b_{uuid4().hex[:6]}",
        email=f"teacher_b_{uuid4().hex[:6]}@test.local",
        first_name="Bob",
        last_name="Teacher",
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    return Employee.objects.create(
        tenant=school,
        employee_number=f"E{uuid4().hex[:6].upper()}",
        joining_date="2020-01-01",
        first_name="Bob",
        last_name="Teacher",
        gender=False,
        is_teaching_staff=True,
        user=u
    )


@pytest.fixture
def svc(school):
    """Create ClassTeacherAssignmentService instance."""
    return ClassTeacherAssignmentService(school)


@pytest.mark.django_db
class TestClassTeacherAssignmentService:
    """ClassTeacherAssignmentService tests."""

    # Tests

    def test_assign_creates_active_assignment(self, svc, batch, employee_a, student):
        """assign() creates an active ClassTeacherAssignment."""
        batch.employee = employee_a
        batch.save()

        assignment = svc.assign(
            str(student.id), str(batch.id), str(employee_a.id),
            reason="test assignment"
        )

        assert assignment.is_active
        assert assignment.employee == employee_a
        assert assignment.student == student
        assert assignment.batch == batch
        assert assignment.academic_year == batch.academic_year
        assert assignment.reason == "test assignment"

    def test_assign_rejects_employee_not_in_pool(self, svc, batch, employee_a, employee_b, student):
        """assign() raises ValidationException if employee not in batch.class_teachers/batch.employee."""
        batch.employee = employee_a
        batch.save()

        with pytest.raises(ValidationException):
            svc.assign(str(student.id), str(batch.id), str(employee_b.id))

    def test_assign_allows_employee_in_class_teachers(self, svc, batch, employee_a, employee_b, student):
        """assign() allows employee in batch.class_teachers M2M."""
        batch.class_teachers.add(employee_a, employee_b)

        assignment = svc.assign(str(student.id), str(batch.id), str(employee_b.id))
        assert assignment.employee == employee_b

    def test_reassign_deactivates_prior_active(self, svc, batch, employee_a, employee_b, student):
        """Reassigning a student deactivates the prior active assignment."""
        batch.class_teachers.add(employee_a, employee_b)

        # Initial assignment
        first = svc.assign(str(student.id), str(batch.id), str(employee_a.id))
        assert first.is_active

        # Reassign to employee_b
        second = svc.assign(str(student.id), str(batch.id), str(employee_b.id))

        # First should now be inactive
        first.refresh_from_db()
        assert not first.is_active
        assert first.deactivated_at is not None
        assert second.is_active

    def test_assign_noop_if_already_assigned_to_same_employee(self, svc, batch, employee_a, student):
        """assign() is a no-op if prior active row already points at the same employee."""
        batch.employee = employee_a
        batch.save()

        first = svc.assign(str(student.id), str(batch.id), str(employee_a.id))
        second = svc.assign(str(student.id), str(batch.id), str(employee_a.id))

        # Should return the same row, no new deactivate/create
        assert first.id == second.id

    def test_bulk_assign(self, svc, batch, employee_a, employee_b, school, course, academic_year):
        """bulk_assign() creates multiple assignments in one transaction."""
        batch.class_teachers.add(employee_a, employee_b)

        # Create two test students
        student_1 = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="John",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student_1,
            roll_number="1",
            tenant=school
        )

        student_2 = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="Jane",
            last_name="Student",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student_2,
            roll_number="2",
            tenant=school
        )

        assignments = svc.bulk_assign(
            str(batch.id),
            [
                {"student_id": str(student_1.id), "employee_id": str(employee_a.id)},
                {"student_id": str(student_2.id), "employee_id": str(employee_b.id)},
            ]
        )

        assert len(assignments) == 2
        assert all(a.is_active for a in assignments)

    def test_deactivate_all_for_student_in_batch(self, svc, batch, employee_a, student):
        """deactivate_all_for_student_in_batch() deactivates all active assignments."""
        batch.employee = employee_a
        batch.save()

        svc.assign(str(student.id), str(batch.id), str(employee_a.id))

        count = svc.deactivate_all_for_student_in_batch(str(student.id), str(batch.id))

        assert count == 1
        assignment = ClassTeacherAssignment.objects.get(
            student=student, batch=batch
        )
        assert not assignment.is_active

    def test_get_active_assignment(self, svc, batch, employee_a, student):
        """get_active_assignment() returns the active assignment or None."""
        batch.employee = employee_a
        batch.save()

        # No assignment yet
        assert svc.get_active_assignment(str(student.id), batch) is None

        # Create assignment
        created = svc.assign(str(student.id), str(batch.id), str(employee_a.id))
        fetched = svc.get_active_assignment(str(student.id), batch)
        assert fetched.id == created.id

    def test_get_assigned_employee_returns_from_assignment(self, svc, batch, employee_a, student):
        """get_assigned_employee() returns the employee from the active assignment."""
        batch.employee = employee_a
        batch.save()

        svc.assign(str(student.id), str(batch.id), str(employee_a.id))
        employee = svc.get_assigned_employee(str(student.id), batch)

        assert employee.id == employee_a.id

    def test_get_assigned_employee_fallback_sole_teacher(self, svc, batch, employee_a, school):
        """get_assigned_employee() falls back to sole batch teacher for unassigned students in single-teacher batches."""
        batch.employee = employee_a
        batch.save()

        # Create a student WITH batch membership but no assignment row
        student = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="John",
            last_name="Unassigned",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student,
            roll_number="99",
            tenant=school
        )

        employee = svc.get_assigned_employee(str(student.id), batch)

        assert employee.id == employee_a.id

    def test_get_assigned_employee_no_fallback_for_multi_teacher_unassigned(self, svc, batch, employee_a, employee_b, school):
        """get_assigned_employee() returns None for unassigned students in multi-teacher batches."""
        batch.class_teachers.add(employee_a, employee_b)
        batch.save()

        # Create a student WITH batch membership but no assignment row
        student = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="Jane",
            last_name="Unassigned",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student,
            roll_number="99",
            tenant=school
        )

        employee = svc.get_assigned_employee(str(student.id), batch)

        assert employee is None

    def test_assigned_student_ids_explicit_assignments(self, svc, batch, employee_a, employee_b, school, course, academic_year):
        """assigned_student_ids() includes explicitly assigned students."""
        batch.class_teachers.add(employee_a, employee_b)

        # Create two test students
        student_1 = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="John",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student_1,
            roll_number="1",
            tenant=school
        )

        student_2 = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="Jane",
            last_name="Student",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student_2,
            roll_number="2",
            tenant=school
        )

        svc.assign(str(student_1.id), str(batch.id), str(employee_a.id))
        svc.assign(str(student_2.id), str(batch.id), str(employee_b.id))

        ids_a = svc.assigned_student_ids(batch, employee_a)
        ids_b = svc.assigned_student_ids(batch, employee_b)

        assert str(student_1.id) in ids_a
        assert str(student_1.id) not in ids_b
        assert str(student_2.id) in ids_b
        assert str(student_2.id) not in ids_a

    def test_assigned_student_ids_sole_teacher_includes_all_active(self, svc, batch, employee_a, school, course, academic_year):
        """assigned_student_ids() includes all active students for sole teacher (fallback)."""
        batch.employee = employee_a
        batch.save()

        # Create two test students
        student_1 = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="John",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student_1,
            roll_number="1",
            tenant=school
        )

        student_2 = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="Jane",
            last_name="Student",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student_2,
            roll_number="2",
            tenant=school
        )

        ids = svc.assigned_student_ids(batch, employee_a)

        # Both students should be included via fallback (no assignment rows)
        assert str(student_1.id) in ids
        assert str(student_2.id) in ids

    def test_batch_assignment_overview(self, svc, batch, employee_a, employee_b, school, course, academic_year):
        """batch_assignment_overview() returns one row per active BatchStudent."""
        batch.class_teachers.add(employee_a, employee_b)

        # Create two test students
        student_1 = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="John",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student_1,
            roll_number="1",
            tenant=school
        )

        student_2 = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6].upper()}",
            first_name="Jane",
            last_name="Student",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(
            batch=batch,
            student=student_2,
            roll_number="2",
            tenant=school
        )

        svc.assign(str(student_1.id), str(batch.id), str(employee_a.id), reason="backfill:auto")
        svc.assign(str(student_2.id), str(batch.id), str(employee_b.id), reason="backfill:needs_review")

        overview = svc.batch_assignment_overview(batch)

        assert len(overview) == 2
        rows_by_student = {r['student'].id: r for r in overview}
        assert rows_by_student[student_1.id]['employee'].id == employee_a.id
        assert rows_by_student[student_1.id]['needs_review'] is False
        assert rows_by_student[student_2.id]['employee'].id == employee_b.id
        assert rows_by_student[student_2.id]['needs_review'] is True

    def test_partial_unique_constraint_prevents_duplicate_active(self, svc, batch, employee_a, student):
        """The partial-unique constraint prevents duplicate active assignments."""
        batch.employee = employee_a
        batch.save()

        svc.assign(str(student.id), str(batch.id), str(employee_a.id))

        # Try to create a duplicate via raw save (bypass service logic)
        with pytest.raises(IntegrityError):
            ClassTeacherAssignment.objects.create(
                tenant=batch.tenant,
                student=student,
                batch=batch,
                employee=employee_a,
                academic_year=batch.academic_year,
                is_active=True
            )
