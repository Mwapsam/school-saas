"""promote_students: moving a student into the active year's batch must
deactivate their prior-year BatchStudent row (not just create a new one),
so BatchStudent.is_active=True keeps meaning "currently enrolled" instead of
accumulating one active row per year a student has been promoted through.
Also covers --fix-stale, the one-time cleanup for rows left behind by older
runs of this command (before the deactivation fix existed)."""
import uuid
import pytest
from io import StringIO
from datetime import date

from django.core.management import call_command

from core.models import Course, Batch, Student, BatchStudent, AcademicYear, School


@pytest.fixture
def prior_year(db, school):
    return AcademicYear.objects.create(
        name=f"2023-2024-{uuid.uuid4().hex[:4]}",
        start_date=date(2023, 9, 1), end_date=date(2024, 7, 31),
        is_active=True, tenant=school,
    )


@pytest.fixture
def current_year(db, school, prior_year):
    # Saving this active auto-deactivates prior_year (model.save() behaviour).
    return AcademicYear.objects.create(
        name=f"2024-2025-{uuid.uuid4().hex[:4]}",
        start_date=date(2024, 9, 1), end_date=date(2025, 7, 31),
        is_active=True, tenant=school,
    )


@pytest.fixture
def course(db, school):
    return Course.objects.create(
        course_name="Grade 1", code=f"G1{uuid.uuid4().hex[:5].upper()}", tenant=school
    )


@pytest.fixture
def old_batch(db, school, course, prior_year):
    return Batch.objects.create(
        name=f"Section A {prior_year.start_date.year}",
        course=course, academic_year=prior_year,
        start_date=date(2023, 9, 1), end_date=date(2024, 7, 31), tenant=school,
    )


@pytest.fixture
def new_batch(db, school, course, current_year):
    return Batch.objects.create(
        name=f"Section A {current_year.start_date.year}",
        course=course, academic_year=current_year,
        start_date=date(2024, 9, 1), end_date=date(2025, 7, 31), tenant=school,
    )


@pytest.fixture
def student(db, school, old_batch):
    s = Student.objects.create(
        first_name="Pat", last_name="Learner",
        admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
        admission_date=date(2023, 9, 1), date_of_birth=date(2017, 1, 1),
        gender="male", tenant=school,
    )
    BatchStudent.objects.create(batch=old_batch, student=s, tenant=school)
    return s


@pytest.mark.django_db
class TestPromoteStudents:
    def test_dry_run_makes_no_changes(self, school, old_batch, new_batch, student, current_year):
        out = StringIO()
        call_command("promote_students", "--tenant", school.schema_name, stdout=out)

        assert "Can promote: 1" in out.getvalue()
        old_enrollment = BatchStudent.objects.get(batch=old_batch, student=student)
        assert old_enrollment.is_active is True
        assert not BatchStudent.objects.filter(batch=new_batch, student=student).exists()

    def test_execute_deactivates_prior_year_row(self, school, old_batch, new_batch, student, current_year):
        out = StringIO()
        call_command("promote_students", "--tenant", school.schema_name, "--execute", stdout=out)

        old_enrollment = BatchStudent.objects.get(batch=old_batch, student=student)
        assert old_enrollment.is_active is False

        new_enrollment = BatchStudent.objects.get(batch=new_batch, student=student)
        assert new_enrollment.is_active is True

        # Exactly one active enrollment across all years for this student.
        assert BatchStudent.objects.filter(student=student, is_active=True).count() == 1

    def test_execute_is_idempotent(self, school, old_batch, new_batch, student, current_year):
        call_command("promote_students", "--tenant", school.schema_name, "--execute", stdout=StringIO())
        call_command("promote_students", "--tenant", school.schema_name, "--execute", stdout=StringIO())

        assert BatchStudent.objects.filter(student=student, is_active=True).count() == 1


@pytest.mark.django_db
class TestFixStale:
    def test_dry_run_reports_without_writing(self, school, old_batch, new_batch, student, current_year):
        # Simulate residue from a pre-fix promotion run: both rows left active.
        BatchStudent.objects.create(batch=new_batch, student=student, tenant=school)
        assert BatchStudent.objects.filter(student=student, is_active=True).count() == 2

        out = StringIO()
        call_command("promote_students", "--tenant", school.schema_name, "--fix-stale", stdout=out)

        assert "Would deactivate 1" in out.getvalue()
        assert BatchStudent.objects.filter(student=student, is_active=True).count() == 2

    def test_execute_keeps_only_most_recent_year(self, school, old_batch, new_batch, student, current_year):
        BatchStudent.objects.create(batch=new_batch, student=student, tenant=school)

        out = StringIO()
        call_command(
            "promote_students", "--tenant", school.schema_name,
            "--fix-stale", "--execute", stdout=out,
        )

        assert "Deactivated 1" in out.getvalue()
        remaining = BatchStudent.objects.filter(student=student, is_active=True)
        assert remaining.count() == 1
        assert remaining.first().batch == new_batch

    def test_no_stale_rows_is_a_no_op(self, school, old_batch, new_batch, student, current_year):
        out = StringIO()
        call_command(
            "promote_students", "--tenant", school.schema_name,
            "--fix-stale", "--execute", stdout=out,
        )
        assert "No stale rows found" in out.getvalue()
        assert BatchStudent.objects.get(batch=old_batch, student=student).is_active is True


