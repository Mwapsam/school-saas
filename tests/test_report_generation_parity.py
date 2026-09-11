"""Tests for report generation parity (Phase 6) — single-report vs bulk should match."""

import pytest
from uuid import uuid4
from datetime import date
from django.utils import timezone

from core.models import (
    ClassTeacherAssignment, BatchStudent, Student, Employee, Batch, User, ExamGroup, Term,
    ReportTemplate, StudentReport, Attendance,
)
from core.services.report_generation_service import ReportGenerationService
from core.services.calendar_service import SchoolCalendarService


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
class TestReportGenerationParity:
    """Parity between single-report and bulk generation."""

    def test_bulk_context_includes_class_teachers(self, school, batch, employee_a, employee_b, academic_year, course):
        """_compute_bulk_context includes both class_teachers and employee."""
        batch.class_teachers.add(employee_a, employee_b)
        batch.employee = employee_a
        batch.save()

        svc = ReportGenerationService(school)
        exam_group = ExamGroup.objects.create(
            tenant=school,
            batch=batch,
            name="Test Exam Group",
            is_published=True,
            exam_date="2025-01-15",
        )
        # Phase 3+: Terms are year-scoped, not per-batch. Use academic_year directly.
        Term.objects.create(
            tenant=school,
            academic_year=academic_year,
            name="Term 1",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )

        bulk_ctx = svc._compute_bulk_context(
            ReportTemplate.objects.create(
                tenant=school,
                batch=batch,
                name="Test Template",
                layout_type="FULL_ACADEMIC",
                academic_year=academic_year,
                term="Term 1",
            ),
            exam_group,
            [],
        )

        # Should include class_teachers, not just employee
        batch_teachers = bulk_ctx.get("batch_teachers", [])
        assert "Alice Teacher" in batch_teachers or "Alice" in " ".join(batch_teachers)
        assert "Bob Teacher" in batch_teachers or "Bob" in " ".join(batch_teachers)

    def test_single_vs_bulk_batch_teachers_match(self, school, batch, employee_a, employee_b, academic_year, course):
        """Single-report _get_student_data and bulk _compute_bulk_context produce same teacher list."""
        batch.class_teachers.add(employee_a, employee_b)
        batch.employee = employee_a
        batch.save()

        student = Student.objects.create(
            tenant=school,
            admission_no="S1",
            first_name="John",
            last_name="Student",
            date_of_birth=date(2015, 1, 1),
            gender="male",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(batch=batch, student=student, tenant=school, roll_number="1")

        svc = ReportGenerationService(school)
        exam_group = ExamGroup.objects.create(
            tenant=school,
            batch=batch,
            name="Test Exam Group",
            is_published=True,
            exam_date="2025-01-15",
        )
        # Phase 3+: Terms are year-scoped, not per-batch. Use academic_year directly.
        Term.objects.create(
            tenant=school,
            academic_year=academic_year,
            name="Term 1",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )
        template = ReportTemplate.objects.create(
            tenant=school,
            batch=batch,
            name="Test Template",
            layout_type="FULL_ACADEMIC",
            academic_year=academic_year,
            term="Term 1",
        )

        # Single-report path
        single_data = svc._get_student_data(student, batch)
        single_teachers = single_data.get("class_teachers", [])

        # Bulk path
        bulk_ctx = svc._compute_bulk_context(template, exam_group, [str(student.id)])
        bulk_teachers = bulk_ctx.get("batch_teachers", [])

        # Should match
        assert sorted(single_teachers) == sorted(bulk_teachers)

    def _attendance_fixture(self, school, batch, academic_year):
        """Common student/exam_group/term/template setup for the attendance
        parity tests below. Returns (svc, student, exam_group, template,
        calendar_days) for a fixed Jan 2025 term."""
        student = Student.objects.create(
            tenant=school,
            admission_no=f"S{uuid4().hex[:6]}",
            first_name="Att",
            last_name="Student",
            date_of_birth=date(2015, 1, 1),
            gender="male",
            admission_date="2025-01-01",
        )
        BatchStudent.objects.create(batch=batch, student=student, tenant=school, roll_number="1")

        svc = ReportGenerationService(school)
        exam_group = ExamGroup.objects.create(
            tenant=school,
            batch=batch,
            name="Test Exam Group",
            is_published=True,
            exam_date="2025-01-15",
        )
        Term.objects.create(
            tenant=school,
            academic_year=academic_year,
            name="Term 1",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )
        template = ReportTemplate.objects.create(
            tenant=school,
            batch=batch,
            name="Test Template",
            layout_type="FULL_ACADEMIC",
            academic_year=academic_year,
            term="Term 1",
        )
        calendar_days = SchoolCalendarService(school).get_working_days(date(2025, 1, 1), date(2025, 1, 31))
        return svc, student, exam_group, template, calendar_days

    def _bulk_attendance_summary(self, svc, template, exam_group, student):
        bulk_ctx = svc._compute_bulk_context(template, exam_group, [str(student.id)])
        records = bulk_ctx['attendance_by_student'].get(str(student.id), [])
        summary = svc._compute_attendance_summary(
            records,
            start_date=bulk_ctx['attendance_start_date'],
            end_date=bulk_ctx['attendance_end_date'],
            batch=bulk_ctx['attendance_batch'],
        )
        return summary, records

    def test_attendance_total_days_not_inflated_by_other_batch_records(
        self, school, batch, academic_year, course,
    ):
        """A student with Attendance rows tagged to a different batch (e.g.
        an old batch from before a mid-term transfer that nothing ever
        cleaned up) must not have those rows counted toward this batch's
        report — total_days must match the calendar, not len(records)."""
        other_batch = Batch.objects.create(
            tenant=school, name=f"OTHER-{uuid4().hex[:6]}", course=course,
            academic_year=academic_year,
            start_date=date(2025, 1, 1), end_date=date(2025, 3, 31),
        )
        svc, student, exam_group, template, calendar_days = self._attendance_fixture(school, batch, academic_year)

        # Real attendance under this batch.
        for d in [date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8)]:
            Attendance.objects.create(
                tenant=school, student=student, batch=batch, month_date=d,
                forenoon=True, afternoon=True,
            )
        # Stray attendance under a DIFFERENT batch, same student, overlapping
        # dates — must not be pulled into this batch's total.
        for d in [date(2025, 1, 9), date(2025, 1, 10)]:
            Attendance.objects.create(
                tenant=school, student=student, batch=other_batch, month_date=d,
                forenoon=True, afternoon=True,
            )

        bulk_summary, _ = self._bulk_attendance_summary(svc, template, exam_group, student)
        single_summary = svc._get_attendance_data(student, template, exam_group)

        assert bulk_summary['total_days'] == calendar_days
        assert single_summary['total_days'] == calendar_days
        assert bulk_summary == single_summary

    def test_attendance_total_days_not_inflated_by_duplicate_rows(
        self, school, batch, academic_year, course,
    ):
        """Two Attendance rows for the same student/batch/date (no unique
        constraint prevents this) must still count as one day, not two."""
        svc, student, exam_group, template, calendar_days = self._attendance_fixture(school, batch, academic_year)

        d = date(2025, 1, 6)
        Attendance.objects.create(
            tenant=school, student=student, batch=batch, month_date=d,
            forenoon=True, afternoon=True,
        )
        Attendance.objects.create(
            tenant=school, student=student, batch=batch, month_date=d,
            forenoon=True, afternoon=False,
        )

        bulk_summary, records = self._bulk_attendance_summary(svc, template, exam_group, student)
        assert len(records) == 2, "sanity: the duplicate rows are both present at the query level"
        assert bulk_summary['total_days'] == calendar_days

        single_summary = svc._get_attendance_data(student, template, exam_group)
        assert single_summary['total_days'] == calendar_days
