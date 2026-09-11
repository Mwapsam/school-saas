from typing import Dict, Any, List, NamedTuple, Optional
from collections import defaultdict
from django.db import transaction, connection
from django.db.models import Avg
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import logging
import threading
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseService
from .exceptions import ServiceException, NotFoundException
from .calendar_service import SchoolCalendarService
from ..models import (
    ReportTemplate, StudentReport, ExamGroup, Student, ExamScore,
    HomeworkAssessment, ProjectWorkAssessment, StudentActivity,
    GradingLevel, Batch, Attendance, BatchStudent, Term,
    SkillsAssessment, SkillAssessmentResult, SkillCategory, SkillItem,
)

logger = logging.getLogger(__name__)


def _as_date(value):
    """Batch.start_date/end_date are DateTimeFields, but the working-day
    calendar (and Term.start_date/end_date) deal in plain dates — comparing a
    datetime against the date objects the calendar computes internally raises
    "can't compare datetime.datetime to datetime.date".

    `localtime` first, because the database hands these back in UTC: a batch
    starting at midnight Lusaka (UTC+2) is stored as 22:00 the previous day, so
    a bare `.date()` would move the whole attendance window back a day. An
    unsaved or fixture-built Batch may hold a plain date already, hence the
    type guards rather than a bare conversion."""
    if not isinstance(value, datetime):
        return value
    if timezone.is_aware(value):
        return timezone.localtime(value).date()
    return value.date()


class AttendanceRange(NamedTuple):
    """The window a report card's attendance figures are computed over, and
    where it came from. See `ReportGenerationService.resolve_attendance_range`."""
    start_date: Optional[date]
    end_date: Optional[date]
    source: str          # 'term' | 'batch' | 'none'
    term_name: str       # what resolve_exam_group_term returned
    term: Optional[Term] # the matched Term row, when source == 'term'


