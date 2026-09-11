"""Tests for backfill_class_teacher_assignments management command."""

import pytest
from io import StringIO
from uuid import uuid4
from django.core.management import call_command

from core.models import ClassTeacherAssignment, BatchStudent, TeacherComment, SkillsTeacherComment, Employee, User, Student, Batch
from core.services import ClassTeacherAssignmentService


@pytest.fixture
def employee_a(db, school):
    """Create test employee A."""
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
    """Create test employee B."""
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


@pytest.mark.django_db
class TestBackfillCommand:
    """Backfill command tests."""

    def test_dry_run_changes_nothing(self, school, batch, employee_a, employee_b, student, course, academic_year):
        """Dry-run (no --execute) doesn't write anything."""
        batch.class_teachers.add(employee_a, employee_b)

        # Dry-run
        out = StringIO()
        call_command("backfill_class_teacher_assignments", tenant=school.schema_name, stdout=out)

        # No assignments created
        assert ClassTeacherAssignment.objects.count() == 0
        assert "DRY-RUN" in out.getvalue()

    def test_execute_creates_auto_assignments_single_teacher(self, school, batch, employee_a, student, course, academic_year):
        """--execute creates one assignment per student (auto, single-teacher)."""
        batch.employee = employee_a
        batch.save()

        out = StringIO()
        call_command("backfill_class_teacher_assignments", tenant=school.schema_name, execute=True, stdout=out)

        # Assignment created
        assignment = ClassTeacherAssignment.objects.filter(student=student, batch=batch, is_active=True).first()
        assert assignment is not None
        assert assignment.employee == employee_a
        assert assignment.reason == "backfill:auto"
        assert "auto, single-teacher" in out.getvalue()

    def test_execute_creates_needs_review_multi_teacher(self, school, batch, employee_a, employee_b, student, course, academic_year):
        """--execute creates assignments flagged needs_review for multi-teacher batches."""
        batch.class_teachers.add(employee_a)
        batch.class_teachers.add(employee_b)

        out = StringIO()
        call_command("backfill_class_teacher_assignments", tenant=school.schema_name, execute=True, stdout=out)

        # Assignment created, pointed at one of the class teachers (ordered by ID)
        assignment = ClassTeacherAssignment.objects.filter(student=student, batch=batch, is_active=True).first()
        assert assignment is not None
        # Should assign to one of the class_teachers (deterministically the one with lower ID)
        assert assignment.employee in [employee_a, employee_b]
        assert assignment.reason == "backfill:needs_review"
        assert "needs_review, multi-teacher" in out.getvalue()

    def test_idempotent_rerun(self, school, batch, employee_a, student, course, academic_year):
        """Re-running --execute is idempotent (doesn't duplicate)."""
        batch.employee = employee_a
        batch.save()

        # First run
        call_command("backfill_class_teacher_assignments", tenant=school.schema_name, execute=True)
        assert ClassTeacherAssignment.objects.filter(student=student, batch=batch).count() == 1

        # Second run
        call_command("backfill_class_teacher_assignments", tenant=school.schema_name, execute=True)
        assert ClassTeacherAssignment.objects.filter(student=student, batch=batch).count() == 1

    def test_rollback_removes_backfill_rows(self, school, batch, employee_a, employee_b, student, course, academic_year):
        """--rollback removes only backfill-tagged rows."""
        batch.employee = employee_a
        batch.class_teachers.add(employee_b)
        batch.save()

        svc = ClassTeacherAssignmentService(school)
        # Admin-created row (assigned to employee_a)
        admin_row = svc.assign(
            str(student.id), str(batch.id), str(employee_a.id),
            reason="admin reassignment"
        )
        assert admin_row.is_active

        # Backfill reassignment to employee_b (different employee)
        backfill_row = svc.assign(
            str(student.id), str(batch.id), str(employee_b.id),
            reason="backfill:needs_review"
        )
        assert backfill_row.is_active
        # Admin row should be deactivated
        admin_row.refresh_from_db()
        assert not admin_row.is_active

        # Rollback
        call_command("backfill_class_teacher_assignments", tenant=school.schema_name, rollback=True, execute=True)

        # Backfill row should be deleted, admin row remains (deactivated)
        remaining = list(ClassTeacherAssignment.objects.filter(student=student, batch=batch).values_list("reason", "is_active", flat=False))
        # Should only have the deactivated admin row
        assert len(remaining) == 1
        assert remaining[0][0] == "admin reassignment"
        assert remaining[0][1] is False

    def test_skips_empty_pool_batches(self, school, batch, student, course, academic_year):
        """Backfill skips batches with no teachers."""
        batch.employee = None
        batch.save()

        out = StringIO()
        call_command("backfill_class_teacher_assignments", tenant=school.schema_name, execute=True, stdout=out)

        # No assignment created
        assert ClassTeacherAssignment.objects.count() == 0
        assert "no teachers — skipping" in out.getvalue()

    def test_stamps_existing_comments(self, school, batch, employee_a, student, course, academic_year):
        """Backfill stamps existing comments with class_teacher."""
        from core.models import ExamGroup
        from datetime import date

        batch.employee = employee_a
        batch.save()

        # Create an exam group for the batch
        eg = ExamGroup.objects.create(
            tenant=school,
            batch=batch,
            name="Test Exam",
            exam_type="TERM",
            exam_date=date.today(),
        )

        # Create a comment without class_teacher
        comment = TeacherComment.objects.create(
            tenant=school,
            student=student,
            exam_group=eg,
            comment="Test comment",
        )
        assert comment.class_teacher is None

        # Backfill
        call_command("backfill_class_teacher_assignments", tenant=school.schema_name, execute=True)

        # Comment now stamped
        comment.refresh_from_db()
        assert comment.class_teacher == employee_a

    def test_batch_filter_option(self, school, batch, employee_a, student, course, academic_year):
        """--batch filters to a specific batch."""
        batch.employee = employee_a
        batch.save()

        # Another batch
        batch2 = Batch.objects.create(
            tenant=school,
            course=course,
            name="Class 2",
            start_date="2025-01-01",
            end_date="2025-12-31",
            academic_year=academic_year,
        )
        student2 = Student.objects.create(
            tenant=school,
            admission_no="S999",
            first_name="Another",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01",
        )
        BatchStudent.objects.create(batch=batch2, student=student2, tenant=school, roll_number="1")

        # Backfill only batch1
        call_command(
            "backfill_class_teacher_assignments",
            tenant=school.schema_name,
            batch=str(batch.id),
            execute=True,
        )

        # Only batch1 backfilled
        assert ClassTeacherAssignment.objects.filter(batch=batch).count() == 1
        assert ClassTeacherAssignment.objects.filter(batch=batch2).count() == 0
