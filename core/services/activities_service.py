from typing import Any, Dict, List, Optional

from django.db import transaction

from .base import BaseService
from ..models import (
    Activity,
    Batch,
    BatchExamTypeConfiguration,
    BatchStudent,
    HomeworkAssessment,
    ProjectWorkAssessment,
    Student,
    StudentActivity,
)


class ActivitiesService(BaseService):
    """Homework / Project Work / Clubs / Sports / Other term activities.

    Single source of truth for the "Activities & Assessments" data shape, used
    by both the admin Exam Group activities modal (``core.views``) and the
    Teacher Portal's activities step (``portal.views``), so the two surfaces
    can never drift the way their previous, independently-maintained
    implementations did.
    """

    def __init__(self, tenant=None):
        super().__init__(HomeworkAssessment, tenant)

    @staticmethod
    def activity_options(tenant) -> Dict[str, List[str]]:
        """Active club / sport / other names, drawn from the Activity catalogue
        (grouped by its ActivityProfile), for populating a picker instead of
        free text. Keys are plural (``clubs``/``sports``/``other``) to match
        ``StudentActivity.activity_type`` choices and the per-student rows."""
        opts: Dict[str, set] = {"clubs": set(), "sports": set(), "other": set()}
        qs = Activity.objects.filter(is_active=True).select_related("activity_profile")
        if tenant is not None:
            qs = qs.filter(tenant=tenant)
        for a in qs.order_by("name"):
            pname = (getattr(a.activity_profile, "name", "") or "").upper()
            if "CLUB" in pname:
                opts["clubs"].add(a.name)
            elif "SPORT" in pname:
                opts["sports"].add(a.name)
            else:
                opts["other"].add(a.name)
        return {k: sorted(v) for k, v in opts.items()}

    @staticmethod
    def activities_enabled(batch: Batch) -> bool:
        """Whether clubs/sports/project-work are enabled for the batch (default
        follows ``enable_activities``; unconfigured batches allow everything)."""
        config = BatchExamTypeConfiguration.for_batch(batch, batch.tenant)
        return True if config is None else config.enable_activities

    @staticmethod
    def homework_enabled(batch: Batch) -> bool:
        """Whether homework assessment is enabled for the batch."""
        config = BatchExamTypeConfiguration.for_batch(batch, batch.tenant)
        return True if config is None else config.enable_homework

    @staticmethod
    def mark_saved(batch: Batch, exam_group, *, ratings: bool = False, activities: bool = False) -> None:
        """Record that the class teacher has saved the Homework & Project
        modal (``ratings``) and/or the Clubs/Sports/Other modal
        (``activities``) at least once for this batch's exam group — the
        single source of truth ``is_complete`` reads from."""
        if not (ratings or activities):
            return
        from django.utils import timezone
        from ..models import ActivitiesSaveCheckpoint
        checkpoint, _ = ActivitiesSaveCheckpoint.objects.get_or_create(
            tenant=batch.tenant, batch=batch, exam_group=exam_group
        )
        now = timezone.now()
        if ratings:
            checkpoint.ratings_saved_at = now
        if activities:
            checkpoint.activities_saved_at = now
        checkpoint.save()

    @staticmethod
    def is_complete(batch: Batch, exam_group) -> bool:
        """Whether the activities sections that matter for this batch have
        been saved at least once. Sections disabled via
        BatchExamTypeConfiguration never block completeness."""
        homework_on = ActivitiesService.homework_enabled(batch)
        activities_on = ActivitiesService.activities_enabled(batch)
        if not homework_on and not activities_on:
            return True
        from ..models import ActivitiesSaveCheckpoint
        checkpoint = ActivitiesSaveCheckpoint.objects.filter(
            tenant=batch.tenant, batch=batch, exam_group=exam_group
        ).first()
        if checkpoint is None:
            return False
        ratings_ok = (not homework_on) or checkpoint.ratings_saved_at is not None
        activities_ok = (not activities_on) or checkpoint.activities_saved_at is not None
        return ratings_ok and activities_ok

    @staticmethod
    def roster_rows(batch: Batch, term: str, academic_year, students=None) -> List[Dict[str, Any]]:
        """Per-student homework / project / clubs-sports-other rows for a term,
        gated on the batch's Gradebook exam-type configuration: disabled
        sections come back empty rather than populated."""
        if students is None:
            students = [
                bs.student for bs in BatchStudent.objects.filter(
                    batch=batch, tenant=batch.tenant, is_active=True
                ).select_related("student").order_by("student__first_name", "student__last_name")
            ]

        homework_on = ActivitiesService.homework_enabled(batch)
        activities_on = ActivitiesService.activities_enabled(batch)

        hw_map = {}
        if homework_on:
            hw_map = {
                str(h.student_id): h
                for h in HomeworkAssessment.objects.filter(
                    student__in=students, term=term, academic_year=academic_year, tenant=batch.tenant
                )
            }

        pw_map = {}
        acts_map: Dict[str, Dict[str, list]] = {}
        if activities_on:
            pw_map = {
                str(p.student_id): p
                for p in ProjectWorkAssessment.objects.filter(
                    student__in=students, term=term, academic_year=academic_year, tenant=batch.tenant
                )
            }
            for a in StudentActivity.objects.filter(
                student__in=students, term=term, academic_year=academic_year, tenant=batch.tenant
            ):
                d = acts_map.setdefault(str(a.student_id), {"club": [], "sport": [], "other": []})
                if a.activity_type in d:
                    d[a.activity_type].append(a.activity_name)

        rows = []
        for s in students:
            sid = str(s.id)
            hw = hw_map.get(sid)
            pw = pw_map.get(sid)
            am = acts_map.get(sid, {})
            rows.append({
                "student_id": sid,
                "full_name": s.full_name,
                "admission_no": s.admission_no,
                "homework": {
                    "submission": hw.submission if hw else "",
                    "presentation": hw.presentation if hw else "",
                    "effort": hw.effort if hw else "",
                },
                "project": {
                    "submission": pw.submission if pw else "",
                    "presentation": pw.presentation if pw else "",
                    "effort": pw.effort if pw else "",
                },
                "clubs": ", ".join(am.get("club", [])),
                "sports": ", ".join(am.get("sport", [])),
                "other": ", ".join(am.get("other", [])),
            })
        return rows

    @staticmethod
    @transaction.atomic
    def save_roster_rows(batch: Batch, term: str, academic_year, rows_payload: List[Dict[str, Any]]) -> int:
        """Upsert homework/project ratings and clubs/sports/other for each row
        in the payload, gated on the batch's Gradebook exam-type configuration.
        Rows for a disabled section are silently skipped rather than saved,
        keeping stored data consistent with what's currently configured."""
        tenant = batch.tenant
        homework_on = ActivitiesService.homework_enabled(batch)
        activities_on = ActivitiesService.activities_enabled(batch)

        valid_grades = {g[0] for g in HomeworkAssessment.ASSESSMENT_GRADES}

        def clean_grade(v):
            return v if v in valid_grades else None

        def split_names(s):
            return [n.strip() for n in (s or "").split(",") if n.strip()]

        saved = 0
        for row in rows_payload:
            student = Student.objects.filter(id=row.get("id") or row.get("student_id"), tenant=tenant).first()
            if not student:
                continue

            # Only touch the sections actually present in the payload, so the
            # Homework/Project modal and the Clubs/Sports/Other modal can save
            # independently without clobbering each other.
            if homework_on and "homework" in row:
                hw = row.get("homework") or {}
                hw_vals = {k: clean_grade(hw.get(k)) for k in ("submission", "presentation", "effort")}
                if any(hw_vals.values()):
                    HomeworkAssessment.objects.update_or_create(
                        student=student, term=term, academic_year=academic_year, tenant=tenant,
                        defaults={k: (v or "Good") for k, v in hw_vals.items()},
                    )

            if activities_on and "project" in row:
                pw = row.get("project") or {}
                pw_vals = {k: clean_grade(pw.get(k)) for k in ("submission", "presentation", "effort")}
                if any(pw_vals.values()):
                    ProjectWorkAssessment.objects.update_or_create(
                        student=student, term=term, academic_year=academic_year, tenant=tenant,
                        defaults={k: (v or "Good") for k, v in pw_vals.items()},
                    )

            if activities_on and (("clubs" in row) or ("sports" in row) or ("other" in row)):
                StudentActivity.objects.filter(
                    student=student, term=term, academic_year=academic_year, tenant=tenant
                ).delete()
                new_acts = []
                for atype, key in (("club", "clubs"), ("sport", "sports"), ("other", "other")):
                    for name in split_names(row.get(key)):
                        new_acts.append(StudentActivity(
                            student=student, term=term, academic_year=academic_year, tenant=tenant,
                            activity_type=atype, activity_name=name,
                        ))
                if new_acts:
                    StudentActivity.objects.bulk_create(new_acts)

            saved += 1
        return saved
