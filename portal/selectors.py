"""
Read-side query helpers for the portal.

These are the only place that knows how portal data is shaped out of the core
models. Views call these and serialize the result; they never build ORM queries
inline. Each function returns plain model instances / dicts so the serializer
layer stays dumb and replaceable.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Prefetch, Q

from core.models import (
    AcademicYear,
    Attendance,
    Batch,
    BatchExamTypeConfiguration,
    BatchStudent,
    Exam,
    ExamGroup,
    ExamScore,
    SkillAssessmentResult,
    SkillCategory,
    SkillItem,
    SkillsAssessment,
    Student,
    Subject,
    Term,
)


# ── Parent side ──────────────────────────────────────────────────────────────

def children_for_guardian(guardian) -> list[Student]:
    """Active students linked to a guardian via StudentGuardianRelation."""
    student_ids = guardian.student_relations.values_list("student_id", flat=True)
    return list(
        Student.objects.filter(id__in=list(student_ids), is_active=True)
        .select_related("immediate_contact")
        .order_by("first_name", "last_name")
    )


def guardian_owns_student(guardian, student_id) -> bool:
    return guardian.student_relations.filter(student_id=student_id).exists()


def co_guardians_for_student(student, exclude_guardian_id) -> list[dict]:
    """Return other guardians linked to this student, excluding the specified one.
    Returns a list of {name, relation, phone, email} dicts for display."""
    from core.models import StudentGuardianRelation

    relations = (
        StudentGuardianRelation.objects
        .filter(student=student)
        .exclude(guardian_id=exclude_guardian_id)
        .select_related("guardian")
        .order_by("guardian__first_name", "guardian__last_name")
    )
    return [
        {
            "name": f"{rel.guardian.first_name} {rel.guardian.last_name}".strip(),
            "relation": rel.relation,
            "phone": rel.guardian.mobile_phone,
            "email": rel.guardian.email,
        }
        for rel in relations
    ]


def outstanding_balance_for_student(student) -> Decimal:
    """Sum of this student's outstanding charges across all academic years,
    excluding charges from a still-draft FeeCollection - parents never see
    those, so they can't count toward a lock either."""
    from django.db.models import Sum
    from core.models import FinanceFee

    total = (
        FinanceFee.objects.filter(tenant=student.tenant, student=student)
        .exclude(fee_collection__status="draft")
        .aggregate(total=Sum("balance"))["total"]
    )
    return total or Decimal("0.00")


def results_locked_for_student(student) -> bool:
    """Exam results and report cards are withheld until a student's visible
    fee balance is fully settled - unless the student carries a 'report_block'
    exemption (Configuration → Exempted Students), which lifts the fee lock."""
    from core.services.configuration_service import is_student_exempt

    if is_student_exempt(student.tenant, student.id, "report_block"):
        return False
    return outstanding_balance_for_student(student) > 0


def current_batch_for_student(student) -> Batch | None:
    membership = (
        BatchStudent.objects.filter(student=student, is_active=True)
        .select_related("batch", "batch__course", "batch__academic_year")
        .order_by("-created_at")
        .first()
    )
    return membership.batch if membership else None


def results_for_student(student) -> list[dict]:
    """
    Exam results for a student, grouped by exam group (term/assessment) then
    subject. Only results from published exam groups are exposed to parents.
    """
    scores = (
        ExamScore.objects.filter(
            student=student,
            exam__exam_group__result_published=True,
        )
        .select_related(
            "exam",
            "exam__subject",
            "exam__exam_group",
            "exam__exam_group__batch",
            "grade_value",
        )
        .order_by("exam__exam_group__exam_date", "exam__subject__name")
    )

    groups: dict[str, dict] = {}
    for score in scores:
        eg = score.exam.exam_group
        key = str(eg.id)
        group = groups.setdefault(
            key,
            {
                "exam_group_id": str(eg.id),
                "name": eg.name,
                "exam_type": eg.exam_type,
                "exam_date": eg.exam_date,
                "batch_name": eg.batch.name if eg.batch_id else None,
                "subjects": [],
            },
        )
        maximum = score.exam.maximum_marks or Decimal("0")
        percentage = None
        if maximum and score.marks is not None:
            percentage = round(float(score.marks) / float(maximum) * 100, 1)
        group["subjects"].append(
            {
                "subject": score.exam.subject.name if score.exam.subject_id else "—",
                "exam_name": score.exam.exam_name or score.exam.display_name or "Exam",
                "marks": float(score.marks) if score.marks is not None else None,
                "maximum_marks": float(maximum) if maximum else None,
                "percentage": percentage,
                "grade": score.grade_value.name if score.grade_value_id else None,
                "is_absent": score.is_absent,
                "remarks": score.remarks,
            }
        )
    return list(groups.values())


def report_cards_for_student(student) -> list[dict]:
    """Generated PDF report cards available to a parent, newest first.

    Only completed generations of already-published exam groups are exposed —
    the same ``result_published`` gate ``results_for_student`` uses, so a
    report card can never appear on the portal before the school has
    published that exam group's results.
    """
    from core.models import StudentReport

    reports = (
        StudentReport.objects.filter(
            student=student,
            generation_status='completed',
            exam_group__result_published=True,
        )
        .select_related("exam_group", "template")
        .order_by("-generation_completed_at")
    )
    return [
        {
            "id": r.id,
            "exam_group_id": str(r.exam_group_id),
            "name": r.exam_group.name,
            "term": r.template.term if r.template_id else None,
            "generated_at": r.generation_completed_at,
        }
        for r in reports
    ]


def report_card_for_guardian(guardian, student_id, report_id):
    """A single completed, published StudentReport, scoped to this guardian's
    child (authorization guard) — a parent can never fetch another family's
    report by guessing an id."""
    from core.models import StudentReport

    if not guardian_owns_student(guardian, student_id):
        return None
    return StudentReport.objects.filter(
        id=report_id,
        student_id=student_id,
        generation_status='completed',
        exam_group__result_published=True,
    ).select_related("student").first()


def attendance_summary_for_student(student, start: date | None = None, end: date | None = None) -> dict:
    """Attendance summary for a student over a date range, using calendar-based
    total-days calculation (matching report card semantics).

    If start/end are not provided, attempts to resolve them via the student's
    active batch/exam_group/term; falls back to raw row count if no term exists.

    Unmarked working days default to present; full term is always accounted for,
    never clipped at "today" — future working days count as expected present until
    marked otherwise.
    """
    from core.models import AcademicYear, ExamGroup
    from core.services.report_generation_service import ReportGenerationService
    from core.services.calendar_service import SchoolCalendarService

    # If start/end not provided, resolve via active batch/term
    if not start or not end:
        try:
            current_batch = student.student_batches.filter(is_active=True).first()
            if current_batch and current_batch.academic_year_id:
                active_year = AcademicYear.objects.filter(
                    tenant=student.tenant, is_active=True
                ).first()
                if active_year:
                    exam_group = ExamGroup.objects.filter(
                        tenant=student.tenant, batch=current_batch, academic_year=active_year
                    ).first()
                    if exam_group:
                        att_range = ReportGenerationService.resolve_attendance_range(exam_group)
                        if att_range.start_date and att_range.end_date:
                            start = att_range.start_date
                            end = att_range.end_date
        except Exception:
            pass

    # If resolved dates are available, use calendar-based calculation
    if start and end:
        try:
            calendar = SchoolCalendarService(student.tenant)
            working_days = calendar.get_working_day_list(start, end)
            records_dict = {r.month_date: r for r in Attendance.objects.filter(
                student=student, month_date__gte=start, month_date__lte=end
            ).only("month_date", "forenoon", "afternoon")}

            total = len(working_days)
            present = half = absent = 0

            for day in working_days:
                record = records_dict.get(day)
                if record is None:
                    # No attendance record for this working day → default to present
                    present += 1
                elif record.forenoon and record.afternoon:
                    present += 1
                elif record.forenoon or record.afternoon:
                    half += 1
                else:
                    absent += 1

            rate = round((present + 0.5 * half) / total * 100, 1) if total else None
            return {
                "total_days": total,
                "present_days": present,
                "half_days": half,
                "absent_days": absent,
                "attendance_rate": rate,
            }
        except Exception:
            pass

    # Fallback: raw row count (for students with no active batch/term, e.g. alumni)
    qs = Attendance.objects.filter(student=student)
    if start:
        qs = qs.filter(month_date__gte=start)
    if end:
        qs = qs.filter(month_date__lte=end)

    total = present = half = absent = 0
    for record in qs.only("forenoon", "afternoon"):
        total += 1
        if record.forenoon and record.afternoon:
            present += 1
        elif record.forenoon or record.afternoon:
            half += 1
        else:
            absent += 1

    counted = present + half + absent
    # Half days count as 0.5 of a present day.
    rate = round((present + 0.5 * half) / counted * 100, 1) if counted else None
    return {
        "total_days": total,
        "present_days": present,
        "half_days": half,
        "absent_days": absent,
        "attendance_rate": rate,
    }


# ── Teacher side ─────────────────────────────────────────────────────────────

def batches_for_teacher(employee) -> list[Batch]:
    """Batches a teacher is responsible for: class teacher (legacy + M2M) and
    any batch where they teach a subject."""
    subject_batch_ids = Subject.objects.filter(
        employee=employee, is_deleted=False
    ).values_list("batch_id", flat=True)

    qs = (
        Batch.objects.filter(is_deleted=False, is_active=True, academic_year__is_active=True)
        .filter(
            Q(employee=employee)
            | Q(class_teachers=employee)
            | Q(id__in=list(subject_batch_ids))
        )
        .select_related("course", "academic_year")
        .distinct()
        .order_by("name")
    )
    return list(qs)