@pytest.fixture
def other_school(db):
    """A second, unrelated tenant — used to prove --tenant scoping actually
    isolates one school's data from another's. School.auto_create_schema is
    disabled tenant-wide in tests (see top of conftest.py), so this is a
    plain row insert, not a slow migrate_schemas run.
    """
    return School.objects.create(
        name="Other Test School", code=f"OTHER{uuid.uuid4().hex[:6].upper()}",
        schema_name=f"other_test_{uuid.uuid4().hex[:8]}",
    )


@pytest.mark.django_db
class TestTenantIsolation:
    """schema_context() sets connection.tenant to a bare FakeTenant (no `pk`
    attribute), which silently disables TenantAwareManager's automatic
    tenant filter — so any query relying on that implicit filter inside a
    `with schema_context(...):` block spans every tenant in the shared
    database, not just the one requested. promote_students.py now uses
    tenant_context() plus explicit tenant= filters everywhere instead.
    These tests prove --fix-stale run against `school` cannot see or touch
    `other_school`'s data.
    """

    def test_fix_stale_does_not_count_other_tenants_students(
        self, school, other_school, old_batch, new_batch, student, current_year
    ):
        # `student` (belongs to `school`) has exactly one stale row.
        BatchStudent.objects.create(batch=new_batch, student=student, tenant=school)

        # An unrelated student on a different tenant, with its own stale
        # residue — must be invisible to a --tenant=<school> run.
        other_course = Course.objects.create(
            course_name="Grade 1", code=f"G1{uuid.uuid4().hex[:5].upper()}", tenant=other_school,
        )
        other_year = AcademicYear.objects.create(
            name=f"2024-2025-{uuid.uuid4().hex[:4]}",
            start_date=date(2024, 9, 1), end_date=date(2025, 7, 31),
            is_active=True, tenant=other_school,
        )
        other_batch_1 = Batch.objects.create(
            name=f"Section A {uuid.uuid4().hex[:4]}", course=other_course, academic_year=other_year,
            start_date=date(2023, 9, 1), end_date=date(2024, 7, 31), tenant=other_school,
        )
        other_batch_2 = Batch.objects.create(
            name=f"Section B {uuid.uuid4().hex[:4]}", course=other_course, academic_year=other_year,
            start_date=date(2024, 9, 1), end_date=date(2025, 7, 31), tenant=other_school,
        )
        other_student = Student.objects.create(
            first_name="Other", last_name="Tenant",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date(2023, 9, 1), date_of_birth=date(2017, 1, 1),
            gender="male", tenant=other_school,
        )
        BatchStudent.objects.create(batch=other_batch_1, student=other_student, tenant=other_school)
        BatchStudent.objects.create(batch=other_batch_2, student=other_student, tenant=other_school)

        out = StringIO()
        call_command("promote_students", "--tenant", school.schema_name, "--fix-stale", stdout=out)

        # Exactly the one stale row that belongs to `school`, not two.
        assert "Students with >1 active enrollment: 1" in out.getvalue()
        assert "Would deactivate 1 stale" in out.getvalue()

        # other_school's rows are completely untouched (both still active).
        assert BatchStudent.objects.filter(
            student=other_student, is_active=True
        ).count() == 2

    def test_run_resolves_active_year_for_the_requested_tenant_only(
        self, school, other_school, current_year
    ):
        # other_school also has an "active" academic year — if promote_students
        # resolved AcademicYear.objects.filter(is_active=True).first() without
        # a tenant filter, it could pick this one up instead of `school`'s.
        AcademicYear.objects.create(
            name=f"Other-2024-{uuid.uuid4().hex[:4]}",
            start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
            is_active=True, tenant=other_school,
        )

        out = StringIO()
        call_command("promote_students", "--tenant", school.schema_name, stdout=out)

        assert f"Active year: {current_year.name}" in out.getvalue()
