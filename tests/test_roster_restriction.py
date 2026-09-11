"""Tests for roster restriction per teacher assignment (Phase 5)."""

import pytest
from uuid import uuid4

from core.models import ClassTeacherAssignment, BatchStudent, Student, Employee, Batch, User
from portal import selectors
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
class TestRosterRestriction:
    """Roster narrowing tests."""

    def test_roster_for_batch_without_employee_returns_all(self, batch, school):
        """roster_for_batch(batch) returns all active students."""
        s1 = Student.objects.create(
            tenant=school,
            admission_no="S1",
            first_name="John",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        s2 = Student.objects.create(
            tenant=school,
            admission_no="S2",
            first_name="Jane",
            last_name="Student",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(batch=batch, student=s1, tenant=school, roll_number="1")
        BatchStudent.objects.create(batch=batch, student=s2, tenant=school, roll_number="2")

        roster = selectors.roster_for_batch(batch)
        assert len(roster) == 2
        assert any(s.id == s1.id for s in roster)
        assert any(s.id == s2.id for s in roster)

    def test_roster_for_batch_with_employee_narrows(self, batch, school, employee_a, employee_b):
        """roster_for_batch(batch, employee=teacher_a) returns only teacher_a's students."""
        batch.class_teachers.add(employee_a, employee_b)

        s1 = Student.objects.create(
            tenant=school,
            admission_no="S1",
            first_name="John",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        s2 = Student.objects.create(
            tenant=school,
            admission_no="S2",
            first_name="Jane",
            last_name="Student",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(batch=batch, student=s1, tenant=school, roll_number="1")
        BatchStudent.objects.create(batch=batch, student=s2, tenant=school, roll_number="2")

        # Assign s1 to employee_a, s2 to employee_b
        svc = ClassTeacherAssignmentService(school)
        svc.assign(str(s1.id), str(batch.id), str(employee_a.id))
        svc.assign(str(s2.id), str(batch.id), str(employee_b.id))

        # Get roster for employee_a
        roster_a = selectors.roster_for_batch(batch, employee=employee_a)
        assert len(roster_a) == 1
        assert roster_a[0].id == s1.id

        # Get roster for employee_b
        roster_b = selectors.roster_for_batch(batch, employee=employee_b)
        assert len(roster_b) == 1
        assert roster_b[0].id == s2.id

    def test_sole_teacher_fallback_includes_all(self, batch, school, employee_a):
        """Single-teacher batch's sole teacher gets all students (fallback)."""
        batch.employee = employee_a
        batch.save()

        s1 = Student.objects.create(
            tenant=school,
            admission_no="S1",
            first_name="John",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        s2 = Student.objects.create(
            tenant=school,
            admission_no="S2",
            first_name="Jane",
            last_name="Student",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(batch=batch, student=s1, tenant=school, roll_number="1")
        BatchStudent.objects.create(batch=batch, student=s2, tenant=school, roll_number="2")

        # No explicit assignments; roster should include all via fallback
        roster = selectors.roster_for_batch(batch, employee=employee_a)
        assert len(roster) == 2

    def test_unassigned_student_in_multi_teacher_absent_from_roster(self, batch, school, employee_a, employee_b):
        """Unassigned student in multi-teacher batch not in narrowed roster."""
        batch.class_teachers.add(employee_a, employee_b)

        s1 = Student.objects.create(
            tenant=school,
            admission_no="S1",
            first_name="John",
            last_name="Student",
            date_of_birth="2015-01-01",
            gender="male",
            admission_date="2025-01-01"
        )
        s2 = Student.objects.create(
            tenant=school,
            admission_no="S2",
            first_name="Jane",
            last_name="Student",
            date_of_birth="2015-02-01",
            gender="female",
            admission_date="2025-01-01"
        )
        BatchStudent.objects.create(batch=batch, student=s1, tenant=school, roll_number="1")
        BatchStudent.objects.create(batch=batch, student=s2, tenant=school, roll_number="2")

        # Assign only s1 to employee_a
        svc = ClassTeacherAssignmentService(school)
        svc.assign(str(s1.id), str(batch.id), str(employee_a.id))
        # s2 left unassigned

        # s2 absent from employee_a's roster
        roster = selectors.roster_for_batch(batch, employee=employee_a)
        assert len(roster) == 1
        assert roster[0].id == s1.id