def teacher_teaches_batch(employee, batch_id) -> bool:
    return any(str(b.id) == str(batch_id) for b in batches_for_teacher(employee))


def _is_skills_exam(exam) -> bool:
    """True for LEVEL-scale exams (Not Yet/Beginning/Satisfactory/Good) — these
    belong on the Skills Assessment page, not the Marks Entry grid. Mirrors
    the admin's own criterion in ``core.views.SingleExamMarksEntryView``
    (``is_level_scale = grading_scale.scale_type == 'LEVEL'``)."""
    scale = exam.get_grading_scale()
    return bool(scale and scale.scale_type == "LEVEL")


# Why an exam is not markable. These names are a diagnostic vocabulary —
# ``diagnose_teacher_exam_visibility`` prints them and support reads them, so
# keep them stable.
GATE_NO_ACCESS = "NO_ACCESS"
GATE_GROUP_UNPUBLISHED = "GROUP_UNPUBLISHED"
GATE_LEVEL_SCALE = "LEVEL_SCALE"
GATE_TYPE_DISABLED = "TYPE_DISABLED"

_VISIBLE = (True, "", "")

# `None` is a meaningful config (the batch has none, so every type is enabled),
# so it cannot double as "not supplied" without re-querying on every exam.
_UNSET = object()


def explain_exam_visibility(employee, exam, *, class_teacher_batch_ids=None,
                            config=_UNSET) -> tuple[bool, str, str]:
    """Whether `employee` may mark `exam`, and if not, which gate stopped it.

    Returns ``(visible, gate, detail)`` — gate is one of the ``GATE_*``
    constants and detail is a human-readable reason naming the deciding field.

    The single source of truth for markable-exam visibility.
    ``markable_exams_for_teacher`` prefilters in SQL for speed (it cannot load
    every exam in the tenant) and then defers here for the actual decision, so
    the portal and the diagnostic command can never disagree about *why* a row
    is missing. Anything that changes what a teacher can mark belongs in this
    function, not in a caller's queryset.

    `class_teacher_batch_ids` and `config` are caches a caller looping over many
    exams may pass to avoid a query per exam; both are derived when omitted.
    """
    batch = exam.exam_group.batch

    if class_teacher_batch_ids is None:
        # Derived exactly as markable_exams_for_teacher does, not via
        # is_class_teacher_for_batch: that one skips the active-batch and
        # active-academic-year filters, and the two must not disagree.
        class_teacher_batch_ids = {
            b.id for b in batches_for_teacher_as_class_teacher(employee)
        }
    is_class_teacher = batch.id in class_teacher_batch_ids
    teaches_subject = bool(exam.subject_id) and exam.subject.employee_id == employee.id
    if not teaches_subject and not is_class_teacher:
        if exam.subject_id is None:
            owner = "the exam has no subject"
        elif exam.subject.employee_id is None:
            owner = f"subject {exam.subject.name!r} has no teacher assigned"
        else:
            owner = f"subject {exam.subject.name!r} belongs to another teacher"
        # A soft-deleted subject row still owns its exams (Exam.subject is a
        # forward FK), and a rename that left the old row behind is the usual
        # way one lands here — worth saying so, or the reason reads as a
        # missing teacher assignment when it is really an orphaned exam.
        orphaned = (
            " — and that subject row is SOFT-DELETED, so this exam was most"
            " likely left behind by a rename"
            if exam.subject_id and exam.subject.is_deleted else ""
        )
        return False, GATE_NO_ACCESS, (
            f"{owner}, and not a class teacher of {batch.name}{orphaned}"
        )

    if not exam.exam_group.is_published:
        return False, GATE_GROUP_UNPUBLISHED, (
            f"exam group {exam.exam_group.name!r} has not been activated"
        )

    # LEVEL-scale exams live on the Skills Assessment page, not marks entry.
    scale = exam.get_grading_scale()
    if scale is not None and scale.scale_type == "LEVEL":
        source = "exam.grading_scale" if exam.grading_scale_id else "subject.grading_scale"
        return False, GATE_LEVEL_SCALE, (
            f"grading scale {scale.name!r} is LEVEL (from {source}) — "
            f"shown on the Skills Assessment page instead"
        )

    if config is _UNSET:
        config = BatchExamTypeConfiguration.for_batch(batch, batch.tenant)
    slot = exam.assessment_slot or "EXAM"
    if config is not None and not config.is_exam_type_enabled(slot):
        return False, GATE_TYPE_DISABLED, (
            f"assessment type {slot} is switched off for {batch.name} in Gradebook"
        )

    return _VISIBLE


def markable_exams_for_teacher(employee) -> list[Exam]:
    """Exams a teacher may enter marks for: any exam for a subject they teach,
    plus every exam in a batch where they are the class teacher.

    The SQL below is a *prefilter* — loading every exam in the tenant is not an
    option — but every exclusion decision is made by
    ``explain_exam_visibility``, which is also what the
    ``diagnose_teacher_exam_visibility`` command reports from. See that function
    for the gates and why each one exists."""
    batch_ids = [b.id for b in batches_for_teacher_as_class_teacher(employee)]
    exams = (
        Exam.objects.filter(
            Q(subject__employee=employee) | Q(exam_group__batch_id__in=batch_ids)
        )
        .filter(exam_group__is_published=True)
        .select_related(
            "subject",
            "subject__grading_scale",
            "grading_scale",
            "exam_group",
            "exam_group__batch",
            "exam_group__batch__course",
            "term",
        )
        .distinct()
        .order_by("-exam_group__exam_date", "exam_group__name", "subject__name")
    )

    # A teacher's exams can span several batches, each with its own config, so
    # decide per batch rather than in one combined query. Configs are cached per
    # batch to avoid a query per exam; so is class-teacher membership.
    batch_id_set = set(batch_ids)
    configs: dict = {}
    result = []
    for exam in exams:
        batch = exam.exam_group.batch
        if batch.id not in configs:
            configs[batch.id] = BatchExamTypeConfiguration.for_batch(batch, batch.tenant)
        visible, _gate, _detail = explain_exam_visibility(
            employee, exam,
            class_teacher_batch_ids=batch_id_set,
            config=configs[batch.id],
        )
        if visible:
            result.append(exam)
    return result


def teacher_can_mark_exam(employee, exam) -> bool:
    # Activation (unpublished exam plans, disabled exam types) is the single
    # source of truth in ExamService.is_exam_markable — mirrored by the admin
    # gradebook in core.views so both surfaces agree on what's markable.
    from core.services.exam_service import ExamService
    if not ExamService(exam.tenant).is_exam_markable(exam):
        return False
    if _is_skills_exam(exam):
        return False
    batch = exam.exam_group.batch
    if exam.subject_id and exam.subject.employee_id == employee.id:
        return True
    return is_class_teacher_for_batch(employee, batch)


def subjects_for_teacher(employee) -> list[Subject]:
    """Subjects directly assigned to this teacher (as subject teacher)."""
    return list(
        Subject.objects.filter(
            employee=employee,
            is_deleted=False
        )
        .select_related("batch", "batch__course")
        .order_by("batch__name", "name")
    )


def batches_for_teacher_as_class_teacher(employee) -> list[Batch]:
    """Batches where this employee is the class teacher (legacy or M2M)."""
    qs = (
        Batch.objects.filter(is_deleted=False, is_active=True, academic_year__is_active=True)
        .filter(Q(employee=employee) | Q(class_teachers=employee))
        .select_related("course", "academic_year")
        .distinct()
        .order_by("name")
    )
    return list(qs)


def is_class_teacher_for_batch(employee, batch) -> bool:
    """True if employee is a class teacher (not subject teacher) for the batch."""
    return batch.employee_id == employee.id or batch.class_teachers.filter(id=employee.id).exists()


def has_markable_exams_for_batch(employee, batch) -> bool:
    """True if teacher has any (non-skills) exams to mark in this batch."""
    if is_class_teacher_for_batch(employee, batch):
        query = Exam.objects.filter(exam_group__is_published=True, exam_group__batch=batch)
    else:
        query = Exam.objects.filter(
            subject__employee=employee, exam_group__is_published=True, exam_group__batch=batch
        )
    query = query.select_related("subject__grading_scale", "grading_scale")
    query = BatchExamTypeConfiguration.filter_enabled_exams(query, batch, batch.tenant)
    return any(not _is_skills_exam(exam) for exam in query)


def markable_exams_for_batch(employee, batch) -> list[Exam]:
    """Exams the teacher can mark for a specific batch (excludes skills exams)."""
    if is_class_teacher_for_batch(employee, batch):
        query = Exam.objects.filter(exam_group__batch=batch)
    else:
        query = Exam.objects.filter(subject__employee=employee, exam_group__batch=batch)

    query = query.filter(exam_group__is_published=True).select_related(
        "subject",
        "subject__grading_scale",
        "grading_scale",
        "exam_group",
        "exam_group__batch",
        "exam_group__batch__course",
        "term",
    )
    query = BatchExamTypeConfiguration.filter_enabled_exams(query, batch, batch.tenant)
    exams = query.distinct().order_by("-exam_group__exam_date", "exam_group__name", "subject__name")
    return [exam for exam in exams if not _is_skills_exam(exam)]


def exam_is_grade_only(exam) -> bool:
    """Mirror of the gradebook rule: grade-only when max marks is zero or the
    effective grading scale is level-based."""
    scale = exam.get_grading_scale()
    return exam.maximum_marks == 0 or bool(scale and getattr(scale, "scale_type", None) == "LEVEL")


def available_grades_for_exam(exam) -> list[dict]:
    return [
        {
            "id": str(g.id),
            "name": g.name,
            "min_percentage": float(g.min_percentage) if g.min_percentage is not None else None,
        }
        for g in exam.get_available_grades()
    ]


def marksheet_entries_for_exam(exam, employee=None) -> list[dict]:
    """Roster of the exam's batch with each student's existing score (if any).

    Pass employee to narrow to that class teacher's assigned subset."""
    roster = roster_for_batch(exam.exam_group.batch, employee=employee)
    scores = {
        str(s.student_id): s
        for s in ExamScore.objects.filter(exam=exam)
    }
    rows = []
    for student in roster:
        score = scores.get(str(student.id))
        rows.append(
            {
                "student_id": str(student.id),
                "full_name": student.full_name,
                "admission_no": student.admission_no,
                "roll_number": student.class_roll_no,
                "marks": float(score.marks) if (score and score.marks is not None) else None,
                "grade_value_id": str(score.grade_value_id) if (score and score.grade_value_id) else None,
                "is_absent": score.is_absent if score else False,
                "remarks": score.remarks if score else None,
            }
        )
    return rows


def roster_for_batch(batch, employee=None) -> list[Student]:
    """Active students in a batch.

    If employee is passed and is a class teacher for the batch, narrows to
    that teacher's assigned subset (ClassTeacherAssignment) — used for
    pastoral responsibilities (attendance, comments, signatures).

    Otherwise (no employee, subject teacher, or employee not in class-teacher
    pool), returns the full active roster — used for academic workflows
    (marks, grades, homework, activities) where subject teachers must see
    all students in the batch, not just a subset."""
    memberships = (
        BatchStudent.objects.filter(batch=batch, is_active=True)
        .select_related("student")
        .order_by("roll_number", "student__first_name")
    )
    students = [m.student for m in memberships if m.student and m.student.is_active]
    if employee is not None and is_class_teacher_for_batch(employee, batch):
        from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
        assigned_ids = ClassTeacherAssignmentService(batch.tenant).assigned_student_ids(batch, employee)
        students = [s for s in students if str(s.id) in assigned_ids]
    return students


def all_active_batches(tenant) -> list[Batch]:
    """Every active batch in the school — used by the librarian issue flow to
    pick a borrower by class instead of typing a student id."""
    return list(
        Batch.objects.filter(
            tenant=tenant,
            is_deleted=False,
            is_active=True,
            academic_year__is_active=True,
        )
        .select_related("course", "academic_year")
        .order_by("name")
    )


def batch_for_tenant(tenant, batch_id) -> Batch | None:
    return Batch.objects.filter(tenant=tenant, id=batch_id).first()


def has_active_skills_for_batch(batch) -> bool:
    """True if the batch has skills assessment enabled in Gradebook and it
    actually has a LEVEL-scale (skills) exam of its own — not merely that
    *some* active skill item exists somewhere in the tenant. Mirrors the
    admin's own ``is_level_scale`` criterion (``core.views.
    SingleExamMarksEntryView``) instead of a tenant-wide catalogue check."""
    if not skills_assessment_enabled_for_batch(batch):
        return False
    exams = (
        Exam.objects.filter(
            exam_group__batch=batch,
            exam_group__is_published=True,
            subject__batch=batch,
        )
        .select_related("grading_scale", "subject__grading_scale")
    )
    return any(_is_skills_exam(exam) for exam in exams)


def skills_assessment_enabled_for_batch(batch) -> bool:
    return BatchExamTypeConfiguration.skills_assessment_enabled(batch, batch.tenant)


def has_accessible_exam_groups_for_batch(employee, batch) -> bool:
    """True if teacher has any published, non-skills exam groups they can
    access for this batch."""
    if not ExamGroup.objects.filter(batch=batch, is_published=True).exists():
        return False

    if is_class_teacher_for_batch(employee, batch):
        query = Exam.objects.filter(exam_group__batch=batch, exam_group__is_published=True)
    else:
        query = Exam.objects.filter(
            subject__employee=employee,
            exam_group__batch=batch,
            exam_group__is_published=True
        )
    query = query.select_related("subject__grading_scale", "grading_scale")
    query = BatchExamTypeConfiguration.filter_enabled_exams(query, batch, batch.tenant)
    return any(not _is_skills_exam(exam) for exam in query)


# ── Skills assessment (Beginners / Reception report layout) ──────────────────

