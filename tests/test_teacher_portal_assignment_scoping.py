"""Tests for teacher portal scoping by ClassTeacherAssignment.

Verifies that each teacher only sees and can modify their assigned students,
not the entire class roster (which only shows up in multi-teacher batches).
"""

import pytest
from uuid import uuid4
from datetime import date, datetime

from core.models import (
    ClassTeacherAssignment, Batch, Student, Employee, BatchStudent,
    Course, AcademicYear, User, Subject, ExamGroup, Exam
)
from core.services import ClassTeacherAssignmentService
from portal import selectors
from portal.views import TeacherSkillsCatalogView, TeacherStudentSkillsView, TeacherActivitiesView


@pytest.fixture
def course(db, school):
    """Create a test course."""
    return Course.objects.create(
        tenant=school,
        course_name="Grade 4",
        code="G4",
    )


@pytest.fixture
def academic_year(db, school):
    """Create a test academic year."""
    return AcademicYear.objects.create(
        tenant=school,
        name="2024-2025",
        start_date="2024-01-01",
        end_date="2024-12-31",
        is_active=True,
    )


@pytest.fixture
def batch(db, school, course, academic_year):
    """Create a batch with no primary teacher (will use class_teachers M2M)."""
    return Batch.objects.create(
        tenant=school,
        course=course,
        academic_year=academic_year,
        name="Grade 4A",
        is_active=True,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )


@pytest.fixture
def employee_a(db, school):
    """Create test employee A (Mrs Banda)."""
    u = User(
        username=f"teacher_a_{uuid4().hex[:6]}",
        email=f"teacher_a_{uuid4().hex[:6]}@test.local",
        first_name="Alice",
        last_name="Banda",
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    emp = Employee.objects.create(
        tenant=school,
        employee_number=f"E{uuid4().hex[:6].upper()}",
        joining_date="2020-01-01",
        first_name="Alice",
        last_name="Banda",
        gender=True,
        is_teaching_staff=True,
        user=u
    )
    return emp


@pytest.fixture
def employee_b(db, school):
    """Create test employee B (Mr Phiri)."""
    u = User(
        username=f"teacher_b_{uuid4().hex[:6]}",
        email=f"teacher_b_{uuid4().hex[:6]}@test.local",
        first_name="Bob",
        last_name="Phiri",
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    emp = Employee.objects.create(
        tenant=school,
        employee_number=f"E{uuid4().hex[:6].upper()}",
        joining_date="2020-01-01",
        first_name="Bob",
        last_name="Phiri",
        gender=False,
        is_teaching_staff=True,
        user=u
    )
    return emp


@pytest.fixture
def student_a1(db, school):
    """Create student assigned to teacher A."""
    return Student.objects.create(
        tenant=school,
        admission_no="S001",
        first_name="John",
        last_name="Doe",
        date_of_birth=date(2015, 1, 1),
        gender="male",
        admission_date=date(2024, 1, 1),
    )


@pytest.fixture
def student_a2(db, school):
    """Create another student assigned to teacher A."""
    return Student.objects.create(
        tenant=school,
        admission_no="S002",
        first_name="Jane",
        last_name="Smith",
        date_of_birth=date(2015, 2, 1),
        gender="female",
        admission_date=date(2024, 1, 1),
    )


@pytest.fixture
def student_b1(db, school):
    """Create student assigned to teacher B."""
    return Student.objects.create(
        tenant=school,
        admission_no="S003",
        first_name="Peter",
        last_name="Brown",
        date_of_birth=date(2015, 3, 1),
        gender="male",
        admission_date=date(2024, 1, 1),
    )


@pytest.fixture
def student_b2(db, school):
    """Create another student assigned to teacher B."""
    return Student.objects.create(
        tenant=school,
        admission_no="S004",
        first_name="Ruth",
        last_name="Johnson",
        date_of_birth=date(2015, 4, 1),
        gender="female",
        admission_date=date(2024, 1, 1),
    )


@pytest.fixture
def employee_subject_teacher(db, school):
    """Create test employee C (subject teacher, not in class_teachers)."""
    u = User(
        username=f"teacher_c_{uuid4().hex[:6]}",
        email=f"teacher_c_{uuid4().hex[:6]}@test.local",
        first_name="Carol",
        last_name="Mweemba",
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    emp = Employee.objects.create(
        tenant=school,
        employee_number=f"E{uuid4().hex[:6].upper()}",
        joining_date="2020-01-01",
        first_name="Carol",
        last_name="Mweemba",
        gender=True,
        is_teaching_staff=True,
        user=u
    )
    return emp


@pytest.fixture
def setup_multi_teacher_batch(
    db, batch, employee_a, employee_b, student_a1, student_a2, student_b1, student_b2
):
    """Set up a batch with two class teachers and students split between them.

    Returns: (batch, employee_a, employee_b, [student_a1, student_a2], [student_b1, student_b2])
    """
    # Add both as class teachers
    batch.class_teachers.add(employee_a, employee_b)
    batch.save()

    # Enroll all students in the batch
    BatchStudent.objects.create(batch=batch, student=student_a1, tenant=batch.tenant, is_active=True, roll_number=1)
    BatchStudent.objects.create(batch=batch, student=student_a2, tenant=batch.tenant, is_active=True, roll_number=2)
    BatchStudent.objects.create(batch=batch, student=student_b1, tenant=batch.tenant, is_active=True, roll_number=3)
    BatchStudent.objects.create(batch=batch, student=student_b2, tenant=batch.tenant, is_active=True, roll_number=4)

    # Assign students to teachers
    svc = ClassTeacherAssignmentService(batch.tenant)
    svc.assign(str(student_a1.id), str(batch.id), str(employee_a.id))
    svc.assign(str(student_a2.id), str(batch.id), str(employee_a.id))
    svc.assign(str(student_b1.id), str(batch.id), str(employee_b.id))
    svc.assign(str(student_b2.id), str(batch.id), str(employee_b.id))

    return batch, employee_a, employee_b, [student_a1, student_a2], [student_b1, student_b2]


@pytest.fixture
def setup_subject_teacher_batch(
    db, batch, employee_subject_teacher, student_a1, student_a2, student_b1, student_b2
):
    """Set up a batch with a subject teacher (not a class teacher).

    The subject teacher is linked via Subject.employee, not in batch.class_teachers.
    All 4 students are enrolled.

    Returns: (batch, employee_subject_teacher, [student_a1, student_a2, student_b1, student_b2])
    """
    # Enroll all students
    BatchStudent.objects.create(batch=batch, student=student_a1, tenant=batch.tenant, is_active=True, roll_number=1)
    BatchStudent.objects.create(batch=batch, student=student_a2, tenant=batch.tenant, is_active=True, roll_number=2)
    BatchStudent.objects.create(batch=batch, student=student_b1, tenant=batch.tenant, is_active=True, roll_number=3)
    BatchStudent.objects.create(batch=batch, student=student_b2, tenant=batch.tenant, is_active=True, roll_number=4)

    # Create a subject and assign the subject teacher to it (not as a class teacher)
    Subject.objects.create(
        tenant=batch.tenant,
        batch=batch,
        name="Mathematics",
        code="MATH",
        employee=employee_subject_teacher,
    )

    return batch, employee_subject_teacher, [student_a1, student_a2, student_b1, student_b2]


@pytest.mark.django_db
class TestTeacherPortalAssignmentScoping:
    """Verify teacher portal respects ClassTeacherAssignment boundaries."""

    def test_roster_for_batch_without_employee_returns_all_students(self, setup_multi_teacher_batch):
        """Baseline: roster_for_batch with no employee param returns all active students."""
        batch, _, _, students_a, students_b = setup_multi_teacher_batch
        roster = selectors.roster_for_batch(batch)
        assert len(roster) == 4
        roster_ids = {str(s.id) for s in roster}
        assert all(str(s.id) in roster_ids for s in students_a + students_b)

    def test_roster_for_batch_with_employee_returns_only_assigned_students(
        self, setup_multi_teacher_batch
    ):
        """teacher A only sees their assigned students, not B's."""
        batch, employee_a, employee_b, students_a, students_b = setup_multi_teacher_batch

        # Teacher A's roster
        roster_a = selectors.roster_for_batch(batch, employee=employee_a)
        assert len(roster_a) == 2
        roster_a_ids = {str(s.id) for s in roster_a}
        assert all(str(s.id) in roster_a_ids for s in students_a)
        assert not any(str(s.id) in roster_a_ids for s in students_b)

        # Teacher B's roster
        roster_b = selectors.roster_for_batch(batch, employee=employee_b)
        assert len(roster_b) == 2
        roster_b_ids = {str(s.id) for s in roster_b}
        assert all(str(s.id) in roster_b_ids for s in students_b)
        assert not any(str(s.id) in roster_b_ids for s in students_a)

    def test_teacher_owns_student_checks_real_assignment_not_batch_membership(
        self, setup_multi_teacher_batch
    ):
        """teacher_owns_student uses ClassTeacherAssignment, not batch class_teachers M2M.

        Teacher A is a class teacher of the batch but only owns students A1/A2, not B1/B2.
        """
        batch, employee_a, employee_b, students_a, students_b = setup_multi_teacher_batch

        # Teacher A owns their own students
        assert selectors.teacher_owns_student(employee_a, str(students_a[0].id))
        assert selectors.teacher_owns_student(employee_a, str(students_a[1].id))

        # Teacher A does NOT own teacher B's students
        assert not selectors.teacher_owns_student(employee_a, str(students_b[0].id))
        assert not selectors.teacher_owns_student(employee_a, str(students_b[1].id))

        # Teacher B owns their own students
        assert selectors.teacher_owns_student(employee_b, str(students_b[0].id))
        assert selectors.teacher_owns_student(employee_b, str(students_b[1].id))

        # Teacher B does NOT own teacher A's students
        assert not selectors.teacher_owns_student(employee_b, str(students_a[0].id))
        assert not selectors.teacher_owns_student(employee_b, str(students_a[1].id))

    def test_teacher_owns_student_returns_false_for_nonexistent_student(
        self, setup_multi_teacher_batch
    ):
        """teacher_owns_student returns False for a student who doesn't exist."""
        _, employee_a, _, _, _ = setup_multi_teacher_batch
        fake_id = uuid4()
        assert not selectors.teacher_owns_student(employee_a, str(fake_id))

    def test_batch_serializer_student_count_respects_assignment(self, setup_multi_teacher_batch):
        """TeacherBatchSerializer.get_student_count returns only assigned students.

        This value feeds the frontend's class dropdown and dashboard, so it must
        reflect the teacher's subset, not the whole batch.
        """
        from portal.serializers import TeacherBatchSerializer
        from django.test import RequestFactory

        batch, employee_a, employee_b, _, _ = setup_multi_teacher_batch
        factory = RequestFactory()

        # Simulate a request as teacher A
        request_a = factory.get("/")
        request_a.tenant = batch.tenant

        # Mock role_context (normally set by middleware)
        class RoleContext:
            def __init__(self, profile):
                self.profile = profile
        request_a.role_context = RoleContext(employee_a)

        serializer_a = TeacherBatchSerializer(batch, context={"request": request_a})
        assert serializer_a.data["student_count"] == 2  # Only A's students

        # Simulate a request as teacher B
        request_b = factory.get("/")
        request_b.tenant = batch.tenant
        request_b.role_context = RoleContext(employee_b)

        serializer_b = TeacherBatchSerializer(batch, context={"request": request_b})
        assert serializer_b.data["student_count"] == 2  # Only B's students

    def test_same_class_two_teachers_visibility(self, setup_multi_teacher_batch):
        """End-to-end: two class teachers in Grade 4A have disjoint student visibility.

        This is the core spec scenario: Mrs Banda and Mr Phiri both teach Grade 4A
        but see different rosters (their own assigned students only).
        """
        batch, employee_a, employee_b, students_a, students_b = setup_multi_teacher_batch

        # Simulate the data as it would be returned to each teacher via the API
        roster_a = selectors.roster_for_batch(batch, employee=employee_a)
        roster_b = selectors.roster_for_batch(batch, employee=employee_b)

        roster_a_names = {s.full_name for s in roster_a}
        roster_b_names = {s.full_name for s in roster_b}

        # No overlap
        assert roster_a_names.isdisjoint(roster_b_names)

        # Expected names
        assert "John Doe" in roster_a_names
        assert "Jane Smith" in roster_a_names
        assert "Peter Brown" in roster_b_names
        assert "Ruth Johnson" in roster_b_names


@pytest.mark.django_db
class TestSubjectTeacherVisibility:
    """Verify subject teachers see all students in their batches, not filtered by ClassTeacherAssignment."""

    def test_subject_teacher_roster_includes_all_students(self, setup_subject_teacher_batch):
        """A subject teacher (not a class teacher) sees the full roster."""
        batch, subject_teacher, all_students = setup_subject_teacher_batch

        roster = selectors.roster_for_batch(batch, employee=subject_teacher)
        assert len(roster) == 4
        roster_ids = {str(s.id) for s in roster}
        assert all(str(s.id) in roster_ids for s in all_students)

    def test_subject_teacher_batch_serializer_student_count_full_roster(self, setup_subject_teacher_batch):
        """TeacherBatchSerializer shows full student count for subject teachers."""
        from portal.serializers import TeacherBatchSerializer
        from django.test import RequestFactory

        batch, subject_teacher, all_students = setup_subject_teacher_batch
        factory = RequestFactory()

        request = factory.get("/")
        request.tenant = batch.tenant

        class RoleContext:
            def __init__(self, profile):
                self.profile = profile
        request.role_context = RoleContext(subject_teacher)

        serializer = TeacherBatchSerializer(batch, context={"request": request})
        # Subject teacher should see all 4 students, not a filtered subset
        assert serializer.data["student_count"] == 4

    def test_subject_teacher_marksheet_entry_full_roster(self, setup_subject_teacher_batch):
        """Subject teacher's marksheet entry GET/POST sees all 4 students, not a filtered subset.

        This end-to-end test verifies that marksheet_entries_for_exam() (used by
        TeacherMarkSheetView) returns the full roster for a subject teacher,
        allowing them to enter marks for all students in the batch, not just
        a ClassTeacherAssignment subset (which would be empty for a subject teacher).
        """
        from datetime import datetime
        from core.models import ExamGroup, Exam
        from portal.selectors import marksheet_entries_for_exam

        batch, subject_teacher, all_students = setup_subject_teacher_batch

        # Create an exam group for this batch
        exam_group = ExamGroup.objects.create(
            tenant=batch.tenant,
            batch=batch,
            name="Mid-Term",
            exam_type="Mid-Term",
            exam_date=date(2024, 6, 1),
        )

        # Get the Subject for this subject teacher
        subject = Subject.objects.filter(batch=batch, employee=subject_teacher).first()
        assert subject is not None

        # Create an exam for this exam group and subject
        exam = Exam.objects.create(
            tenant=batch.tenant,
            exam_group=exam_group,
            subject=subject,
            exam_name="Mathematics Mid-Term",
            start_time=datetime(2024, 6, 1, 9, 0),
            end_time=datetime(2024, 6, 1, 11, 0),
            maximum_marks=100,
            minimum_marks=0,
        )

        # Get marksheet entries as the subject teacher
        entries = marksheet_entries_for_exam(exam, employee=subject_teacher)

        # Should see all 4 students, not filtered to ClassTeacherAssignment
        assert len(entries) == 4
        entry_ids = {entry["student_id"] for entry in entries}
        assert all(str(s.id) in entry_ids for s in all_students)
