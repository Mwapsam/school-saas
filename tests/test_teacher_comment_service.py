"""Tests for TeacherCommentService — the single routing read/write path for
teacher report-card comments and signatures.

Covers: layout-based routing, term resolution convergence, cross-portal
save/load symmetry (staff exam-group surface vs portal skills wizard),
report-generation reads, empty-overwrite protection, the skills submission
lock, and the reconcile_teacher_comments command.
"""

import uuid
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client

from core.models import (
    Batch,
    Course,
    Employee,
    ExamGroup,
    ReportTemplate,
    SkillsTeacherComment,
    Student,
    BatchStudent,
    TeacherComment,
    Term,
)
from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
from core.services.exceptions import PermissionException
from core.services.teacher_comment_service import (
    SkillsLockedException,
    TeacherCommentService,
)

User = get_user_model()

SAVE_URL = '/api/teacher-comments/save/'
GET_URL = '/api/teacher-comments/{exam_group_id}/'
PORTAL_URL = '/api/portal/teacher/classes/{batch_id}/skills-comments/'

SIGNATURE = 'data:image/png;base64,AAAA'
OTHER_SIGNATURE = 'data:image/png;base64,BBBB'


@pytest.fixture
def skills_batch(db, academic_year, tenant):
    """A batch whose course name marks it as a SKILLS (Reception) class."""
    course = Course.objects.create(
        course_name="Reception Class",
        code=f"RC{uuid.uuid4().hex[:4].upper()}",
        tenant=tenant,
    )
    return Batch.objects.create(
        name=f"REC-{uuid.uuid4().hex[:4].upper()}",
        course=course,
        academic_year=academic_year,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=330),
        tenant=tenant,
    )


def _exam_group(batch, tenant, with_term=True):
    eg = ExamGroup.objects.create(
        name=f"Exam Plan {uuid.uuid4().hex[:4]}",
        batch=batch,
        exam_type="TERM",
        exam_date=date.today(),
        tenant=tenant,
    )
    if with_term:
        # Phase 3+: Terms are year-scoped, not per-batch. Use academic_year directly.
        # Use get_or_create to handle multiple _exam_group() calls in same test.
        Term.objects.get_or_create(
            tenant=tenant,
            academic_year=batch.academic_year,
            name="Term 1",
            defaults={
                "start_date": date.today() - timedelta(days=30),
                "end_date": date.today() + timedelta(days=30),
            }
        )
    return eg


def _template(batch, tenant, layout):
    return ReportTemplate.objects.create(
        name=f"Template {uuid.uuid4().hex[:4]}",
        # ReportTemplate is unique per (tenant, batch, term, academic_year) and
        # routing never reads template.term, so keep it unique per template.
        term=f"T-{uuid.uuid4().hex[:6]}",
        batch=batch,
        academic_year=batch.academic_year,
        layout_type=layout,
        tenant=tenant,
    )


def _raise_duplicate_key(*_args, **_kwargs):
    """Stand in for the unique-constraint rejection a concurrent INSERT gets."""
    from django.db import IntegrityError
    raise IntegrityError(
        'duplicate key value violates unique constraint '
        '"core_skillsteachercommen_tenant_id_student_id_bat_uniq"'
    )


def _student(batch, tenant):
    student = Student.objects.create(
        first_name="Comment",
        last_name="Student",
        admission_no=f"TCADM{uuid.uuid4().hex[:5].upper()}",
        admission_date=date.today(),
        date_of_birth=date(2018, 1, 1),
        gender="male",
        tenant=tenant,
    )
    BatchStudent.objects.create(
        batch=batch,
        student=student,
        roll_number=f"TC{uuid.uuid4().hex[:3].upper()}",
        tenant=tenant,
    )
    return student


