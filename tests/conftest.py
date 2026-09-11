import pytest
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.db import connection
import uuid

from core.models import (
    School, Course, Batch, Subject, Employee, Student,
    ClassTiming, BatchStudent, PeriodEntry, Domain, AcademicYear,
)

User = get_user_model()

# Tests never need a real per-tenant Postgres schema. The `core` app is in
# SHARED_APPS, so its tables live in the public schema and tests isolate tenants
# logically via the `tenant` FK (the search path always falls back to public).
# Leaving auto_create_schema on means every `School.objects.create(...)` runs
# migrate_schemas -> the migration autodetector, which is slow with disabled
# migrations and times out under xdist. Disabling it makes School creation a
# plain row insert. (Existing schemas, e.g. the one the `testserver` domain
# points at, are untouched and keep working for request-routed API tests.)
School.auto_create_schema = False


# ---------------------------------------------------------------------------
# Schema isolation
#
# django-tenants activates a tenant schema with a *session-level* `SET
# search_path` (not SET LOCAL). It is issued whenever a tenant schema is
# created or activated — most notably by TenantMainMiddleware while an
# APIClient request is being served. Because a session SET is not undone by
# the per-test transaction rollback, the search path leaks into the next test,
# which then fails with "Can't create tenant outside the public schema. Current
# schema is test_<...>".
#
# Resetting to the public schema before (and after) every test neutralises the
# leak. set_schema_to_public() only marks the search path to be re-applied on
# the next cursor, so it performs no SQL and is safe for tests that never touch
# the database.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_schema_to_public():
    connection.set_schema_to_public()
    yield
    connection.set_schema_to_public()


# ---------------------------------------------------------------------------
# Session-level setup: Create ONE test school schema for all tests
# This avoids the massive overhead of creating schemas per-test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    """Keep the test database alive for the whole session."""
    with django_db_blocker.unblock():
        pass


def _get_or_create_idempotent(model, defaults=None, **lookup):
    """get_or_create that tolerates a concurrent create.

    pytest-xdist runs session fixtures once per worker (separate processes), so
    several workers race to create the shared school/domain. A losing racer hits
    a unique-constraint IntegrityError; re-fetch instead of failing the fixture.
    """
    from django.db import IntegrityError, transaction
    try:
        with transaction.atomic():
            obj, _ = model.objects.get_or_create(defaults=defaults or {}, **lookup)
            return obj
    except IntegrityError:
        return model.objects.get(**lookup)


def _ensure_schema(schema_name):
    """Create the tenant's Postgres schema if missing (raw + idempotent).

    auto_create_schema is disabled in tests (see top of file), so nothing else
    creates it. The schema only needs to exist so the tenant search_path is
    valid; the actual core tables live in the public schema (SHARED_APPS).

    `CREATE SCHEMA IF NOT EXISTS` is NOT atomic against concurrency: two xdist
    workers can both pass the existence check and then collide on pg_namespace.
    Run it inside a savepoint and swallow that conflict (the schema exists either
    way) so the connection stays usable.
    """
    from django_tenants.utils import get_public_schema_name
    from django.db import IntegrityError, ProgrammingError, transaction
    if not schema_name or schema_name == get_public_schema_name():
        return
    connection.set_schema_to_public()
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('CREATE SCHEMA IF NOT EXISTS "%s"' % schema_name)
    except (IntegrityError, ProgrammingError):
        pass  # another worker created it concurrently
    connection.set_schema_to_public()


@pytest.fixture(scope="session")
def shared_school(django_db_setup, django_db_blocker):
    """One shared test school for all tests (no per-test schema overhead).

    Requests route by the `testserver` host, and ``tenant_users``'
    TenantAccessMiddleware rejects (404) an authenticated user who is not a
    member of the routed tenant. So the shared school MUST be whichever tenant
    already owns the `testserver` domain (a previous APITestCase run may have
    committed `testserver -> TESTSERVER`). Adopting that tenant keeps data,
    user membership, and request routing consistent.
    """
    with django_db_blocker.unblock():
        connection.set_schema_to_public()
        existing = (
            Domain.objects.filter(domain="testserver")
            .select_related("tenant")
            .first()
        )
        if existing:
            school = existing.tenant
        else:
            school = _get_or_create_idempotent(
                School,
                code="TEST_SHARED",
                defaults={
                    "name": "Shared Test School",
                    "schema_name": "test_shared_schema",
                },
            )
        # Routed API requests need the tenant's schema to exist regardless of DB
        # state (auto_create_schema is off in tests).
        _ensure_schema(school.schema_name)
        connection.set_schema_to_public()
    return school