SKILL_LEVELS = ("NOT_YET", "BEGINNING", "SATISFACTORY", "GOOD")


def active_academic_year() -> AcademicYear | None:
    return AcademicYear.objects.filter(is_active=True).first()


def batch_in_active_academic_year(batch) -> bool:
    """True if ``batch`` belongs to the tenant's currently active academic
    year. Used to gate the teacher portal's direct-by-id lookups so ownership
    of a batch/exam from a past year no longer implies current access."""
    year = active_academic_year()
    return batch is not None and year is not None and batch.academic_year_id == year.id


def term_names(batch=None) -> list[str]:
    """Distinct term names (skills are keyed by term name, mirroring the admin
    skills workflow). Scoped to ``batch``'s academic year when given, so teachers
    only see terms relevant to their class instead of every term across the
    tenant; ordered by term order with case-insensitive de-dupe.

    Phase 4: Terms are year-scoped (``Term.academic_year``); the removed
    per-batch ``Term.exam_group`` link is no longer used here."""
    qs = Term.objects.all()
    if batch is not None:
        qs = qs.filter(
            tenant_id=batch.tenant_id, academic_year=batch.academic_year
        )
    qs = qs.order_by("order", "start_date").values_list("name", flat=True)

    seen: set[str] = set()
    names: list[str] = []
    for name in qs:
        name = (name or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def resolve_term(name: str | None, batch=None):
    """Resolve a term by name. When ``batch`` is given, look up the term
    scoped to the batch's academic year (Phase 3: Terms are year-scoped,
    not per-batch). The fallback is scoped to the batch's own tenant, never
    global — Term rows for every school live in one shared table, and the
    implicit per-request tenant filter on TenantAwareManager isn't active
    outside a real request (e.g. inside django_tenants.utils.schema_context,
    as management commands use), so an unscoped lookup here could return
    another tenant's row."""
    if not name:
        return None
    name = name.strip()
    if batch is None:
        return None
    # Phase 3: Look up term by (batch.academic_year, name), not per-batch exam_group
    scoped = Term.objects.filter(
        tenant_id=batch.tenant_id, name__iexact=name, academic_year=batch.academic_year
    ).first()
    if scoped is not None:
        return scoped
    # Fallback: any term with this name in the same tenant (shouldn't happen post-Phase-2)
    return Term.objects.filter(
        tenant_id=batch.tenant_id, name__iexact=name
    ).first()


def skills_exam_group_term(batch) -> str | None:
    """Term name for the batch's skills-assessment exam, resolved exactly the
    way ``core.views.SingleExamMarksEntryView`` does for the admin marks-entry
    page: find the exam whose effective grading scale is LEVEL, then read
    *that exam's own* ``term`` FK (``exam.term.name``) — not a label guessed
    from scanning the exam group's terms, which can point at a different Term
    row than the one actually attached to the exam."""
    exams = (
        Exam.objects.filter(
            exam_group__batch=batch,
            exam_group__is_published=True,
            subject__batch=batch,
        )
        .select_related("grading_scale", "subject__grading_scale", "term", "exam_group")
        .order_by("-exam_group__exam_date")
    )
    for exam in exams:
        grading_scale = exam.get_grading_scale()
        if grading_scale and grading_scale.scale_type == "LEVEL":
            if exam.term_id:
                return exam.term.name
    return None


def skill_catalog(batch=None) -> list[dict]:
    """Active skill items grouped by category, ordered for display.

    Scoped to ``batch`` the same way the admin category page and the
    marks-entry skills UI are: shared items (no batches attached) plus items
    explicitly attached to this batch (mirrors ``core.views._skill_items_for_batch``).
    """
    items_qs = SkillItem.objects.filter(is_active=True)
    if batch is not None:
        items_qs = items_qs.filter(
            Q(batches__isnull=True) | Q(batches=batch)
        ).distinct()

    items_by_cat: dict[str, list[dict]] = {}
    for item in (
        items_qs
        .select_related("category")
        .order_by("category__display_order", "display_order", "description")
    ):
        items_by_cat.setdefault(str(item.category_id), []).append(
            {"id": str(item.id), "description": item.description}
        )

    catalog = []
    for cat in SkillCategory.objects.filter(is_active=True).order_by(
        "display_order", "name"
    ):
        items = items_by_cat.get(str(cat.id), [])
        if items:
            catalog.append(
                {"code": cat.code, "name": cat.name, "items": items}
            )
    return catalog


def activity_options(tenant=None) -> dict[str, list[str]]:
    """Prefilled clubs / sports / other choices, drawn from the Activity
    catalogue. Delegates to ``ActivitiesService`` so the portal and the admin
    Exam Group activities modal always agree on the catalogue shape."""
    from core.services.activities_service import ActivitiesService

    return ActivitiesService.activity_options(tenant)


def teacher_owns_student(employee, student_id) -> bool:
    """True if employee is the assigned class teacher for this student.

    Checks the actual ClassTeacherAssignment, not batch-level class-teacher
    membership, so only the teacher explicitly assigned to a student in a
    multi-teacher batch has access to that student's per-student endpoints
    (e.g., /teacher/skills/students/{id}/).
    """
    student = Student.objects.filter(id=student_id).first()
    if student is None:
        return False
    batch = current_batch_for_student(student)
    if batch is None:
        return False
    from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
    assigned_ids = ClassTeacherAssignmentService(batch.tenant).assigned_student_ids(batch, employee)
    return str(student.id) in assigned_ids


def skills_levels_for_student(student, year, term_obj) -> dict[str, str]:
    assessment = SkillsAssessment.objects.filter(
        student=student, academic_year=year, term=term_obj
    ).first()
    if not assessment:
        return {}
    return {
        str(r.skill_item_id): r.level
        for r in SkillAssessmentResult.objects.filter(assessment=assessment)
    }


def attendance_map_for_batch(batch, day: date) -> dict[str, Attendance]:
    """student_id -> Attendance record for a given day (if marked)."""
    records = Attendance.objects.filter(batch=batch, month_date=day)
    return {str(r.student_id): r for r in records}


# ── Attendance status mapping ────────────────────────────────────────────────
# The portal exposes a friendly status vocabulary; the underlying Attendance
# model stores two half-day booleans + a free-text reason. The translation
# between the two representations is shared with the admin dashboard via
# core.services.attendance_semantics -- re-exported here so existing callers
# (selectors.status_from_record, selectors.fields_for_status, etc.) keep working.
from core.services.attendance_semantics import (  # noqa: E402
    ATTENDANCE_STATUSES,
    STATUS_ABSENT,
    STATUS_HALF_DAY,
    STATUS_LATE,
    STATUS_PRESENT,
    STATUS_UNMARKED,
    fields_for_status,
    status_from_record,
)


# ── Parent fees ──────────────────────────────────────────────────────────────

def academic_years_for_student(student) -> list[AcademicYear]:
    """Academic years that a student has fee activity in, newest first."""
    from core.models import FinanceFee, FeeTransaction
    year_ids = set(
        FinanceFee.objects.filter(tenant=student.tenant, student=student)
        .values_list("academic_year_id", flat=True)
    ) | set(
        FeeTransaction.objects.filter(tenant=student.tenant, student=student)
        .values_list("academic_year_id", flat=True)
    )
    year_ids.discard(None)
    return list(
        AcademicYear.objects.filter(tenant=student.tenant, id__in=year_ids).order_by("-start_date")
    )


def resolve_student_fee_year(student, academic_year_id=None) -> AcademicYear | None:
    """Pick the academic year for a parent fee view: requested → active → latest."""
    years = academic_years_for_student(student)
    if academic_year_id:
        for ay in years:
            if str(ay.id) == str(academic_year_id):
                return ay
    active = AcademicYear.objects.filter(tenant=student.tenant, is_active=True).first()
    if active is not None:
        return active
    return years[0] if years else None


def fee_statement_for_student(student, academic_year) -> dict | None:
    """Read-only fee statement for a student/year, reusing FeeReportingService.

    Charges from a still-draft FeeCollection are excluded from the reported
    outstanding balance - parents must never see a charge before staff have
    published its collection's invoices.
    """
    if academic_year is None:
        return None
    from core.services.fee_reporting_service import FeeReportingService
    return FeeReportingService(student.tenant).student_statement(
        student, academic_year, exclude_unpublished_collections=True,
    )


def family_invoices_for_guardian(guardian) -> list:
    """This guardian's consolidated FamilyInvoice rows, newest year first."""
    from core.models import FamilyInvoice
    return list(
        FamilyInvoice.objects.filter(tenant=guardian.tenant, guardian=guardian)
        .select_related("academic_year")
        .order_by("-academic_year__start_date")
    )


def family_invoice_for_guardian(guardian, invoice_id):
    """A single FamilyInvoice, scoped to this guardian (authorization guard)."""
    from core.models import FamilyInvoice
    return FamilyInvoice.objects.filter(
        tenant=guardian.tenant, guardian=guardian, id=invoice_id
    ).select_related("guardian", "academic_year").first()


def receipts_for_guardian(guardian) -> list[dict]:
    """One entry per payment (grouped by reference_number) across this
    guardian's children, newest first. Always visible once paid - unlike
    invoices, receipts are never gated by FeeCollection publish status."""
    from django.db.models import Sum, Min
    from core.models import FeeTransaction

    student_ids = [s.id for s in children_for_guardian(guardian)]
    rows = (
        FeeTransaction.objects.filter(
            tenant=guardian.tenant, student_id__in=student_ids, transaction_type="payment",
        )
        .values("reference_number", "student_id", "student__first_name", "student__last_name")
        .annotate(total_amount=Sum("amount"), paid_on=Min("transaction_date"))
        .order_by("-paid_on")
    )
    return [
        {
            "reference_number": r["reference_number"],
            "student_id": r["student_id"],
            "student_name": f"{r['student__first_name']} {r['student__last_name']}",
            "total_amount": r["total_amount"],
            "paid_on": r["paid_on"],
        }
        for r in rows
    ]


def receipt_for_guardian(guardian, reference_number) -> dict | None:
    """A single payment receipt, scoped to this guardian's children
    (authorization guard - a reference_number belonging to another family's
    payment returns None)."""
    from core.services.fee_reporting_service import FeeReportingService

    student_ids = [s.id for s in children_for_guardian(guardian)]
    return FeeReportingService(guardian.tenant).receipt_by_reference(reference_number, student_ids)


# ── Announcements / newsletters ──────────────────────────────────────────────

def announcements_for_tenant(tenant) -> list:
    """Active school announcements (News), newest first."""
    from core.models import News
    return list(
        News.objects.filter(tenant=tenant, is_active=True).order_by("-created_at")
    )


# ── Librarian side ──────────────────────────────────────────────────────────────

def libraries_for_librarian(employee) -> list:
    """Active libraries this librarian is assigned to."""
    from core.models import Library
    return list(
        Library.objects.filter(
            staff_assignments__employee=employee,
            staff_assignments__is_active=True,
            is_active=True
        ).distinct().order_by("name")
    )


def librarian_has_library(employee, library_id) -> bool:
    """Check if a librarian is assigned to a specific library."""
    from core.models import Library
    return Library.objects.filter(
        id=library_id,
        staff_assignments__employee=employee,
        staff_assignments__is_active=True,
        is_active=True
    ).exists()


def books_for_librarian(employee, library_id=None, **filters) -> list:
    """Books a librarian can access (via their assigned libraries)."""
    from core.models import Book
    from django.db.models import Q

    # Get all libraries this librarian is assigned to
    assigned_libraries = libraries_for_librarian(employee)
    if not assigned_libraries:
        return []

    # If a specific library is requested, verify it's one they're assigned to
    if library_id:
        if not librarian_has_library(employee, library_id):
            return []
        library_ids = [library_id]
    else:
        library_ids = [lib.id for lib in assigned_libraries]

    # Build unified query for all accessible libraries
    query = Q(tenant=employee.tenant, library__in=library_ids)
    if filters.get('query'):
        query &= (
            Q(title__icontains=filters['query']) |
            Q(author__icontains=filters['query']) |
            Q(isbn__icontains=filters['query']) |
            Q(book_number__icontains=filters['query'])
        )
    if filters.get('category_id'):
        query &= Q(category_id=filters['category_id'])
    if filters.get('available_only'):
        query &= Q(available_copies__gt=0)

    queryset = Book.objects.filter(query)
    if filters.get('limit'):
        queryset = queryset[:filters['limit']]
    return list(queryset)


def librarian_owns_book(employee, book_id) -> bool:
    """Check if a book belongs to one of the librarian's assigned libraries."""
    from core.models import Book
    return Book.objects.filter(
        id=book_id,
        library__in=[lib.id for lib in libraries_for_librarian(employee)]
    ).exists()


def librarian_dashboard_stats(employee) -> dict:
    """Aggregate library statistics for all assigned libraries."""
    from core.services.library_service import LibraryService

    service = LibraryService(employee.tenant)
    assigned_libraries = libraries_for_librarian(employee)

    combined_stats = {
        'total_books': 0,
        'total_copies': 0,
        'available_copies': 0,
        'issued_copies': 0,
        'overdue_books': 0,
        'total_issues': 0,
        'active_issues': 0,
        'utilization_rate': 0,
    }

    if not assigned_libraries:
        return combined_stats

    # Aggregate stats per library
    for library in assigned_libraries:
        stats = service.get_library_statistics(str(library.id))
        combined_stats['total_books'] += stats['total_books']
        combined_stats['total_copies'] += stats['total_copies']
        combined_stats['available_copies'] += stats['available_copies']
        combined_stats['issued_copies'] += stats['issued_copies']
        combined_stats['overdue_books'] += stats['overdue_books']
        combined_stats['total_issues'] += stats['total_issues']
        combined_stats['active_issues'] += stats['active_issues']

    # Recalculate utilization rate
    if combined_stats['total_copies'] > 0:
        combined_stats['utilization_rate'] = round(
            (combined_stats['issued_copies'] / combined_stats['total_copies'] * 100), 2
        )

    return combined_stats