@pytest.mark.django_db
@pytest.mark.unit
class TestRouting:
    def test_skills_template_routes_to_skills(self, tenant, skills_batch):
        eg = _exam_group(skills_batch, tenant)
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        route = TeacherCommentService(tenant=tenant).resolve_route(eg)
        assert route.is_skills
        assert route.term is not None and route.term.name == "Term 1"

    def test_full_template_routes_to_exam_group(self, tenant, batch):
        eg = _exam_group(batch, tenant)
        _template(batch, tenant, ReportTemplate.LAYOUT_FULL)
        route = TeacherCommentService(tenant=tenant).resolve_route(eg)
        assert not route.is_skills
        assert route.exam_group == eg

    def test_no_template_infers_skills_from_course_name(self, tenant, skills_batch):
        eg = _exam_group(skills_batch, tenant)
        route = TeacherCommentService(tenant=tenant).resolve_route(eg)
        assert route.is_skills

    def test_no_template_plain_course_routes_to_exam_group(self, tenant, batch):
        eg = _exam_group(batch, tenant)
        route = TeacherCommentService(tenant=tenant).resolve_route(eg)
        assert not route.is_skills

    def test_explicit_template_overrides_batch_default(self, tenant, skills_batch):
        eg = _exam_group(skills_batch, tenant)
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        full = _template(skills_batch, tenant, ReportTemplate.LAYOUT_FULL)
        route = TeacherCommentService(tenant=tenant).resolve_route(eg, template=full)
        assert not route.is_skills

    def test_portal_and_staff_contexts_key_the_same_term(self, tenant, skills_batch):
        """The wizard's batch context and the staff exam-group context must
        resolve identical routes, or saves land on different rows."""
        eg = _exam_group(skills_batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        staff_route = svc.resolve_route(eg)
        portal_route = svc.skills_route(skills_batch, term_name="Term 1")
        portal_route_no_term = svc.skills_route(skills_batch)
        assert staff_route.term == portal_route.term == portal_route_no_term.term


@pytest.mark.django_db
@pytest.mark.unit
class TestSaveSemantics:
    def _setup(self, tenant, skills_batch):
        eg = _exam_group(skills_batch, tenant)
        student = _student(skills_batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        return svc, svc.resolve_route(eg), student

    def test_save_and_read_roundtrip(self, tenant, skills_batch):
        svc, route, student = self._setup(tenant, skills_batch)
        saved = svc.save_comments(
            route, [{'student_id': str(student.id), 'comment': 'Great term'}], SIGNATURE
        )
        assert saved == 1
        data = svc.get_comments(route)
        assert data['comments'] == [{'student_id': str(student.id), 'comment': 'Great term'}]
        assert data['signature_image'] == SIGNATURE
        # Skills route: rows land in SkillsTeacherComment only.
        assert SkillsTeacherComment.objects.filter(batch=skills_batch).count() == 1
        assert not TeacherComment.objects.filter(exam_group__batch=skills_batch).exists()

    def test_empty_signature_preserves_existing(self, tenant, skills_batch):
        svc, route, student = self._setup(tenant, skills_batch)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'A'}], SIGNATURE)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'B'}], '')
        data = svc.get_comments(route)
        assert data['comments'][0]['comment'] == 'B'
        assert data['signature_image'] == SIGNATURE

    def test_clear_signature_flag_clears(self, tenant, skills_batch):
        svc, route, student = self._setup(tenant, skills_batch)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'A'}], SIGNATURE)
        svc.save_comments(
            route, [{'student_id': str(student.id), 'comment': 'A'}], '',
            clear_signature=True,
        )
        assert svc.get_comments(route)['signature_image'] == ''

    def test_cleared_flag_is_explicit_clear(self, tenant, skills_batch):
        svc, route, student = self._setup(tenant, skills_batch)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'A'}], SIGNATURE)
        svc.save_comments(
            route, [{'student_id': str(student.id), 'comment': '', 'cleared': True}], ''
        )
        assert svc.get_comments(route)['comments'][0]['comment'] == ''

    def test_bare_empty_comment_without_cleared_flag_preserves_existing(self, tenant, skills_batch):
        """A payload that arrives with a blank comment but no explicit
        `cleared: True` must not wipe out previously-saved content — this
        protects against a caller that resubmits the whole roster before a
        student's real comment has loaded (the "comments disappeared
        overnight" report)."""
        svc, route, student = self._setup(tenant, skills_batch)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'A'}], SIGNATURE)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': ''}], '')
        assert svc.get_comments(route)['comments'][0]['comment'] == 'A'

    def test_absent_student_untouched(self, tenant, skills_batch):
        svc, route, student = self._setup(tenant, skills_batch)
        other = _student(skills_batch, tenant)
        svc.save_comments(route, [
            {'student_id': str(student.id), 'comment': 'A'},
            {'student_id': str(other.id), 'comment': 'B'},
        ], SIGNATURE)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'A2'}], '')
        by_sid = svc.get_comments_map(route)
        assert by_sid[str(student.id)]['comment'] == 'A2'
        assert by_sid[str(other.id)]['comment'] == 'B'

    def test_invalid_student_ids_skipped(self, tenant, skills_batch):
        svc, route, student = self._setup(tenant, skills_batch)
        saved = svc.save_comments(
            route,
            [
                {'student_id': str(student.id), 'comment': 'A'},
                {'student_id': str(uuid.uuid4()), 'comment': 'ghost'},
            ],
            '',
            valid_student_ids={str(student.id)},
        )
        assert saved == 1

    def test_no_duplicate_rows_for_null_term(self, tenant, skills_batch):
        """unique_together doesn't cover term=None in Postgres — repeated saves
        must still hit one row."""
        _exam_group(skills_batch, tenant, with_term=False)
        student = _student(skills_batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        route = svc.skills_route(skills_batch)
        assert route.term is None
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'A'}], '')
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'B'}], '')
        rows = SkillsTeacherComment.objects.filter(batch=skills_batch, term=None)
        assert rows.count() == 1
        assert rows.first().comment == 'B'

    def test_lost_insert_race_falls_back_to_the_winning_row(self, tenant, skills_batch):
        """Two writers saving a student's *first* comment both take the INSERT
        branch; the unique constraint rejects the loser. That must not abort the
        whole roster's save — the loser re-reads the row that won and applies
        its payload on top.

        The rejection is injected rather than raced for real: the constraint
        itself is asserted by the model Meta and migration 0117, and tests run
        against a database whose schema is not rebuilt per run (see the no-op
        django_db_setup in conftest), so depending on it here would make this
        test assert the DB's migration state instead of the recovery logic.
        """
        svc, route, student = self._setup(tenant, skills_batch)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'Winner'}], '')

        real = svc._row_for_student
        calls = []

        def racing_row_for_student(*args, **kwargs):
            calls.append(1)
            if len(calls) > 1:
                return real(*args, **kwargs)
            # The losing writer's state: a fresh unsaved row for a key that a
            # concurrent writer has already inserted, so the INSERT is rejected.
            row = SkillsTeacherComment(
                tenant=tenant, student_id=str(student.id),
                batch=route.batch, term=route.term,
            )
            row.save = _raise_duplicate_key
            return row

        svc._row_for_student = racing_row_for_student
        saved = svc.save_comments(
            route, [{'student_id': str(student.id), 'comment': 'Loser retry'}], ''
        )

        assert saved == 1
        rows = SkillsTeacherComment.objects.filter(batch=skills_batch, student=student)
        assert rows.count() == 1
        assert rows.first().comment == 'Loser retry'

    def test_skills_lock_blocks_save(self, tenant, skills_batch):
        from portal.models import SkillsSubmission
        svc, route, student = self._setup(tenant, skills_batch)
        SkillsSubmission.objects.create(
            batch=skills_batch, term=route.term,
            status=SkillsSubmission.STATUS_SUBMITTED, tenant=tenant,
        )
        with pytest.raises(SkillsLockedException):
            svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'A'}], '')

    def test_lock_does_not_affect_exam_group_route(self, tenant, batch):
        from portal.models import SkillsSubmission
        eg = _exam_group(batch, tenant)
        student = _student(batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(eg)
        SkillsSubmission.objects.create(
            batch=batch, term=None,
            status=SkillsSubmission.STATUS_SUBMITTED, tenant=tenant,
        )
        saved = svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'A'}], '')
        assert saved == 1
        assert TeacherComment.objects.filter(exam_group=eg).count() == 1


