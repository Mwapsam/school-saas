import logging
from typing import Dict, Any
from datetime import date
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import (
    Attendance, Student, Batch
)
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException
)
from .logging_service import ServiceLogger, logged_operation
from .calendar_service import SchoolCalendarService
from .attendance_semantics import (
    STATUS_ABSENT,
    STATUS_LATE,
    STATUS_PRESENT,
    LOCKED_MESSAGE,
    NOT_SCHOOL_DAY_MESSAGE,
    NO_ACTIVE_TERM_MESSAGE,
    status_from_record,
)

logger = logging.getLogger(__name__)
audit = logging.getLogger('core.audit')


class AttendanceService(TenantAwareService[Attendance]):
    def __init__(self, tenant):
        super().__init__(Attendance, tenant)
        self.logger = ServiceLogger('attendance', tenant)
        self.calendar = SchoolCalendarService(tenant)
    
    @logged_operation(action='record', resource_type='student_attendance', log_result=True)
    @transaction.atomic
    def record_student_attendance(
        self,
        student_id: str,
        batch_id: str,
        attendance_date: date,
        forenoon: bool = True,
        afternoon: bool = True,
        reason: str = None,
        user=None
    ) -> Attendance:
        student = self._get_student_by_id(student_id)
        batch = self._get_batch_by_id(batch_id)

        if not self.calendar.is_school_day(attendance_date):
            raise ValidationException(
                NOT_SCHOOL_DAY_MESSAGE.format(date=attendance_date.strftime('%Y-%m-%d')),
                details={"attendance_date": attendance_date.strftime('%Y-%m-%d')}
            )

        if self.calendar.is_locked(attendance_date, allow_admin=True):
            raise ValidationException(
                LOCKED_MESSAGE.format(date=attendance_date.strftime('%Y-%m-%d')),
                details={"attendance_date": attendance_date.strftime('%Y-%m-%d')}
            )

        if not self.calendar.is_within_active_term(batch.academic_year, attendance_date):
            raise ValidationException(
                NO_ACTIVE_TERM_MESSAGE.format(date=attendance_date.strftime('%Y-%m-%d')),
                details={"attendance_date": attendance_date.strftime('%Y-%m-%d')}
            )

        if not self._is_student_in_batch(student_id, batch_id):
            raise ValidationException(
                f"Student {student.first_name} {student.last_name} is not enrolled in batch {batch.name}",
                details={"student_id": student_id, "batch_id": batch_id}
            )

        _prior = Attendance.objects.filter(
            student=student, batch=batch, month_date=attendance_date, tenant=self.tenant
        ).first()

        attendance, created = Attendance.objects.update_or_create(
            student=student,
            batch=batch,
            month_date=attendance_date,
            tenant=self.tenant,
            defaults={
                'forenoon': forenoon,
                'afternoon': afternoon,
                'reason': reason,
            }
        )

        from core.services.attendance_notifications import notify_newly_absent
        notify_newly_absent(
            self.tenant, batch, attendance_date, {str(student.id): _prior},
            [{'student_id': str(student.id), 'forenoon': forenoon, 'afternoon': afternoon}],
        )

        action = 'create' if created else 'update'
        self.logger.log_action(
            action=action,
            resource_type='student_attendance',
            resource_id=str(attendance.id),
            user=user,
            details={
                'student': f"{student.first_name} {student.last_name}",
                'batch': batch.name,
                'date': str(attendance_date),
                'forenoon': forenoon,
                'afternoon': afternoon,
            }
        )

        return attendance
    
    def get_attendance_statistics(
        self,
        student_id: str = None,
        batch_id: str = None,
        start_date: date = None,
        end_date: date = None
    ) -> Dict[str, Any]:
        query = Q(tenant=self.tenant)
        
        if student_id:
            query &= Q(student_id=student_id)
        
        if batch_id:
            query &= Q(batch_id=batch_id)
        
        if start_date:
            query &= Q(month_date__gte=start_date)
        
        if end_date:
            query &= Q(month_date__lte=end_date)
        
        total_records = Attendance.objects.filter(query).count()
        present_records = Attendance.objects.filter(
            query & (Q(forenoon=True) | Q(afternoon=True))
        ).count()
        absent_records = total_records - present_records
        
        attendance_rate = 0
        if total_records > 0:
            attendance_rate = (present_records / total_records) * 100
        
        stats = {
            'total_records': total_records,
            'present_count': present_records,
            'absent_count': absent_records,
            'attendance_rate': round(attendance_rate, 2)
        }
        
        if start_date:
            stats['period_start'] = start_date
        if end_date:
            stats['period_end'] = end_date
        
        return stats
    
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
        
        required_fields = ['student', 'batch', 'subject', 'month_date']
        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValidationException(
                    f"Required field '{field}' is missing",
                    details={"field": field}
                )
        
        attendance_date = data.get('month_date')
        if attendance_date and attendance_date > date.today():
            raise ValidationException(
                "Attendance date cannot be in the future",
                details={"attendance_date": attendance_date}
            )
    
    def get_daily_attendance_summary(self, target_date: date = None) -> Dict[str, Any]:
        """Get attendance summary for a specific date."""
        if target_date is None:
            target_date = date.today()
        
        return self.get_attendance_statistics(
            start_date=target_date,
            end_date=target_date
        )
    
    def get_student_attendance_summary(self, student_id: str, days: int = 30) -> Dict[str, Any]:
        """Get attendance summary for a student over the last N days."""
        from datetime import timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        stats = self.get_attendance_statistics(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Add more readable field names
        stats.update({
            'present_days': stats['present_count'],
            'absent_days': stats['absent_count'],
            'attendance_percentage': stats['attendance_rate']
        })
        
        return stats
    
    def search_attendance(
        self, 
        query: str = None,
        batch_id: str = None,
        start_date: date = None,
        end_date: date = None
    ):
        """Search attendance records with various filters"""
        queryset = self.get_base_queryset()
        
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        
        if start_date:
            queryset = queryset.filter(month_date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(month_date__lte=end_date)
        
        if query:
            queryset = queryset.filter(
                Q(student__first_name__icontains=query) |
                Q(student__last_name__icontains=query) |
                Q(student__admission_no__icontains=query) |
                Q(batch__name__icontains=query)
            )
        
        return queryset.select_related('student', 'batch')
    
    def get_attendance_context(self) -> Dict[str, Any]:
        """Get context data for attendance views"""
        from core.models import Batch
        
        return {
            'batches': Batch.objects.filter(
                tenant=self.tenant, 
                is_active=True, 
                is_deleted=False
            ),
            'total_records': self.count()
        }

    def get_batch_attendance_for_date(self, batch_id: str, attendance_date: str):
        """Read-only: load saved attendance for a batch on a given date.

        Returns existing records only — does NOT create anything.
        Students with no saved record are premarked present (forenoon=True,
        afternoon=True) so the teacher only has to flag exceptions.
        """
        from datetime import datetime
        from core.models import BatchStudent

        if isinstance(attendance_date, str):
            attendance_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()

        batch = self._get_batch_by_id(batch_id)

        batch_students = BatchStudent.objects.filter(
            batch=batch,
            is_active=True,
            tenant=self.tenant,
        ).select_related('student').order_by('student__first_name', 'student__last_name')

        # Fetch all saved attendance records for this batch + date in one query
        existing = {
            a.student_id: a
            for a in Attendance.objects.filter(
                batch=batch,
                month_date=attendance_date,
                tenant=self.tenant,
            )
        }

        students_data = []
        present_count = 0
        absent_count = 0
        partial_count = 0

        for batch_student in batch_students:
            student = batch_student.student
            attendance = existing.get(student.id)

            forenoon  = attendance.forenoon  if attendance else True
            afternoon = attendance.afternoon if attendance else True
            reason    = (attendance.reason or '') if attendance else ''

            # Count attendance status
            cell_status = status_from_record(attendance)
            if cell_status in (STATUS_PRESENT, STATUS_LATE):
                present_count += 1
            elif cell_status == STATUS_ABSENT:
                absent_count += 1
            else:
                partial_count += 1

            students_data.append({
                'student': student,
                'attendance': attendance,
                'forenoon': forenoon,
                'afternoon': afternoon,
                'reason': reason
            })
        
        total_students = len(students_data)
        attendance_percentage = (present_count / total_students * 100) if total_students > 0 else 0
        
        return {
            'batch': batch,
            'students': students_data,
            'total_students': total_students,
            'present_count': present_count,
            'absent_count': absent_count,
            'partial_count': partial_count,
            'attendance_percentage': attendance_percentage
        }
    
    def mark_batch_attendance(self, batch_id: str, attendance_date: str, attendance_records: list, user=None):
        """Mark attendance for multiple students at once"""
        from datetime import datetime
        from core.models import BatchStudent, PeriodEntry

        if isinstance(attendance_date, str):
            attendance_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()

        batch = self._get_batch_by_id(batch_id)

        if not self.calendar.is_school_day(attendance_date):
            raise ValidationException(
                NOT_SCHOOL_DAY_MESSAGE.format(date=attendance_date.strftime('%Y-%m-%d')),
                details={"attendance_date": attendance_date.strftime('%Y-%m-%d')}
            )

        if self.calendar.is_locked(attendance_date, allow_admin=True):
            raise ValidationException(
                LOCKED_MESSAGE.format(date=attendance_date.strftime('%Y-%m-%d')),
                details={"attendance_date": attendance_date.strftime('%Y-%m-%d')}
            )

        if not self.calendar.is_within_active_term(batch.academic_year, attendance_date):
            raise ValidationException(
                NO_ACTIVE_TERM_MESSAGE.format(date=attendance_date.strftime('%Y-%m-%d')),
                details={"attendance_date": attendance_date.strftime('%Y-%m-%d')}
            )

        # Use existing period entry if one exists for this date; leave null otherwise.
        # Never auto-create phantom subjects, timings, or employees.
        period_entry = PeriodEntry.objects.filter(
            month_date=attendance_date,
            batch=batch,
            tenant=self.tenant
        ).first()


        # Snapshot prior rows so the notification hook can tell a *newly* absent
        # student from a re-save of an already-absent day.
        _prior_by_student = {
            str(a.student_id): a
            for a in Attendance.objects.filter(
                tenant=self.tenant, batch=batch, month_date=attendance_date,
                student_id__in=[r['student_id'] for r in attendance_records],
            )
        }

        updated_records = []

        with transaction.atomic():
            for record in attendance_records:
                student_id = record['student_id']
                forenoon = record['forenoon']
                afternoon = record['afternoon']
                reason = record.get('reason', '')

                student = self._get_student_by_id(student_id)

                # Use update_or_create to avoid duplicates
                attendance, created = Attendance.objects.update_or_create(
                    student=student,
                    batch=batch,
                    month_date=attendance_date,
                    tenant=self.tenant,
                    defaults={
                        'period_table_entry': period_entry,
                        'forenoon': forenoon,
                        'afternoon': afternoon,
                        'reason': reason
                    }
                )
                
                updated_records.append({
                    'student_id': str(student.id),
                    'student_name': f"{student.first_name} {student.last_name}",
                    'forenoon': attendance.forenoon,
                    'afternoon': attendance.afternoon,
                    'created': created
                })

        audit.info(
            "attendance.save user=%s tenant=%s batch=%s date=%s entries=%d",
            getattr(user, 'id', None),
            getattr(self.tenant, 'schema_name', '?'),
            batch.id,
            attendance_date.isoformat(),
            len(updated_records),
        )

        from core.services.attendance_notifications import notify_newly_absent
        notify_newly_absent(
            self.tenant, batch, attendance_date, _prior_by_student, updated_records
        )

        return updated_records
    
    def get_batch_students_for_attendance(self, batch_id: str, attendance_date: str):
        """Get students in a batch with their existing attendance data"""
        from datetime import datetime
        from core.models import BatchStudent
        
        if isinstance(attendance_date, str):
            attendance_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
        
        batch = self._get_batch_by_id(batch_id)
        
        batch_students = BatchStudent.objects.filter(
            batch=batch,
            is_active=True,
            tenant=self.tenant
        ).select_related('student').order_by(
            'roll_number', 'student__first_name', 'student__last_name'
        )

        students_data = []
        for batch_student in batch_students:
            student = batch_student.student
            
            # Get existing attendance
            attendance = Attendance.objects.filter(
                student=student,
                batch=batch,
                month_date=attendance_date,
                tenant=self.tenant
            ).first()
            
            student_data = {
                'id': str(student.id),
                'name': f"{student.first_name} {student.last_name}",
                'student_id': student.admission_no,  # human-facing id; Student has no `student_id` field
                'forenoon': attendance.forenoon if attendance else True,
                'afternoon': attendance.afternoon if attendance else True,
                'reason': attendance.reason if attendance else ''
            }
            
            students_data.append(student_data)
        
        return students_data
    
    def get_student_attendance_report(self, student_id: str, start_date: str, end_date: str, batch_id: str = None):
        """Get detailed attendance report for a student, optionally scoped to a specific batch"""
        from datetime import datetime, timedelta

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        student = self._get_student_by_id(student_id)

        # Get all attendance records for the period, optionally scoped to a batch
        query = Q(student=student, month_date__gte=start_date, month_date__lte=end_date, tenant=self.tenant)
        if batch_id:
            query &= Q(batch_id=batch_id)

        attendance_records = Attendance.objects.filter(query).order_by('month_date')
        records_dict = {r.month_date: r for r in attendance_records}

        # Get working days (excluding weekends and holidays)
        working_day_list = self.calendar.get_working_day_list(start_date, end_date)
        # Exclude future dates (no attendance record means assumed present, so we only count dates up to today)
        today = timezone.localdate()
        working_day_list = [d for d in working_day_list if d <= today]

        attendance_data = []
        present_days = 0
        absent_days = 0
        partial_days = 0

        for current_date in working_day_list:
            attendance_record = records_dict.get(current_date)

            cell_status = status_from_record(attendance_record)
            if attendance_record:
                forenoon = attendance_record.forenoon
                afternoon = attendance_record.afternoon
                reason = attendance_record.reason
            else:
                # No record means assumed present (teacher marks exceptions)
                forenoon = afternoon = True
                reason = ''

            if cell_status in (STATUS_PRESENT, STATUS_LATE):
                present_days += 1
            elif cell_status == STATUS_ABSENT:
                absent_days += 1
            else:
                partial_days += 1

            attendance_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'forenoon': forenoon,
                'afternoon': afternoon,
                'reason': reason or ''
            })

        total_days = len(working_day_list)
        attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0

        return {
            'student': student,
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'partial_days': partial_days,
            'attendance_percentage': attendance_percentage,
            'attendance_records': attendance_data,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
    
    def get_batch_attendance_report(self, batch_id: str, start_date: str, end_date: str):
        """Get attendance report for all students in a batch"""
        from datetime import datetime
        from core.models import BatchStudent
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        batch = self._get_batch_by_id(batch_id)
        
        # Get all students in batch
        batch_students = BatchStudent.objects.filter(
            batch=batch,
            is_active=True,
            tenant=self.tenant
        ).select_related('student')
        
        student_summaries = []
        total_attendance_percentage = 0
        
        for batch_student in batch_students:
            student = batch_student.student
            
            # Get student's attendance for the period
            student_report = self.get_student_attendance_report(
                student_id=str(student.id),
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            student_summaries.append({
                'student_name': f"{student.first_name} {student.last_name}",
                'student_id': student.admission_no,  # Student has no `student_id` field
                'present_days': student_report['present_days'],
                'absent_days': student_report['absent_days'],
                'partial_days': student_report['partial_days'],
                'attendance_percentage': student_report['attendance_percentage']
            })
            
            total_attendance_percentage += student_report['attendance_percentage']
        
        # Calculate total working days in the period using calendar service
        total_days = self.calendar.get_working_days(start_date, end_date)

        average_attendance = total_attendance_percentage / len(student_summaries) if student_summaries else 0
        
        return {
            'batch': batch,
            'total_students': len(student_summaries),
            'total_days': total_days,
            'average_attendance': average_attendance,
            'student_summaries': student_summaries,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
    
    def get_daily_attendance_report(self, batch_id: str, report_date: str):
        """Get daily attendance report for a batch"""
        from datetime import datetime
        from core.models import BatchStudent
        
        if isinstance(report_date, str):
            report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
        
        batch = self._get_batch_by_id(batch_id)
        
        # Get all students in batch
        batch_students = BatchStudent.objects.filter(
            batch=batch,
            is_active=True,
            tenant=self.tenant
        ).select_related('student')
        
        student_attendance = []
        present_count = 0
        absent_count = 0
        partial_count = 0
        
        for batch_student in batch_students:
            student = batch_student.student
            
            # Get attendance for this date
            attendance = Attendance.objects.filter(
                student=student,
                batch=batch,
                month_date=report_date,
                tenant=self.tenant
            ).first()
            
            # Default to present if no record
            forenoon = attendance.forenoon if attendance else True
            afternoon = attendance.afternoon if attendance else True
            reason = attendance.reason if attendance else ''

            cell_status = status_from_record(attendance)
            if cell_status in (STATUS_PRESENT, STATUS_LATE):
                present_count += 1
            elif cell_status == STATUS_ABSENT:
                absent_count += 1
            else:
                partial_count += 1

            student_attendance.append({
                'student_name': f"{student.first_name} {student.last_name}",
                'student_id': student.admission_no,  # Student has no `student_id` field
                'forenoon': forenoon,
                'afternoon': afternoon,
                'reason': reason
            })
        
        total_students = len(student_attendance)
        attendance_percentage = (present_count / total_students * 100) if total_students > 0 else 0
        
        return {
            'batch': batch,
            'report_date': report_date,
            'total_students': total_students,
            'present_count': present_count,
            'absent_count': absent_count,
            'partial_count': partial_count,
            'attendance_percentage': attendance_percentage,
            'student_attendance': student_attendance
        }
    
    def get_student_monthly_summary(self, student_id: str, month: str):
        """Get monthly attendance summary for a student"""
        from datetime import datetime
        
        # Parse month (YYYY-MM format)
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1).date()
        
        # Get last day of month
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month_num + 1, 1).date()
        
        # Use the existing student report method
        return self.get_student_attendance_report(
            student_id=student_id,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
    
    def get_batch_monthly_summary(self, batch_id: str, month: str):
        """Get monthly attendance summary for a batch"""
        from datetime import datetime
        
        # Parse month (YYYY-MM format)
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1).date()
        
        # Get last day of month
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month_num + 1, 1).date()
        
        # Use the existing batch report method
        return self.get_batch_attendance_report(
            batch_id=batch_id,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )