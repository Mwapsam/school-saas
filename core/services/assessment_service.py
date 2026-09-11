"""
Unified Assessment Service - Black Box Interface

This service provides a single, clean interface for retrieving student assessments
regardless of whether they come from:
- Traditional exams (numeric marks)
- Skills assessments (descriptive levels)
- Activity-based assessments (graded activities)
- Hybrid combinations of the above

The service abstracts away the complexity of different assessment types and
presents a unified view for report generation and grade calculation.
"""

import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from django.db.models import Q, QuerySet, Avg, Sum
from datetime import date

from core.models import (
    Student,
    Subject,
    SubjectSkillSet,
    Exam,
    ExamScore,
    SkillsAssessment,
    SkillAssessmentResult,
    Term,
    AcademicYear,
)
from .base import TenantAwareService
from .exceptions import NotFoundException, ValidationException
from .logging_service import ServiceLogger, logged_operation

logger = logging.getLogger(__name__)


class UnifiedAssessment:
    """
    Unified data structure representing a student's assessment for a subject.

    This is the primitive returned by the AssessmentService - a simple,
    consistent structure regardless of the underlying assessment type.
    """

    def __init__(
        self,
        subject: Subject,
        student: Student,
        term: Optional[Term] = None,
        academic_year: Optional[AcademicYear] = None
    ):
        self.subject = subject
        self.student = student
        self.term = term
        self.academic_year = academic_year

        # Assessment results
        self.exam_scores = []  # List of {exam, marks, max_marks, percentage}
        self.skill_results = []  # List of {skill_set, skills: [{skill, level}]}
        self.activity_grades = []  # List of {activity, grade, grade_level}

        # Computed values
        self.total_marks = None
        self.maximum_marks = None
        self.percentage = None
        self.final_grade = None
        self.assessment_type = subject.get_assessment_type()

    def has_data(self):
        """Returns True if any assessment data exists"""
        return bool(
            self.exam_scores or
            self.skill_results or
            self.activity_grades
        )

    def get_numeric_component(self):
        """Returns the numeric marks component (from exams or converted skills)"""
        if self.total_marks is not None and self.maximum_marks is not None:
            return {
                'marks': float(self.total_marks),
                'max_marks': float(self.maximum_marks),
                'percentage': float(self.percentage) if self.percentage else 0.0
            }
        return None

    def get_descriptive_component(self):
        """Returns the descriptive skills component"""
        return self.skill_results if self.skill_results else None

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'subject': {
                'id': str(self.subject.id),
                'name': self.subject.name,
                'code': self.subject.code
            },
            'student': {
                'id': str(self.student.id),
                'name': self.student.full_name
            },
            'assessment_type': self.assessment_type,
            'exam_scores': self.exam_scores,
            'skill_results': self.skill_results,
            'activity_grades': self.activity_grades,
            'summary': {
                'total_marks': float(self.total_marks) if self.total_marks else None,
                'maximum_marks': float(self.maximum_marks) if self.maximum_marks else None,
                'percentage': float(self.percentage) if self.percentage else None,
                'final_grade': self.final_grade
            }
        }