@pytest.mark.django_db
@pytest.mark.integration
class TestReportGenerationReads:
    def test_skills_layout_reads_skills_row_only(self, tenant, skills_batch):
        from core.services.report_generation_service import ReportGenerationService
        eg = _exam_group(skills_batch, tenant)
        template = _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        student = _student(skills_batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        svc.save_comments(
            svc.skills_route(skills_batch, "Term 1"),
            [{'student_id': str(student.id), 'comment': 'Skills comment'}], SIGNATURE,
        )
        # A stale exam-group row must be ignored, not merged per-field.
        TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Stale staff comment', signature_image=OTHER_SIGNATURE,
        )
        report_svc = ReportGenerationService(tenant=tenant)
        row = report_svc._get_teacher_comment_data(student, eg, template=template)
        assert row == {'comment': 'Skills comment', 'signature_image': SIGNATURE}

    def test_full_layout_reads_teacher_comment_only(self, tenant, batch):
        from core.services.report_generation_service import ReportGenerationService
        eg = _exam_group(batch, tenant)
        template = _template(batch, tenant, ReportTemplate.LAYOUT_FULL)
        student = _student(batch, tenant)
        TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Exam comment', signature_image=SIGNATURE,
        )
        SkillsTeacherComment.objects.create(
            tenant=tenant, student=student, batch=batch, term=None,
            comment='Skills comment', signature_image=OTHER_SIGNATURE,
        )
        report_svc = ReportGenerationService(tenant=tenant)
        row = report_svc._get_teacher_comment_data(student, eg, template=template)
        assert row == {'comment': 'Exam comment', 'signature_image': SIGNATURE}


