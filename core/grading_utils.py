"""
Grading utility functions for different grading systems
Supports Normal, GPA, CCE, ICSE, and CWA grading types
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from django.db.models import Avg, Sum, Count, Q
from .models import (
    Student, GradingType, GradingLevel, EnhancedExamScore,
    CoScholasticScore, StudentGradingProfile, Subject, Exam,
    SkillCategory, SkillItem, SkillsAssessment, SkillAssessmentResult,
    SkillsBasedGradingProfile, HomeworkAssessment
)


class GradingCalculator:
    """Main calculator for different grading systems"""

    @staticmethod
    def get_grade_for_score(score: Decimal, grading_type: GradingType) -> Optional[GradingLevel]:
        """Get the appropriate grade level for a given score"""
        if score is None:
            return None

        grade_levels = grading_type.grading_levels.filter(
            min_score__lte=score
        ).order_by('-min_score').first()

        return grade_levels

    @staticmethod
    def calculate_percentage(obtained_marks: Decimal, total_marks: Decimal) -> Decimal:
        """Calculate percentage with proper rounding"""
        if total_marks == 0:
            return Decimal('0.00')

        percentage = (obtained_marks / total_marks) * 100
        return percentage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_gpa(scores: List[EnhancedExamScore], grading_type: GradingType) -> Decimal:
        """Calculate GPA based on credit hours and grade points"""
        total_credit_points = Decimal('0.00')
        total_credit_hours = Decimal('0.00')

        for score in scores:
            if score.grade_points and score.subject.grading_settings:
                credit_hours = score.subject.grading_settings.credit_hours or Decimal('1.00')
                credit_points = score.grade_points * credit_hours

                total_credit_points += credit_points
                total_credit_hours += credit_hours

        if total_credit_hours > 0:
            gpa = total_credit_points / total_credit_hours
            return gpa.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return Decimal('0.00')

    @staticmethod
    def calculate_class_rankings(batch, exam_group, tenant) -> dict:
        """Calculate overall percentage and class rank for every student in the batch.

        Returns a dict mapping student_id (str) → {'total_pct': Decimal, 'rank': int}.
        Students with no marks are excluded from the ranking. Students carrying a
        'ranking' or 'grading' exemption (Configuration → Exempted Students) are
        also excluded so they neither take nor displace a position.
        """
        from django.db.models import Sum as _Sum
        from .models import ExamScore
        from core.services.configuration_service import exempt_student_ids

        excluded = exempt_student_ids(tenant, 'ranking') | exempt_student_ids(tenant, 'grading')

        # Aggregate marks per student across all exams in this exam_group
        qs = (
            ExamScore.objects
            .filter(exam__exam_group=exam_group, tenant=tenant, is_absent=False)
            .exclude(student_id__in=excluded)
            .values('student_id')
            .annotate(
                total_obtained=_Sum('marks'),
                total_possible=_Sum('exam__maximum_marks'),
            )
        )

        student_pcts = []
        for row in qs:
            if row['total_possible'] and row['total_possible'] > 0:
                pct = (
                    Decimal(str(row['total_obtained'] or 0)) /
                    Decimal(str(row['total_possible'])) * 100
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                student_pcts.append((str(row['student_id']), pct))

        # Sort descending; ties share the same rank
        student_pcts.sort(key=lambda x: x[1], reverse=True)

        rankings = {}
        current_rank = 1
        for i, (sid, pct) in enumerate(student_pcts):
            if i > 0 and pct < student_pcts[i - 1][1]:
                current_rank = i + 1
            rankings[sid] = {'total_pct': pct, 'rank': current_rank}

        return rankings


class CCEGradingCalculator:
    """Specialized calculator for CCE (Continuous Comprehensive Evaluation) system"""

    @staticmethod
    def calculate_scholastic_grade(student: Student, academic_year, term=None) -> Dict:
        """Calculate scholastic assessment grade for CCE"""
        scores = EnhancedExamScore.objects.filter(
            student=student,
            exam__exam_group__batch__academic_year=academic_year
        )

        if term:
            scores = scores.filter(exam__exam_group__term=term)

        # Calculate weighted average based on formative and summative assessments
        formative_total = Decimal('0.00')
        summative_total = Decimal('0.00')
        formative_obtained = Decimal('0.00')
        summative_obtained = Decimal('0.00')

        for score in scores:
            if score.formative_marks and score.formative_total:
                formative_obtained += score.formative_marks
                formative_total += score.formative_total

            if score.summative_marks and score.summative_total:
                summative_obtained += score.summative_marks
                summative_total += score.summative_total

        # Calculate weighted percentage
        formative_percentage = (formative_obtained / formative_total * 100) if formative_total > 0 else Decimal('0')
        summative_percentage = (summative_obtained / summative_total * 100) if summative_total > 0 else Decimal('0')

        # Default CCE weights (can be customized per grading type)
        formative_weight = Decimal('40.00')  # 40%
        summative_weight = Decimal('60.00')  # 60%

        overall_percentage = (
            (formative_percentage * formative_weight / 100) +
            (summative_percentage * summative_weight / 100)
        )

        return {
            'formative_percentage': formative_percentage.quantize(Decimal('0.01')),
            'summative_percentage': summative_percentage.quantize(Decimal('0.01')),
            'overall_percentage': overall_percentage.quantize(Decimal('0.01')),
            'grade': CCEGradingCalculator._get_cce_grade(overall_percentage)
        }

    @staticmethod
    def calculate_coscholastic_grade(student: Student, academic_year, term=None) -> Dict:
        """Calculate co-scholastic assessment grade for CCE"""
        scores = CoScholasticScore.objects.filter(
            student=student,
            academic_year=academic_year
        )

        if term:
            scores = scores.filter(term=term)

        total_obtained = Decimal('0.00')
        total_possible = Decimal('0.00')
        assessments_count = scores.count()

        for score in scores:
            if score.obtained_score and score.max_score:
                total_obtained += score.obtained_score
                total_possible += score.max_score

        if total_possible > 0:
            percentage = (total_obtained / total_possible) * 100
            grade = CCEGradingCalculator._get_cce_grade(percentage)
        else:
            percentage = Decimal('0.00')
            grade = 'E'

        return {
            'total_obtained': total_obtained,
            'total_possible': total_possible,
            'percentage': percentage.quantize(Decimal('0.01')),
            'grade': grade,
            'assessments_count': assessments_count
        }

    @staticmethod
    def _get_cce_grade(percentage: Decimal) -> str:
        """Convert percentage to CCE grade"""
        if percentage >= 90:
            return 'A+'
        elif percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B+'
        elif percentage >= 60:
            return 'B'
        elif percentage >= 50:
            return 'C+'
        elif percentage >= 40:
            return 'C'
        elif percentage >= 30:
            return 'D'
        else:
            return 'E'

    @staticmethod
    def calculate_overall_cce_grade(student: Student, academic_year, grading_type: GradingType) -> str:
        """Calculate overall CCE grade combining scholastic and co-scholastic"""
        scholastic_data = CCEGradingCalculator.calculate_scholastic_grade(student, academic_year)
        coscholastic_data = CCEGradingCalculator.calculate_coscholastic_grade(student, academic_year)

        # Weight the grades according to CCE system (typically 70% scholastic, 30% co-scholastic)
        scholastic_weight = grading_type.cce_scholastic_weight or Decimal('70.00')
        coscholastic_weight = grading_type.cce_coscholastic_weight or Decimal('30.00')

        overall_percentage = (
            (scholastic_data['overall_percentage'] * scholastic_weight / 100) +
            (coscholastic_data['percentage'] * coscholastic_weight / 100)
        )

        return CCEGradingCalculator._get_cce_grade(overall_percentage)


class ReportCardGenerator:
    """Generate comprehensive report card data"""

    @staticmethod
    def generate_student_report_data(student: Student, academic_year, term=None, grading_type: GradingType = None) -> Dict:
        """Generate comprehensive report card data for a student"""
        if not grading_type:
            # Try to get grading type from student's batch
            batch = student.student_batches.filter(
                batch__academic_year=academic_year,
                is_active=True
            ).first()
            if batch and batch.batch.grading_type:
                grading_type = batch.batch.grading_type
            else:
                # Default to Normal grading
                grading_type = GradingType.objects.filter(code='NORMAL').first()

        report_data = {
            'student_info': {
                'name': student.full_name,
                'admission_no': student.admission_no,
                'class': None,
                'age': student.age_in_years,
                'academic_year': academic_year.name,
                'term': term.name if term else 'Full Year',
            },
            'subjects': [],
            'scholastic_summary': {},
            'coscholastic_assessments': {},
            'activities': {},
            'attendance': {},
            'grading_scale': {},
        }

        # Get student's batch/class information
        batch_student = student.student_batches.filter(
            batch__academic_year=academic_year,
            is_active=True
        ).first()
        batch = batch_student.batch if batch_student else None

        if batch_student:
            report_data['student_info']['class'] = batch.name
            report_data['student_info']['class_teacher'] = batch.employee.full_name if batch.employee else 'N/A'

        # Get student's term-level effort from homework assessment
        homework_effort = 'N/A'
        try:
            hw = HomeworkAssessment.objects.get(
                student=student,
                academic_year=academic_year,
                term=term
            )
            homework_effort = hw.effort
        except HomeworkAssessment.DoesNotExist:
            pass

        # Get academic subjects and scores
        exam_scores = EnhancedExamScore.objects.filter(
            student=student,
            exam__exam_group__batch__academic_year=academic_year
        ).select_related('subject', 'exam')

        if term:
            exam_scores = exam_scores.filter(exam__exam_group__term=term)

        # Group by subject
        subject_data = {}
        for score in exam_scores:
            subject_name = score.subject.name
            if subject_name not in subject_data:
                subject_data[subject_name] = {
                    'name': subject_name,
                    'subject_id': score.subject.id,
                    'scores': [],
                    'total_marks': Decimal('0.00'),
                    'obtained_marks': Decimal('0.00'),
                }

            subject_data[subject_name]['scores'].append(score)
            if score.obtained_marks:
                subject_data[subject_name]['obtained_marks'] += score.obtained_marks
            subject_data[subject_name]['total_marks'] += score.total_marks

        # Pre-compute class averages for all subjects in this batch.
        # Aggregate total obtained and total possible marks per subject across
        # all exams so that subjects with multiple exam components (e.g. midterm
        # + final) produce a single weighted average rather than a last-write-wins value.
        class_averages = {}
        if batch:
            avg_qs = EnhancedExamScore.objects.filter(
                exam__exam_group__batch=batch,
                obtained_marks__isnull=False,
            )
            if term:
                avg_qs = avg_qs.filter(exam__exam_group__term=term)
            from django.db.models import Sum as _Sum
            for row in avg_qs.values('subject__name').annotate(
                total_obtained=_Sum('obtained_marks'),
                total_possible=_Sum('exam__maximum_marks'),
            ):
                subj = row['subject__name']
                total_possible = row['total_possible']
                if total_possible and total_possible > 0:
                    pct = Decimal(str(row['total_obtained'])) / Decimal(str(total_possible)) * 100
                    class_averages[subj] = pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Calculate subject-wise results
        for subject_name, data in subject_data.items():
            percentage = GradingCalculator.calculate_percentage(
                data['obtained_marks'],
                data['total_marks']
            )
            grade_level = GradingCalculator.get_grade_for_score(percentage, grading_type)

            subject_info = {
                'name': subject_name,
                'obtained_marks': data['obtained_marks'],
                'total_marks': data['total_marks'],
                'percentage': percentage,
                'grade': grade_level.name if grade_level else 'N/A',
                'class_average': class_averages.get(subject_name, Decimal('0.00')),
                'attainment': grade_level.name if grade_level else 'N/A',
                'effort': homework_effort,
            }

            report_data['subjects'].append(subject_info)

        # CCE-specific calculations
        if grading_type.code == 'CCE':
            report_data['scholastic_summary'] = CCEGradingCalculator.calculate_scholastic_grade(
                student, academic_year, term
            )
            report_data['coscholastic_assessments'] = CCEGradingCalculator.calculate_coscholastic_grade(
                student, academic_year, term
            )

        # Get co-scholastic scores
        coscholastic_scores = CoScholasticScore.objects.filter(
            student=student,
            academic_year=academic_year
        )

        if term:
            coscholastic_scores = coscholastic_scores.filter(term=term)

        coscholastic_data = {}
        for score in coscholastic_scores:
            assessment_name = score.assessment.name
            coscholastic_data[assessment_name] = {
                'name': assessment_name,
                'grade': score.grade or 'N/A',
                'remarks': score.remarks or '',
            }

        report_data['coscholastic_assessments']['details'] = coscholastic_data

        # Get grading scale information
        grade_levels = grading_type.grading_levels.all().order_by('-min_score')
        grading_scale = []
        for level in grade_levels:
            grading_scale.append({
                'grade': level.name,
                'min_score': level.min_score,
                'max_score': level.max_score,
                'description': level.description or '',
            })

        report_data['grading_scale'] = grading_scale

        return report_data


class SkillsAssessmentCalculator:
    """Calculator for early childhood skills-based assessment"""

    @staticmethod
    def get_age_appropriate_skills(student: Student, category: SkillCategory = None) -> List[SkillItem]:
        """Get skills appropriate for student's age"""
        age_in_months = student.age_in_months if hasattr(student, 'age_in_months') else None

        skills = SkillItem.objects.filter(is_active=True)

        if category:
            skills = skills.filter(category=category)

        if age_in_months:
            skills = skills.filter(
                Q(min_age_months__lte=age_in_months) | Q(min_age_months__isnull=True),
                Q(max_age_months__gte=age_in_months) | Q(max_age_months__isnull=True)
            )

        return skills.order_by('category__display_order', 'display_order')

    @staticmethod
    def calculate_category_summary(student: Student, category: SkillCategory, academic_year, term=None) -> Dict:
        """Calculate summary for a skill category"""
        assessments = SkillsAssessment.objects.filter(
            student=student,
            academic_year=academic_year,
            is_completed=True
        )

        if term:
            assessments = assessments.filter(term=term)

        # Get results for this category
        results = SkillAssessmentResult.objects.filter(
            assessment__in=assessments,
            skill_item__category=category
        )

        total_count = results.count()
        if total_count == 0:
            return {
                'category': category.name,
                'total_skills': 0,
                'not_yet': 0,
                'beginning': 0,
                'satisfactory': 0,
                'good': 0,
                'not_yet_percentage': 0,
                'beginning_percentage': 0,
                'satisfactory_percentage': 0,
                'good_percentage': 0,
                'overall_level': 'NOT_YET'
            }

        not_yet_count = results.filter(level='NOT_YET').count()
        beginning_count = results.filter(level='BEGINNING').count()
        satisfactory_count = results.filter(level='SATISFACTORY').count()
        good_count = results.filter(level='GOOD').count()

        return {
            'category': category.name,
            'total_skills': total_count,
            'not_yet': not_yet_count,
            'beginning': beginning_count,
            'satisfactory': satisfactory_count,
            'good': good_count,
            'not_yet_percentage': (not_yet_count / total_count) * 100,
            'beginning_percentage': (beginning_count / total_count) * 100,
            'satisfactory_percentage': (satisfactory_count / total_count) * 100,
            'good_percentage': (good_count / total_count) * 100,
            'overall_level': SkillsAssessmentCalculator._determine_category_level(
                not_yet_count, beginning_count, satisfactory_count, good_count
            )
        }

    @staticmethod
    def _determine_category_level(not_yet: int, beginning: int, satisfactory: int, good: int) -> str:
        """Determine overall level for a category based on skill distribution"""
        total = not_yet + beginning + satisfactory + good
        if total == 0:
            return 'NOT_YET'

        good_percentage = (good / total) * 100
        satisfactory_plus_good = ((satisfactory + good) / total) * 100

        if good_percentage >= 60:
            return 'GOOD'
        elif satisfactory_plus_good >= 60:
            return 'SATISFACTORY'
        elif (beginning + satisfactory + good) / total * 100 >= 60:
            return 'BEGINNING'
        else:
            return 'NOT_YET'

    @staticmethod
    def generate_skills_report_data(student: Student, academic_year, term=None) -> Dict:
        """Generate comprehensive skills assessment report"""
        report_data = {
            'student_info': {
                'name': student.full_name,
                'admission_no': student.admission_no,
                'age': student.age_in_years if hasattr(student, 'age_in_years') else 'N/A',
                'academic_year': academic_year.name,
                'term': term.name if term else 'Full Year',
                'class': None,
                'class_teachers': [],
            },
            'skill_categories': [],
            'overall_summary': {},
            'project_work': {},
            'attendance': {}
        }

        # Get student's batch/class information
        batch_student = student.student_batches.filter(
            batch__academic_year=academic_year,
            is_active=True
        ).first()

        if batch_student:
            report_data['student_info']['class'] = batch_student.batch.name
            if batch_student.batch.employee:
                report_data['student_info']['class_teachers'].append(
                    batch_student.batch.employee.full_name
                )

        # Get all skill categories
        categories = SkillCategory.objects.filter(is_active=True).order_by('display_order')

        # Generate category summaries
        for category in categories:
            category_summary = SkillsAssessmentCalculator.calculate_category_summary(
                student, category, academic_year, term
            )

            # Get detailed skill results for this category
            assessments = SkillsAssessment.objects.filter(
                student=student,
                academic_year=academic_year,
                is_completed=True
            )

            if term:
                assessments = assessments.filter(term=term)

            skill_results = []
            results = SkillAssessmentResult.objects.filter(
                assessment__in=assessments,
                skill_item__category=category
            ).select_related('skill_item')

            for result in results:
                skill_results.append({
                    'description': result.skill_item.description,
                    'level': result.get_level_display(),
                    'level_code': result.level,
                    'notes': result.notes or ''
                })

            category_summary['skills'] = skill_results
            report_data['skill_categories'].append(category_summary)

        # Calculate overall summary
        total_skills = sum(cat['total_skills'] for cat in report_data['skill_categories'])
        if total_skills > 0:
            total_not_yet = sum(cat['not_yet'] for cat in report_data['skill_categories'])
            total_beginning = sum(cat['beginning'] for cat in report_data['skill_categories'])
            total_satisfactory = sum(cat['satisfactory'] for cat in report_data['skill_categories'])
            total_good = sum(cat['good'] for cat in report_data['skill_categories'])

            report_data['overall_summary'] = {
                'total_skills_assessed': total_skills,
                'not_yet_count': total_not_yet,
                'beginning_count': total_beginning,
                'satisfactory_count': total_satisfactory,
                'good_count': total_good,
                'not_yet_percentage': (total_not_yet / total_skills) * 100,
                'beginning_percentage': (total_beginning / total_skills) * 100,
                'satisfactory_percentage': (total_satisfactory / total_skills) * 100,
                'good_percentage': (total_good / total_skills) * 100,
                'overall_development_level': SkillsAssessmentCalculator._determine_category_level(
                    total_not_yet, total_beginning, total_satisfactory, total_good
                )
            }

        return report_data


