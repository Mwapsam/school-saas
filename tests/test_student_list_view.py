"""/students/ page: surfaces data problems directly in the table — a student
with more than one active BatchStudent row (the promote_students.py --fix-stale
residue) gets a visible warning badge and a per-batch breakdown, instead of
only being discoverable via a management command."""
import uuid
import pytest
from datetime import date

from django.test import RequestFactory

from core.models import Course, Batch, Student, BatchStudent, AcademicYear
from core.views import StudentListView


@pytest.fixture
def current_year(db, school):
    return AcademicYear.objects.create(
        name=f"2024-2025-{uuid.uuid4().hex[:4]}",
        start_date=date(2024, 9, 1), end_date=date(2025, 7, 31),
        is_active=True, tenant=school,
    )


@pytest.fixture
def prior_year(db, school, current_year):
    # Created after current_year so it doesn't get auto-deactivated by it.
    return AcademicYear.objects.create(
        name=f"2023-2024-{uuid.uuid4().hex[:4]}",
        start_date=date(2023, 9, 1), end_date=date(2024, 7, 31),
        is_active=False, tenant=school,
    )


@pytest.fixture
def course(db, school):
    return Course.objects.create(
        course_name="Grade 1", code=f"G1{uuid.uuid4().hex[:5].upper()}", tenant=school
    )


@pytest.fixture
def batch(db, school, course, current_year):
    return Batch.objects.create(
        name=f"Section A {uuid.uuid4().hex[:4]}", course=course, academic_year=current_year,
        start_date=date(2024, 9, 1), end_date=date(2025, 7, 31), tenant=school,
    )


@pytest.fixture
def old_batch(db, school, course, prior_year):
    return Batch.objects.create(
        name=f"Old Section {uuid.uuid4().hex[:4]}", course=course, academic_year=prior_year,
        start_date=date(2023, 9, 1), end_date=date(2024, 7, 31), tenant=school,
    )


def _render_student_list(school, user):
    request = RequestFactory().get('/students/', HTTP_HX_REQUEST='true')
    request.tenant = school
    request.user = user
    response = StudentListView.as_view()(request)
    response.render()
    return response.content.decode()


@pytest.mark.django_db
class TestStudentListDataChecks:
    def test_single_enrollment_shows_ok(self, school, user, batch, course, current_year):
        student = Student.objects.create(
            first_name="Clean", last_name="Record",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date(2024, 9, 1), date_of_birth=date(2018, 1, 1),
            gender="male", tenant=school,
        )
        BatchStudent.objects.create(batch=batch, student=student, tenant=school)

        html = _render_student_list(school, user)

        assert "Clean Record" in html
        assert "OK" in html
        assert "active enrollments" not in html

    def test_duplicate_active_enrollment_is_flagged(
        self, school, user, batch, old_batch, course, current_year, prior_year
    ):
        student = Student.objects.create(
            first_name="Dupe", last_name="Residue",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date(2023, 9, 1), date_of_birth=date(2017, 1, 1),
            gender="male", tenant=school,
        )
        BatchStudent.objects.create(batch=old_batch, student=student, tenant=school)
        BatchStudent.objects.create(batch=batch, student=student, tenant=school)

        html = _render_student_list(school, user)

        assert "Dupe Residue" in html
        assert "2 active enrollments" in html
        assert batch.name in html
        assert old_batch.name in html
        assert current_year.name in html
        assert prior_year.name in html