@pytest.mark.django_db
@pytest.mark.integration
class TestCrossPortalEndpoints:
    """The staff exam-group endpoints and the portal skills wizard must
    read/write the same rows for a SKILLS batch."""

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def tenant(self, school, domain):
        return school

    @pytest.fixture
    def admin_client(self, client, tenant):
        suffix = uuid.uuid4().hex[:6]
        u = User(
            username=f"tcadmin_{suffix}",
            email=f"tcadmin_{suffix}@example.com",
            first_name="TC", last_name="Admin", is_admin=True,
        )
        u.set_password("testpass123")
        u.save()
        u.tenants.add(tenant)
        client.force_login(u)
        return client

    @pytest.fixture
    def teacher_client(self, tenant, skills_batch):
        from core.models import Employee
        suffix = uuid.uuid4().hex[:6]
        user = User(
            username=f"tcteacher_{suffix}",
            email=f"tcteacher_{suffix}@example.com",
            first_name="TC", last_name="Teacher",
        )
        user.set_password("testpass123")
        user.save()
        user.tenants.add(tenant)
        employee = Employee.objects.create(
            first_name="TC", last_name="Teacher",
            employee_number=f"TCEMP{uuid.uuid4().hex[:5].upper()}",
            joining_date=date.today(), gender=True,
            tenant=tenant, user=user,
        )
        skills_batch.class_teachers.add(employee)
        c = Client()
        c.force_login(user)
        return c

    def test_staff_save_visible_in_portal(self, tenant, skills_batch, admin_client, teacher_client):
        eg = _exam_group(skills_batch, tenant)
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        student = _student(skills_batch, tenant)

        resp = admin_client.post(SAVE_URL, {
            'exam_group_id': str(eg.id),
            'comments': [{'student_id': str(student.id), 'comment': 'From staff'}],
            'signature_image': SIGNATURE,
        }, content_type='application/json')
        assert resp.status_code == 200, resp.content
        assert resp.json()['saved_count'] == 1

        # Canonical row is the skills one; no exam-group row created.
        assert SkillsTeacherComment.objects.filter(batch=skills_batch).count() == 1
        assert not TeacherComment.objects.filter(exam_group=eg).exists()

        portal = teacher_client.get(
            PORTAL_URL.format(batch_id=skills_batch.id), {'term': 'Term 1'}
        )
        assert portal.status_code == 200, portal.content
        body = portal.json()
        assert body['comments'] == [{'student_id': str(student.id), 'comment': 'From staff'}]
        assert body['signature_image'] == SIGNATURE

    def test_portal_save_visible_to_staff(self, tenant, skills_batch, admin_client, teacher_client):
        eg = _exam_group(skills_batch, tenant)
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        student = _student(skills_batch, tenant)

        resp = teacher_client.post(
            PORTAL_URL.format(batch_id=skills_batch.id),
            {
                'term': 'Term 1',
                'comments': [{'student_id': str(student.id), 'comment': 'From portal'}],
                'signature_image': SIGNATURE,
            },
            content_type='application/json',
        )
        assert resp.status_code == 200, resp.content
        assert resp.json()['saved'] == 1

        staff = admin_client.get(GET_URL.format(exam_group_id=eg.id))
        assert staff.status_code == 200, staff.content
        body = staff.json()
        assert body['comments'] == [{'student_id': str(student.id), 'comment': 'From portal'}]
        assert body['signature_image'] == SIGNATURE

    def test_non_skills_batch_uses_teacher_comment(self, tenant, batch, admin_client):
        eg = _exam_group(batch, tenant)
        _template(batch, tenant, ReportTemplate.LAYOUT_FULL)
        student = _student(batch, tenant)

        resp = admin_client.post(SAVE_URL, {
            'exam_group_id': str(eg.id),
            'comments': [{'student_id': str(student.id), 'comment': 'Marks comment'}],
            'signature_image': SIGNATURE,
        }, content_type='application/json')
        assert resp.status_code == 200, resp.content
        assert TeacherComment.objects.filter(exam_group=eg).count() == 1
        assert not SkillsTeacherComment.objects.filter(batch=batch).exists()

        staff = admin_client.get(GET_URL.format(exam_group_id=eg.id))
        assert staff.json()['comments'][0]['comment'] == 'Marks comment'

    def test_teacher_session_not_gated_from_shared_endpoint(
        self, tenant, batch, teacher_client
    ):
        """DashboardAccessMiddleware gates the `core`-namespaced dashboard to
        `is_admin` accounts, but SAVE_URL/GET_URL are explicitly shared with
        the JWT-authenticated teacher portal (see save_teacher_comments_api's
        docstring) and must stay reachable by a non-admin teacher — otherwise
        the middleware silently 302s every portal comment save/load, as it
        did in production before /api/teacher-comments/ was added to that
        middleware's skip list."""
        eg = _exam_group(batch, tenant)
        _template(batch, tenant, ReportTemplate.LAYOUT_FULL)
        student = _student(batch, tenant)

        resp = teacher_client.post(SAVE_URL, {
            'exam_group_id': str(eg.id),
            'comments': [{'student_id': str(student.id), 'comment': 'From teacher session'}],
            'signature_image': SIGNATURE,
        }, content_type='application/json')
        assert resp.status_code == 200, resp.content
        assert resp.json()['saved_count'] == 1

        get_resp = teacher_client.get(GET_URL.format(exam_group_id=eg.id))
        assert get_resp.status_code == 200, get_resp.content
        assert get_resp.json()['comments'][0]['comment'] == 'From teacher session'

    def test_staff_save_blocked_when_skills_submitted(self, tenant, skills_batch, admin_client):
        from portal.models import SkillsSubmission
        eg = _exam_group(skills_batch, tenant)
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        student = _student(skills_batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        SkillsSubmission.objects.create(
            batch=skills_batch, term=svc.resolve_route(eg).term,
            status=SkillsSubmission.STATUS_SUBMITTED, tenant=tenant,
        )
        resp = admin_client.post(SAVE_URL, {
            'exam_group_id': str(eg.id),
            'comments': [{'student_id': str(student.id), 'comment': 'X'}],
            'signature_image': '',
        }, content_type='application/json')
        assert resp.status_code == 400
        assert 'locked' in resp.json()['error']


@pytest.mark.django_db
@pytest.mark.integration
class TestReconcileCommand:
    def _dual_rows(self, tenant, skills_batch):
        """A skills batch with a stray TeacherComment row and a canonical
        skills row, as the pre-refactor code could produce."""
        eg = _exam_group(skills_batch, tenant)
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        student = _student(skills_batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        term = svc.resolve_route(eg).term
        stray = TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Newer staff comment', signature_image='',
        )
        canonical = SkillsTeacherComment.objects.create(
            tenant=tenant, student=student, batch=skills_batch, term=term,
            comment='Older portal comment', signature_image=SIGNATURE,
        )
        # Make the stray row the most recently updated one.
        SkillsTeacherComment.objects.filter(pk=canonical.pk).update(
            updated_at=stray.updated_at - timedelta(days=1)
        )
        canonical.refresh_from_db()
        return eg, student, stray, canonical

    def test_dry_run_changes_nothing(self, tenant, skills_batch):
        eg, student, stray, canonical = self._dual_rows(tenant, skills_batch)
        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(skills_batch.id),
        )
        assert TeacherComment.objects.filter(pk=stray.pk).exists()
        canonical.refresh_from_db()
        assert canonical.comment == 'Older portal comment'

    def test_execute_merges_and_deletes(self, tenant, skills_batch):
        eg, student, stray, canonical = self._dual_rows(tenant, skills_batch)
        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(skills_batch.id), execute=True,
        )
        assert not TeacherComment.objects.filter(pk=stray.pk).exists()
        canonical.refresh_from_db()
        # Newest non-empty comment wins; existing signature kept (stray had none).
        assert canonical.comment == 'Newer staff comment'
        assert canonical.signature_image == SIGNATURE
        assert SkillsTeacherComment.objects.filter(batch=skills_batch).count() == 1

    def test_execute_moves_row_when_no_skills_row_exists(self, tenant, skills_batch):
        eg = _exam_group(skills_batch, tenant)
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        student = _student(skills_batch, tenant)
        TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Only staff comment', signature_image=SIGNATURE,
        )
        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(skills_batch.id), execute=True,
        )
        assert not TeacherComment.objects.filter(exam_group=eg).exists()
        row = SkillsTeacherComment.objects.get(batch=skills_batch)
        assert row.comment == 'Only staff comment'
        assert row.signature_image == SIGNATURE
        assert row.term is not None and row.term.name == 'Term 1'

    def test_rerun_is_noop(self, tenant, skills_batch):
        self._dual_rows(tenant, skills_batch)
        for _ in range(2):
            call_command(
                'reconcile_teacher_comments',
                tenant=tenant.schema_name, batch=str(skills_batch.id), execute=True,
            )
        assert SkillsTeacherComment.objects.filter(batch=skills_batch).count() == 1
        assert not TeacherComment.objects.filter(exam_group__batch=skills_batch).exists()

    def test_several_strays_converge_on_one_target_without_losing_content(
        self, tenant, skills_batch
    ):
        """The common shape: a student has a stray TeacherComment in each of a
        batch's exam groups, and all of them resolve to the same (student,
        term) skills row. Folding them one at a time re-read the target's
        `updated_at`, which `save()` bumps to now — so every stray after the
        first lost the recency tie-break and was deleted with its content."""
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        # Both exam groups carry "Term 1", so both strays resolve to the same
        # skills row — the convergence this test is about.
        eg_old = _exam_group(skills_batch, tenant)
        eg_new = _exam_group(skills_batch, tenant)
        student = _student(skills_batch, tenant)

        older = TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg_old,
            comment='Older comment', signature_image=SIGNATURE,
        )
        newer = TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg_new,
            comment='Newer comment', signature_image='',
        )
        TeacherComment.objects.filter(pk=older.pk).update(
            updated_at=newer.updated_at - timedelta(days=1)
        )

        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(skills_batch.id), execute=True,
        )

        rows = SkillsTeacherComment.objects.filter(batch=skills_batch, student=student)
        assert rows.count() == 1
        row = rows.first()
        # Newest content wins the field it fills; the older row still gets to
        # supply the signature the newer one didn't have.
        assert row.comment == 'Newer comment'
        assert row.signature_image == SIGNATURE
        assert not TeacherComment.objects.filter(student=student).exists()

    def test_older_stray_cannot_overwrite_a_newer_strays_text(
        self, tenant, skills_batch
    ):
        """Two strays folding into a target that *already exists*. Ranking each
        stray against one fixed baseline let the older one clear the bar a
        second time and overwrite the text the newer one had just written —
        which was then deleted along with its row. Each field must instead be
        ranked against whichever row currently supplies it."""
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        eg_mid = _exam_group(skills_batch, tenant)
        eg_new = _exam_group(skills_batch, tenant)
        student = _student(skills_batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        term = svc.resolve_route(eg_new).term

        newest = TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg_new,
            comment='Newest comment',
        )
        middle = TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg_mid,
            comment='Middle comment',
        )
        target = SkillsTeacherComment.objects.create(
            tenant=tenant, student=student, batch=skills_batch, term=term,
            comment='Oldest target comment', signature_image=SIGNATURE,
        )
        # newest > middle > target, so both strays out-rank the target and the
        # order they are folded in decides the outcome.
        TeacherComment.objects.filter(pk=middle.pk).update(
            updated_at=newest.updated_at - timedelta(days=1)
        )
        SkillsTeacherComment.objects.filter(pk=target.pk).update(
            updated_at=newest.updated_at - timedelta(days=2)
        )

        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(skills_batch.id), execute=True,
        )

        target.refresh_from_db()
        assert target.comment == 'Newest comment'
        assert not TeacherComment.objects.filter(student=student).exists()

    def test_stamp_follows_the_comment_into_an_unstamped_target(
        self, tenant, skills_batch
    ):
        """The migration moves class_teacher with the comment text; the command
        has to agree, or folding a stamped stray into an unstamped target drops
        the stamp and the report card loses its signature."""
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        eg = _exam_group(skills_batch, tenant)
        student = _student(skills_batch, tenant)
        teacher = _employee(tenant, "Stamp")
        svc = TeacherCommentService(tenant=tenant)
        term = svc.resolve_route(eg).term

        stray = TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Stamped stray', class_teacher=teacher,
        )
        target = SkillsTeacherComment.objects.create(
            tenant=tenant, student=student, batch=skills_batch, term=term,
            comment='Older target', class_teacher=None,
        )
        SkillsTeacherComment.objects.filter(pk=target.pk).update(
            updated_at=stray.updated_at - timedelta(days=1)
        )

        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(skills_batch.id), execute=True,
        )

        target.refresh_from_db()
        assert target.comment == 'Stamped stray'
        assert target.class_teacher_id == teacher.id

    def test_unstamped_stray_does_not_erase_the_targets_stamp(
        self, tenant, skills_batch
    ):
        """A NULL stamp means "we don't know who was responsible", not
        "nobody", so a legacy stray without one must not null a stamp the
        target has — even when its comment text wins."""
        _template(skills_batch, tenant, ReportTemplate.LAYOUT_SKILLS)
        eg = _exam_group(skills_batch, tenant)
        student = _student(skills_batch, tenant)
        teacher = _employee(tenant, "Kept")
        svc = TeacherCommentService(tenant=tenant)
        term = svc.resolve_route(eg).term

        stray = TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Legacy stray', class_teacher=None,
        )
        target = SkillsTeacherComment.objects.create(
            tenant=tenant, student=student, batch=skills_batch, term=term,
            comment='Older target', class_teacher=teacher,
        )
        SkillsTeacherComment.objects.filter(pk=target.pk).update(
            updated_at=stray.updated_at - timedelta(days=1)
        )

        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(skills_batch.id), execute=True,
        )

        target.refresh_from_db()
        assert target.comment == 'Legacy stray'
        assert target.class_teacher_id == teacher.id

    def test_full_layout_batch_untouched(self, tenant, batch):
        eg = _exam_group(batch, tenant)
        _template(batch, tenant, ReportTemplate.LAYOUT_FULL)
        student = _student(batch, tenant)
        TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Marks comment', signature_image=SIGNATURE,
        )
        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(batch.id), execute=True,
        )
        assert TeacherComment.objects.filter(exam_group=eg).count() == 1
        assert not SkillsTeacherComment.objects.filter(batch=batch).exists()

    def test_reverse_moves_stray_skills_row_when_batch_no_longer_skills(self, tenant, batch):
        """A batch that used to route to SkillsTeacherComment (e.g. before an
        admin changed its default report template) can leave stray rows
        there even though the batch is currently non-SKILLS layout. The
        command must fold in this direction too, not just skills-ward."""
        eg = _exam_group(batch, tenant)
        _template(batch, tenant, ReportTemplate.LAYOUT_FULL)
        student = _student(batch, tenant)
        stray = SkillsTeacherComment.objects.create(
            tenant=tenant, student=student, batch=batch, term=None,
            comment='Stray skills comment', signature_image=SIGNATURE,
        )
        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(batch.id), execute=True,
        )
        assert not SkillsTeacherComment.objects.filter(pk=stray.pk).exists()
        row = TeacherComment.objects.get(exam_group=eg, student=student)
        assert row.comment == 'Stray skills comment'
        assert row.signature_image == SIGNATURE

    def test_reverse_folds_into_existing_teacher_comment_row(self, tenant, batch):
        eg = _exam_group(batch, tenant)
        _template(batch, tenant, ReportTemplate.LAYOUT_FULL)
        student = _student(batch, tenant)
        canonical = TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Older exam-group comment', signature_image='',
        )
        stray = SkillsTeacherComment.objects.create(
            tenant=tenant, student=student, batch=batch, term=None,
            comment='Newer skills comment', signature_image=SIGNATURE,
        )
        TeacherComment.objects.filter(pk=canonical.pk).update(
            updated_at=stray.updated_at - timedelta(days=1)
        )
        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(batch.id), execute=True,
        )
        assert not SkillsTeacherComment.objects.filter(pk=stray.pk).exists()
        canonical.refresh_from_db()
        assert canonical.comment == 'Newer skills comment'
        assert canonical.signature_image == SIGNATURE

    def test_reverse_dry_run_changes_nothing(self, tenant, batch):
        eg = _exam_group(batch, tenant)
        _template(batch, tenant, ReportTemplate.LAYOUT_FULL)
        student = _student(batch, tenant)
        stray = SkillsTeacherComment.objects.create(
            tenant=tenant, student=student, batch=batch, term=None,
            comment='Stray skills comment', signature_image=SIGNATURE,
        )
        call_command(
            'reconcile_teacher_comments',
            tenant=tenant.schema_name, batch=str(batch.id),
        )
        assert SkillsTeacherComment.objects.filter(pk=stray.pk).exists()
        assert not TeacherComment.objects.filter(exam_group=eg, student=student).exists()