class AssessmentService(TenantAwareService):
    """
    Unified service for retrieving and managing all types of student assessments.

    This service is the single entry point for assessment data, regardless of type.
    It follows the black box principle: consumers don't need to know about
    the underlying structure of Exam, ExamScore, SkillSet, etc.
    """

    def __init__(self, tenant):
        super().__init__(Subject, tenant)
        self.logger = ServiceLogger('assessment', tenant)

    @logged_operation(action='retrieve', resource_type='student_assessment')
    def get_student_assessment(
        self,
        student_id: str,
        subject_id: str,
        term_id: Optional[str] = None,
        academic_year_id: Optional[str] = None
    ) -> UnifiedAssessment:
        """
        Retrieve a unified assessment for a student in a specific subject.

        This is the primary interface method. It returns a UnifiedAssessment
        object that contains all assessment data regardless of type.
        """
        student = self._get_student_by_id(student_id)
        subject = self.get_by_id(subject_id)

        term = None
        academic_year = None

        if term_id:
            term = self._get_term_by_id(term_id)
        if academic_year_id:
            academic_year = self._get_academic_year_by_id(academic_year_id)

        assessment = UnifiedAssessment(
            subject=subject,
            student=student,
            term=term,
            academic_year=academic_year
        )

        # Populate exam scores if subject has exams
        if subject.has_exams():
            self._populate_exam_scores(assessment, student, subject, term)

        # Populate skill results if subject has skills
        if subject.has_skills():
            self._populate_skill_results(assessment, student, subject, term, academic_year)

        # Calculate final summary
        self._calculate_summary(assessment)

        return assessment

    def get_batch_assessments(
        self,
        batch_id: str,
        term_id: Optional[str] = None,
        academic_year_id: Optional[str] = None
    ) -> List[UnifiedAssessment]:
        """
        Retrieve assessments for all students in a batch.

        Returns a list of UnifiedAssessment objects for easier batch processing.
        """
        from core.models import Batch, BatchStudent

        try:
            batch = Batch.objects.get(id=batch_id, tenant=self.tenant, is_deleted=False)
        except Batch.DoesNotExist:
            raise NotFoundException(f"Batch with id {batch_id} not found")

        # Get all active students in batch
        batch_students = BatchStudent.objects.filter(
            batch=batch,
            is_active=True,
            tenant=self.tenant
        ).select_related('student')

        # Get all subjects for the batch
        subjects = Subject.objects.filter(
            batch=batch,
            is_deleted=False,
            tenant=self.tenant
        )

        assessments = []
        for batch_student in batch_students:
            for subject in subjects:
                assessment = self.get_student_assessment(
                    student_id=str(batch_student.student.id),
                    subject_id=str(subject.id),
                    term_id=term_id,
                    academic_year_id=academic_year_id
                )
                if assessment.has_data():
                    assessments.append(assessment)

        return assessments

    def _populate_exam_scores(
        self,
        assessment: UnifiedAssessment,
        student: Student,
        subject: Subject,
        term: Optional[Term]
    ):
        """Populate exam scores from ExamScore model"""
        query = Q(
            student=student,
            exam__subject=subject,
            tenant=self.tenant
        )

        if term:
            query &= Q(exam__term=term)

        exam_scores = ExamScore.objects.filter(query).select_related(
            'exam', 'exam__exam_group'
        )

        total_marks = Decimal('0')
        maximum_marks = Decimal('0')

        for score in exam_scores:
            if not score.is_absent and score.marks is not None:
                total_marks += score.marks
                maximum_marks += score.exam.maximum_marks

                percentage = (score.marks / score.exam.maximum_marks * 100) if score.exam.maximum_marks > 0 else 0

                assessment.exam_scores.append({
                    'exam': score.exam,
                    'marks': float(score.marks),
                    'max_marks': float(score.exam.maximum_marks),
                    'percentage': round(float(percentage), 2),
                    'is_absent': False,
                    'remarks': score.remarks
                })

        assessment.total_marks = total_marks
        assessment.maximum_marks = maximum_marks
        if maximum_marks > 0:
            assessment.percentage = (total_marks / maximum_marks * 100)

    def _populate_skill_results(
        self,
        assessment: UnifiedAssessment,
        student: Student,
        subject: Subject,
        term: Optional[Term],
        academic_year: Optional[AcademicYear]
    ):
        """Populate skill assessment results from SkillsAssessment model"""
        # Get active skill sets for the subject
        subject_skill_sets = SubjectSkillSet.objects.filter(
            subject=subject,
            is_active=True,
            tenant=self.tenant
        ).select_related('skill_set').order_by('display_order')

        for subject_skill_set in subject_skill_sets:
            skill_set = subject_skill_set.skill_set

            # Find skills assessment for this student
            query = Q(
                student=student,
                tenant=self.tenant
            )
            if term:
                query &= Q(term=term)
            if academic_year:
                query &= Q(academic_year=academic_year)

            skills_assessment = SkillsAssessment.objects.filter(query).first()

            if skills_assessment:
                # Get all skill results for skills in this skill set
                from core.models import SkillItem, SkillCategory

                skill_results = []
                skill_categories = SkillCategory.objects.filter(
                    skill_set=skill_set,
                    is_active=True,
                    tenant=self.tenant
                ).prefetch_related('skill_items')

                for category in skill_categories:
                    for skill_item in category.skill_items.filter(is_active=True):
                        result = SkillAssessmentResult.objects.filter(
                            assessment=skills_assessment,
                            skill_item=skill_item,
                            tenant=self.tenant
                        ).first()

                        if result:
                            skill_results.append({
                                'skill': skill_item.description,
                                'category': category.name,
                                'level': result.get_level_display(),
                                'notes': result.notes
                            })

                if skill_results:
                    assessment.skill_results.append({
                        'skill_set': skill_set.name,
                        'assessment_mode': subject_skill_set.get_assessment_mode_display(),
                        'skills': skill_results
                    })

    def _calculate_summary(self, assessment: UnifiedAssessment):
        """Calculate final summary values"""
        # If we have both exams and skills with numeric conversion, combine them
        if assessment.total_marks and assessment.maximum_marks:
            if assessment.maximum_marks > 0:
                assessment.percentage = (assessment.total_marks / assessment.maximum_marks * 100)

        # Standard 5-point scholastic scale (matches default grading scale in
        # report generation and the printed scale table on reports).
        if assessment.percentage is not None:
            if assessment.percentage >= 80:
                assessment.final_grade = 'A'
            elif assessment.percentage >= 60:
                assessment.final_grade = 'B'
            elif assessment.percentage >= 50:
                assessment.final_grade = 'C'
            elif assessment.percentage >= 40:
                assessment.final_grade = 'D'
            else:
                assessment.final_grade = 'E'

    def _get_student_by_id(self, student_id: str) -> Student:
        """Helper to retrieve student"""
        try:
            return Student.objects.get(
                id=student_id,
                tenant=self.tenant,
                is_active=True
            )
        except Student.DoesNotExist:
            raise NotFoundException(f"Student with id {student_id} not found")

    def _get_term_by_id(self, term_id: str) -> Term:
        """Helper to retrieve term"""
        try:
            return Term.objects.get(id=term_id, tenant=self.tenant)
        except Term.DoesNotExist:
            raise NotFoundException(f"Term with id {term_id} not found")

    def _get_academic_year_by_id(self, academic_year_id: str) -> AcademicYear:
        """Helper to retrieve academic year"""
        try:
            return AcademicYear.objects.get(id=academic_year_id, tenant=self.tenant)
        except AcademicYear.DoesNotExist:
            raise NotFoundException(f"Academic year with id {academic_year_id} not found")