class ReportGenerationService(BaseService):
    """Service for generating student reports from templates"""
    
    # Thread-local storage for WeasyPrint FontConfiguration to avoid expensive 
    # filesystem font scans on every PDF generation while remaining thread-safe.
    _thread_local = threading.local()

    def __init__(self, tenant=None):
        super().__init__(StudentReport, tenant)

    @classmethod
    def _get_font_config(cls):
        """Get or create a thread-local FontConfiguration instance."""
        if not hasattr(cls._thread_local, 'font_config'):
            from weasyprint.text.fonts import FontConfiguration
            cls._thread_local.font_config = FontConfiguration()
        return cls._thread_local.font_config

    @property
    def _teacher_comment_service(self):
        """Canonical read path for teacher comments/signatures — see
        TeacherCommentService for the routing rules."""
        if not hasattr(self, '_tc_svc'):
            from .teacher_comment_service import TeacherCommentService
            self._tc_svc = TeacherCommentService(tenant=self.tenant)
        return self._tc_svc
    
    def generate_student_report(self, student_id: str, template_id: str, exam_group_id: str,
                               _template=None, _bulk_ctx: Optional[Dict] = None) -> StudentReport:
        """Generate a complete student report."""
        try:
            student = Student.objects.get(id=student_id, tenant=self.tenant)
            template = _template or ReportTemplate.objects.select_related('batch__employee', 'report_signature').get(
                id=template_id, tenant=self.tenant
            )
            exam_group = ExamGroup.objects.get(id=exam_group_id, tenant=self.tenant)
        except (Student.DoesNotExist, ReportTemplate.DoesNotExist, ExamGroup.DoesNotExist) as e:
            raise NotFoundException(f"Required object not found: {e}")

        try:
            # FIX 1: Use get_or_create to prevent race conditions/duplicates in concurrent environments
            report, created = StudentReport.objects.get_or_create(
                student=student, template=template,
                exam_group=exam_group, tenant=self.tenant,
                defaults={'generation_status': 'pending', 'report_data': {}}
            )
            
            # Lock the specific row to safely update its status
            with transaction.atomic():
                report = StudentReport.objects.select_for_update().get(id=report.id)
                report.generation_status = 'generating'
                report.generation_started_at = timezone.now()
                report.save()
                
        except Exception as e:
            logger.error(f"Error initialising student report: {e}")
            raise ServiceException(f"Report generation error: {e}")

        try:
            report_data = self._collect_report_data(
                student, template, exam_group, _bulk_ctx=_bulk_ctx
            )
            html_content = self._generate_html_report(template, report_data)
            pdf_content  = self._generate_pdf_from_html(html_content)
            
            # FIX 2: Save files sequentially to avoid nested thread pools when called from bulk_generate_reports.
            # The outer ThreadPoolExecutor already handles concurrency across students efficiently.
            html_path = self._save_report_file(report, html_content, 'html')
            pdf_path = self._save_report_file(report, pdf_content, 'pdf')

            # Use .update() to avoid triggering signals and loading the model again
            update_fields = {
                'report_data': self._json_safe(report_data),
                'html_file_path': html_path,
                'pdf_file_path': pdf_path,
                'generation_status': 'completed',
                'generation_completed_at': timezone.now(),
                'generation_error': None,
            }
            StudentReport.objects.filter(id=report.id).update(**update_fields)
            
            # Update local instance to reflect changes before returning
            for k, v in update_fields.items():
                setattr(report, k, v)

            logger.info(f"Successfully generated report for student {student.full_name}")
            return report

        except Exception as e:
            StudentReport.objects.filter(id=report.id).update(
                generation_status='failed',
                generation_error=str(e),
            )
            logger.error(f"Error generating student report for {student.full_name}: {e}")
            raise ServiceException(f"Report generation failed: {e}")
    
    def _collect_report_data(self, student: Student, template: ReportTemplate,
                             exam_group: ExamGroup,
                             _bulk_ctx: Optional[Dict] = None) -> Dict[str, Any]:
        """Collect all data needed for the report."""
        ctx = _bulk_ctx or {}
        sid = str(student.id)

        data = {
            'student':   self._get_student_data(student, template.batch, _bulk_ctx=ctx),
            'school':    ctx.get('school')   or self._get_school_data(template),
            'template':  ctx.get('template') or self._get_template_data(template),
            'term_info': ctx.get('term_info') or self._get_term_data(template, exam_group),
        }

        grading_scale = ctx.get('grading_scale') or self._get_grading_scale_data(template.batch, template=template)
        rankings = ctx.get('rankings') or self._get_class_rankings(template, exam_group)

        if template.include_exam_scores:
            scores = ctx['scores_by_student'].get(sid, []) if 'scores_by_student' in ctx else None
            subject_order = getattr(template, 'subject_order', None) or []
            data['exam_results']  = self._get_exam_results_data(
                student, exam_group, grading_scale, _scores=scores,
                subject_order=subject_order,
            )
            data['class_averages'] = ctx.get('class_averages') or self._get_class_averages(exam_group)

        if template.include_homework_assessment:
            if 'homework_by_student' in ctx:
                data['homework'] = self._format_homework(ctx['homework_by_student'].get(sid))
            else:
                data['homework'] = self._get_homework_data(student, exam_group)

        if template.include_project_work:
            if 'projects_by_student' in ctx:
                data['project_work'] = self._format_project(ctx['projects_by_student'].get(sid))
            else:
                data['project_work'] = self._get_project_work_data(student, exam_group)

        if template.include_clubs or template.include_sports or template.include_other_activities:
            if 'activities_by_student' in ctx:
                acts = ctx['activities_by_student'].get(sid, [])
                data['activities'] = self._format_activities(acts)
            else:
                data['activities'] = self._get_activities_data(student, exam_group)

        if template.include_attendance:
            if 'attendance_by_student' in ctx:
                records = ctx['attendance_by_student'].get(sid, [])
                data['attendance'] = self._compute_attendance_summary(
                    records,
                    start_date=ctx.get('attendance_start_date'),
                    end_date=ctx.get('attendance_end_date'),
                    batch=ctx.get('attendance_batch'),
                )
            else:
                data['attendance'] = self._get_attendance_data(student, template, exam_group)

        if template.include_grading_scale:
            data['grading_scale'] = grading_scale

        tc = self._get_teacher_comment_data(student, exam_group, template=template, _bulk_ctx=ctx)
        data['teacher_comment']   = tc.get('comment', '')
        data['teacher_signature'] = tc.get('signature_image', '')

        layout = getattr(template, 'layout_type', 'FULL_ACADEMIC') or 'FULL_ACADEMIC'
        if layout == 'SKILLS' and getattr(template, 'include_skills', True):
            data['skills'] = self._get_skills_data(student, template, exam_group, _bulk_ctx=ctx)

        student_rank = rankings.get(sid)
        data['ranking'] = {
            'position': student_rank['rank'] if student_rank else None,
            'total_pct': student_rank['total_pct'] if student_rank else None,
            'class_size': len(rankings),
        }

        return data
    
    def _get_student_data(self, student: Student, batch: Batch,
                          _bulk_ctx: Optional[Dict] = None) -> Dict[str, Any]:
        """Get student basic information."""
        age = self._calculate_age(student.date_of_birth)
        ctx = _bulk_ctx or {}

        class_teachers = ctx.get('batch_teachers')
        if not class_teachers and batch:
            class_teachers = [f"{e.first_name} {e.last_name}".strip() for e in batch.class_teachers.all()]
            if not class_teachers and batch.employee:
                class_teachers = [f"{batch.employee.first_name} {batch.employee.last_name}".strip()]
        class_teachers = class_teachers or []
        average_age = ctx.get('average_batch_age')
        if average_age is None and 'average_batch_age' not in ctx:
            today = date.today()
            dobs = BatchStudent.objects.filter(
                batch=batch, is_active=True, student__date_of_birth__isnull=False
            ).values_list('student__date_of_birth', flat=True)
            if dobs:
                ages = [(today - dob).days / 365.25 for dob in dobs]
                average_age = round(sum(ages) / len(ages), 1)

        return {
            'full_name': student.full_name,
            'admission_number': student.admission_no,
            'class_name': batch.name,
            'age': age,
            'class_teachers': class_teachers,
            'average_age_of_grade': average_age,
        }
    
    def _embed_image(self, filefield) -> str:
        """Return a base64 data URI for an ImageField, or None."""
        import base64, mimetypes
        if not filefield or not getattr(filefield, 'name', None):
            return None
        try:
            with filefield.open('rb') as f:
                raw = base64.b64encode(f.read()).decode('utf-8')
            mime = mimetypes.guess_type(filefield.name)[0] or 'image/png'
            return f"data:{mime};base64,{raw}"
        except Exception:
            return None

    def _get_school_data(self, template: ReportTemplate) -> Dict[str, Any]:
        """Global school branding for the report, read from the School record so a
        single edit applies to every report (falling back to the template's stored
        values, then the model defaults, when a field is blank)."""
        school = self.tenant

        logo_url = self._embed_image(school.logo) or (template.school_logo_url or None)

        # Signature resolution: the template's own explicit choice first, else the
        # tenant's default SchoolSignature, else no signature (HTML templates already
        # fall back to "Head of School" via |default:"Head of School").
        signature = template.report_signature
        if signature is None:
            from ..models import SchoolSignature
            signature = SchoolSignature.objects.filter(tenant=school, is_default=True).first()

        if signature is not None:
            signature_url = self._embed_image(signature.image)
            signature_title = signature.title or 'Head of School'
        else:
            signature_url = None
            signature_title = 'Head of School'

        return {
            'name': school.name or template.school_name,
            'address': school.address_line1 or template.school_address,
            'contact': school.phone or template.school_contact,
            'email': school.email or template.school_email,
            'website': str(school.website or '') or template.school_website,
            'logo_url': logo_url,
            'logo_secondary_url': self._embed_image(school.logo_secondary),
            'signature_url': signature_url,
            'report_title': getattr(school, 'report_title', '') or template.report_title,
            'footer_quote': getattr(school, 'footer_quote', '') or template.footer_quote,
            'signature_title': signature_title,
        }
    
    def _lighten_hex(self, hex_color: str, factor: float = 0.75) -> str:
        try:
            h = hex_color.lstrip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            r = min(255, int(r + (255 - r) * factor))
            g = min(255, int(g + (255 - g) * factor))
            b = min(255, int(b + (255 - b) * factor))
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return '#d9ebc9'

    def _darken_hex(self, hex_color: str, factor: float = 0.30) -> str:
        """Darken a hex color. `factor` scales up automatically for already-light
        colors (e.g. pale yellow/cyan brand colors) so the result stays readable
        as text against white or against `_lighten_hex` of the same color."""
        try:
            h = hex_color.lstrip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            if luminance > 0.6:
                factor = 0.65
            elif luminance > 0.4:
                factor = 0.45
            r = max(0, int(r * (1 - factor)))
            g = max(0, int(g * (1 - factor)))
            b = max(0, int(b * (1 - factor)))
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return '#3f7a23'

    LAYOUT_TEMPLATES = {
        'SKILLS':          'core/reports/student_report_skills.html',
        'SIMPLE_ACADEMIC': 'core/reports/student_report_simple.html',
        'FULL_ACADEMIC':   'core/reports/student_report_full.html',
    }

    def _get_html_template_name(self, template: ReportTemplate) -> str:
        layout = getattr(template, 'layout_type', 'FULL_ACADEMIC') or 'FULL_ACADEMIC'
        return self.LAYOUT_TEMPLATES.get(layout, self.LAYOUT_TEMPLATES['FULL_ACADEMIC'])

    def _get_template_data(self, template: ReportTemplate) -> Dict[str, Any]:
        primary = getattr(template, 'primary_color', None) or '#5a9e2f'
        raw_order = getattr(template, 'section_order', None)
        section_order = raw_order if raw_order else self.DEFAULT_SECTION_ORDER
        return {
            'name': template.name,
            'title': template.report_title,
            'footer_quote': template.footer_quote,
            'primary_color': primary,
            'primary_color_light': self._lighten_hex(primary),
            'primary_color_dark': self._darken_hex(primary),
            'section_order': section_order,
            'layout_type': getattr(template, 'layout_type', 'FULL_ACADEMIC'),
        }
    
    def _get_term_data(self, template: ReportTemplate, exam_group: ExamGroup) -> Dict[str, Any]:
        # Phase 4: Terms are year-scoped, not per-exam-group. Use academic_year directly.
        current_terms = []
        if hasattr(template, 'academic_year') and template.academic_year:
            current_terms = list(template.academic_year.terms_by_year.order_by('order'))
        term_name = self._resolve_term_name(template, exam_group)

        next_term_start = None
        found = False
        for t in current_terms:
            if found:
                next_term_start = t.start_date
                break
            if t.name == term_name:
                found = True

        return {
            'term': term_name,
            'academic_year': template.academic_year.name,
            'exam_group': exam_group.name,
            'exam_type': exam_group.exam_type,
            # A template-level date wins; otherwise use the next Term's start date.
            'next_term_start': getattr(template, 'next_term_start', None) or next_term_start,
        }

    @staticmethod
    def _resolve_term_name(template: ReportTemplate, exam_group: ExamGroup) -> str:
        """Best-effort academic term label for the report.

        A template's ``term`` is sometimes auto-populated with the exam group
        (class) name, which would otherwise print as the 'term'. Prefer a real
        term-looking value: the template term, then the exam group's actual
        current term (``resolve_exam_group_term``), falling back to whatever
        is available.
        """
        def termish(s):
            s = (s or '').strip().lower()
            return bool(s) and ('term' in s or s == 'annual')

        raw = (getattr(template, 'term', '') or '').strip()
        eg_name = (exam_group.name or '').strip()
        if termish(raw) and raw != eg_name:
            return raw
        return ReportGenerationService.resolve_exam_group_term(exam_group) or raw or eg_name
    
    def _grade_for_percentage(self, percentage, grading_scale) -> str:
        if percentage is None or not grading_scale:
            return '-'
        for row in sorted(grading_scale, key=lambda r: r['minimum_score'], reverse=True):
            if percentage >= row['minimum_score']:
                return row['grade']
        return grading_scale[-1]['grade'] if grading_scale else '-'

    def _get_exam_results_data(self, student: Student, exam_group: ExamGroup,
                               grading_scale=None,
                               _scores=None,
                               subject_order=None) -> List[Dict[str, Any]]:
        if _scores is not None:
            all_scores = sorted(_scores, key=lambda s: s.exam.subject.name)
        else:
            all_scores = ExamScore.objects.filter(
                student=student,
                exam__exam_group=exam_group,
                tenant=self.tenant
            ).select_related(
                'exam__subject', 'grading_level', 'grade_value'
            ).order_by('exam__subject__name')

        # Bucket scores by assessment_slot; also record subject id→name mapping
        exam_scores = {}   # subject name → score for EXAM/TEST slot (numeric marks)
        att_scores  = {}   # subject name → score for ATTAINMENT slot
        eff_scores  = {}   # subject name → score for EFFORT slot
        cw_scores   = {}   # subject name → score for CLASSWORK slot
        subject_id_map = {}  # subject name → subject UUID string

        for score in all_scores:
            slot = getattr(score.exam, 'assessment_slot', 'EXAM') or 'EXAM'
            subj = score.exam.subject.name
            subject_id_map[subj] = str(score.exam.subject.id)
            if slot == 'ATTAINMENT':
                att_scores[subj] = score
            elif slot == 'EFFORT':
                eff_scores[subj] = score
            elif slot == 'CLASSWORK':
                cw_scores[subj] = score
            else:
                # EXAM and TEST both produce the numeric marks row
                exam_scores[subj] = score

        # One result row per subject — apply template subject_order when provided,
        # otherwise fall back to alphabetical.
        all_subjects_set = set(list(exam_scores) + list(att_scores) + list(cw_scores))
        if subject_order:
            id_to_name = {v: k for k, v in subject_id_map.items()}
            ordered = [id_to_name[sid] for sid in subject_order if sid in id_to_name and id_to_name[sid] in all_subjects_set]
            remaining = sorted(s for s in all_subjects_set if s not in set(ordered))
            all_subjects = ordered + remaining
        else:
            all_subjects = sorted(all_subjects_set)

        results = []
        for subj in all_subjects:
            es  = exam_scores.get(subj)
            att = att_scores.get(subj)
            eff = eff_scores.get(subj)
            cw  = cw_scores.get(subj)

            max_marks = float(es.exam.maximum_marks) if es else 0
            pct = round((float(es.marks or 0) / max_marks) * 100, 1) if max_marks and es else 0

            if es and es.marks is not None and not es.is_absent:
                # Numeric mark present: always derive grade from the template's
                # scale so the GRADE column matches the Scholastic Grade Scale
                # table printed at the bottom of the report.
                grade = self._grade_for_percentage(pct, grading_scale)
            elif es and es.grading_level and (es.marks is None or es.is_absent):
                # Qualitative-only exam (e.g., PE with no numeric marks): honour
                # the stored grading_level (teacher-entered or migrated value).
                grade = es.grading_level.name
            else:
                grade = '-'

            results.append({
                'subject':       subj,
                'marks':         float(es.marks) if es and es.marks else 0,
                'grade':         grade,
                'maximum_marks': max_marks,
                'percentage':    pct,
                'remarks':       es.remarks if es else '',
                'is_absent':     es.is_absent if es else False,
                'attainment':    att.grade_value.name if att and att.grade_value_id else '',
                'effort':        eff.grade_value.name if eff and eff.grade_value_id else '',
                'classwork':     cw.grade_value.name  if cw  and cw.grade_value_id  else '',
            })

        return results
    
    def _get_class_averages(self, exam_group: ExamGroup) -> Dict[str, float]:
        rows = (
            ExamScore.objects
            .filter(exam__exam_group=exam_group, tenant=self.tenant,
                    is_absent=False, marks__isnull=False)
            .values('exam__subject__name', 'exam__maximum_marks')
            .annotate(avg_marks=Avg('marks'))
        )
        averages = {}
        for row in rows:
            max_marks = float(row['exam__maximum_marks'] or 0)
            if max_marks > 0:
                pct = round(float(row['avg_marks']) / max_marks * 100, 1)
                averages[row['exam__subject__name']] = pct
        return averages

    def _get_class_rankings(self, template: ReportTemplate, exam_group: ExamGroup) -> Dict[str, Dict]:
        layout = getattr(template, 'layout_type', 'FULL_ACADEMIC') or 'FULL_ACADEMIC'
        if layout == 'SKILLS':
            return {}
        from ..grading_utils import GradingCalculator
        return GradingCalculator.calculate_class_rankings(template.batch, exam_group, self.tenant)

    @staticmethod
    def _json_safe(value):
        from decimal import Decimal as _Decimal
        if isinstance(value, _Decimal):
            return float(value)
        if isinstance(value, dict):
            return {k: ReportGenerationService._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [ReportGenerationService._json_safe(v) for v in value]
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def _format_homework(self, hw) -> Dict[str, str]:
        """Convert a HomeworkAssessment ORM object or dict to a data dict."""
        if hw is None:
            return {'submission': '-', 'presentation': '-', 'effort': '-'}
        if isinstance(hw, dict):
            return {
                'submission': hw.get('submission') or '-',
                'presentation': hw.get('presentation') or '-',
                'effort': hw.get('effort') or '-',
            }
        return {'submission': hw.submission, 'presentation': hw.presentation, 'effort': hw.effort}

    def _format_project(self, pw) -> Dict[str, str]:
        """Convert a ProjectWorkAssessment ORM object or dict to a data dict."""
        if pw is None:
            return {'submission': '-', 'presentation': '-', 'effort': '-'}
        if isinstance(pw, dict):
            return {
                'submission': pw.get('submission') or '-',
                'presentation': pw.get('presentation') or '-',
                'effort': pw.get('effort') or '-',
            }
        return {'submission': pw.submission, 'presentation': pw.presentation, 'effort': pw.effort}

    def _format_activities(self, acts: list) -> Dict[str, List[str]]:
        clubs, sports, other = [], [], []
        for a in acts:
            if a.activity_type == 'club':
                clubs.append(a.activity_name)
            elif a.activity_type == 'sport':
                sports.append(a.activity_name)
            else:
                other.append(a.activity_name)
        return {'clubs': clubs, 'sports': sports, 'other': other}

    def _compute_attendance_summary(self, records: list, start_date: date = None, end_date: date = None, batch: Batch = None) -> Dict[str, Any]:
        """The single implementation both the single-report and bulk-report
        paths must use for attendance totals. `records` may contain more
        than one row per date (e.g. a student transferred between batches
        mid-term) — dedupe by `month_date` here rather than trusting the
        caller's query to have already scoped it correctly.

        The `else` branch below is a last-resort fallback for the rare case
        where no calendar range could be resolved at all (no term, no batch
        dates) — it counts raw rows, which is only meaningful if `records`
        is already known to have at most one row per date. Callers should
        always supply `start_date`/`end_date`/`batch` when at all possible;
        do not treat this branch as an acceptable default."""
        if start_date and end_date and batch:
            calendar = SchoolCalendarService(self.tenant)
            total_days = calendar.get_working_days(start_date, end_date)
            working_day_list = calendar.get_working_day_list(start_date, end_date)
            # Exclude future dates (no record means assumed present, so we only count dates up to today)
            today = timezone.localdate()
            working_day_list = [d for d in working_day_list if d <= today]
            total_days = len(working_day_list)
            records_dict = {r['month_date']: r for r in records if 'month_date' in r}

            present_days = sum(1 for dt in working_day_list if (
                records_dict.get(dt, {}).get('forenoon') or records_dict.get(dt, {}).get('afternoon') or
                dt not in records_dict
            ))
            absent_days = total_days - present_days
        else:
            logger.warning(
                "Attendance summary computed without a calendar range (no start_date/end_date/batch) — "
                "falling back to a raw row count that cannot dedupe cross-batch/duplicate records."
            )
            total_days = len(records)
            present_days = sum(1 for r in records if r['forenoon'] or r['afternoon'])
            absent_days = total_days - present_days

        percentage = round(present_days / total_days * 100, 1) if total_days else 0.0
        return {
            'days_present': float(present_days),
            'days_absent': float(absent_days),
            'total_days': float(total_days),
            'attendance_percentage': percentage,
        }

    @staticmethod
    def resolve_attendance_range(exam_group: ExamGroup) -> "AttendanceRange":
        """The date range the report card's attendance block is computed over.

        Single source of truth for the single-report path, the bulk path, and
        `diagnose_attendance_totals`. The total on the card is a pure calendar
        count over this range (see `_compute_attendance_summary`), so when the
        number is wrong this range is usually why — and a diagnostic that
        re-derived it could drift and point at the wrong input.

        `source` is 'term', 'batch', or 'none'; 'none' means no range could be
        resolved at all and the caller falls back to counting raw rows.

        Phase 3: Terms are year-scoped, not per-exam_group.
        """
        term_name = ReportGenerationService.resolve_exam_group_term(exam_group)
        term = None
        if term_name:
            # Phase 3: Look up term by (academic_year, name), not exam_group
            batch = exam_group.batch
            term = Term.objects.filter(
                academic_year=batch.academic_year, name__iexact=term_name
            ).first()

        if term and term.start_date and term.end_date:
            return AttendanceRange(term.start_date, term.end_date, 'term', term_name, term)

        batch = exam_group.batch
        if exam_group.exam_date and batch.start_date and batch.end_date:
            return AttendanceRange(
                _as_date(batch.start_date), _as_date(batch.end_date),
                'batch', term_name, None,
            )

        return AttendanceRange(None, None, 'none', term_name, None)

    @staticmethod
    def resolve_exam_group_term(exam_group: ExamGroup, as_of: Optional[date] = None) -> str:
        """Canonical term label used to key Homework / Project / Activity records to an
        exam group, so data entry and report lookups always agree (independent of the
        unreliable ``template.term``).

        Picks the Term whose ``[start_date, end_date]`` window contains ``as_of``
        (today, by default); if that date falls in a gap between terms (e.g. a
        holiday), picks whichever term's range is closest by date. Never just
        returns the first Term by ordinal position — that always meant "Term 1"
        regardless of what day it actually is.

        Phase 3: Terms are year-scoped, not per-exam_group.
        """
        batch = exam_group.batch
        # Phase 3: Look up year-scoped terms for this batch's academic year
        terms = [
            t for t in Term.objects.filter(
                academic_year=batch.academic_year
            ).all()
            if (t.name or '').strip()
        ]
        if not terms:
            return (exam_group.name or '').strip()

        today = as_of or timezone.localdate()

        def distance(t):
            if t.start_date <= today <= t.end_date:
                return 0
            return min(abs((t.start_date - today).days), abs((t.end_date - today).days))

        return min(terms, key=distance).name.strip()

    @staticmethod
    def resolve_current_term(academic_year, as_of: Optional[date] = None) -> Optional[Term]:
        """Term whose [start_date, end_date] contains as_of (today by default) for
        the given academic_year, or the nearest one by date if today falls in a
        gap between terms. Same nearest-term semantics as resolve_exam_group_term,
        decoupled from ExamGroup for callers that only have an academic_year
        (e.g. the student attendance report). Returns the Term object (not just name)."""
        terms = list(Term.objects.filter(academic_year=academic_year))
        if not terms:
            return None
        today = as_of or timezone.localdate()

        def distance(t):
            if t.start_date <= today <= t.end_date:
                return 0
            return min(abs((t.start_date - today).days), abs((t.end_date - today).days))

        return min(terms, key=distance)

    @staticmethod
    def resolve_term_for_student(student: Student, academic_year, as_of: Optional[date] = None) -> Optional[str]:
        """Ground-truth current term for a student's batch in a given academic
        year, as of a given date (today by default) — the same
        ``resolve_exam_group_term`` logic, just resolved via the student's
        active batch membership first. Single source of truth for the
        term-repair management command and the Django admin "recalculate
        term" actions, so there's one implementation of "what term should
        this row belong to," not several.

        Phase 3: Terms are year-scoped; delegates to resolve_exam_group_term.
        """
        bs = (
            BatchStudent.objects.filter(
                student=student, batch__academic_year=academic_year, is_active=True
            )
            .select_related("batch")
            .first()
        )
        if bs is None:
            return None

        exam_group = (
            ExamGroup.objects.filter(batch=bs.batch, is_published=True)
            .order_by("-exam_date")
            .first()
        )
        if exam_group is None:
            return None

        return ReportGenerationService.resolve_exam_group_term(exam_group, as_of=as_of)

    def _get_homework_data(self, student: Student, exam_group: ExamGroup) -> Dict[str, str]:
        hw = HomeworkAssessment.objects.filter(
            student=student, term=self.resolve_exam_group_term(exam_group),
            academic_year=exam_group.batch.academic_year, tenant=self.tenant
        ).first()
        return self._format_homework(hw)

    def _get_project_work_data(self, student: Student, exam_group: ExamGroup) -> Dict[str, str]:
        pw = ProjectWorkAssessment.objects.filter(
            student=student, term=self.resolve_exam_group_term(exam_group),
            academic_year=exam_group.batch.academic_year, tenant=self.tenant
        ).first()
        return self._format_project(pw)

    def _get_activities_data(self, student: Student, exam_group: ExamGroup) -> Dict[str, List[str]]:
        acts = list(StudentActivity.objects.filter(
            student=student, term=self.resolve_exam_group_term(exam_group),
            academic_year=exam_group.batch.academic_year, tenant=self.tenant,
        ))
        return self._format_activities(acts)
    
    def _get_attendance_data(self, student: Student, template: ReportTemplate, exam_group: ExamGroup) -> Dict[str, Any]:
        batch = exam_group.batch
        qs = Attendance.objects.filter(student=student, tenant=self.tenant, batch=batch)

        start_date, end_date, *_ = self.resolve_attendance_range(exam_group)
        if start_date and end_date:
            qs = qs.filter(month_date__gte=start_date, month_date__lte=end_date)

        records = list(qs.values('forenoon', 'afternoon', 'month_date'))
        return self._compute_attendance_summary(records, start_date=start_date, end_date=end_date, batch=batch)
    
    DEFAULT_SECTION_ORDER = [
        'exam_scores', 'homework_project', 'clubs_sports', 
        'other_activities', 'attendance_scale',
    ]

    DEFAULT_GRADING_SCALE = [
        {'grade': 'A', 'minimum_score': 80, 'description': 'Very Good'},
        {'grade': 'B', 'minimum_score': 60, 'description': 'Good'},
        {'grade': 'C', 'minimum_score': 50, 'description': 'Satisfactory'},
        {'grade': 'D', 'minimum_score': 40, 'description': 'Weak'},
        {'grade': 'E', 'minimum_score': 0,  'description': 'Very Weak'},
    ]

    DEFAULT_GRADING_SCALE_4POINT = [
        {'grade': 'A', 'minimum_score': 80, 'description': 'Very Good'},
        {'grade': 'B', 'minimum_score': 60, 'description': 'Good'},
        {'grade': 'C', 'minimum_score': 50, 'description': 'Satisfactory'},
        {'grade': 'D', 'minimum_score': 0,  'description': 'Weak'},
    ]

    def _get_grading_scale_data(self, batch: Batch, template: 'ReportTemplate' = None) -> List[Dict[str, Any]]:
        from ..models import GradeValue

        layout = getattr(template, 'layout_type', 'FULL_ACADEMIC') if template else 'FULL_ACADEMIC'
        if layout == 'SKILLS':
            return []

        def _scale_from_grading_scale_id(scale_id):
            grade_values = GradeValue.objects.filter(
                grading_scale_id=scale_id, tenant=self.tenant, min_percentage__isnull=False,
            ).order_by('-min_percentage')
            return [
                {'grade': gv.name, 'minimum_score': float(gv.min_percentage), 'description': gv.code or gv.name}
                for gv in grade_values
            ]

        gs_fk = getattr(template, 'grading_scale_id', None) if template else None
        if gs_fk:
            scale = _scale_from_grading_scale_id(gs_fk)
            if scale:
                return scale

        # Template didn't pin a scale (or it has no usable rows) — fall back to
        # the batch's configured default, matching the same Exam -> Subject ->
        # Batch hierarchy used everywhere else (see Subject.get_grading_scale
        # and Exam.get_grading_scale). Without this step, a scale set up on
        # /gradebook/grading-settings/ never reaches the PDF unless someone
        # separately re-links it on the report template.
        batch_gs_fk = getattr(batch, 'default_grading_scale_id', None) if batch else None
        if batch_gs_fk:
            scale = _scale_from_grading_scale_id(batch_gs_fk)
            if scale:
                return scale

        # Skip the legacy GradingLevel fallback: those records store raw mark
        # thresholds (not percentages) from Fedena migration and would produce
        # wrong scale boundaries and grade mismatches.
        if layout == 'SIMPLE_ACADEMIC':
            return [dict(row) for row in self.DEFAULT_GRADING_SCALE_4POINT]
        return [dict(row) for row in self.DEFAULT_GRADING_SCALE]
    
    def _get_skills_data(self, student: Student, template: ReportTemplate,
                         exam_group: ExamGroup, _bulk_ctx: Optional[Dict] = None) -> List[Dict[str, Any]]:
        if _bulk_ctx and 'skills_by_student' in _bulk_ctx:
            return _bulk_ctx['skills_by_student'].get(str(student.id), [])
        return self._build_skills_from_assessment(student, template)

    def _build_skills_from_assessment(self, student: Student, template: ReportTemplate) -> List[Dict[str, Any]]:
        from django.db.models import Prefetch, Q
        # Shared skill activities (no batches attached) + those attached to this
        # report's batch.
        items_qs = SkillItem.objects.filter(is_active=True).filter(
            Q(batches__isnull=True) | Q(batches=template.batch_id)
        ).distinct().order_by('display_order')
        skill_category_order = getattr(template, 'skill_category_order', None) or []
        if skill_category_order:
            # Fetch all active categories then sort by the saved order list.
            cats_qs = SkillCategory.objects.filter(tenant=self.tenant, is_active=True).prefetch_related(
                Prefetch('skill_items', queryset=items_qs, to_attr='active_items')
            )
            cat_map = {str(c.id): c for c in cats_qs}
            ordered = [cat_map[cid] for cid in skill_category_order if cid in cat_map]
            remaining = [c for sid, c in cat_map.items() if sid not in set(skill_category_order)]
            remaining.sort(key=lambda c: (c.display_order, c.name))
            categories = ordered + remaining
        else:
            categories = list(
                SkillCategory.objects.filter(tenant=self.tenant, is_active=True)
                .prefetch_related(
                    Prefetch('skill_items', queryset=items_qs, to_attr='active_items')
                ).order_by('display_order')
            )
        if not categories:
            return []

        assessment = SkillsAssessment.objects.filter(
            student=student,
            academic_year=template.academic_year,
            tenant=self.tenant,
        ).order_by('-assessment_date').first()

        level_map: Dict[str, str] = {}
        if assessment:
            for r in SkillAssessmentResult.objects.filter(
                assessment=assessment
            ).select_related('skill_item'):
                level_map[str(r.skill_item_id)] = r.level

        result: List[Dict[str, Any]] = []
        for cat in categories:
            items = getattr(cat, 'active_items', [])
            if not items:
                continue
            result.append({
                'category': cat.name,
                'items': [
                    {'name': item.description, 'level': level_map.get(str(item.id), '')}
                    for item in items
                ]
            })
        return result

    def _get_teacher_comment_data(self, student: Student, exam_group: ExamGroup,
                                  template: Optional[ReportTemplate] = None,
                                  _bulk_ctx: Optional[Dict] = None) -> dict:
        if _bulk_ctx and 'teacher_comments' in _bulk_ctx:
            return _bulk_ctx['teacher_comments'].get(str(student.id), {})
        # The explicit template matters: comments must come from the storage
        # matching the layout actually being rendered.
        svc = self._teacher_comment_service
        route = svc.resolve_route(exam_group, template=template)
        full_data = svc.get_comments_map(route, [str(student.id)]).get(str(student.id), {})
        # Return only comment and signature_image for simplicity
        return {
            'comment': full_data.get('comment', ''),
            'signature_image': full_data.get('signature_image', ''),
        }

    def _generate_html_report(self, template: ReportTemplate, report_data: Dict[str, Any]) -> str:
        try:
            html_template = self._get_html_template_name(template)
            return render_to_string(html_template, {'template': template, 'data': report_data})
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {str(e)}")
            raise ServiceException(f"HTML generation failed: {str(e)}")
    
    def _generate_pdf_from_html(self, html_content: str) -> bytes:
        try:
            from django.conf import settings
            from weasyprint import HTML
            # Reuse thread-local font configuration to avoid expensive filesystem scans
            font_config = self._get_font_config()
            base_url = f"file://{settings.MEDIA_ROOT}/"
            html_doc = HTML(string=html_content, base_url=base_url)
            return html_doc.write_pdf(font_config=font_config)
        except Exception as e:
            logger.error(f"Failed to generate PDF: {str(e)}")
            raise ServiceException(f"PDF generation failed: {str(e)}")
    
    def _save_report_file(self, report: StudentReport, content: Any, file_type: str) -> str:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{report.student.admission_no}_{report.template.name}_{timestamp}.{file_type}"
            file_path = f"reports/{report.tenant.schema_name}/{filename}"
            
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            return default_storage.save(file_path, ContentFile(content))
        except Exception as e:
            logger.error(f"Failed to save {file_type} file: {str(e)}")
            raise ServiceException(f"File save failed: {str(e)}")
    
    def _calculate_age(self, birth_date: date) -> str:
        if not birth_date:
            return "Unknown"
        today = date.today()
        age_years = today.year - birth_date.year
        age_months = today.month - birth_date.month
        if age_months < 0:
            age_years -= 1
            age_months += 12
        return f"{age_years} years {age_months} months"
    
    def _get_attainment_grade(self, score: ExamScore) -> str:
        if score.grading_level:
            return score.grading_level.name
        return 'A'
    
    def _get_effort_grade(self, score: ExamScore) -> str:
        return self._get_attainment_grade(score)
    
    def _get_default_grade_description(self, grade_name: str) -> str:
        grade_descriptions = {'A': 'Very Good', 'B': 'Good', 'C': 'Satisfactory', 'D': 'Weak', 'E': 'Very Weak'}
        return grade_descriptions.get(grade_name, 'Good')
    
    _SECTION_FLAGS = [
        'include_exam_scores', 'include_homework_assessment', 'include_project_work',
        'include_clubs', 'include_sports', 'include_other_activities',
        'include_attendance', 'include_grading_scale',
    ]

    def _compute_bulk_context(self, template: ReportTemplate, exam_group: ExamGroup,
                               student_ids: List[str]) -> Dict[str, Any]:
        batch = template.batch

        school_data   = self._get_school_data(template)
        template_data = self._get_template_data(template)
        term_data     = self._get_term_data(template, exam_group)
        grading_scale = self._get_grading_scale_data(batch, template=template)
        class_averages = self._get_class_averages(exam_group)
        rankings = self._get_class_rankings(template, exam_group)

        today = date.today()
        dobs = BatchStudent.objects.filter(
            batch=batch, is_active=True, student__date_of_birth__isnull=False
        ).values_list('student__date_of_birth', flat=True)
        average_batch_age = (
            round(sum((today - d).days / 365.25 for d in dobs) / len(dobs), 1)
            if dobs else None
        )

        batch_teachers = [f"{e.first_name} {e.last_name}".strip() for e in batch.class_teachers.all()]
        if not batch_teachers and batch.employee:
            batch_teachers = [f"{batch.employee.first_name} {batch.employee.last_name}".strip()]

        all_scores = (
            ExamScore.objects
            .filter(exam__exam_group=exam_group, tenant=self.tenant, student_id__in=student_ids)
            .select_related(
                'exam__subject', 'exam__grading_scale',
                'exam__subject__grading_scale',
                'grading_level', 'grade_value',
            )
        )
        scores_by_student: Dict[str, list] = defaultdict(list)
        for s in all_scores:
            scores_by_student[str(s.student_id)].append(s)

        # Homework / Project / Activities are keyed to the exam group's term + the
        # batch academic year — the same key the entry UI saves under.
        activity_term = self.resolve_exam_group_term(exam_group)
        activity_ay = exam_group.batch.academic_year

        # OPTIMIZATION: Use .values() to avoid full model instantiation overhead
        all_hw = HomeworkAssessment.objects.filter(
            student_id__in=student_ids, term=activity_term,
            academic_year=activity_ay, tenant=self.tenant,
        ).values('student_id', 'submission', 'presentation', 'effort')
        homework_by_student = {str(h['student_id']): h for h in all_hw}

        all_pw = ProjectWorkAssessment.objects.filter(
            student_id__in=student_ids, term=activity_term,
            academic_year=activity_ay, tenant=self.tenant,
        ).values('student_id', 'submission', 'presentation', 'effort')
        projects_by_student = {str(p['student_id']): p for p in all_pw}

        all_acts = StudentActivity.objects.filter(
            student_id__in=student_ids, term=activity_term,
            academic_year=activity_ay, tenant=self.tenant,
        )
        activities_by_student: Dict[str, list] = defaultdict(list)
        for a in all_acts:
            activities_by_student[str(a.student_id)].append(a)

        att_qs = Attendance.objects.filter(student_id__in=student_ids, tenant=self.tenant, batch=batch)
        attendance_start_date, attendance_end_date, *_ = self.resolve_attendance_range(exam_group)
        if attendance_start_date and attendance_end_date:
            att_qs = att_qs.filter(
                month_date__gte=attendance_start_date, month_date__lte=attendance_end_date
            )
        attendance_by_student: Dict[str, list] = defaultdict(list)
        for rec in att_qs.values('student_id', 'forenoon', 'afternoon', 'month_date'):
            attendance_by_student[str(rec['student_id'])].append(rec)

        ctx = {
            'school':                school_data,
            'template':              template_data,
            'term_info':             term_data,
            'grading_scale':         grading_scale,
            'class_averages':        class_averages,
            'rankings':              rankings,
            'average_batch_age':     average_batch_age,
            'batch_teachers':        batch_teachers,
            'scores_by_student':     dict(scores_by_student),
            'homework_by_student':   homework_by_student,
            'projects_by_student':   projects_by_student,
            'activities_by_student': dict(activities_by_student),
            'attendance_by_student': dict(attendance_by_student),
            'attendance_start_date': attendance_start_date,
            'attendance_end_date':   attendance_end_date,
            'attendance_batch':      batch,
        }

        layout = getattr(template, 'layout_type', 'FULL_ACADEMIC') or 'FULL_ACADEMIC'
        if layout == 'SKILLS':
            from django.db.models import Prefetch, Q
            # Shared skill activities (no batches attached) + those attached to
            # this report's batch (one batch per report run).
            items_qs = SkillItem.objects.filter(is_active=True).filter(
                Q(batches__isnull=True) | Q(batches=template.batch_id)
            ).distinct().order_by('display_order')
            categories = list(
                SkillCategory.objects.filter(tenant=self.tenant, is_active=True)
                .prefetch_related(
                    Prefetch('skill_items', queryset=items_qs, to_attr='active_items')
                ).order_by('display_order')
            )

            # Most recent assessment per student for this academic year
            assessment_list = list(SkillsAssessment.objects.filter(
                student_id__in=student_ids,
                academic_year=template.academic_year,
                tenant=self.tenant,
            ).order_by('-assessment_date'))
            assessments: Dict[str, Any] = {}
            for a in assessment_list:
                sid = str(a.student_id)
                if sid not in assessments:
                    assessments[sid] = a

            # All results for those assessments in one query
            assessment_ids = [a.id for a in assessments.values()]
            results_by_assessment: Dict[str, Dict[str, str]] = defaultdict(dict)
            for r in SkillAssessmentResult.objects.filter(
                assessment_id__in=assessment_ids
            ).select_related('skill_item'):
                results_by_assessment[str(r.assessment_id)][str(r.skill_item_id)] = r.level

            def _build_skills(sid: str) -> list:
                a = assessments.get(sid)
                level_map = results_by_assessment.get(str(a.id), {}) if a else {}
                out = []
                for cat in categories:
                    items = getattr(cat, 'active_items', [])
                    if not items:
                        continue
                    out.append({
                        'category': cat.name,
                        'items': [
                            {'name': item.description, 'level': level_map.get(str(item.id), '')}
                            for item in items
                        ]
                    })
                return out

            ctx['skills_by_student'] = {sid: _build_skills(sid) for sid in student_ids}

        tc_svc = self._teacher_comment_service
        tc_route = tc_svc.resolve_route(exam_group, template=template)
        ctx['teacher_comments'] = tc_svc.get_comments_map(tc_route, student_ids)

        return ctx

    def _process_student_in_thread(self, student, template_id, exam_group_id, template, bulk_ctx):
        """Worker function for parallel bulk generation."""
        try:
            self.generate_student_report(
                str(student.id), template_id, exam_group_id,
                _template=template, _bulk_ctx=bulk_ctx,
            )
            return str(student.id), None
        except Exception as e:
            return str(student.id), str(e)
        finally:
            # Crucial: Close the DB connection in each thread to prevent "too many connections" errors
            connection.close()

    def bulk_generate_reports(self, template_id: str, exam_group_id: str,
                              student_ids: List[str] = None,
                              section_overrides: Dict[str, bool] = None) -> Dict[str, Any]:
        """Generate reports for multiple students in parallel."""
        try:
            template   = ReportTemplate.objects.select_related('batch__employee', 'report_signature').get(id=template_id, tenant=self.tenant)
            exam_group = ExamGroup.objects.get(id=exam_group_id, tenant=self.tenant)

            if section_overrides:
                for flag in self._SECTION_FLAGS:
                    if flag in section_overrides:
                        setattr(template, flag, bool(section_overrides[flag]))

            students_query = Student.objects.filter(tenant=self.tenant, is_active=True)
            if student_ids:
                students_query = students_query.filter(id__in=student_ids)
            else:
                students_query = students_query.filter(
                    batchstudent__batch=template.batch, batchstudent__is_active=True,
                ).distinct()

            students = list(students_query)
            resolved_ids = [str(s.id) for s in students]

            bulk_ctx = self._compute_bulk_context(template, exam_group, resolved_ids)
            logger.info(f"Bulk context ready for {len(students)} students in exam group {exam_group.name}")

            results = {'total_students': len(students), 'successful': 0, 'failed': 0, 'errors': []}

            max_workers = min(8, len(students))  # Cap workers to avoid overwhelming the DB/CPU
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        self._process_student_in_thread, 
                        student, template_id, exam_group_id, template, bulk_ctx
                    ): student for student in students
                }
                
                for future in as_completed(futures):
                    student_id, error = future.result()
                    if error:
                        results['failed'] += 1
                        student = futures[future]
                        results['errors'].append({
                            'student_id': student_id,
                            'student_name': student.full_name,
                            'error': error,
                        })
                    else:
                        results['successful'] += 1

            logger.info(f"Bulk generation done: {results['successful']}/{results['total_students']} succeeded")
            return results

        except (ReportTemplate.DoesNotExist, ExamGroup.DoesNotExist) as e:
            raise NotFoundException(f"Required object not found: {e}")
        except Exception as e:
            logger.error(f"Bulk report generation failed: {e}")
            raise ServiceException(f"Bulk generation error: {e}")
    
    def get_report_status(self, student_id: str, template_id: str, exam_group_id: str) -> Dict[str, Any]:
        try:
            report = StudentReport.objects.get(
                student_id=student_id, template_id=template_id,
                exam_group_id=exam_group_id, tenant=self.tenant
            )
            return {
                'status': report.generation_status,
                'started_at': report.generation_started_at,
                'completed_at': report.generation_completed_at,
                'error': report.generation_error,
                'pdf_path': report.pdf_file_path,
                'html_path': report.html_file_path,
            }
        except StudentReport.DoesNotExist:
            return {'status': 'not_started'}