def _employee(tenant, tag):
    return Employee.objects.create(
        first_name=tag, last_name="Teacher",
        employee_number=f"MT{tag}{uuid.uuid4().hex[:5].upper()}",
        joining_date=date.today(), gender=True, tenant=tenant,
    )


@pytest.mark.django_db
@pytest.mark.unit
class TestMultiTeacherIdentity:
    """Comment rows are keyed by (student, period) only. `class_teacher` is a
    stamp of who was resolved as responsible at the last save — used for
    display and grouping, never for row identity — so a reassignment restamps
    the student's one row instead of starting a second one. See
    class_teacher_assignment_service for how the teacher is resolved."""

    def _two_teachers(self, tenant, batch):
        a, b = _employee(tenant, "A"), _employee(tenant, "B")
        batch.class_teachers.add(a, b)
        return a, b

    def test_comments_isolated_between_teachers(self, tenant, batch):
        teacher_a, teacher_b = self._two_teachers(tenant, batch)
        student_a, student_b = _student(batch, tenant), _student(batch, tenant)
        assign_svc = ClassTeacherAssignmentService(tenant)
        assign_svc.assign(str(student_a.id), str(batch.id), str(teacher_a.id))
        assign_svc.assign(str(student_b.id), str(batch.id), str(teacher_b.id))

        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(_exam_group(batch, tenant))
        svc.save_comments(route, [{'student_id': str(student_a.id), 'comment': 'From A'}],
                          acting_teacher=teacher_a)
        svc.save_comments(route, [{'student_id': str(student_b.id), 'comment': 'From B'}],
                          acting_teacher=teacher_b)

        by_sid = svc.get_comments_map(route)
        assert by_sid[str(student_a.id)]['comment'] == 'From A'
        assert by_sid[str(student_b.id)]['comment'] == 'From B'
        assert by_sid[str(student_a.id)]['class_teacher_id'] == str(teacher_a.id)
        assert by_sid[str(student_b.id)]['class_teacher_id'] == str(teacher_b.id)

    def test_teacher_cannot_save_for_unassigned_student(self, tenant, batch):
        teacher_a, teacher_b = self._two_teachers(tenant, batch)
        student_b = _student(batch, tenant)
        ClassTeacherAssignmentService(tenant).assign(
            str(student_b.id), str(batch.id), str(teacher_b.id)
        )

        eg = _exam_group(batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(eg)

        with pytest.raises(PermissionException):
            svc.save_comments(
                route, [{'student_id': str(student_b.id), 'comment': 'Hijack'}],
                acting_teacher=teacher_a,
            )
        assert not TeacherComment.objects.filter(exam_group=eg, student=student_b).exists()

    def test_admin_save_unaffected_by_ownership_check(self, tenant, batch):
        """acting_teacher is opt-in — the staff/admin path (which omits it)
        may still save on a student's behalf regardless of assignment."""
        teacher_a, teacher_b = self._two_teachers(tenant, batch)
        student_b = _student(batch, tenant)
        ClassTeacherAssignmentService(tenant).assign(
            str(student_b.id), str(batch.id), str(teacher_b.id)
        )
        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(_exam_group(batch, tenant))
        saved = svc.save_comments(
            route, [{'student_id': str(student_b.id), 'comment': 'Admin edit'}],
        )
        assert saved == 1

    def test_reassignment_restamps_the_single_row(self, tenant, batch):
        """Reassignment must not fork a student's comment into a second row:
        the one row survives, keeps showing A's comment until B writes, and is
        restamped to B when B does."""
        teacher_a, teacher_b = self._two_teachers(tenant, batch)
        student = _student(batch, tenant)
        assign_svc = ClassTeacherAssignmentService(tenant)
        assign_svc.assign(str(student.id), str(batch.id), str(teacher_a.id))

        eg = _exam_group(batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(eg)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'From A'}],
                          acting_teacher=teacher_a)

        assign_svc.assign(str(student.id), str(batch.id), str(teacher_b.id))
        assert svc.get_comments_map(route)[str(student.id)]['comment'] == 'From A'
        assert TeacherComment.objects.filter(exam_group=eg, student=student).count() == 1

        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'From B'}],
                          acting_teacher=teacher_b)
        by_sid = svc.get_comments_map(route)
        assert by_sid[str(student.id)]['comment'] == 'From B'
        assert by_sid[str(student.id)]['class_teacher_id'] == str(teacher_b.id)
        assert TeacherComment.objects.filter(exam_group=eg, student=student).count() == 1

    def test_new_teacher_can_clear_a_previous_teachers_comment(self, tenant, batch):
        """Regression: an explicit clear by the newly assigned teacher must
        take effect. While rows were keyed by (student, teacher), B's clear
        landed on B's own row and A's stale contentful row kept winning the
        read forever, so the teacher's deletion silently never applied."""
        teacher_a, teacher_b = self._two_teachers(tenant, batch)
        student = _student(batch, tenant)
        assign_svc = ClassTeacherAssignmentService(tenant)
        assign_svc.assign(str(student.id), str(batch.id), str(teacher_a.id))

        eg = _exam_group(batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(eg)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'From A'}],
                          acting_teacher=teacher_a)

        assign_svc.assign(str(student.id), str(batch.id), str(teacher_b.id))
        svc.save_comments(
            route,
            [{'student_id': str(student.id), 'comment': '', 'cleared': True}],
            acting_teacher=teacher_b,
        )
        assert svc.get_comments_map(route)[str(student.id)]['comment'] == ''
        assert TeacherComment.objects.filter(exam_group=eg, student=student).count() == 1

    def test_stale_matching_row_does_not_shadow_newer_reassigned_comment(self, tenant, batch):
        """Regression for the "comments disappeared overnight" report: a
        legacy row (class_teacher=NULL) is the student's row, so a later save
        under a resolved teacher updates it in place — it can never linger as
        a second, competing row."""
        teacher_a = _employee(tenant, "A")
        batch.class_teachers.add(teacher_a)  # sole teacher for now
        student = _student(batch, tenant)
        eg = _exam_group(batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(eg)

        TeacherComment.objects.create(
            tenant=tenant, student=student, exam_group=eg,
            comment='Legacy stale comment', class_teacher=None,
        )
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'From A'}],
                          acting_teacher=teacher_a)
        assert TeacherComment.objects.filter(exam_group=eg, student=student).count() == 1

        # Pool becomes ambiguous (a second teacher added, no explicit
        # per-student assignment yet) — today's resolved teacher is None,
        # which matches the legacy row's class_teacher=NULL.
        batch.class_teachers.add(_employee(tenant, "B"))

        by_sid = svc.get_comments_map(route)
        assert by_sid[str(student.id)]['comment'] == 'From A'

    def test_unresolvable_teacher_does_not_erase_the_stamp(self, tenant, batch):
        """An unresolvable teacher means "we don't know today", not "nobody".
        Once row identity stopped including class_teacher, a save on a batch
        that had just become multi-teacher nulled the existing stamp — costing
        the report card its class-teacher signature and dropping the student
        into the UNASSIGNED group."""
        teacher_a = _employee(tenant, "A")
        batch.class_teachers.add(teacher_a)  # sole teacher, so resolution works
        student = _student(batch, tenant)
        eg = _exam_group(batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(eg)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'From A'}],
                          acting_teacher=teacher_a)

        # Pool becomes ambiguous with no per-student assignment, so
        # get_assigned_employee now returns None.
        batch.class_teachers.add(_employee(tenant, "B"))
        assert ClassTeacherAssignmentService(tenant).get_assigned_employee(
            str(student.id), batch
        ) is None

        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'Edited by staff'}])

        by_sid = svc.get_comments_map(route)
        assert by_sid[str(student.id)]['comment'] == 'Edited by staff'
        assert by_sid[str(student.id)]['class_teacher_id'] == str(teacher_a.id)

    def test_untouched_blank_payload_after_reassignment_preserves_comment(self, tenant, batch):
        """Regression for the "comments disappeared overnight" report: after a
        reassignment the new teacher's page submits the whole roster, and
        students whose comment never loaded arrive blank and untouched. Those
        must leave the saved comment alone (only `cleared: True` overwrites)."""
        teacher_a, teacher_b = self._two_teachers(tenant, batch)
        student = _student(batch, tenant)
        assign_svc = ClassTeacherAssignmentService(tenant)
        assign_svc.assign(str(student.id), str(batch.id), str(teacher_a.id))

        eg = _exam_group(batch, tenant)
        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(eg)
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': 'Real comment'}],
                          acting_teacher=teacher_a)

        assign_svc.assign(str(student.id), str(batch.id), str(teacher_b.id))
        svc.save_comments(route, [{'student_id': str(student.id), 'comment': ''}],
                          acting_teacher=teacher_b)

        assert TeacherComment.objects.filter(exam_group=eg, student=student).count() == 1
        assert svc.get_comments_map(route)[str(student.id)]['comment'] == 'Real comment'

    def test_get_comments_grouped_by_teacher(self, tenant, batch):
        teacher_a, teacher_b = self._two_teachers(tenant, batch)
        student_a, student_b = _student(batch, tenant), _student(batch, tenant)
        assign_svc = ClassTeacherAssignmentService(tenant)
        assign_svc.assign(str(student_a.id), str(batch.id), str(teacher_a.id))
        assign_svc.assign(str(student_b.id), str(batch.id), str(teacher_b.id))

        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(_exam_group(batch, tenant))
        svc.save_comments(route, [
            {'student_id': str(student_a.id), 'comment': 'From A'},
            {'student_id': str(student_b.id), 'comment': 'From B'},
        ])

        grouped = svc.get_comments_grouped_by_teacher(route)
        assert set(grouped.keys()) == {str(teacher_a.id), str(teacher_b.id)}
        assert grouped[str(teacher_a.id)]['students'] == [
            {'student_id': str(student_a.id), 'comment': 'From A'}
        ]
        assert grouped[str(teacher_b.id)]['students'] == [
            {'student_id': str(student_b.id), 'comment': 'From B'}
        ]

    def test_skills_lock_scoped_to_acting_teacher(self, tenant, skills_batch):
        from portal.models import SkillsSubmission
        _exam_group(skills_batch, tenant)  # establishes "Term 1" on the batch
        teacher_a, teacher_b = self._two_teachers(tenant, skills_batch)
        student_a, student_b = _student(skills_batch, tenant), _student(skills_batch, tenant)
        assign_svc = ClassTeacherAssignmentService(tenant)
        assign_svc.assign(str(student_a.id), str(skills_batch.id), str(teacher_a.id))
        assign_svc.assign(str(student_b.id), str(skills_batch.id), str(teacher_b.id))

        svc = TeacherCommentService(tenant=tenant)
        route = svc.skills_route(skills_batch, term_name="Term 1")
        SkillsSubmission.objects.create(
            tenant=tenant, batch=skills_batch, term=route.term,
            employee=teacher_a, status=SkillsSubmission.STATUS_SUBMITTED,
        )

        with pytest.raises(SkillsLockedException):
            svc.save_comments(
                route, [{'student_id': str(student_a.id), 'comment': 'x'}],
                acting_teacher=teacher_a,
            )

        saved = svc.save_comments(
            route, [{'student_id': str(student_b.id), 'comment': 'From B'}],
            acting_teacher=teacher_b,
        )
        assert saved == 1


