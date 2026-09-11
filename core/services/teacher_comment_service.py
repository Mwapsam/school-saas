from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from django.db import IntegrityError, transaction

from .base import BaseService
from .exceptions import BusinessLogicException, PermissionException
from ..grading_utils import infer_report_layout
from ..models import (
    Batch,
    ExamGroup,
    ReportTemplate,
    SkillsTeacherComment,
    TeacherComment,
    Term,
)


class SkillsLockedException(BusinessLogicException):
    """Saving comments for a batch+term whose skills results were submitted."""


@dataclass(frozen=True)
class CommentRoute:
    is_skills: bool
    batch: Batch
    exam_group: Optional[ExamGroup] = None
    term: Optional[Term] = None


class TeacherCommentService(BaseService):

    def __init__(self, tenant=None):
        super().__init__(TeacherComment, tenant)
        from .class_teacher_assignment_service import ClassTeacherAssignmentService
        self._assignment_svc = ClassTeacherAssignmentService(tenant)

    # ── Routing ──────────────────────────────────────────────────────────

    @staticmethod
    def resolve_template_for_batch(tenant, batch: Batch) -> Optional[ReportTemplate]:
        qs = ReportTemplate.objects.filter(tenant=tenant, batch=batch, is_active=True)
        return qs.filter(is_default=True).first() or qs.order_by('-created_at').first()

    def resolve_route(self, exam_group: ExamGroup,
                      template: Optional[ReportTemplate] = None) -> CommentRoute:
        batch = exam_group.batch
        template = template or self.resolve_template_for_batch(self.tenant, batch)
        if template is not None:
            layout = template.layout_type
        else:
            layout, _scale = infer_report_layout(batch)
        if layout == ReportTemplate.LAYOUT_SKILLS:
            return CommentRoute(
                is_skills=True, batch=batch, exam_group=exam_group,
                term=self.resolve_skills_term(batch, exam_group=exam_group),
            )
        return CommentRoute(is_skills=False, batch=batch, exam_group=exam_group)

    def skills_route(self, batch: Batch, term_name: Optional[str] = None) -> CommentRoute:
        return CommentRoute(
            is_skills=True, batch=batch,
            term=self.resolve_skills_term(batch, term_name=term_name),
        )

    def resolve_skills_term(self, batch: Batch,
                            exam_group: Optional[ExamGroup] = None,
                            term_name: Optional[str] = None) -> Optional[Term]:
        """Phase 3: Resolve year-scoped term for skills assessment.

        Delegates to portal_selectors.resolve_term() which uses academic_year-based lookup.
        """
        from portal import selectors as portal_selectors

        name = (term_name or '').strip() or portal_selectors.skills_exam_group_term(batch)
        if not name:
            if exam_group is None:
                # Batch-only context (portal wizard): borrow the batch's latest
                # exam plan so both contexts fall back to the same term.
                exam_group = ExamGroup.objects.filter(
                    tenant=self.tenant, batch=batch
                ).order_by('-exam_date').first()
            if exam_group is not None:
                from .report_generation_service import ReportGenerationService
                name = ReportGenerationService.resolve_exam_group_term(exam_group)
        return portal_selectors.resolve_term(name, batch=batch)

    def current_route_for_batch(self, batch: Batch) -> CommentRoute:
        template = self.resolve_template_for_batch(self.tenant, batch)
        layout = template.layout_type if template else infer_report_layout(batch)[0]
        if layout == ReportTemplate.LAYOUT_SKILLS:
            return self.skills_route(batch)
        exam_group = ExamGroup.objects.filter(tenant=self.tenant, batch=batch).order_by('-exam_date').first()
        if exam_group is None:
            return CommentRoute(is_skills=False, batch=batch, exam_group=None)
        return self.resolve_route(exam_group, template=template)

    # ── Reads ────────────────────────────────────────────────────────────

    def get_comments(self, route: CommentRoute, student_ids: Optional[List[str]] = None) -> Dict:

        rows = self._current_rows(route, student_ids)
        # Try row signature_image first, then class_teacher's signature
        signature = next(
            (r.signature_image for r in rows if r.signature_image), ''
        )
        if not signature:
            signature = next(
                (r.class_teacher.signature_image for r in rows
                 if r.class_teacher and r.class_teacher.signature_image), ''
            )
        return {
            'comments': [
                {'student_id': str(r.student_id), 'comment': r.comment}
                for r in rows
            ],
            'signature_image': signature,
        }

    def get_comments_map(self, route: CommentRoute,
                         student_ids: Optional[List[str]] = None
                         ) -> Dict[str, Dict]:

        out = {}
        for r in self._current_rows(route, student_ids):
            emp = r.class_teacher
            # Try row signature_image first, then class_teacher's signature
            signature = r.signature_image or (emp.signature_image if emp else '')
            out[str(r.student_id)] = {
                'comment': r.comment,
                'signature_image': signature,
                'class_teacher_id': str(emp.id) if emp else None,
                'class_teacher_name': emp.full_name if emp else '',
                'updated_at': r.updated_at,
            }
        return out

    def get_comments_grouped_by_teacher(self, route: CommentRoute,
                                        student_ids: Optional[List[str]] = None
                                        ) -> Dict[str, Dict]:
        """Current rows partitioned by class_teacher, for screens that present
        each teacher's comments/signature as a group (e.g. the admin
        exam-group page for multi-teacher batches). Unassigned students are
        grouped under the 'UNASSIGNED' key."""
        grouped: Dict[str, Dict] = {}
        for r in self._current_rows(route, student_ids):
            emp = r.class_teacher
            key = str(emp.id) if emp else 'UNASSIGNED'
            group = grouped.setdefault(key, {
                'teacher_id': key if emp else None,
                'teacher_name': emp.full_name if emp else '',
                'signature_image': (emp.signature_image if emp else '') or '',
                'students': [],
            })
            if r.signature_image:
                group['signature_image'] = r.signature_image
            group['students'].append({
                'student_id': str(r.student_id),
                'comment': r.comment,
            })
        return grouped

    # ── Writes ───────────────────────────────────────────────────────────

    def save_comments(self, route: CommentRoute, comments: List[Dict], signature: str = '',
                      *,
                      enforce_skills_lock: bool = True,
                      clear_signature: bool = False,
                      valid_student_ids: Optional[Set[str]] = None,
                      acting_teacher=None) -> int:
        """acting_teacher: pass the authenticated teacher for teacher-portal
        callers to enforce that they only save comments for students currently
        assigned to them. Omit for staff/admin callers, which may save on a
        student's behalf regardless of who is logged in — matches the existing
        admin exam-group flow.

        THE `cleared` CONTRACT (authoritative — every UI implements this):
        each entry in `comments` is `{student_id, comment, cleared?}`. A blank
        `comment` is ambiguous on its own: it means either "the teacher emptied
        this field" or "this field never received its saved value". Callers
        must set `cleared: True` only for a field the user edited down to blank
        *since the last successful load* of that student's comment; only then
        does a blank overwrite saved content. A blank without `cleared` leaves
        an existing comment untouched.

        Implementations: `useTouchedComments`
        (frontend/src/hooks/use-touched-comments.ts) for the teacher portal,
        and the `data-touched` tracking in
        templates/core/gradebook/exam_group_marks_entry.html for the staff
        exam-group page."""

        if (route.is_skills and enforce_skills_lock
                and self.is_skills_locked(route.batch, route.term, employee=acting_teacher)):
            raise SkillsLockedException(
                "Skills results have been submitted and are locked."
            )

        def apply(row, new_comment, cleared):
            """Write one payload entry onto `row`. Kept separate so the retry
            below can re-apply it to a different row."""
            # A blank incoming comment only overwrites existing saved content
            # when the caller explicitly marks it as an intentional clear
            # (mirrors `clear_signature`). Without this, a payload that never
            # loaded a student's real comment (or omitted it) would wipe it out.
            if new_comment or cleared or not row.comment:
                row.comment = new_comment
            if clear_signature:
                row.signature_image = ''
            elif signature:
                row.signature_image = signature

        saved = 0
        with transaction.atomic():
            for entry in comments:
                sid = str(entry.get('student_id') or '')
                if not sid:
                    continue
                if valid_student_ids is not None and sid not in valid_student_ids:
                    continue
                teacher = self._assignment_svc.get_assigned_employee(sid, route.batch)
                if acting_teacher is not None and (
                    teacher is None or str(teacher.id) != str(acting_teacher.id)
                ):
                    raise PermissionException(
                        f"You are not the assigned class teacher for student {sid}."
                    )
                new_comment = (entry.get('comment') or '').strip()
                cleared = bool(entry.get('cleared'))

                row = self._row_for_student(route, sid, teacher)
                apply(row, new_comment, cleared)
                try:
                    # Savepoint: a conflict on one student must not poison the
                    # transaction and abort the whole roster's save.
                    with transaction.atomic():
                        row.save()
                except IntegrityError:
                    # Lost the INSERT race for this (student, route) — a
                    # concurrent save created the row between our lookup and
                    # our write. Re-read the winner and apply this payload on
                    # top of it. Re-applying (rather than reusing the values we
                    # already computed) is what keeps the `cleared` contract
                    # honest: `not row.comment` has to be judged against the
                    # value that actually landed.
                    row = self._row_for_student(route, sid, teacher)
                    apply(row, new_comment, cleared)
                    row.save()
                saved += 1
        return saved

    def is_skills_locked(self, batch: Batch, term: Optional[Term], employee=None) -> bool:

        from portal.models import SkillsSubmission  # avoid core↔portal import cycle

        # Check whole-batch lock (legacy/staff submission)
        whole_batch_locked = SkillsSubmission.objects.filter(
            tenant=self.tenant, batch=batch, term=term,
            employee__isnull=True,
            status=SkillsSubmission.STATUS_SUBMITTED,
        ).exists()

        if whole_batch_locked:
            return True

        # If employee is given, also check their own per-teacher lock
        if employee:
            return SkillsSubmission.objects.filter(
                tenant=self.tenant, batch=batch, term=term,
                employee=employee,
                status=SkillsSubmission.STATUS_SUBMITTED,
            ).exists()

        return False

    # ── Internals ────────────────────────────────────────────────────────

    # Most-recently-updated first. The database enforces one row per student
    # per route, so this ordering should never actually have to break a tie —
    # it is here so that if a duplicate ever does exist, `_row_for_student`'s
    # .first() and `_current_rows` pick the *same* row instead of reads and
    # writes silently diverging on unordered queryset order.
    _ORDER = ('-updated_at', '-id')

    def _rows(self, route: CommentRoute):
        if route.is_skills:
            return SkillsTeacherComment.objects.filter(
                tenant=self.tenant, batch=route.batch, term=route.term
            ).order_by(*self._ORDER)
        if route.exam_group is None:
            return TeacherComment.objects.none()
        return TeacherComment.objects.filter(
            tenant=self.tenant, exam_group=route.exam_group
        ).order_by(*self._ORDER)

    def _current_rows(self, route: CommentRoute, student_ids: Optional[List[str]] = None) -> List:
        """One row per student for the route. The database enforces that there
        is only ever one to choose from (unique_together, plus the partial
        index covering skills rows with a NULL term, which unique_together
        cannot reach). The dedupe below is belt-and-braces: it keeps the same
        row `_row_for_student` would write to — see `_ORDER`."""
        qs = self._rows(route).select_related('class_teacher')
        if student_ids is not None:
            qs = qs.filter(student_id__in=student_ids)

        current, seen = [], set()
        for row in qs:
            sid = str(row.student_id)
            if sid in seen:
                continue
            seen.add(sid)
            current.append(row)
        return current

    def _row_for_student(self, route: CommentRoute, student_id: str, teacher):
        """Get-or-create the one row identified by (student, route), restamping
        its `class_teacher` with today's resolved teacher. Reassignment
        restamps this row rather than starting a second one — a student has
        exactly one comment per route, so a second row would only force reads
        to guess which of them is current.

        An unresolvable teacher (`None` — e.g. the batch just became
        multi-teacher and this student has no assignment row yet) means "we
        don't know today", not "nobody", so it must not erase a stamp we do
        have: the report card's signature lookup and
        `get_comments_grouped_by_teacher` both read it. A brand-new row still
        takes `None`, which is honest — nothing is known about it yet.

        filter().first() rather than update_or_create: a bare upsert can
        accumulate duplicate rows (see `_rows` for the ordering that keeps
        reads and writes agreeing on which row is current)."""
        row = self._rows(route).filter(student_id=student_id).first()
        if row is not None:
            if teacher is not None:
                row.class_teacher = teacher
            return row
        if route.is_skills:
            return SkillsTeacherComment(
                tenant=self.tenant, student_id=student_id,
                batch=route.batch, term=route.term, class_teacher=teacher,
            )
        return TeacherComment(
            tenant=self.tenant, student_id=student_id, exam_group=route.exam_group,
            class_teacher=teacher,
        )
