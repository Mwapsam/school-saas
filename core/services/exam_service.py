import logging
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.db.models import Q, QuerySet, Avg, Sum, Max, Min

from core.models import (
    Exam, ExamGroup, ExamScore, Student, Subject, 
    Batch
)
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException
)
from .logging_service import ServiceLogger, logged_operation

logger = logging.getLogger(__name__)


class ExamService(TenantAwareService[Exam]):    
    def __init__(self, tenant):
        super().__init__(Exam, tenant)
        self.logger = ServiceLogger('exam', tenant)
    
    @logged_operation(action='create', resource_type='exam', log_result=True)
    @transaction.atomic
    def create_exam(
        self,
        name: str,
        exam_group_id: str,
        subject_id: str,
        start_time: datetime,
        end_time: datetime,
        maximum_marks: Decimal,
        minimum_marks: Decimal,
        user=None,
        **additional_data
    ) -> Exam:
        exam_group = self._get_exam_group_by_id(exam_group_id)
        subject = self._get_subject_by_id(subject_id)
        
        if start_time >= end_time:
            raise ValidationException(
                "Exam start time must be before end time",
                details={"start_time": start_time, "end_time": end_time}
            )
        
        if minimum_marks >= maximum_marks:
            raise ValidationException(
                "Minimum marks must be less than maximum marks",
                details={"minimum_marks": minimum_marks, "maximum_marks": maximum_marks}
            )
        
        exam_data = {
            "name": name,
            "exam_group": exam_group,
            "subject": subject,
            "start_time": start_time,
            "end_time": end_time,
            "maximum_marks": maximum_marks,
            "minimum_marks": minimum_marks,
            "school": self.tenant,
            **additional_data
        }
        
        exam = Exam.objects.create(**exam_data)
        
        self.logger.log_create(
            resource_type='exam',
            resource_id=str(exam.id),
            user=user,
            details={
                'name': name,
                'exam_group': exam_group.name,
                'subject': subject.name,
                'start_time': str(start_time),
                'maximum_marks': str(maximum_marks)
            }
        )
        
        return exam
    
    @logged_operation(action='create', resource_type='exam_group', log_result=True)
    def create_exam_group(
        self,
        name: str,
        batch_id: str,
        exam_type: str = "regular",
        user=None,
        **additional_data
    ) -> ExamGroup:
        batch = self._get_batch_by_id(batch_id)
        
        if ExamGroup.objects.filter(
            name=name,
            batch=batch,
            tenant=self.tenant,
            is_deleted=False
        ).exists():
            raise DuplicateException(
                f"Exam group '{name}' already exists for batch '{batch.name}'",
                details={"name": name, "batch_id": batch_id}
            )
        
        exam_group_data = {
            "name": name,
            "batch": batch,
            "exam_type": exam_type,
            "school": self.tenant,
            **additional_data
        }
        
        exam_group = ExamGroup.objects.create(**exam_group_data)
        
        self.logger.log_create(
            resource_type='exam_group',
            resource_id=str(exam_group.id),
            user=user,
            details={
                'name': name,
                'batch': batch.name,
                'exam_type': exam_type
            }
        )
        
        return exam_group
    
    @logged_operation(action='record', resource_type='exam_score', log_result=True)
    @transaction.atomic
    def record_exam_score(
        self,
        exam_id: str,
        student_id: str,
        marks: Decimal,
        is_absent: bool = False,
        user=None,
        **additional_data
    ) -> ExamScore:
        exam = self.get_by_id(exam_id)
        student = self._get_student_by_id(student_id)
        
        if not self._is_student_in_batch(student_id, exam.subject.batch.id):
            raise ValidationException(
                f"Student {student.first_name} {student.last_name} is not enrolled in the required batch",
                details={"student_id": student_id, "batch_id": exam.subject.batch.id}
            )
        
        if not is_absent:
            if marks < 0 or marks > exam.maximum_marks:
                raise ValidationException(
                    f"Marks must be between 0 and {exam.maximum_marks}",
                    details={"marks": marks, "maximum_marks": exam.maximum_marks}
                )
        
        existing_score = ExamScore.objects.filter(
            exam=exam,
            student=student,
            tenant=self.tenant
        ).first()
        
        if existing_score:
            existing_score.marks = marks if not is_absent else None
            existing_score.is_absent = is_absent
            existing_score.save()
            
            self.logger.log_update(
                resource_type='exam_score',
                resource_id=str(existing_score.id),
                user=user,
                changed_fields={'marks': marks, 'is_absent': is_absent}
            )
            
            return existing_score
        
        score_data = {
            "exam": exam,
            "student": student,
            "marks": marks if not is_absent else None,
            "is_absent": is_absent,
            "school": self.tenant,
            **additional_data
        }
        
        exam_score = ExamScore.objects.create(**score_data)
        
        self.logger.log_create(
            resource_type='exam_score',
            resource_id=str(exam_score.id),
            user=user,
            details={
                'exam': exam.name,
                'student': f"{student.first_name} {student.last_name}",
                'marks': str(marks) if not is_absent else 'ABSENT',
                'subject': exam.subject.name
            }
        )
        
        return exam_score
    
    def get_exam_scores(
        self,
        exam_id: str = None,
        student_id: str = None,
        batch_id: str = None,
        subject_id: str = None
    ) -> QuerySet[ExamScore]:
        query = Q(tenant=self.tenant)
        
        if exam_id:
            query &= Q(exam_id=exam_id)
        
        if student_id:
            query &= Q(student_id=student_id)
        
        if batch_id:
            query &= Q(exam__subject__batch_id=batch_id)
        
        if subject_id:
            query &= Q(exam__subject_id=subject_id)
        
        return ExamScore.objects.filter(query).select_related(
            'exam', 'student', 'exam__subject'
        )
    
    def get_student_performance_summary(
        self,
        student_id: str,
        batch_id: str = None,
        exam_group_id: str = None
    ) -> Dict[str, Any]:
        student = self._get_student_by_id(student_id)
        
        query = Q(student=student, tenant=self.tenant)
        
        if batch_id:
            query &= Q(exam__subject__batch_id=batch_id)
        
        if exam_group_id:
            query &= Q(exam__exam_group_id=exam_group_id)
        
        scores = ExamScore.objects.filter(query).exclude(is_absent=True)
        
        if not scores.exists():
            return {
                'student': student,
                'total_exams': 0,
                'exams_taken': 0,
                'exams_absent': 0,
                'average_marks': 0,
                'total_marks': 0,
                'maximum_possible': 0,
                'percentage': 0,
                'subject_performance': []
            }
        
        total_exams_count = ExamScore.objects.filter(
            student=student,
            tenant=self.tenant
        ).count()
        
        absent_count = ExamScore.objects.filter(
            student=student,
            tenant=self.tenant,
            is_absent=True
        ).count()
        
        total_marks = scores.aggregate(total=Sum('marks'))['total'] or Decimal('0')
        max_possible = sum(score.exam.maximum_marks for score in scores)
        average_marks = scores.aggregate(avg=Avg('marks'))['avg'] or Decimal('0')
        
        percentage = (total_marks / max_possible * 100) if max_possible > 0 else 0
        
        subject_performance = []
        subjects = scores.values('exam__subject').distinct()
        
        for subject_data in subjects:
            subject_id = subject_data['exam__subject']
            subject_scores = scores.filter(exam__subject_id=subject_id)
            
            subject_total = subject_scores.aggregate(total=Sum('marks'))['total'] or Decimal('0')
            subject_max = sum(score.exam.maximum_marks for score in subject_scores)
            subject_avg = subject_scores.aggregate(avg=Avg('marks'))['avg'] or Decimal('0')
            subject_percentage = (subject_total / subject_max * 100) if subject_max > 0 else 0
            
            subject = Subject.objects.get(id=subject_id)
            
            subject_performance.append({
                'subject': subject,
                'exams_count': subject_scores.count(),
                'total_marks': subject_total,
                'maximum_possible': subject_max,
                'average_marks': float(subject_avg),
                'percentage': round(float(subject_percentage), 2)
            })
        
        return {
            'student': student,
            'total_exams': total_exams_count,
            'exams_taken': scores.count(),
            'exams_absent': absent_count,
            'average_marks': float(average_marks),
            'total_marks': float(total_marks),
            'maximum_possible': float(max_possible),
            'percentage': round(float(percentage), 2),
            'subject_performance': subject_performance
        }
    
    def get_batch_performance_report(
        self,
        batch_id: str,
        exam_group_id: str = None
    ) -> Dict[str, Any]:
        batch = self._get_batch_by_id(batch_id)
        
        query = Q(exam__subject__batch=batch, tenant=self.tenant)
        
        if exam_group_id:
            query &= Q(exam__exam_group_id=exam_group_id)
        
        all_scores = ExamScore.objects.filter(query)
        scores_taken = all_scores.exclude(is_absent=True)
        
        if not all_scores.exists():
            return {
                'batch': batch,
                'total_students': 0,
                'total_exams': 0,
                'scores_recorded': 0,
                'absent_count': 0,
                'class_average': 0,
                'highest_score': 0,
                'lowest_score': 0,
                'subject_statistics': []
            }
        
        total_students = Student.objects.filter(
            student_batches__batch=batch,
            student_batches__is_active=True,
            tenant=self.tenant,
            is_active=True
        ).count()
        
        class_average = scores_taken.aggregate(avg=Avg('marks'))['avg'] or Decimal('0')
        highest_score = scores_taken.aggregate(max=Max('marks'))['max'] or Decimal('0')
        lowest_score = scores_taken.aggregate(min=Min('marks'))['min'] or Decimal('0')
        absent_count = all_scores.filter(is_absent=True).count()
        
        subject_stats = []
        subjects = Subject.objects.filter(batch=batch, tenant=self.tenant, is_deleted=False)
        
        for subject in subjects:
            subject_scores = all_scores.filter(exam__subject=subject)
            subject_taken = subject_scores.exclude(is_absent=True)
            
            if subject_taken.exists():
                subject_avg = subject_taken.aggregate(avg=Avg('marks'))['avg'] or Decimal('0')
                subject_max = subject_taken.aggregate(max=Max('marks'))['max'] or Decimal('0')
                subject_min = subject_taken.aggregate(min=Min('marks'))['min'] or Decimal('0')
            else:
                subject_avg = subject_max = subject_min = Decimal('0')
            
            subject_stats.append({
                'subject': subject,
                'total_scores': subject_scores.count(),
                'scores_taken': subject_taken.count(),
                'absent_count': subject_scores.filter(is_absent=True).count(),
                'average_marks': float(subject_avg),
                'highest_marks': float(subject_max),
                'lowest_marks': float(subject_min)
            })
        
        return {
            'batch': batch,
            'total_students': total_students,
            'total_exams': Exam.objects.filter(
                subject__batch=batch,
                tenant=self.tenant
            ).count(),
            'scores_recorded': all_scores.count(),
            'scores_taken': scores_taken.count(),
            'absent_count': absent_count,
            'class_average': float(class_average),
            'highest_score': float(highest_score),
            'lowest_score': float(lowest_score),
            'subject_statistics': subject_stats
        }
    
    def _get_exam_group_by_id(self, exam_group_id: str) -> ExamGroup:
        try:
            return ExamGroup.objects.get(
                id=exam_group_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except ExamGroup.DoesNotExist:
            raise NotFoundException(
                f"Exam group with id {exam_group_id} not found",
                details={"exam_group_id": exam_group_id}
            )
    
    def _get_subject_by_id(self, subject_id: str) -> Subject:
        try:
            return Subject.objects.get(
                id=subject_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except Subject.DoesNotExist:
            raise NotFoundException(
                f"Subject with id {subject_id} not found",
                details={"subject_id": subject_id}
            )
    
    def _get_batch_by_id(self, batch_id: str) -> Batch:
        try:
            return Batch.objects.get(
                id=batch_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except Batch.DoesNotExist:
            raise NotFoundException(
                f"Batch with id {batch_id} not found",
                details={"batch_id": batch_id}
            )
    
    def _get_student_by_id(self, student_id: str) -> Student:
        try:
            return Student.objects.get(
                id=student_id,
                tenant=self.tenant,
                is_active=True
            )
        except Student.DoesNotExist:
            raise NotFoundException(
                f"Student with id {student_id} not found",
                details={"student_id": student_id}
            )
    
    def _is_student_in_batch(self, student_id: str, batch_id: str) -> bool:
        from core.models import BatchStudent
        return BatchStudent.objects.filter(
            student_id=student_id,
            batch_id=batch_id,
            tenant=self.tenant,
            is_active=True
        ).exists()
    
    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        super()._validate_create_data(data)
        
        required_fields = ['name', 'exam_group', 'subject', 'start_time', 'end_time', 'maximum_marks']
        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValidationException(
                    f"Required field '{field}' is missing",
                    details={"field": field}
                )
        
        max_marks = data.get('maximum_marks')
        min_marks = data.get('minimum_marks', 0)
        
        if max_marks is not None and max_marks <= 0:
            raise ValidationException(
                "Maximum marks must be positive",
                details={"maximum_marks": max_marks}
            )
        
        if min_marks is not None and min_marks < 0:
            raise ValidationException(
                "Minimum marks cannot be negative",
                details={"minimum_marks": min_marks}
            )
    
    def get_all_exam_groups(self) -> QuerySet[ExamGroup]:
        """Get all exam groups for the tenant"""
        return ExamGroup.objects.filter(
            tenant=self.tenant
        ).select_related('batch').prefetch_related('exams__subject').order_by('-exam_date', 'name')
    
    def create_exam_group(self, exam_group_data: Dict[str, Any]) -> ExamGroup:
        """Create a new exam group with validation"""
        try:
            batch = Batch.objects.get(id=exam_group_data['batch_id'], tenant=self.tenant)
        except Batch.DoesNotExist:
            raise NotFoundException(f"Batch with id {exam_group_data['batch_id']} not found")
        
        # Check for duplicate name in the same batch
        if ExamGroup.objects.filter(
            name=exam_group_data['name'],
            batch=batch,
            tenant=self.tenant
        ).exists():
            raise ValidationException(f"Exam group '{exam_group_data['name']}' already exists for batch '{batch.name}'")
        
        exam_group = ExamGroup.objects.create(
            name=exam_group_data['name'],
            batch=batch,
            exam_type=exam_group_data.get('exam_type', 'Regular'),
            exam_date=exam_group_data['exam_date'],
            is_final_exam=exam_group_data.get('is_final_exam', False),
            tenant=self.tenant
        )
        
        return exam_group
    
    def create_exam(self, exam_data: Dict[str, Any]) -> Exam:
        """Create a new exam with validation"""
        try:
            exam_group = ExamGroup.objects.get(id=exam_data['exam_group_id'], tenant=self.tenant)
            subject = Subject.objects.get(id=exam_data['subject_id'], tenant=self.tenant)
        except ExamGroup.DoesNotExist:
            raise NotFoundException(f"Exam group with id {exam_data['exam_group_id']} not found")
        except Subject.DoesNotExist:
            raise NotFoundException(f"Subject with id {exam_data['subject_id']} not found")
        
        # Validate times
        from datetime import datetime
        start_time = datetime.fromisoformat(exam_data['start_time'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(exam_data['end_time'].replace('Z', '+00:00'))
        
        if start_time >= end_time:
            raise ValidationException("Start time must be before end time")
        
        # Check for duplicate exam in the same group and subject
        if Exam.objects.filter(
            exam_group=exam_group,
            subject=subject,
            tenant=self.tenant
        ).exists():
            raise ValidationException(f"Exam for {subject.name} already exists in {exam_group.name}")
        
        exam = Exam.objects.create(
            exam_group=exam_group,
            subject=subject,
            start_time=start_time,
            end_time=end_time,
            maximum_marks=exam_data['maximum_marks'],
            minimum_marks=exam_data.get('minimum_marks', 0),
            tenant=self.tenant
        )
        
        return exam
    
    def toggle_exam_group_publication(self, exam_group_id: str) -> bool:
        """Toggle the publication status of an exam group"""
        try:
            exam_group = ExamGroup.objects.get(id=exam_group_id, tenant=self.tenant)
        except ExamGroup.DoesNotExist:
            raise NotFoundException(f"Exam group with id {exam_group_id} not found")

        exam_group.is_published = not exam_group.is_published
        exam_group.save()

        return exam_group.is_published

    def is_exam_group_activated(self, exam_group: ExamGroup) -> bool:
        """Single source of truth for exam-plan activation: an exam group is
        markable only once explicitly published (see toggle_exam_group_publication).
        Every surface (teacher portal, staff gradebook) must check this before
        showing or accepting marks for an exam group."""
        return bool(exam_group.is_published)

    def is_exam_markable(self, exam: Exam) -> bool:
        """Whether marks can currently be entered for this exam: its exam
        group must be activated, and its assessment type must be enabled for
        the batch (BatchExamTypeConfiguration)."""
        if not self.is_exam_group_activated(exam.exam_group):
            return False
        from core.models import BatchExamTypeConfiguration
        batch = exam.exam_group.batch
        config = BatchExamTypeConfiguration.for_batch(batch, self.tenant)
        if config is not None and not config.is_exam_type_enabled(exam.assessment_slot or "EXAM"):
            return False
        return True

    def assert_exam_markable(self, exam: Exam) -> None:
        if not self.is_exam_markable(exam):
            raise ValidationException(
                f"Exam '{exam.name}' has not been activated yet — marks cannot be "
                "entered until its exam plan is published.",
                details={"exam_id": str(exam.id), "exam_group_id": str(exam.exam_group_id)},
            )

    def is_skills_exam(self, exam: Exam) -> bool:
        """True for LEVEL-scale ('skills') exams. These never get ExamScore
        or MarkSubmission rows — the portal's separate Skills Assessment
        flow stores ratings in SkillAssessmentResult and submission in
        SkillsSubmission (keyed by batch+term, not per exam) instead, so any
        check walking ExamScore/MarkSubmission must skip them and use
        get_skills_submission_info in its place."""
        scale = exam.get_grading_scale()
        return bool(scale and scale.scale_type == "LEVEL")

    def _resolve_skills_term(self, exam_group: ExamGroup, batch: Batch):
        from core.services.report_generation_service import ReportGenerationService
        from portal import selectors as portal_selectors

        return portal_selectors.resolve_term(
            ReportGenerationService.resolve_exam_group_term(exam_group), batch=batch
        )

    def get_skills_submission_info(self, exam: Exam, batch: Batch) -> Dict[str, Any]:
        """Entered-count + submission status for a LEVEL-scale ('skills')
        exam, read from the portal's Skills Assessment tables
        (SkillsAssessment, SkillsSubmission) rather than
        ExamScore/MarkSubmission, which this exam type never populates."""
        from core.models import BatchStudent, SkillsAssessment
        from portal import selectors as portal_selectors
        from portal.models import SkillsSubmission

        term_obj = self._resolve_skills_term(exam.exam_group, batch)
        year = portal_selectors.active_academic_year()

        batch_student_ids = list(
            BatchStudent.objects.filter(batch=batch, tenant=self.tenant, is_active=True)
            .values_list('student_id', flat=True)
        )
        assessed_count = (
            SkillsAssessment.objects.filter(
                tenant=self.tenant,
                student_id__in=batch_student_ids,
                term=term_obj,
                academic_year=year,
            ).count()
            if year else 0
        )
        submission = SkillsSubmission.objects.filter(
            tenant=self.tenant, batch=batch, term=term_obj
        ).first()

        return {
            'score_count': assessed_count,
            'status': submission.status if submission else None,
        }

    @logged_operation(action='undo_submit', resource_type='skills_submission', log_result=True)
    @transaction.atomic
    def undo_skills_submission(self, exam: Exam, batch: Batch) -> bool:
        """Reopen submitted SkillsSubmission row(s) for this exam's batch+term.

        There may be one whole-batch row (employee=None) and/or one per
        teacher (unique_together on batch/term/employee) — an admin undo
        doesn't distinguish which teacher submitted, it just reopens every
        submitted row for the term at once. Returns False when there was
        nothing submitted to undo.
        """
        from portal.models import SkillsSubmission

        term_obj = self._resolve_skills_term(exam.exam_group, batch)
        updated = SkillsSubmission.objects.filter(
            tenant=self.tenant, batch=batch, term=term_obj,
            status=SkillsSubmission.STATUS_SUBMITTED,
        ).update(status=SkillsSubmission.STATUS_DRAFT, submitted_by=None, submitted_at=None)
        return updated > 0

    def get_missing_marks(self, exam_group: ExamGroup, batch: Batch) -> list:
        """Subjects (enabled exam types only) still missing marks for an
        active student in this batch. Used by the Missing Marks modal."""
        from core.models import BatchExamTypeConfiguration, BatchStudent

        exams_in_group = Exam.objects.filter(exam_group=exam_group, tenant=self.tenant)
        exams_to_check = BatchExamTypeConfiguration.filter_enabled_exams(
            exams_in_group, batch, self.tenant
        )

        batch_student_ids = list(
            BatchStudent.objects.filter(batch=batch, tenant=self.tenant, is_active=True)
            .values_list('student_id', flat=True)
        )

        missing = []
        for exam in exams_to_check:
            if self.is_skills_exam(exam):
                info = self.get_skills_submission_info(exam, batch)
                not_scored_count = max(len(batch_student_ids) - info['score_count'], 0)
                if not_scored_count:
                    missing.append({
                        'exam': exam.subject.name if exam.subject else str(exam.id),
                        'subject': exam.subject.name if exam.subject else 'Unknown',
                        'count': not_scored_count,
                    })
                continue

            scored_ids = set(
                ExamScore.objects.filter(exam=exam, tenant=self.tenant, student_id__in=batch_student_ids)
                .values_list('student_id', flat=True)
            )
            not_scored = [str(sid) for sid in batch_student_ids if sid not in scored_ids]
            if not_scored:
                missing.append({
                    'exam': exam.subject.name if exam.subject else str(exam.id),
                    'subject': exam.subject.name if exam.subject else 'Unknown',
                    'count': len(not_scored),
                })
        return missing

    def get_unsubmitted_exams(self, exam_group: ExamGroup, batch: Batch) -> list:
        """Subjects (enabled types only) a teacher saved via the portal but
        hasn't formally submitted (MarkSubmission status stays 'draft').
        Exams with no MarkSubmission row at all were entered directly by
        staff and are never considered unsubmitted."""
        from core.models import BatchExamTypeConfiguration
        from portal.models import MarkSubmission, SkillsSubmission

        exams_in_group = Exam.objects.filter(exam_group=exam_group, tenant=self.tenant)
        exams_to_check = BatchExamTypeConfiguration.filter_enabled_exams(
            exams_in_group, batch, self.tenant
        )

        submission_status = dict(
            MarkSubmission.objects.filter(exam__in=exams_to_check, tenant=self.tenant)
            .values_list('exam_id', 'status')
        )

        unsubmitted = []
        for exam in exams_to_check:
            if self.is_skills_exam(exam):
                info = self.get_skills_submission_info(exam, batch)
                if info['status'] != SkillsSubmission.STATUS_SUBMITTED:
                    unsubmitted.append({
                        'exam': exam.subject.name if exam.subject else str(exam.id),
                        'subject': exam.subject.name if exam.subject else 'Unknown',
                    })
                continue

            status = submission_status.get(exam.id)
            if status is not None and status != MarkSubmission.STATUS_SUBMITTED:
                unsubmitted.append({
                    'exam': exam.subject.name if exam.subject else str(exam.id),
                    'subject': exam.subject.name if exam.subject else 'Unknown',
                })
        return unsubmitted

    def get_student_exam_schedules(self, student_id: str):
        """Get published exam schedules for a student"""
        try:
            student = Student.objects.get(id=student_id, tenant=self.tenant)
        except Student.DoesNotExist:
            raise NotFoundException(f"Student with id {student_id} not found")
        
        # Get student's current batch (assuming they have one active batch)
        from core.models import BatchStudent
        batch_student = BatchStudent.objects.filter(
            student=student,
            is_active=True,
            tenant=self.tenant
        ).first()
        
        if not batch_student:
            return []
        
        # Get published exam groups for the student's batch
        exam_groups = ExamGroup.objects.filter(
            batch=batch_student.batch,
            is_published=True,
            tenant=self.tenant
        ).order_by('exam_date')
        
        schedules = []
        from datetime import date, datetime
        today = date.today()
        
        for exam_group in exam_groups:
            exams = exam_group.exams.filter(tenant=self.tenant).order_by('start_time')
            
            # Calculate some useful info
            exam_dates = [exam.start_time.date() for exam in exams]
            first_exam_date = min(exam_dates) if exam_dates else None
            days_until_first_exam = (first_exam_date - today).days if first_exam_date else 0
            
            # Add duration calculation for each exam
            exam_list = []
            for exam in exams:
                duration = exam.end_time - exam.start_time
                duration_hours = duration.total_seconds() // 3600
                duration_minutes = (duration.total_seconds() % 3600) // 60
                
                exam_dict = {
                    'id': exam.id,
                    'subject': exam.subject,
                    'start_time': exam.start_time,
                    'end_time': exam.end_time,
                    'maximum_marks': exam.maximum_marks,
                    'duration_hours': int(duration_hours),
                    'duration_minutes': int(duration_minutes)
                }
                exam_list.append(exam_dict)
            
            schedule_data = {
                'exam_group': exam_group,
                'exams': exam_list,
                'days_until_first_exam': days_until_first_exam,
                'has_exam_today': any(exam_date == today for exam_date in exam_dates),
                'has_upcoming_exams': days_until_first_exam > 0
            }
            
            schedules.append(schedule_data)
        
        return schedules