@pytest.mark.unit
class TestCollapseMigration:
    """The 0117 data migration that folded the pre-existing per-teacher rows
    into one row per (student, route) before the tighter unique_together could
    be applied."""

    # The pre-migration state (several rows per student) can no longer be
    # built through the ORM — the tightened unique_together forbids it — so
    # the merge rule is pinned directly on the migration's fold helper.
    @staticmethod
    def _fold_group():
        from importlib import import_module
        return import_module(
            'core.migrations.0117_collapse_teacher_comment_rows'
        )._fold_group

    @staticmethod
    def _row(pk, minutes_old, comment='', signature='', teacher=None):
        from datetime import datetime, timezone as dt_timezone
        from types import SimpleNamespace
        return SimpleNamespace(
            pk=pk,
            updated_at=datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
            - timedelta(minutes=minutes_old),
            comment=comment,
            signature_image=signature,
            class_teacher_id=teacher,
        )

    def test_newest_row_survives_and_inherits_the_only_comment(self):
        """The shape a reassignment used to leave behind: a contentful row
        under teacher A plus a newer blank row under teacher B. The blank row
        survives (it is newest) but inherits the comment, signature and stamp
        it had no value of its own for."""
        old = self._row('a', minutes_old=10, comment='From A',
                        signature=SIGNATURE, teacher='emp-a')
        newest_blank = self._row('b', minutes_old=1, teacher='emp-b')

        survivor, losers = self._fold_group()([old, newest_blank])

        assert survivor is newest_blank
        assert [r.pk for r in losers] == ['a']
        assert survivor.comment == 'From A'
        assert survivor.signature_image == SIGNATURE
        # The stamp follows the comment text it belongs to.
        assert survivor.class_teacher_id == 'emp-a'

    def test_newest_content_wins_and_is_never_overwritten(self):
        """A loser can only fill a field the survivor left blank — it must
        never overwrite a newer value, and among losers the freshest wins."""
        oldest = self._row('a', minutes_old=30, comment='Oldest',
                           signature=OTHER_SIGNATURE, teacher='emp-a')
        middle = self._row('b', minutes_old=20, comment='Middle', teacher='emp-b')
        newest = self._row('c', minutes_old=1, comment='Newest', teacher='emp-c')

        survivor, losers = self._fold_group()([oldest, middle, newest])

        assert survivor is newest
        assert survivor.comment == 'Newest'
        assert survivor.class_teacher_id == 'emp-c'
        # Only the blank signature was filled in, from the one row that had it.
        assert survivor.signature_image == OTHER_SIGNATURE
        assert sorted(r.pk for r in losers) == ['a', 'b']

    def test_unstamped_loser_does_not_erase_the_survivors_stamp(self):
        """The stamp travels with the comment, but only when the loser has one.
        A legacy row with class_teacher NULL means "we don't know", not
        "nobody" — copying it over would drop the class-teacher signature the
        report card prints."""
        legacy = self._row('a', minutes_old=10, comment='From the legacy row',
                           teacher=None)
        newest_blank = self._row('b', minutes_old=1, teacher='emp-b')

        survivor, _losers = self._fold_group()([legacy, newest_blank])

        assert survivor.comment == 'From the legacy row'
        assert survivor.class_teacher_id == 'emp-b'


