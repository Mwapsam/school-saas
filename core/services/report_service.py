import logging
from datetime import datetime, date
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Spacer
)
from reportlab.lib.enums import TA_CENTER
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Avg

# Ensure your models are imported
from core.models import (
    Exam, ExamScore, HomeworkAssessment, ProjectWorkAssessment,
    StudentActivity, Attendance, BatchStudent, GradingLevel
)

logger = logging.getLogger(__name__)

class StudentReportService:
    """Optimized Service for generating student assessment reports"""

    def __init__(self, tenant):
        self.tenant = tenant
        self.styles = getSampleStyleSheet()
        self.school_green = colors.Color(0.4, 0.7, 0.4)
        self.header_green = colors.Color(0.78, 0.89, 0.78)
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom styles for the report (unchanged from original)"""
        self.school_name_style = ParagraphStyle("SchoolName", parent=self.styles["Title"], fontSize=18, fontName="Helvetica-Bold", spaceAfter=4, alignment=TA_CENTER, textColor=self.school_green)
        self.school_details_style = ParagraphStyle("SchoolDetails", parent=self.styles["Normal"], fontSize=8, spaceAfter=2, alignment=TA_CENTER)
        self.normal_style = ParagraphStyle("CustomNormal", parent=self.styles["Normal"], fontSize=8, spaceAfter=4)

    def generate_student_report(self, student, exam_group, batch, template=None):
        """Main entry point to generate the PDF"""
        from core.models import StudentReport
        from django.utils import timezone

        # 1. Pre-fetch ALL data in minimal queries (Fixes N+1 problem)
        ctx = self._build_context(student, exam_group, batch)

        # 2. Setup PDF document
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)
        
        story = []
        story.extend(self._build_header(ctx))
        story.extend(self._build_student_info(ctx))
        story.extend(self._build_additional_sections(ctx)) # Homework, Projects, Clubs
        story.extend(self._build_examination_results(ctx))
        story.extend(self._build_attendance_and_grading(ctx))
        story.extend(self._build_signature(ctx))

        # 3. Build and Save PDF
        doc.build(story)
        buffer.seek(0)
        
        filename = f"report_{student.admission_no}_{exam_group.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        report_path = f"reports/{self.tenant.schema_name}/{filename}"
        saved_path = default_storage.save(report_path, ContentFile(buffer.read()))

        return default_storage.url(saved_path)

    # ─────────────────────────────────────────────────────────────────────────────
    # DATA FETCHING (Optimized)
    # ─────────────────────────────────────────────────────────────────────────────

    def _build_context(self, student, exam_group, batch):
        """Fetch all required data in minimal database queries."""
        ctx = {'student': student, 'batch': batch, 'exam_group': exam_group, 'tenant': self.tenant}

        # 1. Student Info & Age
        ctx['age_display'] = self._calculate_age(student.date_of_birth)
        ctx['class_teacher'] = (batch.class_teacher_names() if batch else "") or "N/A"
        
        # Average age of grade (1 query)
        dobs = BatchStudent.objects.filter(batch=batch, is_active=True, student__date_of_birth__isnull=False).values_list('student__date_of_birth', flat=True)
        if dobs:
            today = date.today()
            ages = [(today - dob).days / 365.25 for dob in dobs]
            ctx['average_age'] = round(sum(ages) / len(ages), 1)
        else:
            ctx['average_age'] = "N/A"

        # Next term start date
        ctx['next_term_start'] = "N/A"
        current_terms = list(batch.academic_year.terms_by_year.order_by('order'))
        for i, t in enumerate(current_terms):
            if t.name == exam_group.name and i + 1 < len(current_terms):
                ctx['next_term_start'] = current_terms[i+1].start_date.strftime("%d/%m/%Y")
                break

        # 2. Exam Results & Class Averages (FIXES N+1 QUERY PROBLEM)
        exams = list(Exam.objects.filter(exam_group=exam_group, subject__batch=batch, tenant=self.tenant).select_related('subject').order_by('subject__name'))
        exam_ids = [e.id for e in exams]
        
        # Student scores (1 query)
        student_scores = ExamScore.objects.filter(student=student, exam_id__in=exam_ids, tenant=self.tenant).select_related('exam', 'exam__subject')
        ctx['score_lookup'] = {s.exam_id: s for s in student_scores}

        # Class averages using SQL aggregation (1 query instead of N queries!)
        class_avgs = ExamScore.objects.filter(
            exam_id__in=exam_ids, student__batchstudent__batch=batch, student__batchstudent__is_active=True, is_absent=False, tenant=self.tenant
        ).values('exam_id').annotate(avg_marks=Avg('marks'))
        ctx['avg_lookup'] = {item['exam_id']: round(float(item['avg_marks']), 1) if item['avg_marks'] else 0 for item in class_avgs}
        ctx['exams'] = exams

        # 3. Homework & Project Work
        term_name = exam_group.name
        academic_year = batch.academic_year
        ctx['homework'] = HomeworkAssessment.objects.filter(student=student, term=term_name, academic_year=academic_year, tenant=self.tenant).first()
        ctx['project_work'] = ProjectWorkAssessment.objects.filter(student=student, term=term_name, academic_year=academic_year, tenant=self.tenant).first()

        # 4. Activities
        activities = StudentActivity.objects.filter(student=student, term=term_name, academic_year=academic_year, tenant=self.tenant)
        ctx['clubs'] = [a.activity_name for a in activities if a.activity_type == 'club']
        ctx['sports'] = [a.activity_name for a in activities if a.activity_type == 'sport']
        ctx['other'] = [a.activity_name for a in activities if a.activity_type not in ['club', 'sport']]

        # 5. Attendance
        records = list(Attendance.objects.filter(student=student, tenant=self.tenant).values('forenoon', 'afternoon'))
        ctx['attendance_present'] = sum(1 for r in records if r['forenoon'] or r['afternoon'])
        ctx['attendance_absent'] = len(records) - ctx['attendance_present']

        # 6. Grading Scale
        ctx['grading_scale'] = list(GradingLevel.objects.filter(batch=batch, is_deleted=False, tenant=self.tenant).order_by('-min_score'))
        if not ctx['grading_scale']:
            ctx['grading_scale'] = [
                {'grade': 'A', 'min_score': 80, 'description': 'Very Good'},
                {'grade': 'B', 'min_score': 60, 'description': 'Good'},
                {'grade': 'C', 'min_score': 50, 'description': 'Satisfactory'},
                {'grade': 'D', 'min_score': 40, 'description': 'Weak'},
                {'grade': 'E', 'min_score': 0, 'description': 'Very Weak'},
            ]

        return ctx

    # ─────────────────────────────────────────────────────────────────────────────
    # PDF BUILDING BLOCKS (Dynamic Data)
    # ─────────────────────────────────────────────────────────────────────────────

    def _build_header(self, ctx):
        elements = []
        # (Header logic remains the same as your original code, just pass ctx if needed)
        # ... [Insert your original _build_enhanced_header logic here] ...
        return elements

    def _build_student_info(self, ctx):
        elements = []
        student, batch, exam_group = ctx['student'], ctx['batch'], ctx['exam_group']
        
        info_data = [
            ["Name of pupil", "Class", "Admn No.", "Age", "Average age of grade", "Class teacher(s)"],
            [student.full_name, batch.name, student.admission_no, ctx['age_display'], str(ctx['average_age']), ctx['class_teacher']],
            ["Term", "", "", "", "", "Next term commences"],
            [exam_group.name, "", "", "", "", str(ctx['next_term_start'])],
        ]
        
        col_widths = [40*mm, 28*mm, 18*mm, 30*mm, 30*mm, 34*mm]
        table = Table(info_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica'), ('FONTSIZE', (0, 2), (-1, 2), 8),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'), ('TEXTCOLOR', (0, 1), (-1, 1), self.school_green),
            ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'), ('TEXTCOLOR', (0, 3), (-1, 3), self.school_green),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.white), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 6))
        return elements

    def _build_examination_results(self, ctx):
        elements = []
        exams, score_lookup, avg_lookup, grading_scale = ctx['exams'], ctx['score_lookup'], ctx['avg_lookup'], ctx['grading_scale']
        
        headers = [
            ["EXAMINATION/TEST", "", "", "TERM", "", ""],
            ["SUBJECTS", "MARKS (%)", "GRADE", "CLASS AV. (%)", "ATTAINMENT", "EFFORT"],
        ]
        
        subjects_data = []
        for exam in exams:
            score = score_lookup.get(exam.id)
            if score and not score.is_absent:
                marks = f"{int(score.marks)}" if score.marks is not None else "-"
                grade = self._calculate_grade(score.marks, grading_scale)
                class_avg = avg_lookup.get(exam.id)
                class_avg_str = f"{int(class_avg)}" if class_avg is not None else "-"
                attainment = effort = grade
            else:
                marks = grade = class_avg_str = attainment = effort = "-"
                
            subjects_data.append([exam.subject.name, marks, grade, class_avg_str, attainment, effort])
            
        all_data = headers + subjects_data
        col_widths = [70*mm, 20*mm, 17*mm, 24*mm, 24*mm, 25*mm]
        
        table = Table(all_data, colWidths=col_widths, repeatRows=2)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 1), self.header_green), ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'),
            ('SPAN', (0, 0), (2, 0)), ('SPAN', (3, 0), (5, 0)), ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 10))
        return elements

    def _build_additional_sections(self, ctx):
        elements = []
        exam_group_name = ctx['exam_group'].name
        
        def get_val(obj, attr): return getattr(obj, attr, "Not Assessed") or "Not Assessed"

        # Homework & Project Work Tables (Dynamic)
        hw_data = [["HOMEWORK", exam_group_name], ["Submission", get_val(ctx['homework'], 'submission')], ["Presentation", get_val(ctx['homework'], 'presentation')], ["Effort", get_val(ctx['homework'], 'effort')]]
        pw_data = [["PROJECT WORK", exam_group_name], ["Submission", get_val(ctx['project_work'], 'submission')], ["Presentation", get_val(ctx['project_work'], 'presentation')], ["Effort", get_val(ctx['project_work'], 'effort')]]
        
        # (Apply your original styling to hw_table and pw_table here...)
        # elements.append(Table([[hw_table, pw_table]], colWidths=[87*mm, 93*mm]))

        # Activities (Dynamic)
        clubs_data = [["CLUBS"]] + [[c] for c in ctx['clubs']] if ctx['clubs'] else [["CLUBS"], ["-"]]
        sports_data = [["SPORTS"]] + [[s] for s in ctx['sports']] if ctx['sports'] else [["SPORTS"], ["-"]]
        other_data = [["OTHER"]] + [[o] for o in ctx['other']] if ctx['other'] else [["OTHER"], ["-"]]
        
        # (Apply your original styling to clubs_table, sports_table, other_table here...)
        return elements

    def _build_attendance_and_grading(self, ctx):
        elements = []
        exam_group_name = ctx['exam_group'].name
        
        # Attendance (Dynamic)
        att_data = [["Attendance", exam_group_name], ["No. of days present", f"{float(ctx['attendance_present'])}"], ["No. of days absent", f"{float(ctx['attendance_absent'])}"]]
        # (Apply styling to att_table)

        # Grading Scale (Dynamic)
        scale_list = []
        for level in ctx['grading_scale']:
            if hasattr(level, 'grade'):
                scale_list.append({'grade': level.grade, 'min_score': level.min_score, 'description': level.description or ''})
            else:
                scale_list.append(level)
                
        grading_data = [
            ["Scholastic Grade Scale: Grades are awarded on a 5 point grading scale as follows", "", "", "", "", ""],
            ["Grade"] + [s['grade'] for s in scale_list],
            ["Minimum score"] + [str(s['min_score']) for s in scale_list],
            ["Description"] + [s['description'] for s in scale_list]
        ]
        # (Apply styling to grading_table)
        
        # elements.append(Table([[att_table, grading_table]], colWidths=[87*mm, 93*mm]))
        return elements

    def _build_signature(self, ctx):
        elements = []
        # (Insert your original signature logic here)
        return elements

    # ─────────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────────

    def _calculate_age(self, birth_date):
        if not birth_date: return "Unknown"
        today = date.today()
        age_years = today.year - birth_date.year
        age_months = today.month - birth_date.month
        if age_months < 0: age_years -= 1; age_months += 12
        return f"{age_years} years {age_months} months"

    def _calculate_grade(self, marks, grading_scale):
        """Dynamic grading based on the fetched grading scale"""
        if marks is None: return "-"
        for level in grading_scale:
            min_score = level.min_score if hasattr(level, 'min_score') else level['min_score']
            grade = level.grade if hasattr(level, 'grade') else level['grade']
            if marks >= min_score:
                return grade
        return "-"