@pytest.fixture(scope="session")
def shared_domain(django_db_blocker, shared_school):
    """Ensure the `testserver` host maps to the shared school."""
    with django_db_blocker.unblock():
        connection.set_schema_to_public()
        domain = _get_or_create_idempotent(
            Domain,
            domain="testserver",
            defaults={
                "tenant": shared_school,
                "is_primary": True,
            },
        )
        connection.set_schema_to_public()
    return domain


# ---------------------------------------------------------------------------
# Function-scoped fixtures: Use shared school, only create test data per-test
# Data is auto-rolled back after each test via transaction isolation
# ---------------------------------------------------------------------------

@pytest.fixture
def school(db, shared_school):
    """Reuse shared school instead of creating per-test schemas"""
    return shared_school


@pytest.fixture
def tenant(school):
    """Alias for `school` — many tests refer to the tenant by this name."""
    return school


@pytest.fixture
def domain(db, shared_domain):
    """Use shared domain"""
    return shared_domain


@pytest.fixture
def academic_year(db, school):
    """Create an active academic year - Batch requires this FK."""
    return AcademicYear.objects.create(
        name=f"AY-{uuid.uuid4().hex[:4].upper()}",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        is_active=True,
        tenant=school,
    )


@pytest.fixture
def user(db, school):
    """Create test user - auto-rolled back per test.

    Mirrors UserService.create_user: instantiate + set_password + save, then
    attach tenant membership via the ``tenants`` M2M. (The tenant_users
    create_user path requires a public-schema tenant + add_user, which this
    project's School model does not provide.)
    """
    u = User(
        username=f"testuser_{uuid.uuid4().hex[:6]}",
        email=f"test_{uuid.uuid4().hex[:6]}@example.com",
        first_name="Test",
        last_name="User",
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    return u


@pytest.fixture
def course(db, school):
    """Create test course - auto-rolled back per test"""
    return Course.objects.create(
        code=f"TC{uuid.uuid4().hex[:4].upper()}",
        course_name="Test Course",
        tenant=school
    )


@pytest.fixture
def batch(db, course, academic_year, school):
    """Create test batch - auto-rolled back per test"""
    return Batch.objects.create(
        name=f"BATCH-{uuid.uuid4().hex[:6].upper()}",
        course=course,
        academic_year=academic_year,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        tenant=school,
    )


@pytest.fixture
def subject(db, batch, school):
    """Create test subject - auto-rolled back per test.

    Subject links to a Batch (not Course) in the current schema.
    """
    return Subject.objects.create(
        code=f"TS{uuid.uuid4().hex[:4].upper()}",
        name="Test Subject",
        batch=batch,
        tenant=school
    )


@pytest.fixture
def employee(db, school):
    """Create test employee - auto-rolled back per test"""
    return Employee.objects.create(
        first_name="Test",
        last_name="Teacher",
        employee_number=f"EMP{uuid.uuid4().hex[:6].upper()}",
        joining_date=date.today(),
        gender=True,
        tenant=school,
    )


@pytest.fixture
def class_timing(db, batch, school):
    """Create test class timing - auto-rolled back per test.

    ClassTiming requires a batch FK and a name; there is no `period_no` field.
    """
    return ClassTiming.objects.create(
        batch=batch,
        name="Period 1",
        start_time="09:00",
        end_time="10:00",
        tenant=school,
    )


@pytest.fixture
def student(db, school, batch):
    """Create test student - auto-rolled back per test"""
    student = Student.objects.create(
        first_name="Test",
        last_name="Student",
        admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
        admission_date=date.today(),
        date_of_birth=date(2005, 1, 1),
        gender="male",
        tenant=school,
    )
    BatchStudent.objects.create(
        batch=batch,
        student=student,
        roll_number=f"R{uuid.uuid4().hex[:3].upper()}",
        tenant=school,
    )
    return student


@pytest.fixture
def batch_student(db, batch, student, school):
    """Get batch-student relationship"""
    return BatchStudent.objects.get(batch=batch, student=student)


@pytest.fixture
def period_entry(db, batch, subject, class_timing, employee, school):
    """Create test period entry - auto-rolled back per test"""
    return PeriodEntry.objects.create(
        batch=batch,
        subject=subject,
        class_timing=class_timing,
        employee=employee,
        month_date=date.today(),
        tenant=school,
    )