# Course-name keywords used to infer the report layout when no grading scale
# states it explicitly. Kept here so the planner view, report generation, and the
# backfill migration all share one definition.
_SKILLS_COURSE_KEYWORDS = (
    'RECEPTION', 'BEGINNERS', 'MIDDLE CLASS', 'NURSERY', 'PRE-SCHOOL', 'PREP',
    'KINDERGARTEN', 'KG',
)
_SIMPLE_COURSE_KEYWORDS = (
    'GRADE 1', 'GRADE 2', 'YEAR 1', 'YEAR 2', 'STD 1', 'STD 2', 'CLASS 1', 'CLASS 2',
)

# Default grading-scale codes seeded per layout (see seed_grading_scales).
_LAYOUT_SCALE_CODES = {
    'SKILLS': 'SKILL_LEVELS',
    'SIMPLE_ACADEMIC': 'LETTER_4POINT',
    'FULL_ACADEMIC': 'LETTER_GRADES',
}


def infer_report_layout(batch):
    """Infer the report-card layout for a batch and a matching default scale.

    Resolution order (mirrors the lazy logic in ``generate_class_reports``):
      1. The batch's default grading scale, if it declares a ``report_layout``.
      2. Course-name keywords (Reception/Beginners/Middle → SKILLS;
         Grade 1/2 → SIMPLE_ACADEMIC; everything else → FULL_ACADEMIC).

    Returns ``(layout_type, grading_scale_or_None)``. ``grading_scale`` is the
    scale that justified the layout (the batch default, or the seeded default
    scale for the inferred layout) and may be ``None`` if none is found.
    """
    from .models import ReportTemplate, GradingScale

    # 1. Batch default grading scale wins when it names a layout.
    batch_scale = getattr(batch, 'default_grading_scale', None)
    if batch_scale and getattr(batch_scale, 'report_layout', ''):
        return batch_scale.report_layout, batch_scale

    # 2. Derive from the course name (fall back to the batch name).
    text = ''
    try:
        text = (batch.course.course_name or '').upper()
    except Exception:
        pass
    text = f"{text} {(getattr(batch, 'name', '') or '').upper()}"

    if any(kw in text for kw in _SKILLS_COURSE_KEYWORDS):
        layout = ReportTemplate.LAYOUT_SKILLS
    elif any(kw in text for kw in _SIMPLE_COURSE_KEYWORDS):
        layout = ReportTemplate.LAYOUT_SIMPLE
    else:
        layout = ReportTemplate.LAYOUT_FULL

    tenant = getattr(batch, 'tenant', None)
    scale = None
    code = _LAYOUT_SCALE_CODES.get(layout)
    if tenant and code:
        scale = GradingScale.objects.filter(
            tenant=tenant, code=code, is_active=True
        ).first()
    return layout, scale


# Report sections (Exam.assessment_slot values) shown per layout, in display
# order. SKILLS layouts have no exam-driven sections — they use the skills
# checklist instead.
_LAYOUT_REPORT_SECTIONS = {
    'FULL_ACADEMIC': [
        ('EXAM',       'Examination / Test'),
        ('ATTAINMENT', 'Attainment'),
        ('EFFORT',     'Effort'),
    ],
    'SIMPLE_ACADEMIC': [
        ('CLASSWORK', 'Classwork'),
        ('TEST',      'Test'),
    ],
    'SKILLS': [],
}


def report_sections_for_layout(layout):
    """Ordered ``[(slot, title), ...]`` of report sections for a layout."""
    return list(_LAYOUT_REPORT_SECTIONS.get(layout, _LAYOUT_REPORT_SECTIONS['FULL_ACADEMIC']))


def valid_slots_for_layout(layout):
    """Set of ``Exam.assessment_slot`` values valid for a layout."""
    return {slot for slot, _ in report_sections_for_layout(layout)}