@pytest.mark.django_db
@pytest.mark.unit
class TestCollapseMigrationScan:
    """`_collapse` finds duplicate keys with an aggregate rather than loading
    every row — comment/signature_image hold base64 blobs, so scanning the
    whole table mid-deploy is an OOM risk."""

    @staticmethod
    def _collapse():
        from importlib import import_module
        return import_module(
            'core.migrations.0117_collapse_teacher_comment_rows'
        )._collapse

    def test_no_duplicates_leaves_every_row_untouched(self, tenant, batch):
        from django.apps import apps
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        eg = _exam_group(batch, tenant)
        students = [_student(batch, tenant) for _ in range(3)]
        for i, student in enumerate(students):
            TeacherComment.objects.create(
                tenant=tenant, student=student, exam_group=eg,
                comment=f'Comment {i}', signature_image=SIGNATURE,
            )

        model = apps.get_model('core', 'TeacherComment')
        with CaptureQueriesContext(connection) as queries:
            collapsed = self._collapse()(
                model, ('tenant_id', 'student_id', 'exam_group_id')
            )

        assert collapsed == 0
        # Nothing loaded the base64 blob columns — the scan is aggregate-only.
        sql = ' '.join(q['sql'] for q in queries.captured_queries).lower()
        assert 'signature_image' not in sql
        assert 'count(' in sql
        by_sid = {
            str(r.student_id): r.comment
            for r in TeacherComment.objects.filter(exam_group=eg)
        }
        assert by_sid == {str(s.id): f'Comment {i}' for i, s in enumerate(students)}
