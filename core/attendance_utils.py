"""
Attendance utilities for enhanced reporting and calculations
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone

from .models import Attendance, AttendanceSummary, Student, Batch, AcademicYear, Term

logger = logging.getLogger(__name__)


class AttendanceCalculator:
    """Utility class for calculating attendance statistics"""

    @staticmethod
    def calculate_student_attendance(student, start_date=None, end_date=None, batch=None):
        """
        Calculate attendance statistics for a student
        Returns: dict with attendance data
        """
        queryset = Attendance.objects.filter(student=student)

        if batch:
            queryset = queryset.filter(batch=batch)

        if start_date:
            queryset = queryset.filter(month_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(month_date__lte=end_date)

        attendances = queryset.order_by('month_date')

        # Single aggregate query instead of five separate COUNT round-trips.
        counts = attendances.aggregate(
            total_days=Count('id'),
            present_days=Count('id', filter=Q(forenoon=True) | Q(afternoon=True)),
            full_day_present=Count('id', filter=Q(forenoon=True, afternoon=True)),
            half_day_present=Count(
                'id',
                filter=Q(forenoon=True, afternoon=False) | Q(forenoon=False, afternoon=True),
            ),
            absent_days=Count('id', filter=Q(forenoon=False, afternoon=False)),
        )
        total_days = counts['total_days']
        present_days = counts['present_days']
        full_day_present = counts['full_day_present']
        half_day_present = counts['half_day_present']
        absent_days = counts['absent_days']

        # Calculate percentage considering half days as 0.5
        if total_days > 0:
            effective_present_days = full_day_present + (half_day_present * 0.5)
            percentage = (effective_present_days / total_days) * 100
        else:
            percentage = 0

        return {
            'total_days': total_days,
            'present_days': present_days,
            'full_day_present': full_day_present,
            'half_day_present': half_day_present,
            'absent_days': absent_days,
            'attendance_percentage': round(percentage, 2),
            'status': AttendanceCalculator._get_attendance_status(percentage),
            'status_color': AttendanceCalculator._get_status_color(percentage)
        }

    @staticmethod
    def calculate_batch_attendance(batch, start_date=None, end_date=None):
        """
        Calculate attendance statistics for an entire batch
        Returns: dict with batch attendance data
        """
        students = Student.objects.filter(
            batchstudent__batch=batch,
            batchstudent__is_active=True
        )

        batch_stats = []
        total_percentage = 0

        for student in students:
            stats = AttendanceCalculator.calculate_student_attendance(
                student, start_date, end_date, batch
            )
            stats['student'] = student
            batch_stats.append(stats)
            total_percentage += stats['attendance_percentage']

        # Calculate batch averages
        student_count = len(batch_stats)
        if student_count > 0:
            average_percentage = total_percentage / student_count
        else:
            average_percentage = 0

        # Count students by status
        excellent_count = sum(1 for s in batch_stats if s['attendance_percentage'] >= 90)
        satisfactory_count = sum(1 for s in batch_stats if 75 <= s['attendance_percentage'] < 90)
        needs_improvement_count = sum(1 for s in batch_stats if s['attendance_percentage'] < 75)

        return {
            'batch': batch,
            'student_count': student_count,
            'average_percentage': round(average_percentage, 2),
            'excellent_count': excellent_count,
            'satisfactory_count': satisfactory_count,
            'needs_improvement_count': needs_improvement_count,
            'student_stats': batch_stats,
            'status_distribution': {
                'excellent': excellent_count,
                'satisfactory': satisfactory_count,
                'needs_improvement': needs_improvement_count
            }
        }

    @staticmethod
    def generate_attendance_summary(student, period_type='MONTHLY', period_start=None, period_end=None):
        """
        Generate or update attendance summary for efficient reporting
        """
        from .models import AttendanceSummary

        if not period_start:
            period_start = timezone.now().date().replace(day=1)

        if not period_end:
            # Last day of the month
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1) - timedelta(days=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1) - timedelta(days=1)

        # Get or create summary — single query for the active enrolment.
        active_batch_student = student.batchstudent.filter(is_active=True).first()
        batch = active_batch_student.batch if active_batch_student else None
        if not batch:
            return None

        academic_year = batch.academic_year

        summary, created = AttendanceSummary.objects.get_or_create(
            student=student,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            defaults={
                'batch': batch,
                'academic_year': academic_year,
                'tenant': student.tenant
            }
        )

        # Calculate attendance stats
        stats = AttendanceCalculator.calculate_student_attendance(
            student, period_start, period_end, batch
        )

        # Update summary
        summary.total_days = stats['total_days']
        summary.present_days = stats['present_days']
        summary.absent_days = stats['absent_days']
        summary.half_day_count = stats['half_day_present']
        summary.attendance_percentage = Decimal(str(stats['attendance_percentage']))
        summary.save()

        return summary

    @staticmethod
    def get_attendance_report_data(batch, start_date, end_date, include_summaries=True):
        """
        Get comprehensive attendance report data for a batch
        """
        batch_stats = AttendanceCalculator.calculate_batch_attendance(batch, start_date, end_date)

        report_data = {
            'batch': batch,
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'total_days': (end_date - start_date).days + 1
            },
            'statistics': {
                'student_count': batch_stats['student_count'],
                'average_attendance': batch_stats['average_percentage'],
                'status_distribution': batch_stats['status_distribution']
            },
            'students': []
        }

        # Add individual student data
        for student_stat in batch_stats['student_stats']:
            student_data = {
                'student': student_stat['student'],
                'attendance': student_stat,
            }

            if include_summaries:
                # Get recent summaries
                summaries = AttendanceSummary.objects.filter(
                    student=student_stat['student'],
                    period_start__gte=start_date,
                    period_end__lte=end_date
                ).order_by('-period_start')[:3]
                student_data['recent_summaries'] = summaries

            report_data['students'].append(student_data)

        return report_data

    @staticmethod
    def _get_attendance_status(percentage):
        """Get attendance status based on percentage"""
        if percentage >= 90:
            return 'Excellent'
        elif percentage >= 75:
            return 'Satisfactory'
        else:
            return 'Needs Improvement'

    @staticmethod
    def _get_status_color(percentage):
        """Get status color based on percentage"""
        if percentage >= 90:
            return 'success'
        elif percentage >= 75:
            return 'warning'
        else:
            return 'danger'


class AttendanceReportGenerator:
    """Class for generating various attendance reports"""

    def __init__(self, tenant):
        self.tenant = tenant

    def generate_student_report(self, student, academic_year=None, term=None):
        """Generate comprehensive attendance report for a student"""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(
                tenant=self.tenant, is_active=True
            ).first()

        batch = student.batchstudent.filter(is_active=True).first()
        if not batch:
            return None

        # Determine date range
        if term:
            start_date = term.start_date
            end_date = term.end_date
        else:
            start_date = academic_year.start_date
            end_date = academic_year.end_date

        # Calculate attendance
        attendance_data = AttendanceCalculator.calculate_student_attendance(
            student, start_date, end_date, batch.batch
        )

        # Get daily attendance records
        daily_records = Attendance.objects.filter(
            student=student,
            month_date__range=[start_date, end_date]
        ).order_by('month_date')

        # Get monthly summaries
        monthly_summaries = AttendanceSummary.objects.filter(
            student=student,
            period_type='MONTHLY',
            period_start__gte=start_date,
            period_end__lte=end_date
        ).order_by('period_start')

        return {
            'student': student,
            'batch': batch.batch,
            'academic_year': academic_year,
            'term': term,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'attendance_summary': attendance_data,
            'daily_records': daily_records,
            'monthly_summaries': monthly_summaries,
            'generated_at': timezone.now()
        }

    def generate_batch_report(self, batch, start_date, end_date):
        """Generate attendance report for an entire batch"""
        return AttendanceCalculator.get_attendance_report_data(
            batch, start_date, end_date, include_summaries=True
        )

    def generate_low_attendance_report(self, threshold=75, academic_year=None):
        """Generate report of students with attendance below threshold"""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(
                tenant=self.tenant, is_active=True
            ).first()

        # Get students with low attendance
        low_attendance_students = []

        batches = Batch.objects.filter(
            tenant=self.tenant,
            academic_year=academic_year
        )

        for batch in batches:
            batch_stats = AttendanceCalculator.calculate_batch_attendance(
                batch, academic_year.start_date, academic_year.end_date
            )

            for student_stat in batch_stats['student_stats']:
                if student_stat['attendance_percentage'] < threshold:
                    low_attendance_students.append({
                        'student': student_stat['student'],
                        'batch': batch,
                        'attendance': student_stat
                    })

        # Sort by attendance percentage (lowest first)
        low_attendance_students.sort(key=lambda x: x['attendance']['attendance_percentage'])

        return {
            'threshold': threshold,
            'academic_year': academic_year,
            'students': low_attendance_students,
            'total_count': len(low_attendance_students),
            'generated_at': timezone.now()
        }


def update_attendance_summaries(tenant, period_type='MONTHLY', start_date=None, end_date=None):
    """
    Utility function to update attendance summaries for all students
    This can be run as a periodic task
    """
    from .models import Student

    students = Student.objects.filter(tenant=tenant)
    updated_count = 0

    for student in students:
        try:
            summary = AttendanceCalculator.generate_attendance_summary(
                student, period_type, start_date, end_date
            )
            if summary:
                updated_count += 1
        except Exception as e:
            # Log error but continue with other students
            logger.error("Error updating attendance summary for %s: %s", student, e)

    return updated_count