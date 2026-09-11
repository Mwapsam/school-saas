from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, Http404, FileResponse
from django.views.generic import TemplateView, ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from core.authz.mixins import PermissionRequiredMixin, require_permission
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.template.loader import render_to_string
from django.contrib import messages
from django.urls import reverse
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


import json
import logging
import os
import tempfile
import zipfile

from django.core.files.storage import default_storage

from .models import (
    AcademicYear, Batch, BatchStudent, Configuration, Exam, ExamGroup,
    ExamScore, GradingLevel, GradingScale, ReportTemplate, SchoolSignature, StudentReport
)
from .services.calendar_service import SchoolCalendarService
from .services.school_signature_service import SchoolSignatureService
from .tasks import bulk_generate_reports_task


import logging

logger = logging.getLogger(__name__)

# Import only the models we still need for some views
from .models import (
    AcademicYear, Timetable, Weekday, Batch, Subject, Course, Attendance, Student, BatchStudent,
    ExamGroup, Term, Exam, ExamScore, PeriodEntry, SkillSet, Skill, SubSkill, ReportTemplate,
    StudentReport, HomeworkAssessment, ProjectWorkAssessment, StudentActivity, News, Guardian
)

from .view_modules.admission_views import (
    AdmissionRegistrationView,
    AdmissionRegistrationSubmitView,
    AdmissionSuccessView as ExtendedAdmissionSuccessView,
    AdmissionStatusCheckView,
    AdmissionManagementListView,
    AdmissionReportView,
    AdmissionStepNavigationView,
    upload_document_api,
    cleanup_temp_files_api,
    PortalLandingView,
    PortalAdmissionRegistrationView,
    PortalAdmissionSuccessView,
    PortalStatusCheckView,
)
from .view_modules.admission_diagnostics import (
    AdmissionDiagnosticsView,
    AdmissionDataStatusAPI
)
from .view_modules.admission_batch_assignment_views import (
    BatchAssignmentListView,
    BatchAssignmentView,
    BatchAssignmentDetailView
)
from .view_modules.enquiry_views import (
    ApplicantEnquiryListView,
    ApplicantEnquiryDetailView,
    ApplicantEnquiryCreateView,
    ApplicantEnquiryUpdateView,
    ApplicantEnquiryDeleteView,
    add_follow_up,
    add_stage_note,
    export_enquiries,
    enquiry_bulk_action,
)
from .view_modules.fee_management_views import (
    FeeCategoryListView,
    FeeCategoryCreateView,
    BatchFeeAssignmentView,
    BatchFeeAssignmentCreateView,
    BatchFeeAssignmentDeleteView,
    StudentFeeManagementView,
    StudentFeePaymentView,
    BatchFeeReportView,
    FeeReportsView,
    # Advanced Fee Management Views
    FeeParticularsView,
    FeeParticularsCreateView,
    FeeDiscountsView,
    FeeDiscountsCreateView,
    FeeWaiversListView,
    FeeWaiverRevokeView,
    FineSlabsView,
    FineSlabsCreateView,
    # API views
    student_search_api as student_fee_search_api,
    batch_students_fees_api,
    batch_students_for_collection_api,
    courses_by_academic_year_api,
    batches_by_course_api
)
from .view_modules.currency_views import (
    CurrencyConfigurationView,
    CurrencyConfigurationUpdateView,
    CurrencyPreviewView
)
from .view_modules.finance_dashboard_views import (
    FinanceDashboardView,
    FeeStructureView,
    FinanceSettingsView,
    FinanceReportsView,
    FeeReceiptsView,
    FeeReceiptPDFView,
    InvoicePDFView,
    QuickBooksWebhookReviewView,
    ParticularWiseStudentTransactionReportView,
    DayBookReportView,
    batches_by_class_api,
    QuickBooksSettingsView,
    QuickBooksConfigUpdateView,
    QuickBooksItemsView,
    QuickBooksStatusView,
    QuickBooksConnectView,
    QuickBooksCallbackView,
    QuickBooksDisconnectView,
    QuickBooksTestConnectionView
)
from .view_modules.admission_ajax_views import (
    AcademicYearAjaxView,
    CourseAjaxView,
    initialize_basic_data_ajax,
    admission_data_status_ajax,
    create_quick_academic_year_ajax
)
from .view_modules.library_hostel_transport_views import (
    LibraryIndexView,
    HostelIndexView,
    AssignmentIndexView,
    AssignmentDetailView as AssignmentDetailPageView,
    NewsIndexView,
    UserManagementView,
    ActivityCatalogueView,
    CommunicationView,
    CommunicationBatchGuardiansView,
)
from .services import (
    StudentService,
    EmployeeService,
    AcademicService, 
    FinanceService,
    LibraryService,
    UserService,
    AttendanceService,
    ExamService,
    CommunicationService,
    ReportingService,
    PermissionService,
    TimetableService
)
from .services.admission_service import AdmissionService
from .services.currency_service import CurrencyService, CurrencyContextMixin
from .forms import AdmissionApplicationForm, AdmissionReviewForm, AdmissionSearchForm
from .services.exceptions import ServiceException, ValidationException, NotFoundException, BusinessLogicException
from core.services.report_generation_service import ReportGenerationService


class HTMXResponseMixin:
    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get('HX-Request') == 'true'
        return super().dispatch(request, *args, **kwargs)
    
    def get_template_names(self):
        template_names = super().get_template_names()
        if self.is_htmx and hasattr(self, 'htmx_template_name'):
            return [self.htmx_template_name]
        return template_names
    
    def render_to_response(self, context, **response_kwargs):
        if self.is_htmx:
            context['is_htmx'] = True
        return super().render_to_response(context, **response_kwargs)


class DashboardView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    template_name = 'core/dashboard.html'
    htmx_template_name = 'core/htmx/dashboard_content.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            try:
                # Use ReportingService for comprehensive dashboard data
                reporting_service = ReportingService(tenant)
                dashboard_stats = reporting_service.get_dashboard_stats()

                context.update({
                    'total_students': dashboard_stats['students']['total_active'],
                    'total_employees': dashboard_stats['employees']['total_active'],
                    'total_batches': dashboard_stats['academic']['active_batches'],
                    'recent_students': dashboard_stats['students']['recent_admissions']
                })
            except Exception as e:
                # Handle cases where tenant is not properly set up
                context.update({
                    'total_students': 0,
                    'total_employees': 0,
                    'total_batches': 0,
                    'recent_students': []
                })

            try:
                context['recent_news'] = News.objects.filter(
                    tenant=tenant, is_active=True
                ).order_by('-created_at')[:3]
            except Exception:
                context['recent_news'] = []
        
        return context


class AdmissionDashboardView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    """Admission dashboard showing all admission-related modules"""
    template_name = 'core/admission/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['header_actions'] = [
            {'label': 'Dashboard', 'variant': 'outline', 'icon': 'fa-arrow-left', 'url': reverse('core:dashboard')},
        ]
        context['dashboard_tiles'] = [
            {'icon': 'fa-question-circle', 'title': 'Applicant Enquiry', 'description': 'View and manage prospective student enquiries and follow-ups', 'url': reverse('core:enquiry_list')},
            {'icon': 'fa-file-alt', 'title': 'Applicant Registration', 'description': 'Create new admission applications and manage student registration', 'url': reverse('core:admission_manage')},
            {'icon': 'fa-layer-group', 'title': 'Batch Assignment', 'description': 'Assign approved students to batches and classes', 'url': reverse('core:batch_assignment_list')},
            {'icon': 'fa-calendar-alt', 'title': 'Academic Years', 'description': 'Manage academic year settings and admission periods', 'url': reverse('core:academic_year_list')},
            {'icon': 'fa-chart-bar', 'title': 'Admission Reports', 'description': 'View admission statistics and generate reports', 'url': reverse('core:admission_diagnostics')},
            {'icon': 'fa-sitemap', 'title': 'Courses & Programs', 'description': 'Manage available courses and programs for admission', 'url': reverse('core:course_list')},
        ]
        return context


class AttendanceDashboardView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    """Attendance dashboard showing all attendance-related modules"""
    template_name = 'core/academic/attendance_dashboard.html'

    def get_context_data(self, **kwargs):
        import calendar as cal_mod
        from django.db.models import Q as _Q
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            context['trend_labels'] = []
            context['trend_values'] = []
            return context

        # Compute last-6-months school-wide attendance rate
        today = date.today()
        # Build list of (year, month) for the past 6 months, oldest first
        months = []
        y, m = today.year, today.month
        for _ in range(6):
            months.insert(0, (y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1

        trend_labels, trend_values = [], []
        for (yr, mo) in months:
            days_in_m = cal_mod.monthrange(yr, mo)[1]
            start = date(yr, mo, 1)
            end = date(yr, mo, days_in_m)
            base_qs = Attendance.objects.filter(tenant=tenant, month_date__gte=start, month_date__lte=end)
            total = base_qs.count()
            present = base_qs.filter(_Q(forenoon=True) | _Q(afternoon=True)).count()
            trend_labels.append(start.strftime('%b %Y'))
            trend_values.append(round(present / total * 100, 1) if total else 0)

        context['trend_labels'] = trend_labels
        context['trend_values'] = trend_values
        return context


class AttendanceRegisterView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    """Attendance register calendar view for marking student attendance"""
    template_name = 'core/academic/attendance_register.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            from .models import AttendanceSettings
            # Use the custom manager method for natural sort (single source of truth)
            batches = Batch.objects.filter(tenant=tenant, is_deleted=False).order_by_name_natural()
            context['batches'] = batches
            settings = AttendanceSettings.get_settings(tenant)
            context['lock_after_days'] = settings.lock_after_days if settings.mark_frequency == 'lock' else 0
        else:
            context['batches'] = []
            context['lock_after_days'] = 0
        return context


class AttendanceReportView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    """Attendance report showing student attendance statistics and percentages"""
    template_name = 'core/academic/attendance_report.html'

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Q
        from datetime import datetime
        import calendar

        context = super().get_context_data(**kwargs)

        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            context.update({
                'batches': [],
                'academic_years': [],
                'attendance_data': [],
                'total_working_days': 0,
                'selected_batch': '',
                'selected_academic_year': '',
                'selected_mode': 'monthly',
                'selected_month': '7',
                'selected_year': '2025'
            })
            return context

        # Add batches and academic years for the dropdowns
        context['batches'] = Batch.objects.filter(tenant=tenant, is_deleted=False).order_by('name')
        context['academic_years'] = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date')

        # Get filter parameters
        selected_batch_id = self.request.GET.get('batch', '')
        selected_academic_year = self.request.GET.get('academic_year', '')
        selected_mode = self.request.GET.get('mode', 'monthly')
        selected_month = int(self.request.GET.get('month', '7'))
        selected_year = int(self.request.GET.get('year', '2025'))
        percentage_filter = self.request.GET.get('percentage_filter', 'below')
        percentage_value = float(self.request.GET.get('percentage_value', '85'))

        context.update({
            'selected_batch': selected_batch_id,
            'selected_academic_year': selected_academic_year,
            'selected_mode': selected_mode,
            'selected_month': selected_month,
            'selected_year': selected_year,
            'percentage_filter': percentage_filter,
            'percentage_value': percentage_value
        })

        # Calculate attendance data
        attendance_data = []
        total_working_days = 0

        if selected_batch_id:
            try:
                batch = Batch.objects.get(id=selected_batch_id, tenant=tenant, is_deleted=False)

                # Determine date range based on mode
                if selected_mode == 'monthly':
                    start_date = datetime(selected_year, selected_month, 1).date()
                    end_date = datetime(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1]).date()
                elif selected_mode == 'overall':
                    # Use academic year dates if available
                    academic_year = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date').first()
                    if academic_year:
                        start_date = academic_year.start_date
                        end_date = academic_year.end_date
                    else:
                        start_date = datetime(selected_year, 1, 1).date()
                        end_date = datetime(selected_year, 12, 31).date()
                else:  # custom
                    start_date = datetime(selected_year, selected_month, 1).date()
                    end_date = datetime(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1]).date()

                # Calculate total working days (excluding weekends for now)
                total_working_days = self._calculate_working_days(start_date, end_date)

                # Get students in the batch
                from core.models import BatchStudent
                batch_students = BatchStudent.objects.filter(
                    batch=batch, is_active=True
                ).select_related('student')

                # Calculate attendance for each student
                for batch_student in batch_students:
                    student = batch_student.student

                    # Get attendance records for the period
                    attendance_records = Attendance.objects.filter(
                        student=student,
                        batch=batch,
                        month_date__range=[start_date, end_date]
                    )

                    # Calculate statistics
                    present_count = 0
                    absent_count = 0
                    late_count = 0

                    for record in attendance_records:
                        # Count as present if both forenoon and afternoon are True
                        if record.forenoon and record.afternoon:
                            present_count += 1
                        # Count as absent if both forenoon and afternoon are False
                        elif not record.forenoon and not record.afternoon:
                            absent_count += 1
                        # Partial attendance could be considered as present (adjust as needed)
                        else:
                            present_count += 0.5  # Half day attendance

                    # Calculate percentage
                    if total_working_days > 0:
                        percentage = (present_count / total_working_days) * 100
                    else:
                        percentage = 0

                    # Apply percentage filter
                    should_include = True
                    if percentage_filter == 'below' and percentage >= percentage_value:
                        should_include = False
                    elif percentage_filter == 'above' and percentage <= percentage_value:
                        should_include = False
                    elif percentage_filter == 'equal' and abs(percentage - percentage_value) > 0.01:
                        should_include = False

                    if should_include:
                        attendance_data.append({
                            'student': student,
                            'present': present_count,
                            'late': late_count,
                            'absent': absent_count,
                            'total': f"{present_count} / {total_working_days}",
                            'percentage': round(percentage, 2)
                        })

            except Batch.DoesNotExist:
                pass

        context['attendance_data'] = attendance_data
        context['total_working_days'] = total_working_days

        return context

    def _calculate_working_days(self, start_date, end_date):
        """Calculate number of working days between two dates (excluding weekends and holidays)"""
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            calendar = SchoolCalendarService(tenant)
            return calendar.get_working_days(start_date, end_date)
        else:
            from datetime import timedelta
            current_date = start_date
            working_days = 0
            while current_date <= end_date:
                if current_date.weekday() < 5:
                    working_days += 1
                current_date += timedelta(days=1)
            return working_days


class AttendanceDaywiseReportView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    """Day-wise attendance report showing attendance by batches for a specific date"""
    template_name = 'core/academic/attendance_daywise_report.html'

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Q, Case, When, IntegerField
        from django.db import models
        from datetime import datetime, date
        from collections import defaultdict

        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)

        if not tenant:
            context.update({
                'batches': [],
                'report_data': {},
                'summary': {},
                'today_date': date.today().strftime('%Y-%m-%d'),
                'selected_date': '',
                'selected_attendance_type': 'all',
                'selected_batch_id': '',
                'attendance_labels': [],
                'attendance_settings': None
            })
            return context

        # Get attendance settings and labels
        from core.models import AttendanceSettings, AttendanceLabel
        attendance_settings = AttendanceSettings.get_settings(tenant)
        attendance_labels = AttendanceLabel.objects.filter(
            tenant=tenant,
            is_active=True
        ).order_by('order', 'name')

        # Get filter parameters
        selected_date_str = self.request.GET.get('date', '')
        selected_attendance_type = self.request.GET.get('attendance_type', 'all')
        selected_batch_id = self.request.GET.get('batch_id', '')

        # Set default date to today if not provided
        if not selected_date_str:
            selected_date = date.today()
            selected_date_str = selected_date.strftime('%Y-%m-%d')
        else:
            try:
                selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                selected_date = date.today()
                selected_date_str = selected_date.strftime('%Y-%m-%d')

        # Get all batches for filter dropdown
        from core.models import Course
        batches = Batch.objects.filter(
            tenant=tenant,
            is_deleted=False
        ).select_related('course').order_by('course__course_name', 'name')

        context.update({
            'batches': batches,
            'today_date': date.today().strftime('%Y-%m-%d'),
            'selected_date': selected_date_str,
            'selected_attendance_type': selected_attendance_type,
            'selected_batch_id': selected_batch_id,
            'attendance_labels': attendance_labels,
            'attendance_settings': attendance_settings
        })

        # Generate report data
        report_data = defaultdict(lambda: {
            'batches': [],
            'total_students': 0,
            'total_late': 0,
            'total_absent': 0
        })

        summary = {
            'total_students': 0,
            'present_count': 0,
            'late_count': 0,
            'absent_count': 0
        }

        # Filter batches if specific batch selected
        if selected_batch_id:
            batches = batches.filter(id=selected_batch_id)

        for batch in batches:
            # Get all students in this batch with date filtering based on settings
            from core.models import BatchStudent
            batch_students_query = BatchStudent.objects.filter(
                batch=batch,
                is_active=True,
                tenant=tenant
            ).select_related('student')

            # Apply date filtering based on attendance calculation settings
            if attendance_settings.calculation_method == 'student_admission':
                # Only include students who were admitted before or on the report date
                batch_students_query = batch_students_query.filter(
                    student__date_of_admission__lte=selected_date
                )
            elif attendance_settings.calculation_method == 'batch_start':
                # Include students based on batch start date or student batch assignment date
                batch_students_query = batch_students_query.filter(
                    models.Q(created_at__date__lte=selected_date) |
                    models.Q(batch__start_date__lte=selected_date)
                )

            batch_students = batch_students_query
            total_students_in_batch = batch_students.count()

            if total_students_in_batch == 0:
                continue

            # Get attendance records for this batch and date
            attendance_query = Attendance.objects.filter(
                batch=batch,
                month_date=selected_date,
                tenant=tenant
            ).select_related('student')

            # Check attendance mark frequency settings
            if attendance_settings.mark_frequency == 'lock':
                # Check if attendance is locked based on lock_after_days setting
                from datetime import timedelta
                lock_date = selected_date + timedelta(days=attendance_settings.lock_after_days)
                current_date = date.today()

                # If the attendance is supposed to be locked and user is not admin, skip
                if current_date > lock_date and not attendance_settings.allow_admin_unlock:
                    # Could add user permission check here
                    pass  # For now, show all data

            attendance_records = attendance_query

            # Calculate attendance statistics using dynamic labels
            present_count = 0
            late_count = 0
            absent_count = 0
            absent_students = []

            # Create label lookups
            present_labels = attendance_labels.filter(is_considered_present=True)
            present_codes = [label.code.upper() for label in present_labels]

            # Create a lookup of attendance by student
            attendance_lookup = {att.student_id: att for att in attendance_records}

            for batch_student in batch_students:
                student = batch_student.student
                attendance = attendance_lookup.get(student.id)

                if attendance:
                    # Use attendance label if available
                    if hasattr(attendance, 'attendance_label') and attendance.attendance_label:
                        label = attendance.attendance_label
                        if label.is_considered_present:
                            present_count += 1
                        elif label.code.upper() == 'L':  # Late
                            late_count += 1
                        else:  # Absent
                            absent_count += 1
                            absent_students.append(student)
                    else:
                        # Fallback to forenoon/afternoon logic if no label
                        if attendance.forenoon and attendance.afternoon:
                            present_count += 1
                        elif not attendance.forenoon and not attendance.afternoon:
                            absent_count += 1
                            absent_students.append(student)
                        else:
                            late_count += 1
                else:
                    # No attendance record - consider as absent
                    absent_count += 1
                    absent_students.append(student)

            # Apply attendance type filter
            if selected_attendance_type != 'all':
                # Check if the filter matches any of the configured labels
                filter_matched = False
                for label in attendance_labels:
                    if selected_attendance_type == label.code.lower():
                        if label.is_considered_present and present_count > 0:
                            filter_matched = True
                        elif label.code.upper() == 'L' and late_count > 0:  # Late
                            filter_matched = True
                        elif not label.is_considered_present and label.code.upper() != 'L' and absent_count > 0:  # Absent
                            filter_matched = True
                        break

                # Fallback to hardcoded logic if no labels match
                if not filter_matched:
                    if selected_attendance_type == 'present' and present_count == 0:
                        continue
                    elif selected_attendance_type == 'absent' and absent_count == 0:
                        continue
                    elif selected_attendance_type == 'late' and late_count == 0:
                        continue
                elif not filter_matched:
                    continue

            # Group by course
            course_name = batch.course.course_name if batch.course else 'Unknown Course'

            batch_data = {
                'name': batch.name,
                'total_students': total_students_in_batch,
                'present_count': present_count,
                'late_count': late_count,
                'absent_count': absent_count,
                'absent_students': absent_students[:3]  # Show only first 3 names
            }

            report_data[course_name]['batches'].append(batch_data)
            report_data[course_name]['total_students'] += total_students_in_batch
            report_data[course_name]['total_late'] += late_count
            report_data[course_name]['total_absent'] += absent_count

            # Update summary
            summary['total_students'] += total_students_in_batch
            summary['present_count'] += present_count
            summary['late_count'] += late_count
            summary['absent_count'] += absent_count

        context['report_data'] = dict(report_data)
        context['summary'] = summary

        # Handle CSV export
        if self.request.GET.get('export') == 'csv':
            return self._export_csv(report_data, summary, selected_date_str)

        return context

    def _export_csv(self, report_data, summary, selected_date):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="daywise_attendance_{selected_date}.csv"'

        writer = csv.writer(response)

        # Write header
        writer.writerow(['Day-wise Attendance Report'])
        writer.writerow(['Date:', selected_date])
        writer.writerow([])  # Empty row
        writer.writerow(['Sl.No.', 'Course-Batch', 'Total', 'Late', 'Absent', 'Absent Students'])

        sl_no = 1
        for course_name, course_data in report_data.items():
            if course_data['batches']:
                # Write course header
                writer.writerow([
                    sl_no,
                    course_name,
                    course_data['total_students'],
                    course_data['total_late'],
                    course_data['total_absent'],
                    ''
                ])
                sl_no += 1

                # Write batch data
                for batch in course_data['batches']:
                    absent_names = ', '.join([student.full_name for student in batch['absent_students']])
                    writer.writerow([
                        '',
                        f"  {batch['name']}",
                        batch['total_students'],
                        batch['late_count'],
                        batch['absent_count'],
                        absent_names
                    ])

        # Write summary
        writer.writerow([])
        writer.writerow(['Summary:'])
        writer.writerow([
            'Total', 'Present', 'Late', 'Absent'
        ])
        writer.writerow([
            summary['total_students'],
            summary['present_count'],
            summary['late_count'],
            summary['absent_count']
        ])

        return response


class AttendanceSettingsView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    """Attendance settings configuration page"""
    template_name = 'core/academic/attendance_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)

        if not tenant:
            context.update({
                'attendance_labels': [],
                'attendance_settings': None
            })
            return context

        # Get attendance settings and labels
        from core.models import AttendanceSettings, AttendanceLabel
        attendance_settings = AttendanceSettings.get_settings(tenant)
        attendance_labels = AttendanceLabel.objects.filter(
            tenant=tenant,
            is_active=True
        ).order_by('order', 'name')

        context.update({
            'attendance_labels': attendance_labels,
            'attendance_settings': attendance_settings
        })

        return context

    def post(self, request, *args, **kwargs):
        """Handle form submission for attendance settings"""
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return self.get(request, *args, **kwargs)

        from core.models import AttendanceSettings
        attendance_settings = AttendanceSettings.get_settings(tenant)

        # Update settings based on form data
        attendance_settings.enable_custom_attendance = request.POST.get('enable_custom_attendance') == 'on'
        attendance_settings.calculation_method = request.POST.get('calculation_method', 'batch_start')
        attendance_settings.mark_frequency = request.POST.get('mark_frequency', 'open')
        attendance_settings.lock_after_days = int(request.POST.get('lock_after_days', 7))
        attendance_settings.allow_admin_unlock = request.POST.get('allow_admin_unlock') == 'on'
        attendance_settings.send_absence_notifications = request.POST.get('send_absence_notifications') == 'on'
        attendance_settings.notification_threshold = int(request.POST.get('notification_threshold', 3))

        # Update working days from form
        working_days = [int(d) for d in request.POST.getlist('working_days')]
        if working_days:
            attendance_settings.working_days = working_days

        attendance_settings.save()

        # Add success message (you can use Django messages framework)
        # messages.success(request, 'Attendance settings saved successfully!')

        return self.get(request, *args, **kwargs)


class AttendanceLabelEditView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    """Edit attendance label (Present, Absent, Late) properties"""
    template_name = 'core/academic/attendance_label_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        label_id = kwargs.get('label_id')

        if not tenant or not label_id:
            context.update({
                'attendance_label': None,
                'error': 'Invalid request'
            })
            return context

        try:
            from core.models import AttendanceLabel
            attendance_label = AttendanceLabel.objects.get(
                id=label_id,
                tenant=tenant
            )

            context.update({
                'attendance_label': attendance_label,
                'error': None
            })
        except AttendanceLabel.DoesNotExist:
            context.update({
                'attendance_label': None,
                'error': 'Attendance label not found'
            })

        return context

    def post(self, request, *args, **kwargs):
        """Handle form submission for attendance label edit"""
        tenant = getattr(request, 'tenant', None)
        label_id = kwargs.get('label_id')

        if not tenant or not label_id:
            return self.get(request, *args, **kwargs)

        try:
            from core.models import AttendanceLabel
            attendance_label = AttendanceLabel.objects.get(
                id=label_id,
                tenant=tenant
            )

            # Update label based on form data
            attendance_label.name = request.POST.get('status_name', attendance_label.name)
            attendance_label.code = request.POST.get('code', attendance_label.code).upper()

            # Determine if this is considered present based on name/code
            label_name_lower = attendance_label.name.lower()
            if 'present' in label_name_lower or attendance_label.code.upper() == 'P':
                attendance_label.is_considered_present = True
            else:
                attendance_label.is_considered_present = False

            # has_notification is not a model field — store via AttendanceSettings instead
            # (the setting is system-wide, not per-label)
            attendance_label.save()

            # Redirect back to settings page with success
            from django.shortcuts import redirect
            return redirect('core:attendance_settings')

        except Exception as e:
            context = self.get_context_data(**kwargs)
            context['error'] = f'Error updating label: {str(e)}'
            return self.render_to_response(context)


class SchoolCalendarView(LoginRequiredMixin, HTMXResponseMixin, TemplateView):
    """School calendar management page for holidays and events"""
    template_name = 'core/academic/school_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)

        if not tenant:
            context.update({
                'events': [],
                'holidays': [],
                'active_year': None,
            })
            return context

        from core.models import Event, AcademicYear, AttendanceSettings
        active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()

        if active_year:
            events = Event.objects.filter(
                tenant=tenant,
                academic_year=active_year
            ).order_by('start_date')
            holidays = events.filter(is_holiday=True)
        else:
            events = Event.objects.none()
            holidays = Event.objects.none()

        settings = AttendanceSettings.get_settings(tenant)
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        working_days_display = [weekday_names[i] for i in settings.working_days]

        context.update({
            'events': events,
            'holidays': holidays,
            'active_year': active_year,
            'settings': settings,
            'working_days_display': ', '.join(working_days_display),
            'all_weekdays': [(i, weekday_names[i]) for i in range(7)],
        })

        return context

    def post(self, request, *args, **kwargs):
        """Handle form submissions (event creation, working days update)"""
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return self.get(request, *args, **kwargs)

        from core.models import Event, AcademicYear, AttendanceSettings
        from django.http import JsonResponse

        action = request.POST.get('action', '').strip()

        if action == 'update_working_days':
            settings = AttendanceSettings.get_settings(tenant)
            working_days = [int(d) for d in request.POST.getlist('working_days')]
            settings.working_days = working_days
            settings.save()
            messages.success(request, 'Working days updated successfully!')

        elif action == 'create_event':
            try:
                from datetime import datetime
                active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
                if not active_year:
                    messages.error(request, 'No active academic year found.')
                    return self.get(request, *args, **kwargs)

                start_date_str = request.POST.get('start_date')
                end_date_str = request.POST.get('end_date')
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

                event = Event(
                    tenant=tenant,
                    academic_year=active_year,
                    title=request.POST.get('title'),
                    description=request.POST.get('description', ''),
                    start_date=start_date,
                    end_date=end_date,
                    is_holiday=request.POST.get('is_holiday') == 'on',
                    is_common=request.POST.get('is_common') == 'on',
                    is_exam=request.POST.get('is_exam') == 'on',
                )
                event.save()
                messages.success(request, f'Event "{event.title}" created successfully!')
            except Exception as e:
                messages.error(request, f'Error creating event: {str(e)}')

        elif action == 'delete_event':
            try:
                event_id = request.POST.get('event_id')
                event = Event.objects.get(id=event_id, tenant=tenant)
                event_title = event.title
                event.delete()
                messages.success(request, f'Event "{event_title}" deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting event: {str(e)}')

        return self.get(request, *args, **kwargs)


class StudentListView(LoginRequiredMixin, HTMXResponseMixin, ListView):
    template_name = 'core/students/list.html'
    htmx_template_name = 'core/htmx/student_list_content.html'
    context_object_name = 'students'
    paginate_by = 20

    # Sentinel batch-filter value for "students not allocated to any class".
    UNALLOCATED = '__unallocated__'

    # Allowed ?sort= values → ORM ordering. Default is alphabetical by name.
    SORT_OPTIONS = {
        'name': ['first_name', 'last_name'],
        'name_desc': ['-first_name', '-last_name'],
        'admission': ['admission_no'],
        'admission_desc': ['-admission_no'],
    }

    def _get_active_academic_year(self, tenant):
        return AcademicYear.objects.filter(tenant=tenant, is_active=True).first()

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Student.objects.none()

        search_query = self.request.GET.get('search', '').strip()
        batch_filter = self.request.GET.get('batch', '').strip()

        active_year = self._get_active_academic_year(tenant)
        if not active_year:
            return Student.objects.none()

        student_service = StudentService(tenant)

        if search_query:
            queryset = student_service.search_students(search_query, active_only=True)
        else:
            queryset = student_service.get_active_students()

        if batch_filter == self.UNALLOCATED:
            # Students with no active enrolment in any batch of the active year.
            queryset = queryset.exclude(
                student_batches__batch__academic_year=active_year,
                student_batches__is_active=True,
            ).distinct()
        else:
            # Scope to students enrolled in a batch that belongs to the active academic year
            queryset = queryset.filter(
                student_batches__batch__academic_year=active_year,
                student_batches__is_active=True,
            ).distinct()

            if batch_filter:
                queryset = queryset.filter(student_batches__batch_id=batch_filter)

        sort_param = self.request.GET.get('sort', '').strip()
        if sort_param:
            ordering = self.SORT_OPTIONS.get(sort_param, self.SORT_OPTIONS['name'])
        else:
            # No explicit choice → fall back to the school-wide configured order
            # (Configuration → Students Sorting).
            from core.services.configuration_service import SORT_FIELDS, student_sort_order
            ordering = SORT_FIELDS[student_sort_order(tenant)]

        # ALL active enrollments (any year), not just the active-year one this
        # list is filtered/scoped to — surfaces data problems like a student
        # having more than one active BatchStudent row (see promote_students.py
        # --fix-stale) directly on the page instead of only via a management
        # command.
        from django.db.models import Prefetch
        active_enrollments_qs = (
            BatchStudent.objects.filter(tenant=tenant, is_active=True)
            .select_related('batch', 'batch__academic_year')
            .order_by('-batch__academic_year__start_date', '-created_at')
        )

        return (
            queryset.select_related('nationality', 'student_category')
            .prefetch_related(
                Prefetch('student_batches', queryset=active_enrollments_qs, to_attr='active_enrollments')
            )
            .order_by(*ordering)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)

        search_query = self.request.GET.get('search', '').strip()
        batch_filter = self.request.GET.get('batch', '').strip()

        if tenant:
            active_year = self._get_active_academic_year(tenant)
            batches = (
                Batch.objects.filter(
                    tenant=tenant,
                    academic_year=active_year,
                    is_active=True,
                    is_deleted=False,
                ).select_related('course').order_by('name')
                if active_year else Batch.objects.none()
            )
            sort = self.request.GET.get('sort', '').strip()
            context.update({
                'search_query': search_query,
                'selected_batch': batch_filter,
                'has_filter': bool(search_query or batch_filter),
                'active_academic_year': active_year,
                'batches': batches,
                'unallocated_value': self.UNALLOCATED,
                'showing_unallocated': batch_filter == self.UNALLOCATED,
                'selected_sort': sort if sort in self.SORT_OPTIONS else 'name',
                'table_columns': ['', 'Sl No.', 'Name', 'Admn No.', 'Batch / Academic Year', 'Data Check', 'Actions'],
                'header_actions': [
                    {'label': 'Add Student', 'variant': 'primary'},
                    {'label': 'Bulk Actions', 'variant': 'outline', 'icon': 'fa-tasks', 'disabled': True, 'attrs': 'id="bulk-actions-btn"'},
                ],
                'single_allocate_footer': [
                    {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                    {'label': 'Allocate', 'variant': 'primary', 'attrs': 'onclick="confirmSingleAllocate()"'},
                ],
            })

        return context


class StudentEditView(LoginRequiredMixin, View):
    """Edit a student's core profile details."""
    template_name = 'core/students/edit.html'

    TEXT_FIELDS = [
        'admission_no', 'class_roll_no', 'first_name', 'middle_name', 'last_name',
        'gender', 'blood_group', 'birth_place', 'language', 'religion',
        'address_line1', 'address_line2', 'city', 'state', 'pin_code',
        'phone1', 'phone2', 'email',
    ]
    REQUIRED_TEXT = {'admission_no', 'first_name', 'last_name', 'gender'}
    FK_FIELDS = ['country', 'nationality', 'student_category']
    DATE_FIELDS = ['admission_date', 'date_of_birth']

    def _context(self, request, student):
        from .models import Country, StudentCategory
        return {
            'student': student,
            'countries': Country.objects.all().order_by('name'),
            'categories': StudentCategory.objects.filter(tenant=request.tenant).order_by('name'),
            'gender_choices': Student._meta.get_field('gender').choices,
        }

    def get(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            raise Http404("Student not found")
        student = StudentService(tenant).get_by_id(pk)
        return render(request, self.template_name, self._context(request, student))

    def post(self, request, pk):
        from django.utils.dateparse import parse_date
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            raise Http404("Student not found")

        service = StudentService(tenant)
        student = service.get_by_id(pk)

        data = {}
        for field in self.TEXT_FIELDS:
            if field in request.POST:
                value = request.POST.get(field, '').strip()
                # Keep required fields as-is (let validation reject blanks);
                # treat blank optional fields as NULL.
                data[field] = value if (value or field in self.REQUIRED_TEXT) else None

        for field in self.DATE_FIELDS:
            value = request.POST.get(field, '').strip()
            if value:
                parsed = parse_date(value)
                if parsed is None:
                    messages.error(request, f"Invalid date for {field.replace('_', ' ')}.")
                    return render(request, self.template_name, self._context(request, student))
                data[field] = parsed

        for field in self.FK_FIELDS:
            if field in request.POST:
                value = request.POST.get(field, '').strip()
                data[f'{field}_id'] = value or None

        data['is_active'] = request.POST.get('is_active') == 'on'

        try:
            service.update_student(str(pk), **data)
            messages.success(request, 'Student details updated successfully.')
            return redirect('core:student_detail', pk=pk)
        except (ValidationException, ServiceException) as e:
            messages.error(request, str(e))
            return render(request, self.template_name, self._context(request, student))


class StudentDetailView(LoginRequiredMixin, HTMXResponseMixin, CurrencyContextMixin, DetailView):
    template_name = 'core/students/detail.html'
    htmx_template_name = 'core/htmx/student_detail_content.html'
    context_object_name = 'student'
    
    def get_object(self):
        tenant = getattr(self.request, 'tenant', None)
        student_id = self.kwargs.get('pk')
        
        if not tenant or not student_id:
            raise NotFoundException("Student not found")
        
        student_service = StudentService(tenant)
        return student_service.get_by_id(student_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        tenant = getattr(self.request, 'tenant', None)

        if tenant:
            student_service = StudentService(tenant)
            finance_service = FinanceService(tenant)

            # Get the student's current active batch first
            current_batch = student.student_batches.filter(is_active=True).select_related('batch__academic_year').first()

            try:
                fee_balance = finance_service.get_student_fee_balance(student.id)
            except Exception:
                fee_balance = Decimal('0.00')

            available_terms = []
            default_term_id = None
            try:
                # Use the same attendance calculation as the report card
                # (calendar-filled, term-based) to match what shows on report cards
                if current_batch and current_batch.batch.academic_year:
                    from .models import AcademicYear
                    # Get available terms for this batch's academic year
                    available_terms = list(Term.objects.filter(tenant=tenant, academic_year=current_batch.batch.academic_year).order_by('order'))

                    # Resolve the current/nearest term
                    selected_term = ReportGenerationService.resolve_current_term(current_batch.batch.academic_year)
                    if selected_term:
                        default_term_id = str(selected_term.id)
                        # Compute attendance summary for the selected term
                        report_svc = ReportGenerationService(tenant)
                        records = list(
                            Attendance.objects.filter(
                                tenant=tenant, student=student, batch=current_batch.batch
                            ).values('month_date', 'forenoon', 'afternoon')
                        )
                        report_data = report_svc._compute_attendance_summary(
                            records,
                            start_date=selected_term.start_date,
                            end_date=selected_term.end_date,
                            batch=current_batch.batch
                        )
                        # Remap keys: days_present → present_days, days_absent → absent_days
                        attendance_summary = {
                            'total_days': report_data.get('total_days'),
                            'present_days': report_data.get('days_present'),
                            'absent_days': report_data.get('days_absent'),
                            'attendance_percentage': report_data.get('attendance_percentage'),
                        }
                    else:
                        attendance_summary = {}
                else:
                    attendance_summary = {}
            except Exception:
                attendance_summary = {}
            
            from .models import StudentGuardianRelation, Guardian
            guardian_relations = (
                StudentGuardianRelation.objects.filter(tenant=tenant, student=student)
                .select_related('guardian')
                .order_by('-is_immediate_contact', 'guardian__first_name')
            )
            linked_ids = guardian_relations.values_list('guardian_id', flat=True)
            available_guardians = Guardian.objects.filter(
                tenant=tenant, is_active=True
            ).exclude(id__in=list(linked_ids)).order_by('first_name', 'last_name')

            # Enhance available_guardians with disambiguating info (email, phone, linked children)
            # to help staff distinguish between guardians with the same name
            from django.db.models import Count

            # Batch query: get child counts for all guardians without email/phone
            guardians_without_contact = [g for g in available_guardians if not g.email and not g.mobile_phone]
            child_counts = {}
            if guardians_without_contact:
                counts_qs = StudentGuardianRelation.objects.filter(
                    tenant=tenant, guardian__in=guardians_without_contact
                ).values('guardian_id').annotate(count=Count('id'))
                child_counts = {item['guardian_id']: item['count'] for item in counts_qs}

            enriched_guardians = []
            for g in available_guardians:
                disambig_text = ""
                if g.email:
                    disambig_text = g.email
                elif g.mobile_phone:
                    disambig_text = g.mobile_phone
                else:
                    # Look up from pre-fetched counts
                    child_count = child_counts.get(g.id, 0)
                    if child_count > 0:
                        disambig_text = f"({child_count} child{'ren' if child_count != 1 else ''})"

                # Pass Guardian object with all fields plus computed display_name
                # Template can access both g.id, g.first_name, etc. AND g.display_name
                g.display_name = f"{g.first_name} {g.last_name}" + (f" — {disambig_text}" if disambig_text else "")
                enriched_guardians.append(g)


            from .models import DocumentCategory, StudentDocument
            student_documents = (
                StudentDocument.objects.filter(tenant=tenant, student=student)
                .select_related('category')
                .order_by('-uploaded_at')
            )
            document_categories = DocumentCategory.objects.filter(
                tenant=tenant, is_active=True
            ).order_by('display_order', 'name')

            context.update({
                'age': student_service.calculate_age(student.id),
                'current_batch': current_batch,
                'fee_balance': fee_balance,
                'attendance_summary': attendance_summary,
                'available_terms': available_terms,
                'default_term_id': default_term_id,
                'guardian_relations': guardian_relations,
                'available_guardians': enriched_guardians,
                'student_documents': student_documents,
                'document_categories': document_categories,
                'attach_guardian_footer': [
                    {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                    {'label': 'Attach', 'variant': 'primary', 'type': 'submit'},
                ],
            })

        return context


@method_decorator(login_required, name='dispatch')
class StudentDocumentsView(View):
    """Upload / delete files against a student, classified by DocumentCategory
    (Configuration → Document Categories). POST-only; redirects back to the
    student detail Documents tab."""

    def _redirect(self, student_id):
        return redirect(f"{reverse('core:student_detail', kwargs={'pk': student_id})}#documents")

    def post(self, request, student_id):
        from .models import DocumentCategory, Student, StudentDocument
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            messages.error(request, 'School not found.')
            return redirect('core:student_list')

        student = Student.objects.filter(tenant=tenant, id=student_id).first()
        if not student:
            messages.error(request, 'Student not found.')
            return redirect('core:student_list')

        action = request.POST.get('action')
        if action == 'delete':
            doc = StudentDocument.objects.filter(
                tenant=tenant, student=student, id=request.POST.get('document_id')
            ).first()
            if doc:
                doc.file.delete(save=False)
                doc.delete()
                messages.success(request, 'Document removed.')
            return self._redirect(student_id)

        upload = request.FILES.get('file')
        category = DocumentCategory.objects.filter(
            tenant=tenant, id=request.POST.get('category_id')
        ).first()
        if not upload or not category:
            messages.error(request, 'Choose a category and a file to upload.')
            return self._redirect(student_id)

        StudentDocument.objects.create(
            tenant=tenant, student=student, category=category, file=upload,
            original_filename=getattr(upload, 'name', '')[:255],
            note=(request.POST.get('note') or '').strip()[:255],
            uploaded_by_id=getattr(request.user, 'id', None),
        )
        messages.success(request, 'Document uploaded.')
        return self._redirect(student_id)


class ParentDetailView(LoginRequiredMixin, CurrencyContextMixin, DetailView):
    """Admin detail page for a single guardian/parent: profile, linked children,
    financial summary, invoices, receipts, and payment agreements."""

    model = Guardian
    template_name = 'core/parents/detail.html'
    context_object_name = 'guardian'
    pk_url_kwarg = 'pk'

    def get_object(self):
        tenant = getattr(self.request, 'tenant', None)
        guardian_id = self.kwargs.get('pk')

        if not tenant or not guardian_id:
            raise NotFoundException("Guardian not found")

        guardian = Guardian.objects.filter(id=guardian_id, tenant=tenant).first()
        if not guardian:
            raise NotFoundException("Guardian not found")

        return guardian

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardian = self.object
        tenant = getattr(self.request, 'tenant', None)

        if tenant:
            from django.db.models import Sum
            from portal import selectors as portal_selectors
            from core.models import Student, StudentGuardianRelation, PaymentAgreement

            # Self-heal: a student can be attached to this guardian through
            # ``Student.immediate_contact`` without a matching
            # ``StudentGuardianRelation`` row (older link paths set only one of
            # the two). Those children are "linked" but never showed up here.
            # Backfill the missing relation rows so the list, the count, and the
            # row action buttons all operate on real records.
            linked_student_ids = set(
                StudentGuardianRelation.objects.filter(
                    tenant=tenant, guardian=guardian
                ).values_list('student_id', flat=True)
            )
            missing_contact_students = Student.objects.filter(
                tenant=tenant, immediate_contact=guardian
            ).exclude(id__in=linked_student_ids)
            if missing_contact_students:
                StudentGuardianRelation.objects.bulk_create([
                    StudentGuardianRelation(
                        tenant=tenant,
                        school=tenant,
                        student=student,
                        guardian=guardian,
                        relation=guardian.relation or 'Guardian',
                        is_immediate_contact=True,
                    )
                    for student in missing_contact_students
                ])

            # Linked students (guardian's children). Materialise the list so the
            # count shown on the page is exactly what is rendered — a bare
            # ``.count()`` would also tally any relation row whose student has
            # since been deleted (the INNER JOIN below drops those from the list).
            guardian_relations = [
                rel
                for rel in StudentGuardianRelation.objects.filter(
                    tenant=tenant, guardian=guardian
                ).select_related('student').order_by(
                    '-is_immediate_contact', 'student__first_name'
                )
                if rel.student_id is not None
            ]
            linked_children_count = len(guardian_relations)

            # Financial data (reuse portal selectors — they're tenant-aware)
            family_invoices = portal_selectors.family_invoices_for_guardian(guardian)
            receipts = portal_selectors.receipts_for_guardian(guardian)

            # Payment agreements for this guardian
            payment_agreements = PaymentAgreement.objects.filter(
                tenant=tenant, guardian=guardian
            ).order_by('-created_at')

            # Total outstanding balance across all invoices
            total_outstanding = sum((inv.balance_due or 0) for inv in family_invoices)
            total_amount_paid = sum((inv.amount_paid or 0) for inv in family_invoices)

            # Portal access info (from linked User, if any)
            has_login = guardian.user is not None
            username = guardian.user.username if has_login else None
            last_login = guardian.user.last_login if has_login else None
            is_active = guardian.user.is_active if has_login else guardian.is_active

            # Count open invoices
            open_invoices_count = sum(1 for inv in family_invoices if inv.status == 'open')

            context.update({
                'guardian_relations': guardian_relations,
                'linked_children_count': linked_children_count,
                'family_invoices': family_invoices,
                'receipts': receipts,
                'payment_agreements': payment_agreements,
                'total_outstanding': total_outstanding,
                'total_amount_paid': total_amount_paid,
                'open_invoices_count': open_invoices_count,
                'has_login': has_login,
                'username': username,
                'last_login': last_login,
                'is_active': is_active,
            })

        return context

    def post(self, request, *args, **kwargs):
        """Handle in-place actions: update profile, toggle active, set primary contact, unlink student."""
        self.object = self.get_object()
        guardian = self.object
        tenant = getattr(request, 'tenant', None)

        if not tenant or not request.user.is_admin:
            messages.error(request, 'Only administrators can modify guardians.')
            return redirect('core:parent_detail', pk=guardian.id)

        action = request.POST.get('action')

        try:
            if action == 'update_profile':
                # Edit guardian's profile fields
                guardian.first_name = request.POST.get('first_name', guardian.first_name)
                guardian.last_name = request.POST.get('last_name', guardian.last_name)
                guardian.relation = request.POST.get('relation', guardian.relation)
                guardian.email = request.POST.get('email') or None
                guardian.mobile_phone = request.POST.get('mobile_phone') or None
                guardian.office_phone = request.POST.get('office_phone') or None
                guardian.office_address_line1 = request.POST.get('office_address_line1') or None
                guardian.office_address_line2 = request.POST.get('office_address_line2') or None
                guardian.city = request.POST.get('city') or None
                guardian.state = request.POST.get('state') or None
                guardian.occupation = request.POST.get('occupation') or None
                guardian.education = request.POST.get('education') or None
                guardian.dob = request.POST.get('dob') or None

                guardian.save()
                messages.success(request, f'{guardian.first_name} {guardian.last_name} profile updated.')

            elif action == 'set_primary_contact':
                # Mark a linked student's primary contact
                student_id = request.POST.get('student_id')
                student_service = StudentService(tenant)
                student_service.set_primary_contact(student_id, str(guardian.id), is_primary=True)
                messages.success(request, 'Primary contact updated.')

            elif action == 'unlink_student':
                # Remove guardian from a student
                student_id = request.POST.get('student_id')
                student_service = StudentService(tenant)
                student_service.remove_guardian(student_id, str(guardian.id), delete_guardian_record=False)
                messages.success(request, 'Student unlinked from guardian.')

            elif action == 'update_relationship':
                # Edit how this guardian relates to one of their linked students
                # (Father/Mother/Guardian/etc) — StudentGuardianRelation.relation.
                student_id = request.POST.get('student_id')
                new_relation = (request.POST.get('relation') or '').strip()
                if not new_relation:
                    messages.error(request, 'Relationship cannot be empty.')
                else:
                    from .models import StudentGuardianRelation
                    updated = StudentGuardianRelation.objects.filter(
                        tenant=tenant, guardian=guardian, student_id=student_id
                    ).update(relation=new_relation)
                    if updated:
                        messages.success(request, 'Relationship updated.')
                    else:
                        messages.error(request, 'This guardian is not linked to that student.')

            elif action == 'toggle_active':
                # Toggle guardian's is_active flag (only affects display, not portal access)
                guardian.is_active = not guardian.is_active
                guardian.save()
                status_label = 'activated' if guardian.is_active else 'deactivated'
                messages.success(request, f'Guardian {status_label}.')

            elif action == 'enable_login':
                # Create portal login for this guardian
                if not guardian.user:
                    from core.services.portal_account_service import PortalAccountService

                    username = request.POST.get('username')
                    password = request.POST.get('password')

                    try:
                        account_service = PortalAccountService(tenant)
                        account_service.grant_guardian_portal_access(
                            guardian=guardian,
                            username=username,
                            password=password
                        )
                        messages.success(request, f'Portal login enabled for {guardian.first_name}.')
                    except Exception as e:
                        messages.error(request, f'Could not enable login: {str(e)}')
                else:
                    messages.warning(request, 'Guardian already has portal access.')

            elif action == 'deactivate_login':
                # Deactivate portal login
                if guardian.user:
                    user_service = UserService(tenant)
                    user_service.deactivate_user(str(guardian.user.id), performing_user=request.user)
                    messages.success(request, f'Portal login deactivated for {guardian.first_name}.')
                else:
                    messages.warning(request, 'Guardian has no portal login to deactivate.')

            elif action == 'reset_password':
                # Reset guardian's portal password
                if guardian.user:
                    new_password = request.POST.get('new_password')
                    from django.contrib.auth.hashers import make_password

                    guardian.user.set_password(new_password)
                    guardian.user.password_change_required = True
                    guardian.user.save()
                    messages.success(request, f'Password reset for {guardian.first_name}. They must change it on next login.')
                else:
                    messages.error(request, 'Guardian has no portal login.')

        except NotFoundException as e:
            messages.error(request, str(e))
        except BusinessLogicException as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

        return redirect('core:parent_detail', pk=guardian.id)


class ChangePrimaryContactView(LoginRequiredMixin, View):
    """Update is_immediate_contact flag on a StudentGuardianRelation via service layer.
    Only one guardian per student can be the immediate contact."""

    def post(self, request, student_id, guardian_id):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'Tenant not found'}, status=400)

        try:
            student_service = StudentService(tenant)
            is_immediate = request.POST.get('is_immediate_contact') in ('on', 'true', '1')

            result = student_service.set_primary_contact(student_id, guardian_id, is_immediate)
            guardian = result['guardian']

            if is_immediate:
                response_message = f'{guardian.first_name} {guardian.last_name} is now the primary contact.'
            else:
                if result['was_changed']:
                    response_message = f'{guardian.first_name} {guardian.last_name} is no longer the primary contact.'
                else:
                    response_message = f'{guardian.first_name} {guardian.last_name} is not currently the primary contact.'

            return JsonResponse({'success': True, 'message': response_message})

        except NotFoundException as e:
            logger.warning(f"Not found in set_primary_contact: {str(e)}")
            return JsonResponse({'error': str(e.message)}, status=404)
        except ServiceException as e:
            logger.error(f"Service error updating primary contact: {str(e)}")
            return JsonResponse({'error': str(e.message)}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error updating primary contact: {str(e)}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


class DeleteGuardianView(LoginRequiredMixin, View):
    """Delete a guardian from a student via service layer.
    If the guardian has no other linked students, offer to delete the guardian record.
    Guardian records with invoices are protected from deletion."""

    def post(self, request, student_id, guardian_id):
        from django.db.models import ProtectedError

        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'Tenant not found'}, status=400)

        try:
            student_service = StudentService(tenant)
            delete_guardian = request.POST.get('delete_guardian') in ('on', 'true', '1')

            result = student_service.remove_guardian(student_id, guardian_id, delete_guardian)
            guardian = result['guardian']

            response_data = {'success': True}

            if result['guardian_deleted']:
                response_data['guardian_deleted'] = True
                response_data['message'] = f'{guardian.first_name} {guardian.last_name} and associated guardian record removed.'
            elif result['has_other_relations']:
                response_data['message'] = f'Removed {guardian.first_name} {guardian.last_name} from student. (Still linked to other students.)'
            else:
                response_data['message'] = f'Removed {guardian.first_name} {guardian.last_name} from student.'

            return JsonResponse(response_data)

        except ProtectedError:
            # Guardian has foreign key constraints (e.g., invoices). Rollback entire transaction.
            # Load guardian name for error message (may fail if guardian was already deleted in prior step)
            guardian_name = f'{guardian_id}'
            try:
                from .models import Guardian
                g = Guardian.objects.get(id=guardian_id, tenant=tenant)
                guardian_name = f'{g.first_name} {g.last_name}'
            except Exception:
                pass
            return JsonResponse({
                'success': False,
                'error': f'{guardian_name} record is protected by linked financial records (invoices). Contact finance admin to resolve.'
            }, status=400)
        except NotFoundException as e:
            logger.warning(f"Not found in remove_guardian: {str(e)}")
            return JsonResponse({'error': str(e.message)}, status=404)
        except ServiceException as e:
            logger.error(f"Service error deleting guardian: {str(e)}")
            return JsonResponse({'error': str(e.message)}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error deleting guardian: {str(e)}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


class AttachGuardianView(LoginRequiredMixin, View):
    """Attach a parent/guardian to a student: link an existing guardian or
    create a new one, then create the StudentGuardianRelation."""

    def post(self, request, student_id):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'Tenant not found'}, status=400)

        from .models import Guardian, StudentGuardianRelation
        from django.db import transaction as db_transaction

        student = StudentService(tenant).get_by_id(student_id)

        guardian_id = (request.POST.get('guardian_id') or '').strip()
        relation = (request.POST.get('relation') or '').strip() or 'Guardian'
        is_immediate = request.POST.get('is_immediate_contact') in ('on', 'true', '1')

        try:
            with db_transaction.atomic():
                # Extract contact info from form (used if creating new guardian)
                email = (request.POST.get('email') or '').strip() or None
                mobile_phone = (request.POST.get('mobile_phone') or '').strip() or None

                if guardian_id:
                    guardian = Guardian.objects.filter(id=guardian_id, tenant=tenant).first()
                    if guardian is None:
                        return JsonResponse({'error': 'Guardian not found'}, status=404)
                    guardian_reused = False
                    # Use guardian's existing contact info if not provided in form
                    if not email:
                        email = guardian.email
                    if not mobile_phone:
                        mobile_phone = guardian.mobile_phone
                else:
                    first_name = (request.POST.get('first_name') or '').strip()
                    last_name = (request.POST.get('last_name') or '').strip()
                    if not first_name or not last_name:
                        return JsonResponse({'error': 'First and last name are required'}, status=400)

                    # Reuse an existing guardian on an exact email/mobile match
                    # instead of creating a duplicate — same rule the admission
                    # flow uses. Staff who skip the search-and-select list above
                    # and type in a parent who's already on file still land on
                    # the same guardian record.
                    from .services.portal_account_service import PortalAccountService
                    guardian = PortalAccountService(tenant).find_existing_guardian(
                        email=email, mobile=mobile_phone,
                        first_name=first_name, last_name=last_name,
                    )
                    guardian_reused = guardian is not None
                    if guardian is None:
                        guardian = Guardian.objects.create(
                            tenant=tenant,
                            first_name=first_name,
                            last_name=last_name,
                            relation=relation,
                            mobile_phone=mobile_phone,
                            office_phone=(request.POST.get('office_phone') or '').strip() or None,
                            email=email,
                            occupation=(request.POST.get('occupation') or '').strip() or None,
                        )

                # Avoid duplicate links.
                if StudentGuardianRelation.objects.filter(
                    tenant=tenant, student=student, guardian=guardian
                ).exists():
                    return JsonResponse({'error': 'This guardian is already linked to the student'}, status=400)

                if is_immediate:
                    StudentGuardianRelation.objects.filter(
                        tenant=tenant, student=student, is_immediate_contact=True
                    ).update(is_immediate_contact=False)

                StudentGuardianRelation.objects.create(
                    tenant=tenant,
                    student=student,
                    guardian=guardian,
                    relation=relation,
                    is_immediate_contact=is_immediate,
                    school=tenant,
                )

                if is_immediate:
                    student.immediate_contact = guardian
                    student.save(update_fields=['immediate_contact'])

            # Auto-provision login credentials if the guardian doesn't have an account yet
            credentials_sent = False
            if guardian.user_id is None:
                try:
                    from .services.portal_account_service import PortalAccountService
                    svc = PortalAccountService(tenant)

                    # Generate unique username based on email or name
                    username_base = (
                        email.split("@")[0]
                        if email
                        else f"{guardian.first_name}.{guardian.last_name}"
                    )
                    username = svc.generate_unique_username(username_base)
                    password = svc.generate_password()

                    # Grant portal access (create User, link to Guardian)
                    svc.grant_portal_access(
                        profile_type="guardian",
                        profile_id=str(guardian.id),
                        username=username,
                        password=password,
                        email=email,
                    )

                    # Send credentials via SMS (best-effort)
                    sms_result = svc.send_credentials_sms(
                        guardian, username=username, password=password
                    )
                    credentials_sent = sms_result.get("success", False)

                    if not credentials_sent:
                        logger.warning(
                            "Failed to send credentials SMS for guardian %s: %s",
                            guardian.id,
                            sms_result.get("error"),
                        )
                except Exception as e:
                    logger.error(
                        "Error provisioning account for guardian %s: %s", guardian.id, e
                    )
                    # Don't raise — attach itself succeeded, only provisioning failed

            message = f'{guardian.first_name} {guardian.last_name} attached as {relation}.'
            if guardian_reused:
                message = (
                    f'Linked to the existing guardian record for '
                    f'{guardian.first_name} {guardian.last_name} instead of '
                    f'creating a duplicate.'
                )

            return JsonResponse({
                'success': True,
                'message': message,
                'credentials_sent': credentials_sent,
            })
        except (ValidationException, ServiceException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error attaching guardian: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET", "POST"])
# @login_required  # Commented out for development
def student_search_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    search_query = request.GET.get('q', '').strip()
    if len(search_query) < 2:
        return JsonResponse({'results': []})
    
    try:
        student_service = StudentService(tenant)
        students = student_service.search_students(
            search_query, 
            active_only=True, 
            limit=10
        )
        
        results = [{
            'id': str(student.id),
            'text': f"{student.first_name} {student.last_name} ({student.admission_no})",
            'admission_no': student.admission_no,
            'full_name': f"{student.first_name} {student.last_name}"
        } for student in students]
        
        return JsonResponse({'results': results})
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def student_bulk_action(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        student_ids = data.get('student_ids', [])

        if not action or not student_ids:
            return JsonResponse({'error': 'Action and student IDs required'}, status=400)

        if action == 'allocate':
            return _bulk_allocate_students(request, tenant, student_ids, data.get('batch_id'))

        student_service = StudentService(tenant)
        results = []

        for student_id in student_ids:
            try:
                if action == 'deactivate':
                    student = student_service.deactivate_student(student_id)
                elif action == 'reactivate':
                    student = student_service.reactivate_student(student_id)
                else:
                    return JsonResponse({'error': f'Unknown action: {action}'}, status=400)

                results.append({
                    'id': str(student.id),
                    'success': True,
                    'name': f"{student.first_name} {student.last_name}"
                })
            except ServiceException as e:
                results.append({
                    'id': student_id,
                    'success': False,
                    'error': str(e)
                })

        return JsonResponse({
            'success': True,
            'results': results,
            'message': f'Bulk action {action} completed'
        })

    except (json.JSONDecodeError, ServiceException) as e:
        return JsonResponse({'error': str(e)}, status=400)


def _bulk_allocate_students(request, tenant, student_ids, batch_id):
    """Allocate students to a class, but only those not already in a class for
    the target batch's academic year. Students already allocated are skipped, so
    this never creates a second active enrolment (no duplicates)."""
    from django.db import transaction
    from core.models import Batch, Student, BatchStudent

    if not batch_id:
        return JsonResponse({'error': 'Please choose a class to allocate students to.'}, status=400)

    try:
        batch = Batch.objects.select_related('academic_year').get(
            id=batch_id, tenant=tenant, is_deleted=False,
        )
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Class (batch) not found'}, status=404)

    academic_year = batch.academic_year
    allocated, skipped, errors = 0, 0, []

    with transaction.atomic():
        for student_id in student_ids:
            try:
                student = Student.objects.get(id=student_id, tenant=tenant)

                # "Not yet allocated" = no active enrolment in any batch of this
                # academic year. Skip anyone who already has a class.
                already = BatchStudent.objects.filter(
                    student=student, tenant=tenant, is_active=True,
                    batch__academic_year=academic_year,
                ).exists()
                if already:
                    skipped += 1
                    continue

                batch_student, created = BatchStudent.objects.get_or_create(
                    batch=batch, student=student, tenant=tenant,
                    defaults={'is_active': True},
                )
                if not created and not batch_student.is_active:
                    batch_student.is_active = True
                    batch_student.save(update_fields=['is_active'])
                allocated += 1
            except Student.DoesNotExist:
                errors.append(f'Student {student_id} not found')
            except Exception as e:
                errors.append(f'Error allocating student {student_id}: {str(e)}')

    parts = [f'Allocated {allocated} student(s) to {batch.name}']
    if skipped:
        parts.append(f'{skipped} already in a class (skipped)')
    if errors:
        parts.append(f'{len(errors)} error(s)')
    return JsonResponse({
        'success': True,
        'allocated': allocated,
        'skipped': skipped,
        'errors': errors,
        'message': '. '.join(parts) + '.',
    })


def _current_year_batches(tenant, academic_service, search_query=''):
    """Active-year batches, grade-ordered — the canonical batch list shown on the
    /batches/ page. Shared by the list view and the create/update htmx responses
    so a partial refresh and a full page load agree (no stale previous-year rows).
    """
    from django.db.models import Case, When, Value, IntegerField

    active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
    if not active_year:
        return Batch.objects.none()

    qs = (academic_service.search_batches(search_query) if search_query
          else academic_service.get_all_batches())

    grade_order = Case(
        When(course__course_name__iexact='BEGINNERS',    then=Value(1)),
        When(course__course_name__iexact='RECEPTION',    then=Value(2)),
        When(course__course_name__iexact='MIDDLE CLASS', then=Value(3)),
        When(course__course_name__iexact='GRADE 1',      then=Value(4)),
        When(course__course_name__iexact='GRADE 2',      then=Value(5)),
        When(course__course_name__iexact='GRADE 3',      then=Value(6)),
        When(course__course_name__iexact='GRADE 4',      then=Value(7)),
        When(course__course_name__iexact='GRADE 5',      then=Value(8)),
        When(course__course_name__iexact='GRADE 6',      then=Value(9)),
        When(course__course_name__iexact='GRADE 7',      then=Value(10)),
        When(course__course_name__iexact='GRADE 8',      then=Value(11)),
        When(course__course_name__iexact='GRADE 9',      then=Value(12)),
        When(course__course_name__iexact='GRADE 10',     then=Value(13)),
        When(course__course_name__iexact='GRADE 11',     then=Value(14)),
        When(course__course_name__iexact='GRADE 12',     then=Value(15)),
        default=Value(99),
        output_field=IntegerField(),
    )
    return qs.filter(academic_year=active_year).annotate(grade_order=grade_order).order_by('grade_order', 'name')


class BatchListView(LoginRequiredMixin, HTMXResponseMixin, ListView):
    template_name = 'core/academic/batches.html'
    htmx_template_name = 'core/htmx/batch_list_content.html'
    context_object_name = 'batches'
    paginate_by = 15
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Batch.objects.none()

        academic_service = AcademicService(tenant)
        search_query = self.request.GET.get('search', '').strip()
        return _current_year_batches(tenant, academic_service, search_query)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['active_academic_year'] = AcademicYear.objects.filter(
                tenant=tenant, is_active=True
            ).first()
        return context


class BatchDetailView(LoginRequiredMixin, HTMXResponseMixin, DetailView):
    template_name = 'core/academic/batch_detail.html'
    htmx_template_name = 'core/htmx/batch_detail_content.html'
    context_object_name = 'batch'

    def get_object(self):
        tenant = getattr(self.request, 'tenant', None)
        batch_id = self.kwargs.get('pk')

        if not tenant or not batch_id:
            raise Http404("Batch not found")

        academic_service = AcademicService(tenant)
        try:
            return academic_service.get_batch_by_id(batch_id)
        except NotFoundException:
            raise Http404("Batch not found")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch = self.object
        tenant = getattr(self.request, 'tenant', None)

        if tenant:
            from core.services import ClassTeacherAssignmentService
            from core.services.teacher_comment_service import TeacherCommentService

            student_service = StudentService(tenant)
            assignment_svc = ClassTeacherAssignmentService(tenant)
            tc_svc = TeacherCommentService(tenant)

            # Get batch students
            batch_students = student_service.get_students_by_batch(batch.id)
            context['batch_students'] = batch_students
            context['student_count'] = batch_students.count()

            # Get batch assignment overview from service
            batch_assignments = assignment_svc.batch_assignment_overview(batch)

            # Enhance with comment presence info
            route = tc_svc.current_route_for_batch(batch)
            student_ids = [str(entry['student'].id) for entry in batch_assignments]
            comments_map = tc_svc.get_comments_map(route, student_ids=student_ids) if student_ids else {}

            for entry in batch_assignments:
                entry['has_comment'] = str(entry['student'].id) in comments_map

            context['batch_assignments'] = batch_assignments

            # Get batch subjects (with assigned teacher)
            context['subjects'] = batch.subjects.filter(
                tenant=tenant, is_deleted=False
            ).select_related('employee')

            # Get timetable entries for this batch
            context['timetable_entries'] = Timetable.objects.filter(
                tenant=tenant,
                batch=batch
            ).select_related('subject', 'employee', 'weekday', 'class_timing')

            # Related objects used in the header / info card
            context['academic_year'] = batch.academic_year
            context['course'] = batch.course
            context['class_teacher'] = batch.employee
            context['class_teachers'] = batch.class_teachers.all()

        return context


@require_http_methods(["GET"])
@login_required  
def batch_students_api(request, batch_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        student_service = StudentService(tenant)
        students = student_service.get_students_by_batch(batch_id, active_only=True)
        
        results = [{
            'id': str(student.id),
            'admission_no': student.admission_no,
            'full_name': ' '.join(filter(None, [student.first_name, student.middle_name, student.last_name])),
            'age': student_service.calculate_age(student.id)
        } for student in students]
        
        return JsonResponse({
            'students': results,
            'count': len(results)
        })
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


# ====== ADDITIONAL BATCH MANAGEMENT APIs ======

@require_http_methods(["POST"])
@login_required
def batch_delete_api(request, batch_id):
    """Delete a batch"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from core.models import Batch
        batch = Batch.objects.get(id=batch_id, tenant=tenant)
        
        # Check if batch has students
        if batch.batchstudent_set.filter(tenant=tenant, is_active=True).exists():
            return JsonResponse({
                'error': 'Cannot delete batch with active students. Remove all students first.',
                'success': False
            }, status=400)
        
        batch.delete()
        return JsonResponse({'success': True, 'message': 'Batch deleted successfully'})
        
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found', 'success': False}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
@login_required
def remove_student_from_batch_api(request, batch_id, student_id):
    """Remove a student from a batch"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from core.models import BatchStudent
        batch_student = BatchStudent.objects.get(
            batch_id=batch_id, 
            student_id=student_id,
            tenant=tenant,
            is_active=True
        )
        
        batch_student.is_active = False
        batch_student.save()
        
        return JsonResponse({'success': True, 'message': 'Student removed from batch successfully'})
        
    except BatchStudent.DoesNotExist:
        return JsonResponse({'error': 'Student not found in batch', 'success': False}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
@login_required
def batch_reassign_teacher_api(request, batch_id, student_id):
    """Reassign a student to a different class teacher within a batch."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        from core.models import Batch, Student, ClassTeacherAssignment
        from core.services import ClassTeacherAssignmentService

        batch = Batch.objects.get(id=batch_id, tenant=tenant)
        student = Student.objects.get(id=student_id, tenant=tenant)

        # Parse request body
        data = json.loads(request.body)
        employee_id = data.get('employee_id')

        if not employee_id:
            return JsonResponse({'error': 'employee_id is required'}, status=400)

        # Use service to handle assignment (validates pool, deactivates old, creates new)
        svc = ClassTeacherAssignmentService(tenant)
        assignment = svc.assign(
            str(student_id),
            str(batch_id),
            employee_id,
            user=request.user,
            reason="admin reassignment"
        )

        return JsonResponse({
            'success': True,
            'message': f'Student reassigned to {assignment.employee.full_name}',
            'assignment': {
                'id': str(assignment.id),
                'employee_id': str(assignment.employee.id),
                'employee_name': assignment.employee.full_name,
            }
        })

    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found', 'success': False}, status=404)
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found', 'success': False}, status=404)
    except Exception as e:
        from core.services.exceptions import ValidationException, NotFoundException
        if isinstance(e, ValidationException):
            return JsonResponse({'error': str(e), 'success': False}, status=400)
        if isinstance(e, NotFoundException):
            return JsonResponse({'error': str(e), 'success': False}, status=404)
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["GET"])
@login_required
def batch_class_teachers_api(request, batch_id):
    """Get the list of class teachers for a batch (used in reassign modal)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        from core.models import Batch

        batch = Batch.objects.get(id=batch_id, tenant=tenant)

        # Get pool: class_teachers or fallback to employee
        pool = list(batch.class_teachers.all()) if batch.class_teachers.exists() else ([batch.employee] if batch.employee else [])

        teachers = [{
            'id': str(teacher.id),
            'name': teacher.full_name,
            'is_current': False,  # Will be set by frontend if needed
        } for teacher in pool if teacher]

        return JsonResponse({'teachers': teachers})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def available_students_for_batch_api(request):
    """Get students available to be added to a batch"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    batch_id = request.GET.get('batch_id')
    query = request.GET.get('q', '')
    
    try:
        student_service = StudentService(tenant)
        # Get students not in the specified batch
        from core.models import Student, BatchStudent
        
        # Students already in this batch
        students_in_batch = BatchStudent.objects.filter(
            batch_id=batch_id, 
            tenant=tenant,
            is_active=True
        ).values_list('student_id', flat=True)
        
        # Available students
        students_queryset = Student.objects.filter(
            tenant=tenant,
            is_deleted=False
        ).exclude(id__in=students_in_batch)
        
        # Apply search filter
        if query:
            students_queryset = students_queryset.filter(
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query) |
                Q(admission_no__icontains=query)
            )
        
        students = students_queryset[:20]  # Limit for performance
        
        results = [{
            'id': str(student.id),
            'admission_no': student.admission_no,
            'full_name': f"{student.first_name} {student.last_name}"
        } for student in students]
        
        return JsonResponse({'students': results})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def batches_by_academic_year_api(request):
    """List batches for a given academic year (used by the cross-year student import)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_year_id = request.GET.get('academic_year_id')
    exclude_id = request.GET.get('exclude')
    if not academic_year_id:
        return JsonResponse({'error': 'academic_year_id is required'}, status=400)

    from core.models import Batch, BatchStudent
    qs = Batch.objects.filter(
        tenant=tenant, academic_year_id=academic_year_id, is_deleted=False
    ).select_related('course').order_by('course__course_name', 'name')
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    results = [{
        'id': str(b.id),
        'name': b.name,
        'course_name': b.course.course_name if b.course else '',
        'student_count': BatchStudent.objects.filter(
            batch=b, tenant=tenant, is_active=True
        ).count(),
    } for b in qs]

    return JsonResponse({'batches': results})


@require_http_methods(["GET"])
@login_required
def batch_importable_students_api(request, batch_id):
    """Active students in a source batch who are not already active in the target batch."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    source_batch_id = request.GET.get('source_batch_id')
    if not source_batch_id:
        return JsonResponse({'error': 'source_batch_id is required'}, status=400)

    from core.models import BatchStudent
    already_in = BatchStudent.objects.filter(
        batch_id=batch_id, tenant=tenant, is_active=True
    ).values_list('student_id', flat=True)

    source_links = BatchStudent.objects.filter(
        batch_id=source_batch_id, tenant=tenant, is_active=True
    ).exclude(student_id__in=already_in).select_related('student')

    results = []
    for link in source_links:
        s = link.student
        if s.is_deleted:
            continue
        results.append({
            'id': str(s.id),
            'admission_no': s.admission_no,
            'full_name': ' '.join(filter(None, [s.first_name, s.middle_name, s.last_name])),
            'roll_number': link.roll_number or '',
        })

    results.sort(key=lambda r: r['full_name'].lower())
    return JsonResponse({'students': results, 'count': len(results)})


@require_http_methods(["POST"])
@login_required
def add_students_to_batch_api(request, batch_id):
    """Add students to a batch, or promote them from a source batch.

    When ``source_batch_id`` is supplied this is a *move* (manual promotion):
    each student is enrolled in the target batch and deactivated in the source
    batch, so they are never active in two classes at once. Academic records
    (exam scores, attendance, etc.) are tied to the Student, not the enrollment
    link, so they are preserved by the move. Without a source batch it behaves
    as a plain add.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        import json
        from django.db import transaction
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])
        source_batch_id = data.get('source_batch_id')

        if not student_ids:
            return JsonResponse({'error': 'No students selected', 'success': False}, status=400)

        from core.models import Batch, Student, BatchStudent

        # Verify batch exists
        batch = Batch.objects.get(id=batch_id, tenant=tenant)

        added_count = 0
        moved_count = 0
        errors = []

        # The whole promotion is one transaction so a student is never left
        # enrolled in both classes (or neither) if something fails midway.
        with transaction.atomic():
            for student_id in student_ids:
                try:
                    student = Student.objects.get(id=student_id, tenant=tenant)

                    # Check if student is already in this batch
                    existing = BatchStudent.objects.filter(
                        batch=batch,
                        student=student,
                        tenant=tenant,
                        is_active=True
                    ).exists()

                    if existing:
                        errors.append(f"{student.first_name} {student.last_name} is already in this batch")
                        continue

                    # The student's current enrollment in the source class (if a
                    # promotion) — used to carry the roll number and to remove
                    # them from the source after the move.
                    source_link = None
                    if source_batch_id and str(source_batch_id) != str(batch_id):
                        source_link = BatchStudent.objects.filter(
                            batch_id=source_batch_id, student=student,
                            tenant=tenant, is_active=True,
                        ).first()

                    # Create or reactivate batch student entry
                    batch_student, created = BatchStudent.objects.get_or_create(
                        batch=batch,
                        student=student,
                        tenant=tenant,
                        defaults={
                            'is_active': True
                        }
                    )

                    if not created and not batch_student.is_active:
                        batch_student.is_active = True

                    # Carry the roll number over from the source enrolment when
                    # the target doesn't already have one.
                    if source_link and source_link.roll_number and not batch_student.roll_number:
                        batch_student.roll_number = source_link.roll_number
                    batch_student.save()

                    # Remove the student from the source class (soft-deactivate,
                    # mirroring remove_student_from_batch_api) so the record is
                    # moved, not duplicated.
                    if source_link:
                        source_link.is_active = False
                        source_link.save(update_fields=['is_active'])
                        moved_count += 1

                    added_count += 1

                except Student.DoesNotExist:
                    errors.append(f"Student {student_id} not found")
                except Exception as e:
                    errors.append(f"Error adding student {student_id}: {str(e)}")

        if added_count > 0:
            if moved_count:
                message = f"Successfully promoted {moved_count} student(s) to {batch.name}"
                if added_count > moved_count:
                    message += f" and added {added_count - moved_count} more"
            else:
                message = f"Successfully added {added_count} student(s) to batch"
            if errors:
                message += f". {len(errors)} error(s) occurred."
            return JsonResponse({
                'success': True, 'message': message,
                'added': added_count, 'moved': moved_count, 'errors': errors,
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No students were added',
                'errors': errors
            }, status=400)

    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found', 'success': False}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
@login_required
def add_subject_to_batch_api(request, batch_id):
    """Add a subject to a batch"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        import json
        from django.db.models import Q
        from core.models import Batch, Subject, Employee

        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        code = (data.get('code') or '').strip()
        teacher_id = data.get('teacher_id')

        if not name:
            return JsonResponse({'error': 'Subject name is required', 'success': False}, status=400)

        batch = Batch.objects.get(id=batch_id, tenant=tenant)

        # Default a code from the name when none is supplied.
        if not code:
            code = name[:10].upper()

        # Subjects are per-batch: create a NEW subject on this batch. Guard against
        # adding one that already exists here (by name or code).
        if Subject.objects.filter(
            tenant=tenant, batch=batch, is_deleted=False
        ).filter(Q(name__iexact=name) | Q(code__iexact=code)).exists():
            return JsonResponse({
                'error': 'A subject with this name or code already exists on this batch',
                'success': False,
            }, status=400)

        subject = Subject.objects.create(
            tenant=tenant, batch=batch, name=name, code=code,
        )

        if teacher_id:
            teacher = Employee.objects.filter(id=teacher_id, tenant=tenant).first()
            if teacher:
                subject.employee = teacher
                subject.save(update_fields=['employee'])

        return JsonResponse({'success': True, 'message': 'Subject added to batch successfully'})

    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found', 'success': False}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)


# ====== BATCH DETAIL TAB PARTIALS (HTMX) ======

def _batch_students_context(tenant, batch):
    student_service = StudentService(tenant)
    students = student_service.get_students_by_batch(batch.id).order_by('first_name', 'last_name')
    return {
        'batch': batch,
        'batch_students': students,
        'student_count': students.count(),
    }


def _batch_subjects_context(tenant, batch):
    subjects = batch.subjects.filter(
        tenant=tenant, is_deleted=False
    ).select_related('employee')
    return {'batch': batch, 'subjects': subjects}


@require_http_methods(["GET"])
@login_required
def batch_students_partial(request, batch_id):
    """Render the Students tab body (used for HTMX partial refresh)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.get_batch_by_id(batch_id)
    except NotFoundException:
        return JsonResponse({'error': 'Batch not found'}, status=404)

    return render(request, 'core/htmx/batch/_students_tab.html',
                  _batch_students_context(tenant, batch))


@require_http_methods(["GET"])
@login_required
def batch_subjects_partial(request, batch_id):
    """Render the Subjects tab body (used for HTMX partial refresh)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.get_batch_by_id(batch_id)
    except NotFoundException:
        return JsonResponse({'error': 'Batch not found'}, status=404)

    return render(request, 'core/htmx/batch/_subjects_tab.html',
                  _batch_subjects_context(tenant, batch))


@require_http_methods(["POST"])
@login_required
def batch_subject_update_api(request, batch_id, subject_id):
    """Update a subject's assigned teacher (and optionally name) in a batch."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.get_batch_by_id(batch_id)

        fields = {}
        teacher_id = request.POST.get('teacher_id')
        # Explicit presence check so an empty value clears the teacher
        if 'teacher_id' in request.POST:
            fields['employee_id'] = teacher_id or None
        name = request.POST.get('name')
        if name:
            fields['name'] = name
        code = request.POST.get('code')
        if code:
            fields['code'] = code

        academic_service.update_subject(str(subject_id), user=request.user, **fields)

        return render(request, 'core/htmx/batch/_subjects_tab.html',
                      _batch_subjects_context(tenant, batch))

    except (NotFoundException, ValidationException, ServiceException) as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def batch_subject_remove_api(request, batch_id, subject_id):
    """Soft-delete a subject from a batch and re-render the Subjects tab."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.get_batch_by_id(batch_id)
        subject = academic_service.get_subject_by_id(str(subject_id))
        if str(subject.batch_id) != str(batch.id):
            return JsonResponse({'error': 'Subject not in this batch'}, status=404)
        subject.is_deleted = True
        subject.save(update_fields=['is_deleted'])

        return render(request, 'core/htmx/batch/_subjects_tab.html',
                      _batch_subjects_context(tenant, batch))

    except NotFoundException as e:
        return JsonResponse({'error': str(e)}, status=404)


@require_http_methods(["GET"])
@login_required
def batch_timetable_partial(request, batch_id):
    """Render the Timetable tab body."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.get_batch_by_id(batch_id)
    except NotFoundException:
        return JsonResponse({'error': 'Batch not found'}, status=404)

    timetable_entries = Timetable.objects.filter(
        tenant=tenant, batch=batch
    ).select_related('subject', 'employee', 'weekday', 'class_timing')

    return render(request, 'core/htmx/batch/_timetable_tab.html', {
        'batch': batch,
        'timetable_entries': timetable_entries,
    })


@require_http_methods(["GET"])
@login_required
def batch_attendance_partial(request, batch_id):
    """Render an inline attendance summary for the batch (lazy-loaded)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.get_batch_by_id(batch_id)
    except NotFoundException:
        return JsonResponse({'error': 'Batch not found'}, status=404)

    month = request.GET.get('month', date.today().strftime('%Y-%m'))
    summary = None
    error = None
    try:
        attendance_service = AttendanceService(tenant)
        summary = attendance_service.get_batch_monthly_summary(str(batch.id), month)
    except Exception as e:
        error = str(e)

    return render(request, 'core/htmx/batch/_attendance_tab.html', {
        'batch': batch,
        'month': month,
        'summary': summary,
        'attendance_error': error,
    })


@require_http_methods(["GET"])
@login_required
def batch_exams_partial(request, batch_id):
    """Render an inline list of exam groups/exams for the batch (lazy-loaded)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.get_batch_by_id(batch_id)
    except NotFoundException:
        return JsonResponse({'error': 'Batch not found'}, status=404)

    exam_groups = ExamGroup.objects.filter(
        tenant=tenant, batch=batch
    ).prefetch_related('exams__subject').order_by('-exam_date')

    return render(request, 'core/htmx/batch/_exams_tab.html', {
        'batch': batch,
        'exam_groups': exam_groups,
    })


@require_http_methods(["GET"])
@login_required
def batch_exam_type_config_api(request, batch_id):
    """Return the exam-type visibility configuration for a batch.

    When no configuration row exists yet, returns defaults (everything except
    activities enabled) with configured=False.
    """
    from .models import BatchExamTypeConfiguration
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
    config = BatchExamTypeConfiguration.for_batch(batch, tenant)

    if config is None:
        return JsonResponse({
            'batch_id': str(batch.id),
            'configured': False,
            'enable_traditional_exams': True,
            'enable_skills_assessment': True,
            'enable_activities': False,
            'enable_classwork': True,
            'enable_tests': True,
            'enable_homework': True,
            'enabled_custom_exam_types': [],
        })

    return JsonResponse({
        'batch_id': str(batch.id),
        'configured': True,
        'enable_traditional_exams': config.enable_traditional_exams,
        'enable_skills_assessment': config.enable_skills_assessment,
        'enable_activities': config.enable_activities,
        'enable_classwork': config.enable_classwork,
        'enable_tests': config.enable_tests,
        'enable_homework': config.enable_homework,
        'enabled_custom_exam_types': config.enabled_custom_exam_types,
    })


@require_http_methods(["POST"])
@login_required
def update_batch_exam_type_config_api(request, batch_id):
    """Create or update the exam-type visibility configuration for a batch.

    Body: JSON with any of enable_traditional_exams, enable_skills_assessment,
    enable_activities, enable_classwork, enable_tests, enable_homework (bool)
    and enabled_custom_exam_types (list of strings). Omitted fields keep their
    current (or default) values.
    """
    from .models import BatchExamTypeConfiguration
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    bool_fields = [
        'enable_traditional_exams', 'enable_skills_assessment', 'enable_activities',
        'enable_classwork', 'enable_tests', 'enable_homework',
    ]
    updates = {f: bool(data[f]) for f in bool_fields if f in data}
    if 'enabled_custom_exam_types' in data:
        custom = data['enabled_custom_exam_types']
        if not isinstance(custom, list) or not all(isinstance(x, str) for x in custom):
            return JsonResponse(
                {'error': 'enabled_custom_exam_types must be a list of strings'}, status=400
            )
        updates['enabled_custom_exam_types'] = custom

    config, created = BatchExamTypeConfiguration.objects.update_or_create(
        batch=batch, tenant=tenant, defaults=updates,
    )

    return JsonResponse({
        'success': True,
        'created': created,
        'batch_id': str(batch.id),
        'enable_traditional_exams': config.enable_traditional_exams,
        'enable_skills_assessment': config.enable_skills_assessment,
        'enable_activities': config.enable_activities,
        'enable_classwork': config.enable_classwork,
        'enable_tests': config.enable_tests,
        'enable_homework': config.enable_homework,
        'enabled_custom_exam_types': config.enabled_custom_exam_types,
    })


@require_http_methods(["GET"])
@login_required
def batch_class_teachers_api(request, batch_id):
    """List candidate teachers, flagging those already assigned to the batch."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.get_batch_by_id(batch_id)
    except NotFoundException:
        return JsonResponse({'error': 'Batch not found'}, status=404)

    assigned = list(batch.class_teachers.all())
    assigned_ids = {str(e.id) for e in assigned}

    from .services.employee_service import EmployeeService
    employees = list(EmployeeService(tenant).get_teaching_staff()[:200])

    # Make sure currently-assigned teachers always appear, even if inactive.
    seen = {str(e.id) for e in employees}
    for e in assigned:
        if str(e.id) not in seen:
            employees.append(e)

    results = [{
        'id': str(e.id),
        'full_name': f"{e.first_name} {e.last_name}",
        'assigned': str(e.id) in assigned_ids,
    } for e in employees]
    results.sort(key=lambda r: r['full_name'].lower())

    return JsonResponse({'teachers': results})


@require_http_methods(["POST"])
@login_required
def batch_assign_teachers_api(request, batch_id):
    """Set the class teachers for a batch and return the refreshed overview card."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    import json
    try:
        data = json.loads(request.body or '{}')
        teacher_ids = data.get('teacher_ids', [])
    except (ValueError, TypeError):
        teacher_ids = request.POST.getlist('teacher_ids')

    academic_service = AcademicService(tenant)
    try:
        batch = academic_service.set_class_teachers(str(batch_id), teacher_ids, user=request.user)
    except (NotFoundException, ValidationException, ServiceException) as e:
        return JsonResponse({'error': str(e)}, status=400)

    return render(request, 'core/htmx/batch/_overview_card.html', {'batch': batch})


@require_http_methods(["GET"])
@login_required
def finance_summary_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        finance_service = FinanceService(tenant)
        summary = finance_service.get_financial_summary()
        
        return JsonResponse({
            'total_income': float(summary.get('total_income', 0)),
            'total_expenses': float(summary.get('total_expenses', 0)),
            'pending_fees': float(summary.get('pending_fees', 0)),
            'collected_fees': float(summary.get('collected_fees', 0))
        })
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def quick_stats_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        student_service = StudentService(tenant)
        academic_service = AcademicService(tenant)
        attendance_service = AttendanceService(tenant)
        
        today_attendance = attendance_service.get_daily_attendance_summary(date.today())
        
        return JsonResponse({
            'active_students': student_service.count(is_active=True),
            'total_batches': academic_service.count_batches(active_only=True),
            'present_today': today_attendance.get('present_count', 0),
            'absent_today': today_attendance.get('absent_count', 0)
        })
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


class LowBandwidthMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'minimal_css': True,
            'compress_images': True,
            'defer_js': True
        })
        return context


# ====== ADMISSION VIEWS ======

class AdmissionApplicationView(HTMXResponseMixin, TemplateView):
    template_name = 'core/admission/application.html'
    htmx_template_name = 'core/htmx/admission_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Make authentication optional for public admissions
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        context['form'] = AdmissionApplicationForm(school=tenant)
        context['back_url'] = self.request.GET.get('back', reverse('core:admission_list_api'))
        context['crumbs'] = [
            {'label': 'Admission', 'url': reverse('core:admission_list_api')},
            {'label': 'New Application'},
        ]
        return context
    
    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            messages.error(request, 'School not found')
            return self.get(request, *args, **kwargs)
        
        form = AdmissionApplicationForm(request.POST, school=tenant)
        
        if form.is_valid():
            try:
                admission_service = AdmissionService(tenant)
                application = admission_service.create_application(
                    first_name=form.cleaned_data['first_name'],
                    middle_name=form.cleaned_data.get('middle_name'),
                    last_name=form.cleaned_data['last_name'],
                    date_of_birth=form.cleaned_data['date_of_birth'],
                    gender=form.cleaned_data['gender'],
                    course_id=str(form.cleaned_data['course_applied'].id),
                    guardian_name=form.cleaned_data['guardian_name'],
                    guardian_phone=form.cleaned_data['guardian_phone'],
                    guardian_email=form.cleaned_data.get('guardian_email'),
                    address=form.cleaned_data['address']
                )
                
                messages.success(
                    request, 
                    f'Application submitted successfully! Your application number is: {application.application_number}'
                )
                
                if self.is_htmx:
                    return JsonResponse({
                        'success': True,
                        'message': f'Application submitted! Application number: {application.application_number}',
                        'redirect': reverse('core:admission_success', kwargs={'app_number': application.application_number})
                    })
                
                return render(request, 'core/admission/success.html', {
                    'application': application
                })
                
            except ServiceException as e:
                messages.error(request, f'Error submitting application: {str(e)}')
                form.add_error(None, str(e))
        
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return self.render_to_response(context)


class AdmissionSuccessView(HTMXResponseMixin, TemplateView):
    template_name = 'core/admission/success.html'
    htmx_template_name = 'core/htmx/admission_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app_number = kwargs.get('app_number')
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant and app_number:
            try:
                admission_service = AdmissionService(tenant)
                application = admission_service.get_application_by_number(app_number)
                context['application'] = application
            except NotFoundException:
                context['error'] = 'Application not found'
        
        return context


class AdmissionListView(HTMXResponseMixin, ListView):
    template_name = 'core/admission/list.html'
    htmx_template_name = 'core/htmx/admission_list_content.html'
    context_object_name = 'applications'
    paginate_by = 20
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        
        admission_service = AdmissionService(tenant)
        
        # Get filter parameters
        status = self.request.GET.get('status', '')
        search_query = self.request.GET.get('query', '')
        
        if search_query:
            queryset = admission_service.search_applications(
                query=search_query,
                status=status if status else None
            )
        else:
            if status:
                if status == 'pending':
                    queryset = admission_service.get_pending_applications()
                elif status == 'approved':
                    queryset = admission_service.get_approved_applications()
                elif status == 'rejected':
                    queryset = admission_service.get_rejected_applications()
                else:
                    queryset = admission_service.get_all()
            else:
                queryset = admission_service.get_all().order_by('-application_date')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        # Add search form
        context['search_form'] = AdmissionSearchForm(
            self.request.GET,
            school=tenant
        )
        
        # Add statistics
        if tenant:
            admission_service = AdmissionService(tenant)
            stats = admission_service.get_admission_statistics()
            context['stats'] = stats
            context['stat_cards'] = [
                {'label': 'Total Applications', 'value': stats.get('total_applications', 0), 'icon': 'fa-file-alt', 'variant': 'primary'},
                {'label': 'Pending Review', 'value': stats.get('pending_applications', 0), 'icon': 'fa-clock', 'variant': 'warning'},
                {'label': 'Approved', 'value': stats.get('approved_applications', 0), 'icon': 'fa-check-circle', 'variant': 'success'},
                {'label': 'Rejected', 'value': stats.get('rejected_applications', 0), 'icon': 'fa-times-circle', 'variant': 'danger'},
            ]

        context['header_actions'] = [
            {'label': 'New Application', 'variant': 'primary', 'icon': 'fa-plus', 'url': reverse('core:admission_apply')},
        ]
        context['apply_url'] = reverse('core:admission_apply')
        context['table_columns'] = [
            'No.', 'Application #', 'Applicant Name', 'Course Applied',
            'Application Date', 'Status', 'Guardian Contact', 'Actions',
        ]
        context['quick_review_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Confirm', 'variant': 'primary', 'type': 'submit', 'attrs': 'id="confirmAction"'},
        ]
        context['admission_status_filters'] = [
            {
                'name': 'status',
                'label': 'Status',
                'value': self.request.GET.get('status', ''),
                'options': [
                    {'value': value, 'label': label}
                    for value, label in AdmissionSearchForm.base_fields['status'].choices
                ],
            },
        ]
        context['admission_list_clear_url'] = (
            reverse('core:admission_list')
            if self.request.GET.get('query') or self.request.GET.get('status')
            else ''
        )

        return context


class AdmissionDetailView(HTMXResponseMixin, DetailView):
    template_name = 'core/admission/detail.html'
    htmx_template_name = 'core/htmx/admission_detail_content.html'
    context_object_name = 'application'
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        tenant = getattr(self.request, 'tenant', None)
        app_id = self.kwargs.get('pk')
        
        if not tenant or not app_id:
            raise Http404("Application not found")
        
        try:
            from core.services.extended_admission_service import ExtendedAdmissionService
            admission_service = ExtendedAdmissionService(tenant)
            return admission_service.get_by_id(app_id)
        except NotFoundException:
            raise Http404("Application not found")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import AdmissionDocument, BatchStudent
        context['documents'] = self.object.documents.all().order_by('document_type')
        context['back_url'] = self.request.META.get('HTTP_REFERER', '')
        context['approve_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Approve', 'variant': 'primary', 'attrs': f'onclick="confirmApprove(\'{self.object.id}\')"'},
        ]
        context['reject_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Reject', 'variant': 'danger', 'attrs': f'onclick="confirmReject(\'{self.object.id}\')"'},
        ]
        if self.object.admitted_student_id:
            context['current_batches'] = (
                BatchStudent.objects
                .filter(student=self.object.admitted_student)
                .select_related('batch', 'batch__course')
                .order_by('batch__name')
            )
        else:
            context['current_batches'] = []
        return context


class AdmissionReviewView(HTMXResponseMixin, TemplateView):
    template_name = 'core/admission/review.html'
    htmx_template_name = 'core/htmx/admission_review_content.html'
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        app_id = kwargs.get('pk')
        
        if not tenant or not app_id:
            return JsonResponse({'error': 'Invalid request'}, status=400)
        
        form = AdmissionReviewForm(request.POST)
        
        if form.is_valid():
            try:
                admission_service = AdmissionService(tenant)
                action = form.cleaned_data['action']
                remarks = form.cleaned_data['remarks']
                
                if action == 'approve':
                    admission_no = form.cleaned_data.get('admission_no')
                    result = admission_service.approve_application(
                        application_id=app_id,
                        admission_no=admission_no,
                        remarks=remarks,
                        user=request.user
                    )
                    
                    message = f'Application approved! Student enrolled with admission number: {result["admission_no"]}'
                    
                elif action == 'reject':
                    admission_service.reject_application(
                        application_id=app_id,
                        reason=remarks,
                        user=request.user
                    )
                    
                    message = 'Application rejected successfully'
                
                if self.is_htmx:
                    return JsonResponse({
                        'success': True,
                        'message': message,
                        'redirect': reverse('core:admission_list')
                    })
                
                messages.success(request, message)
                return JsonResponse({
                    'success': True,
                    'redirect': reverse('core:admission_list')
                })
                
            except ServiceException as e:
                if self.is_htmx:
                    return JsonResponse({
                        'success': False,
                        'error': str(e)
                    })
                messages.error(request, f'Error processing application: {str(e)}')
        
        # Return form with errors
        context = {'form': form, 'app_id': app_id}
        return self.render_to_response(context)


@require_http_methods(["GET"])
def admission_status_api(request, app_number):
    """Public API to check admission application status."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        # Try extended admission service first (new system)
        from core.services.extended_admission_service import ExtendedAdmissionService
        admission_service = ExtendedAdmissionService(tenant)
        application = admission_service.get_application_by_number(app_number)
        
        return JsonResponse({
            'application_number': application.application_number,
            'applicant_name': f"{application.first_name} {application.last_name}",
            'status': application.status.title(),
            'application_date': application.application_date.strftime('%d %B %Y'),
            'course_applied': application.course_applied.course_name,
            'remarks': application.remarks or ''
        })
    
    except NotFoundException:
        return JsonResponse({'error': 'Application not found'}, status=404)
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def generate_admission_number_api(request):
    """Generate a unique admission number based on batch selection."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        from django.utils import timezone
        import random
        import string
        
        batch_id = request.GET.get('batchSelect')
        current_year = timezone.now().year
        
        if batch_id:
            # Get batch information for contextualized admission number
            try:
                batch = Batch.objects.get(id=batch_id, tenant=tenant)
                # Generate admission number with batch prefix
                batch_prefix = batch.name[:3].upper()
                year_suffix = str(current_year)[-2:]
                
                # Find the next available sequential number for this batch
                base_pattern = f"{batch_prefix}{year_suffix}"
                
                # Get all existing admission numbers with this pattern
                existing_numbers = Student.objects.filter(
                    tenant=tenant,
                    admission_no__startswith=base_pattern
                ).values_list('admission_no', flat=True)
                
                # Extract the numeric parts and find the next available number
                used_numbers = set()
                for admission_no in existing_numbers:
                    if len(admission_no) >= len(base_pattern) + 3:  # Ensure it has the 3-digit suffix
                        suffix = admission_no[len(base_pattern):]
                        if suffix.isdigit():
                            used_numbers.add(int(suffix))
                
                # Find the next available number
                next_number = 1
                while next_number in used_numbers:
                    next_number += 1
                
                admission_number = f"{base_pattern}{str(next_number).zfill(3)}"
                
            except Batch.DoesNotExist:
                # Generate generic admission number
                year_suffix = str(current_year)[-2:]
                random_digits = ''.join(random.choices(string.digits, k=4))
                admission_number = f"ADM{year_suffix}{random_digits}"
        else:
            # Generate generic admission number
            year_suffix = str(current_year)[-2:]
            # Generate generic admission number with uniqueness check
            while True:
                random_digits = ''.join(random.choices(string.digits, k=4))
                admission_number = f"ADM{year_suffix}{random_digits}"
                if not Student.objects.filter(tenant=tenant, admission_no=admission_number).exists():
                    break
        
        # Final uniqueness check (extra safety)
        if Student.objects.filter(tenant=tenant, admission_no=admission_number).exists():
            return JsonResponse({
                'success': False,
                'error': 'Unable to generate unique admission number. Please try again.'
            }, status=500)
        
        # Return JSON response for easier parsing
        return JsonResponse({
            'success': True,
            'admission_number': admission_number
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def validate_admission_number_api(request):
    """Validate if an admission number is unique."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    admission_number = request.GET.get('admission_number', '').strip()
    
    if not admission_number:
        return HttpResponse('<small class="text-muted">Enter an admission number</small>')
    
    try:
        # Check if admission number already exists
        exists = Student.objects.filter(
            tenant=tenant,
            admission_no=admission_number
        ).exists()
        
        if exists:
            return HttpResponse('<small class="text-danger"><i class="fas fa-times-circle"></i> This admission number is already in use</small>')
        else:
            return HttpResponse('<small class="text-success"><i class="fas fa-check-circle"></i> Admission number is available</small>')
            
    except Exception as e:
        return HttpResponse('<small class="text-warning"><i class="fas fa-exclamation-triangle"></i> Unable to validate admission number</small>')


@require_http_methods(["GET"])
def active_batches_api(request):
    """Get list of active batches for batch assignment."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
        qs = Batch.objects.filter(tenant=tenant, is_active=True).select_related('course').order_by('name')
        if active_year:
            qs = qs.filter(academic_year=active_year)
        course_id = request.GET.get('course_id')
        if course_id:
            qs = qs.filter(course_id=course_id)

        batch_data = [
            {
                'id': str(b.id),
                'name': b.name,
                'course_name': b.course.course_name,
                'course_code': b.course.code,
            }
            for b in qs
        ]
        return JsonResponse({'batches': batch_data})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["DELETE"])
def admission_delete_api(request, pk):
    tenant = getattr(request, 'tenant', None)

    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)

    logger.debug("admission_delete_api for tenant %s (%s)", tenant.id, tenant.name)

    try:
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import NotFoundException

        admission_service = ExtendedAdmissionService(tenant)
        application = admission_service.get_by_id(pk)

        application.delete()

        return JsonResponse({
            'success': True,
            'message': 'Application deleted successfully'
        })

    except NotFoundException:
        return JsonResponse({'error': 'Application not found', 'success': False}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
def admission_admit_api(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)

    try:
        import json
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import NotFoundException
        from django.utils import timezone

        data = json.loads(request.body)
        batch_id = data.get('batch_id')
        admission_number = (data.get('admission_number') or '').strip()
        admission_date_str = data.get('admission_date')
        remarks = data.get('remarks', '')

        if not batch_id:
            return JsonResponse({'error': 'Batch is required', 'success': False}, status=400)

        admission_service = ExtendedAdmissionService(tenant)
        application = admission_service.get_by_id(pk)

        if not application.first_name or not application.last_name:
            return JsonResponse({
                'error': 'Application is missing student name. Please complete the application before admitting.',
                'success': False
            }, status=400)

        if not application.date_of_birth:
            return JsonResponse({
                'error': 'Application is missing date of birth. Please complete the application before admitting.',
                'success': False
            }, status=400)

        from .models import Student, Batch, BatchStudent

        batch = Batch.objects.get(id=batch_id, tenant=tenant)

        # Auto-generate admission number if not provided
        if not admission_number:
            batch_prefix = batch.name[:3].upper()
            year_suffix = str(timezone.now().year)[-2:]
            base_pattern = f"{batch_prefix}{year_suffix}"
            existing = set(
                Student.objects.filter(tenant=tenant, admission_no__startswith=base_pattern)
                .values_list('admission_no', flat=True)
            )
            next_num = 1
            while True:
                candidate = f"{base_pattern}{str(next_num).zfill(3)}"
                if candidate not in existing:
                    admission_number = candidate
                    break
                next_num += 1

        # Check uniqueness of the provided/generated number
        if Student.objects.filter(tenant=tenant, admission_no=admission_number).exists():
            return JsonResponse({
                'error': f'Admission number "{admission_number}" is already in use. Please generate a new number.',
                'success': False
            }, status=400)

        # Parse admission date
        admission_date = timezone.now().date()
        if admission_date_str:
            from datetime import date as date_type
            try:
                admission_date = date_type.fromisoformat(admission_date_str)
            except ValueError:
                pass

        gender = application.gender if application.gender in ('male', 'female', 'other') else 'other'

        from django.db import IntegrityError
        try:
            student = Student.objects.create(
                tenant=tenant,
                admission_no=admission_number,
                first_name=application.first_name,
                middle_name=application.middle_name or '',
                last_name=application.last_name,
                date_of_birth=application.date_of_birth,
                gender=gender,
                email=application.email or '',
                phone1=application.mobile or '',
                admission_date=admission_date,
                is_active=True,
            )
        except IntegrityError:
            return JsonResponse({
                'error': f'Admission number "{admission_number}" is already in use. Please generate a new number.',
                'success': False
            }, status=400)

        BatchStudent.objects.create(
            tenant=tenant,
            batch=batch,
            student=student,
            is_active=True,
        )

        application.status = 'admitted'
        application.admitted_student = student
        if remarks:
            application.remarks = remarks
        application.save()

        # The student is committed at this point (view is not atomic), so a
        # parent-account failure must degrade to "skipped", never block admission.
        parent_account = {
            'status': 'skipped',
            'reason': 'No guardian details on application',
        }
        try:
            from core.services.portal_account_service import PortalAccountService
            parent_account = PortalAccountService(tenant).provision_parent_account_from_application(
                application, student
            )
        except Exception as e:
            logger.error(
                f"Parent account provisioning failed for application {pk}: {e}",
                exc_info=True,
            )
            parent_account = {
                'status': 'skipped',
                'reason': 'Parent account creation failed; create it manually from the Users page.',
            }

        return JsonResponse({
            'success': True,
            'message': f'Student admitted and assigned to {batch.name} successfully',
            'student_id': str(student.id),
            'admission_number': student.admission_no,
            'parent_account': parent_account,
        })

    except NotFoundException:
        return JsonResponse({'error': 'Application not found', 'success': False}, status=404)
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found', 'success': False}, status=404)
    except Exception as e:
        logger.error(f"admission_admit_api error: {e}", exc_info=True)
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
def admission_assign_batch_api(request, pk):
    """Assign or change the batch for an already-admitted student."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)

    try:
        import json
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import NotFoundException
        from .models import Batch, BatchStudent

        data = json.loads(request.body)
        batch_id = data.get('batch_id')

        if not batch_id:
            return JsonResponse({'error': 'Batch is required', 'success': False}, status=400)

        admission_service = ExtendedAdmissionService(tenant)
        application = admission_service.get_by_id(pk)

        if not application.admitted_student_id:
            return JsonResponse({'error': 'No student has been admitted for this application yet.', 'success': False}, status=400)

        student = application.admitted_student
        batch = Batch.objects.get(id=batch_id, tenant=tenant)

        BatchStudent.objects.get_or_create(
            tenant=tenant,
            batch=batch,
            student=student,
            defaults={'is_active': True},
        )

        return JsonResponse({
            'success': True,
            'message': f'{student.full_name} assigned to {batch.name}.',
            'batch_name': batch.name,
        })

    except NotFoundException:
        return JsonResponse({'error': 'Application not found', 'success': False}, status=404)
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found', 'success': False}, status=404)
    except Exception as e:
        logger.error(f"admission_assign_batch_api error: {e}", exc_info=True)
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
def admission_duplicate_api(request, pk):
    """Duplicate an admission application."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import NotFoundException
        import uuid
        
        admission_service = ExtendedAdmissionService(tenant)
        original_application = admission_service.get_by_id(pk)
        
        # Create a duplicate with modified data
        duplicate_data = {
            'tenant': tenant,
            'application_number': f"DUP-{uuid.uuid4().hex[:8].upper()}",
            'first_name': original_application.first_name,
            'last_name': original_application.last_name,
            'date_of_birth': original_application.date_of_birth,
            'gender': original_application.gender,
            'course_applied': original_application.course_applied,
            'status': 'draft',
            'application_date': timezone.now().date()
        }
        
        # Copy other fields if they exist
        for field in ['middle_name', 'mobile', 'email', 'guardian1_first_name', 'guardian1_last_name', 'guardian1_mobile']:
            if hasattr(original_application, field):
                value = getattr(original_application, field)
                if value:
                    duplicate_data[field] = value
        
        # Create the duplicate
        duplicate = original_application.__class__.objects.create(**duplicate_data)
        
        return JsonResponse({
            'success': True,
            'message': 'Application duplicated successfully',
            'duplicate_id': str(duplicate.id),
            'application_number': duplicate.application_number
        })
        
    except NotFoundException:
        return JsonResponse({'error': 'Application not found', 'success': False}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["GET"])
def admission_export_pdf(request, pk):
    """Export admission application as PDF."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import NotFoundException
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        
        admission_service = ExtendedAdmissionService(tenant)
        application = admission_service.get_by_id(pk)
        
        # For now, return a simple HTML response that can be converted to PDF
        # In a full implementation, you'd use a library like WeasyPrint or ReportLab
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Application {application.application_number}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .field {{ margin-bottom: 10px; }}
                .label {{ font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Admission Application</h1>
                <h3>Application #: {application.application_number}</h3>
            </div>
            
            <div class="field">
                <span class="label">Applicant Name:</span> 
                {application.first_name} {application.last_name}
            </div>
            <div class="field">
                <span class="label">Date of Birth:</span> 
                {application.date_of_birth}
            </div>
            <div class="field">
                <span class="label">Gender:</span> 
                {application.get_gender_display()}
            </div>
            <div class="field">
                <span class="label">Course Applied:</span> 
                {application.course_applied.course_name}
            </div>
            <div class="field">
                <span class="label">Application Date:</span> 
                {application.application_date}
            </div>
            <div class="field">
                <span class="label">Status:</span> 
                {application.status.title()}
            </div>
        </body>
        </html>
        """
        
        response = HttpResponse(html_content, content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="application_{application.application_number}.html"'
        return response
        
    except NotFoundException:
        return JsonResponse({'error': 'Application not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def admission_approve_api(request, pk):
    """Approve an admission application."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        import json
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import NotFoundException
        
        data = json.loads(request.body)
        remarks = data.get('remarks', '')
        admission_no = data.get('admission_no', '')
        
        admission_service = ExtendedAdmissionService(tenant)
        application = admission_service.get_by_id(pk)
        
        # Check if application can be approved
        if application.status not in ['submitted', 'under_review']:
            return JsonResponse({
                'error': f'Cannot approve application with status "{application.status}"',
                'success': False
            }, status=400)
        
        # Update application status
        application.status = 'approved'
        application.remarks = remarks
        application.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Application approved successfully',
            'new_status': 'approved'
        })
        
    except NotFoundException:
        return JsonResponse({'error': 'Application not found', 'success': False}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
def admission_reject_api(request, pk):
    """Reject an admission application."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        import json
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import NotFoundException
        
        data = json.loads(request.body)
        remarks = data.get('remarks', '')
        
        if not remarks.strip():
            return JsonResponse({
                'error': 'Reason for rejection is required',
                'success': False
            }, status=400)
        
        admission_service = ExtendedAdmissionService(tenant)
        application = admission_service.get_by_id(pk)
        
        # Check if application can be rejected
        if application.status not in ['submitted', 'under_review']:
            return JsonResponse({
                'error': f'Cannot reject application with status "{application.status}"',
                'success': False
            }, status=400)
        
        # Update application status
        application.status = 'rejected'
        application.remarks = remarks
        application.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Application rejected successfully',
            'new_status': 'rejected'
        })
        
    except NotFoundException:
        return JsonResponse({'error': 'Application not found', 'success': False}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)


# ====== ACADEMIC MANAGEMENT VIEWS ======

class CourseListView(HTMXResponseMixin, ListView):
    template_name = 'core/academic/courses.html'
    htmx_template_name = 'core/htmx/course_list_content.html'
    context_object_name = 'courses'
    paginate_by = 15
    
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        
        academic_service = AcademicService(tenant)
        
        search_query = self.request.GET.get('search', '')
        if search_query:
            return academic_service.search_courses(search_query)
        else:
            return academic_service.get_active_courses()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        count = context['page_obj'].paginator.count if context.get('page_obj') else len(context.get('courses') or [])
        context['header_description'] = f"{count} course{'s' if count != 1 else ''} in the system"
        context['header_actions'] = [
            {'label': 'Export', 'variant': 'outline', 'icon': 'fa-download', 'size': 'sm', 'attrs': 'onclick="exportCourses()"'},
            {'label': 'Add Course', 'variant': 'primary', 'icon': 'fa-plus', 'size': 'sm', 'attrs': 'onclick="openCourseModal()"'},
        ]
        context['courses_list_url'] = reverse('core:course_list') if self.request.GET.get('search') else ''
        return context


class SubjectListView(HTMXResponseMixin, ListView):
    template_name = 'core/academic/subjects.html'
    htmx_template_name = 'core/htmx/subject_list_content.html'
    context_object_name = 'subjects'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        
        academic_service = AcademicService(tenant)
        
        batch_filter = self.request.GET.get('batch')
        search_query = self.request.GET.get('search', '')
        
        return academic_service.search_subjects(
            query=search_query,
            batch_id=batch_filter
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            academic_service = AcademicService(tenant)
            context.update({
                'selected_batch': self.request.GET.get('batch'),
                'batches': academic_service.get_active_batches()
            })
        
        return context


class TimetableListView(HTMXResponseMixin, ListView):
    template_name = 'core/academic/timetables.html'
    htmx_template_name = 'core/htmx/timetable_list_content.html'
    context_object_name = 'timetables'
    paginate_by = 30
    
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        
        timetable_service = TimetableService(tenant)
        
        batch_filter = self.request.GET.get('batch')
        weekday_filter = self.request.GET.get('weekday')
        
        return timetable_service.get_timetables(
            batch_id=batch_filter,
            weekday_id=weekday_filter,
            include_related=True
        ).order_by('weekday__day_of_week', 'class_timing__start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            academic_service = AcademicService(tenant)
            timetable_service = TimetableService(tenant)
            
            context.update({
                'selected_batch': self.request.GET.get('batch'),
                'selected_weekday': self.request.GET.get('weekday'),
                'batches': academic_service.get_active_batches(),
                'weekdays': timetable_service.get_weekdays()
            })
        
        return context


class AttendanceListView(HTMXResponseMixin, ListView):
    template_name = 'core/academic/attendance.html'
    htmx_template_name = 'core/htmx/attendance_list_content.html'
    context_object_name = 'attendance_records'
    paginate_by = 25
    
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        
        attendance_service = AttendanceService(tenant)
        
        batch_filter = self.request.GET.get('batch')
        search_query = self.request.GET.get('search', '')
        
        start_date = None
        end_date = None
        date_filter = self.request.GET.get('date')
        if date_filter:
            try:
                filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                start_date = filter_date
                end_date = filter_date
            except ValueError:
                pass
        
        return attendance_service.search_attendance(
            query=search_query if search_query else None,
            batch_id=batch_filter,
            start_date=start_date,
            end_date=end_date
        ).order_by('-month_date', 'student__admission_no')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            academic_service = AcademicService(tenant)
            context.update({
                'selected_batch': self.request.GET.get('batch'),
                'selected_date': self.request.GET.get('date'),
                'batches': academic_service.get_active_batches()
            })
        
        return context


class AcademicYearListView(HTMXResponseMixin, ListView):
    template_name = 'core/academic/academic_years.html'
    htmx_template_name = 'core/htmx/academic_year_list_content.html'
    context_object_name = 'academic_years'
    paginate_by = 15
    
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        
        academic_service = AcademicService(tenant)
        queryset = academic_service.get_all_academic_years()
        
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        
        return queryset.order_by('-start_date')


# ====== ACADEMIC API VIEWS ======

@require_http_methods(["GET"])
def courses_api(request):
    """API endpoint to get courses list"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        academic_service = AcademicService(tenant)
        courses = academic_service.get_active_courses()
        
        search_query = request.GET.get('search', '')
        if search_query:
            courses = courses.filter(
                Q(course_name__icontains=search_query) |
                Q(code__icontains=search_query)
            )
        
        results = [{
            'id': str(course.id),
            'name': course.course_name,
            'code': course.code,
            'section_name': course.section_name or '',
            'batch_count': course.batches.filter(is_active=True, is_deleted=False).count()
        } for course in courses[:50]]
        
        return JsonResponse({
            'courses': results,
            'count': len(results)
        })
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def subjects_api(request):
    """API endpoint to get subjects list"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        academic_service = AcademicService(tenant)
        batch_id = request.GET.get('batch_id')
        search_query = request.GET.get('search', '')
        
        queryset = academic_service.search_subjects(
            query=search_query if search_query else None,
            batch_id=batch_id
        )
        
        results = [{
            'id': str(subject.id),
            'name': subject.name,
            'code': subject.code,
            'batch_name': subject.batch.name,
            'batch_id': str(subject.batch.id)
        } for subject in queryset.select_related('batch')[:1000]]

        return JsonResponse({
            'subjects': results,
            'count': len(results)
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def subjects_by_class_api(request, class_id):
    """API endpoint to get subjects for a specific class/course"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        from .models import Subject, Course, CourseSubject

        # Get the course/class
        try:
            course = Course.objects.get(id=class_id, tenant=tenant, is_deleted=False)
        except Course.DoesNotExist:
            return JsonResponse({'error': 'Class not found'}, status=404)

        # Get subjects from CourseSubject relationship first (course template)
        course_subjects = CourseSubject.objects.filter(
            course=course,
            tenant=tenant,
            is_active=True
        ).select_related('subject').order_by('subject__name')

        subjects_data = [{
            'id': str(cs.subject.id),
            'name': cs.subject.name,
            'code': cs.subject.code or ''
        } for cs in course_subjects]

        return JsonResponse({
            'success': True,
            'subjects': subjects_data,
            'class_name': course.course_name,
            'count': len(subjects_data)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["GET"])
def timetable_api(request):
    """API endpoint to get timetable for a batch and day"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        batch_id = request.GET.get('batch_id')
        weekday_id = request.GET.get('weekday_id')
        include_breaks = request.GET.get('include_breaks', 'false').lower() == 'true'

        if not batch_id:
            return JsonResponse({'error': 'Batch ID required'}, status=400)

        timetable_service = TimetableService(tenant)
        queryset = timetable_service.get_timetables(
            batch_id=batch_id,
            weekday_id=weekday_id,
            include_related=True
        )

        timetable_data = {}
        for entry in queryset:
            day_name = entry.weekday.weekday
            if day_name not in timetable_data:
                timetable_data[day_name] = []

            timetable_data[day_name].append({
                'id': str(entry.id),
                'time_slot': f"{entry.class_timing.start_time.strftime('%H:%M')} - {entry.class_timing.end_time.strftime('%H:%M')}",
                'subject': entry.subject.name if entry.subject else '',
                'employee': f"{entry.employee.first_name} {entry.employee.last_name}" if entry.employee else '',
                'timing_name': entry.class_timing.name,
                'is_break': entry.class_timing.is_break
            })

        # If requested, add break ClassTiming rows (appears on all valid weekdays)
        if include_breaks:
            from core.models import ClassTiming
            breaks = ClassTiming.objects.filter(
                tenant=tenant,
                batch_id=batch_id,
                is_break=True,
                is_deleted=False
            ).select_related('batch', 'batch__course')

            valid_weekdays = Weekday.objects.filter(tenant=tenant).order_by('day_of_week')

            for br in breaks:
                # Add this break to all weekdays
                for wd in valid_weekdays:
                    day_name = wd.weekday
                    if day_name not in timetable_data:
                        timetable_data[day_name] = []

                    timetable_data[day_name].append({
                        'id': str(br.id),
                        'time_slot': f"{br.start_time.strftime('%H:%M')} - {br.end_time.strftime('%H:%M')}",
                        'subject': '',
                        'employee': '',
                        'timing_name': br.name,
                        'is_break': True
                    })

        # Sort entries by start time for each day
        for day in timetable_data:
            timetable_data[day].sort(key=lambda x: x['time_slot'])

        return JsonResponse({
            'timetable': timetable_data,
            'batch_id': batch_id
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def timetable_crud_api(request, timetable_id=None):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        import json
        from core.models import Timetable, Batch, Weekday, ClassTiming, Subject

        if request.method == 'GET':
            # Handle existing GET logic from timetable_api
            batch_id = request.GET.get('batch_id')
            weekday_id = request.GET.get('weekday_id')
            include_breaks = request.GET.get('include_breaks', 'false').lower() == 'true'

            if not batch_id:
                return JsonResponse({'error': 'Batch ID required'}, status=400)

            timetable_service = TimetableService(tenant)
            queryset = timetable_service.get_timetables(
                batch_id=batch_id,
                weekday_id=weekday_id,
                include_related=True
            )

            timetable_data = {}
            for entry in queryset:
                day_name = entry.weekday.weekday
                if day_name not in timetable_data:
                    timetable_data[day_name] = []

                timetable_data[day_name].append({
                    'id': str(entry.id),
                    'time_slot': f"{entry.class_timing.start_time.strftime('%H:%M')} - {entry.class_timing.end_time.strftime('%H:%M')}",
                    'subject': entry.subject.name if entry.subject else '',
                    'employee': f"{entry.employee.first_name} {entry.employee.last_name}" if entry.employee else '',
                    'timing_name': entry.class_timing.name,
                    'is_break': entry.class_timing.is_break
                })

            # If requested, add break ClassTiming rows
            if include_breaks:
                from core.models import ClassTiming
                breaks = ClassTiming.objects.filter(
                    tenant=tenant,
                    batch_id=batch_id,
                    is_break=True,
                    is_deleted=False
                ).select_related('batch', 'batch__course')

                valid_weekdays = Weekday.objects.filter(tenant=tenant).order_by('day_of_week')

                for br in breaks:
                    for wd in valid_weekdays:
                        day_name = wd.weekday
                        if day_name not in timetable_data:
                            timetable_data[day_name] = []

                        timetable_data[day_name].append({
                            'id': str(br.id),
                            'time_slot': f"{br.start_time.strftime('%H:%M')} - {br.end_time.strftime('%H:%M')}",
                            'subject': '',
                            'employee': '',
                            'timing_name': br.name,
                            'is_break': True
                        })

            for day in timetable_data:
                timetable_data[day].sort(key=lambda x: x['time_slot'])

            return JsonResponse({
                'timetable': timetable_data,
                'batch_id': batch_id
            })

        if request.method == 'DELETE':
            if not timetable_id:
                return JsonResponse({'error': 'Timetable ID required for deletion'}, status=400)

            timetable = Timetable.objects.get(id=timetable_id, tenant=tenant)
            timetable.delete()
            return JsonResponse({'success': True, 'message': 'Timetable entry deleted'})

        payload = json.loads(request.body)

        batch_id = payload.get('batch')
        weekday_id = payload.get('weekday')
        class_timing_id = payload.get('class_timing')
        subject_id = payload.get('subject')
        employee_id = payload.get('employee')

        if not all([batch_id, weekday_id, class_timing_id]):
            return JsonResponse({
                'error': 'Missing required fields: batch, weekday, class_timing'
            }, status=400)

        # Verify related objects exist
        batch = Batch.objects.get(id=batch_id, tenant=tenant, is_deleted=False)
        weekday = Weekday.objects.get(id=weekday_id, tenant=tenant)
        class_timing = ClassTiming.objects.get(id=class_timing_id, tenant=tenant, is_deleted=False)

        subject = None
        if subject_id:
            subject = Subject.objects.get(id=subject_id, tenant=tenant, is_deleted=False)

        employee = None
        if employee_id:
            from core.models import Employee
            employee = Employee.objects.get(id=employee_id, tenant=tenant)

        if request.method == 'POST':
            # Create new timetable entry
            timetable = Timetable.objects.create(
                tenant=tenant,
                batch=batch,
                weekday=weekday,
                class_timing=class_timing,
                subject=subject,
                employee=employee
            )
            return JsonResponse({
                'success': True,
                'message': 'Timetable entry created',
                'id': str(timetable.id)
            })

        elif request.method == 'PUT':
            if not timetable_id:
                return JsonResponse({'error': 'Timetable ID required for update'}, status=400)

            timetable = Timetable.objects.get(id=timetable_id, tenant=tenant)
            timetable.batch = batch
            timetable.weekday = weekday
            timetable.class_timing = class_timing
            timetable.subject = subject
            timetable.employee = employee
            timetable.save()
            return JsonResponse({
                'success': True,
                'message': 'Timetable entry updated'
            })

    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    except Weekday.DoesNotExist:
        return JsonResponse({'error': 'Weekday not found'}, status=404)
    except ClassTiming.DoesNotExist:
        return JsonResponse({'error': 'Class timing not found'}, status=404)
    except Subject.DoesNotExist:
        return JsonResponse({'error': 'Subject not found'}, status=404)
    except Timetable.DoesNotExist:
        return JsonResponse({'error': 'Timetable entry not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
def build_batch_schedule_api(request, batch_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        import json
        from datetime import datetime
        from core.services.exceptions import ValidationException, NotFoundException

        payload = json.loads(request.body)

        period_duration_minutes = payload.get('period_duration_minutes')
        periods_count = payload.get('periods_count')
        start_time_str = payload.get('start_time')
        breaks = payload.get('breaks', [])

        if not all([period_duration_minutes, periods_count, start_time_str]):
            return JsonResponse({
                'error': 'Missing required fields: period_duration_minutes, periods_count, start_time'
            }, status=400)

        # Parse start time
        start_time = datetime.strptime(start_time_str, '%H:%M').time()

        timetable_service = TimetableService(tenant)
        class_timings = timetable_service.build_batch_schedule(
            batch_id=batch_id,
            period_duration_minutes=period_duration_minutes,
            periods_count=periods_count,
            start_time=start_time,
            breaks=breaks
        )

        return JsonResponse({
            'success': True,
            'message': f'Built schedule with {len(class_timings)} time slots',
            'class_timings': [{
                'id': str(ct.id),
                'name': ct.name,
                'start_time': ct.start_time.strftime('%H:%M'),
                'end_time': ct.end_time.strftime('%H:%M'),
                'is_break': ct.is_break,
            } for ct in class_timings]
        })

    except ValidationException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except NotFoundException as e:
        return JsonResponse({'error': str(e)}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
def generate_timetable_api(request, batch_id):
    """POST /api/batches/<uuid:batch_id>/generate-timetable/

    Auto-generate a timetable for a batch based on subject requirements.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        from core.services.timetable_generation_service import TimetableGenerationService
        from core.services.exceptions import NotFoundException

        gen_service = TimetableGenerationService(tenant)
        result = gen_service.generate(batch_id=batch_id)

        return JsonResponse({
            'success': True,
            'placed_count': result.placed_count,
            'unplaced_count': result.unplaced_count,
            'conflicts': result.conflicts,
            'message': f'Placed {result.placed_count} periods. {result.unplaced_count} could not be placed.'
        })

    except NotFoundException as e:
        return JsonResponse({'error': str(e)}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def class_timings_api(request, batch_id):
    """API endpoint to get class timings (time slots) for a batch"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        from core.models import ClassTiming, Batch

        # Verify batch exists
        batch = Batch.objects.get(id=batch_id, tenant=tenant, is_deleted=False)

        # Get all class timings for this batch, ordered by start time
        timings = ClassTiming.objects.filter(
            batch=batch,
            tenant=tenant,
            is_deleted=False
        ).order_by('start_time')

        timing_list = []
        for timing in timings:
            timing_list.append({
                'id': str(timing.id),
                'name': timing.name,
                'start_time': timing.start_time.strftime('%H:%M') if timing.start_time else '',
                'end_time': timing.end_time.strftime('%H:%M') if timing.end_time else '',
                'is_break': timing.is_break
            })

        return JsonResponse({
            'results': timing_list
        })

    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def weekdays_api(request):
    """API endpoint to get working weekdays for the active academic year"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        from core.models import Weekday

        # Get all weekdays, ordered by day_of_week
        weekdays = Weekday.objects.filter(
            tenant=tenant
        ).order_by('day_of_week')

        # If no weekdays exist, return empty results
        if not weekdays.exists():
            return JsonResponse({'results': []})

        weekday_list = []
        for weekday in weekdays:
            weekday_list.append({
                'id': str(weekday.id),
                'weekday': weekday.weekday,
                'day_of_week': weekday.day_of_week
            })

        return JsonResponse({'results': weekday_list})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def teachers_api(request):
    """API endpoint to get active teachers for a batch or all teachers"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        from core.services.employee_service import EmployeeService
        employee_service = EmployeeService(tenant)
        teachers = employee_service.get_teaching_staff()[:100]

        teacher_list = []
        for teacher in teachers:
            teacher_list.append({
                'id': str(teacher.id),
                'first_name': teacher.first_name,
                'last_name': teacher.last_name,
                'full_name': f"{teacher.first_name} {teacher.last_name}"
            })

        return JsonResponse({'results': teacher_list})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def attendance_summary_api(request):
    """API endpoint to get attendance summary"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        batch_id = request.GET.get('batch_id')
        date_str = request.GET.get('date', date.today().strftime('%Y-%m-%d'))
        
        try:
            filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
        
        attendance_service = AttendanceService(tenant)
        
        # Get attendance summary for the specific date
        summary = attendance_service.get_daily_attendance_summary(filter_date)
        
        if batch_id:
            # Get batch-specific stats if requested
            batch_stats = attendance_service.get_batch_attendance_stats(
                batch_id=batch_id,
                start_date=filter_date,
                end_date=filter_date
            )
            summary.update({
                'batch_stats': batch_stats
            })
        
        return JsonResponse({
            'date': date_str,
            'total_records': summary.get('total_records', 0),
            'present_count': summary.get('present_count', 0),
            'absent_count': summary.get('absent_count', 0),
            'batch_id': batch_id,
            'summary': summary
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ====== SETTINGS/CONFIGURATION VIEWS ======

class ConfigurationView(HTMXResponseMixin, TemplateView):
    template_name = 'core/configuration.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school'] = getattr(self.request, 'tenant', None)
        return context


@method_decorator(login_required, name='dispatch')
class SchoolSettingsView(TemplateView):
    """School-level configuration: logos, signature, contact details and report
    branding. These values are read by report generation for every report."""
    template_name = 'core/configuration/school_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        context['school'] = school
        context['signatures'] = SchoolSignatureService(school).list() if school else []
        return context

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            messages.error(request, 'School not found.')
            return redirect('core:school_settings')

        action = request.POST.get('action')

        if action == 'upload_logo':
            logo_file = request.FILES.get('logo')
            if not logo_file:
                messages.error(request, 'No file selected.')
            else:
                if school.logo:
                    school.logo.delete(save=False)
                school.logo = logo_file
                school.save(update_fields=['logo'])
                messages.success(request, 'School logo updated.')

        elif action == 'remove_logo':
            if school.logo:
                school.logo.delete(save=False)
                school.logo = None
                school.save(update_fields=['logo'])
                messages.success(request, 'Logo removed.')

        elif action == 'upload_logo_secondary':
            crest_file = request.FILES.get('logo_secondary')
            if not crest_file:
                messages.error(request, 'No file selected.')
            else:
                if school.logo_secondary:
                    school.logo_secondary.delete(save=False)
                school.logo_secondary = crest_file
                school.save(update_fields=['logo_secondary'])
                messages.success(request, 'Crest updated.')

        elif action == 'remove_logo_secondary':
            if school.logo_secondary:
                school.logo_secondary.delete(save=False)
                school.logo_secondary = None
                school.save(update_fields=['logo_secondary'])
                messages.success(request, 'Crest removed.')

        elif action == 'add_signature':
            svc = SchoolSignatureService(school)
            try:
                svc.create(
                    name=request.POST.get('name', '').strip(),
                    title=request.POST.get('title', '').strip() or 'Head of School',
                    section_label=request.POST.get('section_label', '').strip() or None,
                    image=request.FILES.get('image'),
                    user=request.user,
                )
                messages.success(request, 'Signature added.')
            except ValidationException as e:
                messages.error(request, e.message)

        elif action == 'update_signature':
            svc = SchoolSignatureService(school)
            try:
                svc.update(
                    request.POST.get('signature_id'),
                    name=request.POST.get('name', '').strip(),
                    title=request.POST.get('title', '').strip() or 'Head of School',
                    section_label=request.POST.get('section_label', '').strip() or None,
                    image=request.FILES.get('image'),
                    remove_image=request.POST.get('remove_image') == 'on',
                    user=request.user,
                )
                messages.success(request, 'Signature updated.')
            except (ValidationException, NotFoundException) as e:
                messages.error(request, e.message)

        elif action == 'delete_signature':
            try:
                SchoolSignatureService(school).delete(request.POST.get('signature_id'), user=request.user)
                messages.success(request, 'Signature removed.')
            except NotFoundException as e:
                messages.error(request, e.message)

        elif action == 'set_default_signature':
            try:
                SchoolSignatureService(school).set_default(request.POST.get('signature_id'), user=request.user)
                messages.success(request, 'Default signature updated.')
            except NotFoundException as e:
                messages.error(request, e.message)

        elif action == 'save_school_details':
            school.name = request.POST.get('name', '').strip() or school.name
            school.address_line1 = request.POST.get('address_line1', '').strip()
            school.phone = request.POST.get('phone', '').strip()
            school.email = request.POST.get('email', '').strip()
            school.website = request.POST.get('website', '').strip()
            school.report_title = request.POST.get('report_title', '').strip() or 'ASSESSMENT REPORT'
            school.footer_quote = request.POST.get('footer_quote', '').strip()
            school.operations_manager_name = request.POST.get('operations_manager_name', '').strip()
            school.fee_note_early_bird_discount_enabled = request.POST.get('fee_note_early_bird_discount_enabled') == 'on'
            school.fee_note_early_bird_discount_percent = request.POST.get('fee_note_early_bird_discount_percent') or '0.00'
            school.fee_note_terms = request.POST.get('fee_note_terms', '').strip()
            school.save(update_fields=[
                'name', 'address_line1', 'phone', 'email', 'website',
                'report_title', 'footer_quote', 'operations_manager_name',
                'fee_note_early_bird_discount_enabled', 'fee_note_early_bird_discount_percent',
                'fee_note_terms',
            ])
            messages.success(request, 'School details updated. They now appear on all generated reports.')

        return redirect('core:school_settings')


class ProgramsView(TemplateView):
    """Programs page for managing classes and batches"""
    template_name = 'core/programs.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            # Add any configuration-specific context here
            academic_service = AcademicService(tenant)
            context.update({
                'total_courses': academic_service.count(is_deleted=False),
                'total_batches': academic_service.count_batches(active_only=False),
                'active_academic_year': academic_service.get_active_academic_year()
            })
        
        return context


# API-powered template views
class StudentListAPIView(HTMXResponseMixin, TemplateView):
    """Student list view powered by DRF API.

    Its table is Alpine-driven, fetching rows from the JSON API client-side —
    there's no server-rendered fragment to swap on htmx navigation, so this
    view (unlike StudentListView) never sets an htmx_template_name.
    """
    template_name = 'core/students/list_api.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            # Load batches for filter dropdown (could also be done via API)
            academic_service = AcademicService(tenant)
            context['batches'] = academic_service.get_all_batches()
        
        return context


class AdmissionListAPIView(HTMXResponseMixin, TemplateView):
    """Admission list view powered by DRF API"""
    template_name = 'core/admission/list_api.html'
    htmx_template_name = 'core/htmx/admission_list_content.html'
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)

        if tenant:
            # Load courses for filter dropdown (could also be done via API)
            academic_service = AcademicService(tenant)
            context['courses'] = academic_service.get_all_courses()

        context['back_url'] = self.request.GET.get('back', reverse('core:admission_manage'))
        context['crumbs'] = [
            {'label': 'Admission'},
        ]
        return context


# ====== ADDITIONAL API ENDPOINTS ======

@require_http_methods(["GET"])
def dashboard_stats_api(request):
    """Comprehensive dashboard stats API using ReportingService"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        reporting_service = ReportingService(tenant)
        dashboard_stats = reporting_service.get_dashboard_stats()
        
        return JsonResponse(dashboard_stats)
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def service_health_api(request):
    """Service health check API"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    health_status = {}
    
    try:
        # Test each service
        student_service = StudentService(tenant)
        employee_service = EmployeeService(tenant)
        academic_service = AcademicService(tenant)
        attendance_service = AttendanceService(tenant)
        timetable_service = TimetableService(tenant)
        reporting_service = ReportingService(tenant)
        
        health_status.update({
            'student_service': {'status': 'healthy', 'count': student_service.count_active_students()},
            'employee_service': {'status': 'healthy', 'count': employee_service.count_active_employees()},
            'academic_service': {'status': 'healthy', 'courses': academic_service.count_courses(), 'batches': academic_service.count_batches()},
            'attendance_service': {'status': 'healthy', 'records': attendance_service.count()},
            'timetable_service': {'status': 'healthy', 'entries': timetable_service.count()},
            'reporting_service': {'status': 'healthy', 'last_updated': timezone.now().isoformat()},
        })
        
        overall_status = 'healthy'
        
    except Exception as e:
        health_status['error'] = str(e)
        overall_status = 'unhealthy'
    
    return JsonResponse({
        'overall_status': overall_status,
        'tenant': str(tenant),
        'services': health_status,
        'timestamp': timezone.now().isoformat()
    })


@require_http_methods(["GET"])
def enrollment_trends_api(request):
    """Enrollment trends API"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        reporting_service = ReportingService(tenant)
        days = int(request.GET.get('days', 30))
        
        trends = reporting_service.get_enrollment_trends(days=days)
        
        return JsonResponse(trends)
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def batch_create_api(request):
    """Create a new batch"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        academic_service = AcademicService(tenant)
        
        name = request.POST.get('name')
        course_id = request.POST.get('course_id')
        academic_year_id = request.POST.get('academic_year_id')
        employee_id = request.POST.get('employee_id')
        grading_type = request.POST.get('grading_type')
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate required fields
        errors = {}
        if not name:
            errors['name'] = ['Batch name is required']
        if not course_id:
            errors['course_id'] = ['Course is required']
        if not academic_year_id:
            errors['academic_year_id'] = ['Academic year is required']
            
        if errors:
            return JsonResponse(errors, status=400)
        
        # Get academic year and use its dates
        from .models import AcademicYear
        from datetime import datetime, time
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id, tenant=tenant, is_active=True)
            # Convert dates to datetime with default times
            start_date_obj = datetime.combine(academic_year.start_date, time(8, 0))  # 8:00 AM
            end_date_obj = datetime.combine(academic_year.end_date, time(17, 0))   # 5:00 PM
        except AcademicYear.DoesNotExist:
            return JsonResponse({'error': 'Academic year not found'}, status=400)
        
        # Create batch with academic year
        batch = academic_service.create_batch(
            name=name,
            course_id=course_id,
            start_date=start_date_obj,
            end_date=end_date_obj,
            employee_id=employee_id if employee_id else None,
            grading_type=grading_type if grading_type else None,
            user=request.user,
            is_active=is_active,
            academic_year_id=academic_year_id
        )
        
        # Return success response with updated batch list, rendered with the same
        # paginated context BatchListView provides so the partial template (which
        # references page_obj / is_paginated / student_count) renders correctly.
        from django.template.loader import render_to_string
        from django.core.paginator import Paginator

        batches = _current_year_batches(tenant, academic_service)
        paginator = Paginator(batches, BatchListView.paginate_by)
        page_obj = paginator.get_page(1)

        html = render_to_string('core/htmx/batch_list_content.html', {
            'batches': page_obj,
            'page_obj': page_obj,
            'paginator': paginator,
            'is_paginated': page_obj.has_other_pages(),
            'request': request,
        })

        return HttpResponse(html)

    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception:
        logger.exception("batch create/update failed")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@require_http_methods(["GET"])
@login_required
def batch_detail_api(request, batch_id):
    """Get batch details for editing"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        academic_service = AcademicService(tenant)
        batch = academic_service.get_batch_by_id(batch_id)
        
        return JsonResponse({
            'id': str(batch.id),
            'name': batch.name,
            'course_id': str(batch.course.id),
            'academic_year_id': str(batch.academic_year.id) if batch.academic_year else None,
            'start_date': batch.start_date.isoformat(),
            'end_date': batch.end_date.isoformat(),
            'employee_id': str(batch.employee.id) if batch.employee else None,
            'grading_type': batch.grading_type,
            'is_active': batch.is_active
        })
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def batch_update_api(request, batch_id):
    """Update an existing batch"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        academic_service = AcademicService(tenant)
        batch = academic_service.get_batch_by_id(batch_id)
        
        name = request.POST.get('name')
        course_id = request.POST.get('course_id')
        academic_year_id = request.POST.get('academic_year_id')
        employee_id = request.POST.get('employee_id')
        grading_type = request.POST.get('grading_type')
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate required fields
        errors = {}
        if not name:
            errors['name'] = ['Batch name is required']
        if not course_id:
            errors['course_id'] = ['Course is required']
        if not academic_year_id:
            errors['academic_year_id'] = ['Academic year is required']
            
        if errors:
            return JsonResponse(errors, status=400)
        
        # Get academic year and update dates
        from .models import Course, AcademicYear
        from datetime import datetime, time
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id, tenant=tenant, is_active=True)
            # Convert dates to datetime with default times
            start_date_obj = datetime.combine(academic_year.start_date, time(8, 0))  # 8:00 AM
            end_date_obj = datetime.combine(academic_year.end_date, time(17, 0))   # 5:00 PM
        except AcademicYear.DoesNotExist:
            return JsonResponse({'error': 'Academic year not found'}, status=400)
        
        # Update batch
        batch.name = name
        batch.academic_year = academic_year
        batch.start_date = start_date_obj
        batch.end_date = end_date_obj
        batch.grading_type = grading_type if grading_type else None
        batch.is_active = is_active
        
        # Update course if changed
        if str(batch.course.id) != course_id:
            try:
                course = Course.objects.get(id=course_id, tenant=tenant, is_deleted=False)
                batch.course = course
            except Course.DoesNotExist:
                return JsonResponse({'error': 'Course not found'}, status=400)
        
        # Update employee if changed
        if employee_id:
            from .services.employee_service import EmployeeService
            employee_service = EmployeeService(tenant)
            employee = employee_service.get_by_id(employee_id)
            batch.employee = employee
        else:
            batch.employee = None
        
        batch.save()
        
        # Return success response with updated batch list, rendered with the same
        # paginated context BatchListView provides so the partial template (which
        # references page_obj / is_paginated / student_count) renders correctly.
        from django.template.loader import render_to_string
        from django.core.paginator import Paginator

        batches = _current_year_batches(tenant, academic_service)
        paginator = Paginator(batches, BatchListView.paginate_by)
        page_obj = paginator.get_page(1)

        html = render_to_string('core/htmx/batch_list_content.html', {
            'batches': page_obj,
            'page_obj': page_obj,
            'paginator': paginator,
            'is_paginated': page_obj.has_other_pages(),
            'request': request,
        })

        return HttpResponse(html)

    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception:
        logger.exception("batch create/update failed")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@require_http_methods(["GET"])
@login_required
def employees_api(request):
    """Get employees list for form dropdowns"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .services.employee_service import EmployeeService
        employee_service = EmployeeService(tenant)
        employees = employee_service.get_active_employees()[:100]  # Limit for performance
        
        results = [{
            'id': str(employee.id),
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'full_name': f"{employee.first_name} {employee.last_name}"
        } for employee in employees]
        
        return JsonResponse({'employees': results})
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def academic_years_api(request):
    """Get academic years list for form dropdowns"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .models import AcademicYear
        # Only one academic year is active per tenant (the current one). Callers
        # that need historical years (e.g. cross-year student import) pass
        # ?all=1 / ?include_inactive=1 to get every year.
        include_inactive = request.GET.get('all') or request.GET.get('include_inactive')
        academic_years = AcademicYear.objects.filter(tenant=tenant)
        if not include_inactive:
            academic_years = academic_years.filter(is_active=True)
        academic_years = academic_years.order_by('-start_date')[:50]

        results = [{
            'id': str(year.id),
            'name': year.name,
            'start_date': year.start_date.strftime('%Y-%m-%d'),
            'end_date': year.end_date.strftime('%Y-%m-%d'),
            'is_active': year.is_active,
        } for year in academic_years]

        return JsonResponse({'academic_years': results})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# Teacher Management Views

def _render_paginated_fragment(request, queryset, template_name, context_key, paginate_by=15, extra_context=None):
    """Render a list partial with a real paginated context (page_obj/paginator/
    is_paginated), for HTMX action endpoints (create/update/etc.) that need to
    return a refreshed list fragment. Templates built on Django's ListView
    pagination (e.g. `{{ forloop.counter0|add:page_obj.start_index }}`) throw
    VariableDoesNotExist if that context is missing entirely.
    """
    from django.template.loader import render_to_string

    paginator = Paginator(queryset, paginate_by)
    page_obj = paginator.get_page(1)

    context = {
        context_key: page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'request': request,
    }
    if extra_context:
        context.update(extra_context)

    return render_to_string(template_name, context)


def _render_teacher_list_fragment(request, teachers):
    return _render_paginated_fragment(
        request, teachers, 'core/htmx/teacher_list_content.html', 'teachers',
        paginate_by=TeacherListView.paginate_by,
    )


class TeacherListView(PermissionRequiredMixin, HTMXResponseMixin, ListView):
    template_name = 'core/academic/teachers.html'
    htmx_template_name = 'core/htmx/teacher_list_content.html'
    context_object_name = 'teachers'
    paginate_by = 15
    required_permission = 'hr.employee.view'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        
        from .services.employee_service import EmployeeService
        employee_service = EmployeeService(tenant)
        
        search_query = self.request.GET.get('search', '')
        department_id = self.request.GET.get('department', '')
        status = self.request.GET.get('status', '')
        staff_type = self.request.GET.get('staff_type', 'all')

        # Apply filters based on request parameters
        active_only = status != 'inactive'
        if status == 'active':
            active_only = True

        return employee_service.search_employees(
            query=search_query,
            department_id=department_id if department_id else None,
            active_only=active_only,
            staff_type=staff_type,
        )


@require_http_methods(["POST"])
@login_required
@require_permission('hr.employee.manage')
def teacher_create_api(request):
    """Create a new teacher"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .services.employee_service import EmployeeService
        employee_service = EmployeeService(tenant)
        
        # Get form data
        employee_number = request.POST.get('employee_number')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        joining_date = request.POST.get('joining_date')
        gender = request.POST.get('gender')
        
        # Validate required fields
        errors = {}
        if not employee_number:
            errors['employee_number'] = ['Employee number is required']
        if not first_name:
            errors['first_name'] = ['First name is required']
        if not last_name:
            errors['last_name'] = ['Last name is required']
        if not joining_date:
            errors['joining_date'] = ['Joining date is required']
        if not gender:
            errors['gender'] = ['Gender is required']
            
        if errors:
            return JsonResponse(errors, status=400)
        
        # Parse date and gender
        from datetime import datetime
        joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d').date()
        gender_bool = gender == 'true'
        
        # Collect additional data
        additional_data = {}
        optional_fields = [
            'middle_name', 'job_title', 'qualification', 'email', 'mobile_phone',
            'date_of_birth', 'marital_status', 'experience_year', 'experience_month',
            'home_address_line1', 'home_address_line2', 'home_city', 'home_state', 
            'home_pin_code', 'employee_department_id', 'employee_category_id',
            'employee_position_id', 'employee_grade_id'
        ]
        
        for field in optional_fields:
            value = request.POST.get(field)
            if value:
                additional_data[field] = value
        
        # Handle status
        additional_data['status'] = request.POST.get('status') == 'on'
        additional_data['is_teaching_staff'] = request.POST.get('is_teaching_staff') == 'on'

        # Create teacher
        # Note: `user` here is the new teacher's own portal login account
        # (Employee.user is a one-to-one FK), not the admin submitting this
        # form — it isn't collected by this form, so it's left unset.
        teacher = employee_service.create_employee(
            employee_number=employee_number,
            first_name=first_name,
            last_name=last_name,
            joining_date=joining_date_obj,
            gender=gender_bool,
            **additional_data
        )
        
        # Return success response with updated teacher list
        teachers = employee_service.search_employees()
        html = _render_teacher_list_fragment(request, teachers)

        return HttpResponse(html)

    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@require_http_methods(["GET"])
@login_required
@require_permission('hr.employee.view')
def teacher_detail_api(request, teacher_id):
    """Get teacher details"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .services.employee_service import EmployeeService
        employee_service = EmployeeService(tenant)
        teacher = employee_service.get_by_id(teacher_id)
        
        return JsonResponse({
            'id': str(teacher.id),
            'employee_number': teacher.employee_number,
            'first_name': teacher.first_name,
            'middle_name': teacher.middle_name,
            'last_name': teacher.last_name,
            'gender': teacher.gender,
            'joining_date': teacher.joining_date.strftime('%Y-%m-%d'),
            'date_of_birth': teacher.date_of_birth.strftime('%Y-%m-%d') if teacher.date_of_birth else None,
            'marital_status': teacher.marital_status,
            'job_title': teacher.job_title,
            'qualification': teacher.qualification,
            'experience_year': teacher.experience_year,
            'experience_month': teacher.experience_month,
            'email': teacher.email,
            'mobile_phone': teacher.mobile_phone,
            'home_address_line1': teacher.home_address_line1,
            'home_address_line2': teacher.home_address_line2,
            'home_city': teacher.home_city,
            'home_state': teacher.home_state,
            'home_pin_code': teacher.home_pin_code,
            'employee_department_id': str(teacher.employee_department.id) if teacher.employee_department else None,
            'employee_category_id': str(teacher.employee_category.id) if teacher.employee_category else None,
            'employee_position_id': str(teacher.employee_position.id) if teacher.employee_position else None,
            'employee_grade_id': str(teacher.employee_grade.id) if teacher.employee_grade else None,
            'status': teacher.status,
            'is_teaching_staff': teacher.is_teaching_staff,
        })
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.employee.manage')
def teacher_update_api(request, teacher_id):
    """Update an existing teacher"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .services.employee_service import EmployeeService
        employee_service = EmployeeService(tenant)
        teacher = employee_service.get_by_id(teacher_id)
        
        # Get form data and validate
        employee_number = request.POST.get('employee_number')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        joining_date = request.POST.get('joining_date')
        gender = request.POST.get('gender')
        
        errors = {}
        if not employee_number:
            errors['employee_number'] = ['Employee number is required']
        if not first_name:
            errors['first_name'] = ['First name is required']
        if not last_name:
            errors['last_name'] = ['Last name is required']
        if not joining_date:
            errors['joining_date'] = ['Joining date is required']
        if not gender:
            errors['gender'] = ['Gender is required']
            
        if errors:
            return JsonResponse(errors, status=400)
        
        # Parse date and gender
        from datetime import datetime
        joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d').date()
        gender_bool = gender == 'true'
        
        # Update teacher fields
        teacher.employee_number = employee_number
        teacher.first_name = first_name
        teacher.last_name = last_name
        teacher.joining_date = joining_date_obj
        teacher.gender = gender_bool
        
        # Update optional fields
        optional_fields = [
            'middle_name', 'job_title', 'qualification', 'email', 'mobile_phone',
            'date_of_birth', 'marital_status', 'experience_year', 'experience_month',
            'home_address_line1', 'home_address_line2', 'home_city', 'home_state', 
            'home_pin_code'
        ]
        
        for field in optional_fields:
            value = request.POST.get(field)
            if hasattr(teacher, field):
                if field == 'date_of_birth' and value:
                    setattr(teacher, field, datetime.strptime(value, '%Y-%m-%d').date())
                elif field in ['experience_year', 'experience_month'] and value:
                    setattr(teacher, field, int(value))
                else:
                    setattr(teacher, field, value if value else None)
        
        # Update foreign key fields
        fk_fields = [
            ('employee_department_id', 'employee_department'),
            ('employee_category_id', 'employee_category'),
            ('employee_position_id', 'employee_position'),
            ('employee_grade_id', 'employee_grade')
        ]
        
        for field_name, attr_name in fk_fields:
            value = request.POST.get(field_name)
            if value:
                from .models import EmployeeDepartment, EmployeeCategory, EmployeePosition, EmployeeGrade
                model_map = {
                    'employee_department': EmployeeDepartment,
                    'employee_category': EmployeeCategory,
                    'employee_position': EmployeePosition,
                    'employee_grade': EmployeeGrade
                }
                try:
                    obj = model_map[attr_name].objects.get(id=value, tenant=tenant)
                    setattr(teacher, attr_name, obj)
                except model_map[attr_name].DoesNotExist:
                    pass
            else:
                setattr(teacher, attr_name, None)
        
        # Update status
        teacher.status = request.POST.get('status') == 'on'
        teacher.is_teaching_staff = request.POST.get('is_teaching_staff') == 'on'

        teacher.save()

        # Return success response with updated teacher list
        teachers = employee_service.search_employees()
        html = _render_teacher_list_fragment(request, teachers)

        return HttpResponse(html)
    
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.employee.manage')
def teacher_toggle_status_api(request, teacher_id):
    """Toggle teacher active status"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .services.employee_service import EmployeeService
        import json
        
        employee_service = EmployeeService(tenant)
        teacher = employee_service.get_by_id(teacher_id)
        
        data = json.loads(request.body)
        new_status = data.get('status', not teacher.status)
        
        teacher.status = new_status
        teacher.save()
        
        return JsonResponse({
            'success': True,
            'status': teacher.status,
            'message': f"Teacher {'activated' if teacher.status else 'deactivated'} successfully"
        })
    
    except ServiceException as e:
        return JsonResponse({'error': str(e), 'success': False}, status=400)


@require_http_methods(["DELETE"])
@login_required
@require_permission('hr.employee.manage')
def teacher_delete_api(request, teacher_id):
    """Delete a teacher"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .services.employee_service import EmployeeService
        employee_service = EmployeeService(tenant)
        teacher = employee_service.get_by_id(teacher_id)
        
        teacher.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Teacher deleted successfully'
        })
    
    except ServiceException as e:
        return JsonResponse({'error': str(e), 'success': False}, status=400)


def _render_employee_subjects_fragment(request, tenant, employee_id):
    from .models import Subject
    search = request.GET.get('search', '')
    subjects = Subject.objects.filter(tenant=tenant, is_deleted=False).select_related('batch', 'employee')
    if search:
        subjects = subjects.filter(Q(name__icontains=search) | Q(batch__name__icontains=search))
    subjects = subjects.order_by('batch__name', 'name')[:200]

    return render_to_string('core/htmx/hr/employee_subjects_tab.html', {
        'employee_id': employee_id,
        'subjects': subjects,
    })


@require_http_methods(["GET"])
@login_required
@require_permission('hr.employee.view')
def employee_subjects_tab(request, employee_id):
    """Subjects tab content for the employee edit modal — every subject
    across every batch, with the ones currently assigned to this employee
    checked, optionally filtered by a batch/subject name search.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    return HttpResponse(_render_employee_subjects_fragment(request, tenant, employee_id))


@require_http_methods(["POST"])
@login_required
@require_permission('hr.employee.manage')
def employee_subjects_update_api(request, employee_id):
    """Bulk-assign the selected subjects to this employee (see
    AcademicService.assign_subjects_to_employee for the actual semantics).
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        from .services.academic_service import AcademicService
        subject_ids = request.POST.getlist('subject_ids')
        AcademicService(tenant).assign_subjects_to_employee(employee_id, subject_ids, user=request.user)
        return HttpResponse(_render_employee_subjects_fragment(request, tenant, employee_id))
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)


class EmployeeDetailView(PermissionRequiredMixin, TemplateView):
    """Full employee profile — Personal, Employment, Academic/Teaching,
    Attendance, Leave, Payroll and Documents tabs. The quick add/edit modal on
    the employee list stays the fast path; this is the record of truth."""
    template_name = 'core/hr/employees/detail.html'
    required_permission = 'hr.employee.view'

    def get_context_data(self, **kwargs):
        from datetime import date, timedelta
        from .models import Employee, EmployeeAttendance, EmployeeLeave, LeaveType, Subject, EmployeePayrollProfile
        from .services.leave_attendance_service import LeaveService

        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            raise Http404('School not found')
        employee = get_object_or_404(
            Employee.objects.select_related(
                'employee_department', 'employee_position', 'employee_category',
                'employee_grade', 'reporting_manager',
            ),
            tenant=tenant, id=kwargs['pk'],
        )
        context['employee'] = employee
        context['back_url'] = reverse('core:teacher_list')
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Employees', 'url': reverse('core:teacher_list')},
            {'label': employee.full_name},
        ]

        context['subjects'] = Subject.objects.filter(
            tenant=tenant, employee=employee, is_deleted=False
        ).select_related('batch').order_by('batch__name', 'name')

        since = date.today() - timedelta(days=30)
        att = EmployeeAttendance.objects.filter(tenant=tenant, employee=employee, date__gte=since)
        context['attendance_summary'] = {
            'window_days': 30,
            'present': att.filter(status='present').count(),
            'absent': att.filter(status='absent').count(),
            'on_leave': att.filter(status='on_leave').count(),
            'half_day': att.filter(status='half_day').count(),
        }
        context['recent_attendance'] = att.order_by('-date')[:15]

        year = date.today().year
        leave_svc = LeaveService(tenant)
        balances = []
        for lt in LeaveType.objects.filter(tenant=tenant, status=True):
            balances.append({'leave_type': lt, **leave_svc.get_leave_balance(employee, lt, year)})
        context['leave_balances'] = balances
        context['leave_year'] = year
        context['recent_leaves'] = EmployeeLeave.objects.filter(
            tenant=tenant, employee=employee
        ).select_related('leave_type').order_by('-created_at')[:15]

        context['payroll_profile'] = EmployeePayrollProfile.objects.filter(
            tenant=tenant, employee=employee
        ).select_related('payroll_group').first()
        return context


class SubjectAssignmentsView(PermissionRequiredMixin, TemplateView):
    """Pick a teaching-staff member, then assign the subjects they teach —
    reuses the employee_subjects_tab htmx endpoint for the picker body."""
    template_name = 'core/hr/employees/subject_assignments.html'
    required_permission = 'hr.employee.manage'

    def get_context_data(self, **kwargs):
        from .services.employee_service import EmployeeService

        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['teaching_staff'] = EmployeeService(tenant).get_teaching_staff()
        context['selected_id'] = self.request.GET.get('employee', '')
        context['back_url'] = reverse('core:hr_dashboard')
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Subject Assignments'},
        ]
        return context


# Employee-related API endpoints for form dropdowns

@require_http_methods(["GET"])
@login_required
def departments_api(request):
    """Get departments list for form dropdowns"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .models import EmployeeDepartment
        departments = EmployeeDepartment.objects.filter(
            tenant=tenant,
            status=True
        ).order_by('name')[:50]
        
        results = [{
            'id': str(dept.id),
            'name': dept.name,
            'code': dept.code
        } for dept in departments]
        
        return JsonResponse({'departments': results})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def employee_categories_api(request):
    """Get employee categories list for form dropdowns"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .models import EmployeeCategory
        categories = EmployeeCategory.objects.filter(
            tenant=tenant,
            status=True
        ).order_by('name')[:50]
        
        results = [{
            'id': str(cat.id),
            'name': cat.name,
            'prefix': cat.prefix
        } for cat in categories]
        
        return JsonResponse({'categories': results})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def employee_positions_api(request):
    """Get employee positions list for form dropdowns"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .models import EmployeePosition
        positions = EmployeePosition.objects.filter(
            tenant=tenant,
            status=True
        ).order_by('name')[:50]
        
        results = [{
            'id': str(pos.id),
            'name': pos.name
        } for pos in positions]
        
        return JsonResponse({'positions': results})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def employee_grades_api(request):
    """Get employee grades list for form dropdowns"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .models import EmployeeGrade
        grades = EmployeeGrade.objects.filter(
            tenant=tenant,
            status=True
        ).order_by('priority')[:50]
        
        results = [{
            'id': str(grade.id),
            'name': grade.name,
            'priority': grade.priority
        } for grade in grades]
        
        return JsonResponse({'grades': results})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# Exam Planner Views

def _notify_exam_results_published(tenant, exam_group_id):
    """Notify guardians of students in a published exam group's batch, through
    Notification Control (Configuration → Notification Control). Best-effort."""
    try:
        from .models import ExamGroup, StudentGuardianRelation
        from core.services.notification_service import NotificationService

        group = ExamGroup.objects.filter(tenant=tenant, id=exam_group_id).select_related('batch').first()
        if not group or not group.batch_id:
            return
        relations = (
            StudentGuardianRelation.objects.filter(
                tenant=tenant,
                student__student_batches__batch_id=group.batch_id,
                student__student_batches__is_active=True,
            )
            .select_related('guardian')
            .distinct()
        )
        recipients = [
            {
                "id": rel.guardian_id, "type": "guardian",
                "phone": getattr(rel.guardian, 'mobile_phone', None),
                "email": getattr(rel.guardian, 'email', None),
            }
            for rel in relations if rel.guardian_id
        ]
        NotificationService(tenant).dispatch(
            "exam_results_published", "guardians", recipients,
            title=f"Results published: {group.name}",
            message=(
                f"Results for {group.name} are now available on the parent "
                f"portal."
            ),
        )
    except Exception:
        logger.exception("exam-results-published notification failed")


@login_required
def publish_exam_group_api(request, exam_group_id):
    """Publish or unpublish an exam group"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        exam_service = ExamService(tenant)
        is_published = exam_service.toggle_exam_group_publication(exam_group_id)

        # Trigger background report generation when exam group is published
        if is_published:
            from .tasks import generate_reports_on_exam_publish
            generate_reports_on_exam_publish.delay(
                tenant_id=str(tenant.id),
                exam_group_id=str(exam_group_id),
            )
            _notify_exam_results_published(tenant, exam_group_id)

        return JsonResponse({
            'success': True,
            'is_published': is_published
        })

    except NotFoundException as e:
        return JsonResponse({'error': str(e)}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Attendance Management Views

class AttendanceManagementView(HTMXResponseMixin, TemplateView):
    """Teacher view for marking attendance"""
    template_name = 'core/academic/attendance_management.html'
    htmx_template_name = 'core/htmx/attendance_management_content.html'
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            try:
                attendance_service = AttendanceService(tenant)

                active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()

                # Batches scoped to active year, with course info for client-side filtering
                batches = (
                    Batch.objects.filter(
                        tenant=tenant,
                        academic_year=active_year,
                        is_active=True,
                        is_deleted=False,
                    ).select_related('course').order_by('course__course_name', 'name')
                    if active_year else Batch.objects.none()
                )

                # Distinct courses that have at least one batch in the active year
                courses = (
                    Course.objects.filter(
                        tenant=tenant,
                        batches__academic_year=active_year,
                        batches__is_active=True,
                        batches__is_deleted=False,
                        is_deleted=False,
                    ).distinct().order_by('course_name')
                    if active_year else Course.objects.none()
                )

                selected_date = self.request.GET.get('date', date.today().strftime('%Y-%m-%d'))
                selected_batch_id = self.request.GET.get('batch_id')
                selected_course_id = self.request.GET.get('course_id', '')

                # If a batch is selected but no course, infer course from batch
                if selected_batch_id and not selected_course_id:
                    try:
                        selected_course_id = str(
                            Batch.objects.get(id=selected_batch_id, tenant=tenant).course_id
                        )
                    except Batch.DoesNotExist:
                        pass

                # Validate the selected date
                from datetime import datetime as _dt
                selected_date_obj = _dt.strptime(selected_date, '%Y-%m-%d').date()
                today = date.today()

                date_invalid_reason = None
                if selected_date_obj > today:
                    date_invalid_reason = 'future'
                elif active_year:
                    if selected_date_obj < active_year.start_date:
                        date_invalid_reason = 'before_year'
                    elif selected_date_obj > active_year.end_date:
                        date_invalid_reason = 'after_year'

                attendance_data = None
                if selected_batch_id:
                    attendance_data = attendance_service.get_batch_attendance_for_date(
                        batch_id=selected_batch_id,
                        attendance_date=selected_date,
                    )

                context.update({
                    'courses': courses,
                    'batches': batches,
                    'selected_date': selected_date,
                    'selected_batch_id': selected_batch_id,
                    'selected_course_id': selected_course_id,
                    'active_academic_year': active_year,
                    'attendance_data': attendance_data,
                    'date_invalid_reason': date_invalid_reason,
                    'page_title': 'Attendance Management',
                })

            except Exception as e:
                context['error'] = str(e)
        
        return context


class AttendanceReportsView(HTMXResponseMixin, TemplateView):
    """Admin/Parent view for attendance reports"""
    template_name = 'core/academic/attendance_reports.html'
    htmx_template_name = 'core/htmx/attendance_reports_content.html'
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            try:
                attendance_service = AttendanceService(tenant)
                
                # Get filter parameters
                report_type = self.request.GET.get('report_type', 'student')
                student_id = self.request.GET.get('student_id')
                batch_id = self.request.GET.get('batch_id')
                start_date = self.request.GET.get('start_date')
                end_date = self.request.GET.get('end_date')
                
                # Get students and batches for dropdowns
                students = Student.objects.filter(tenant=tenant, is_active=True).order_by('first_name', 'last_name')
                batches = Batch.objects.filter(tenant=tenant).order_by('name')
                
                report_data = None
                if report_type == 'student' and student_id and start_date and end_date:
                    report_data = attendance_service.get_student_attendance_report(
                        student_id=student_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                elif report_type == 'batch' and batch_id and start_date and end_date:
                    report_data = attendance_service.get_batch_attendance_report(
                        batch_id=batch_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                elif report_type == 'daily' and batch_id and start_date:
                    report_data = attendance_service.get_daily_attendance_report(
                        batch_id=batch_id,
                        report_date=start_date
                    )
                
                context.update({
                    'students': students,
                    'batches': batches,
                    'report_type': report_type,
                    'student_id': student_id,
                    'batch_id': batch_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'report_data': report_data,
                    'page_title': 'Attendance Reports'
                })
                
            except Exception as e:
                context['error'] = str(e)
        
        return context


@login_required
def mark_attendance_api(request):
    """Bulk mark attendance for students"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        data = json.loads(request.body)
        attendance_service = AttendanceService(tenant)
        
        batch_id = data.get('batch_id')
        attendance_date = data.get('attendance_date')
        attendance_records = data.get('attendance_records', [])
        
        result = attendance_service.mark_batch_attendance(
            batch_id=batch_id,
            attendance_date=attendance_date,
            attendance_records=attendance_records,
            user=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Attendance marked for {len(result)} students',
            'records': result
        })
        
    except ValidationException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def batch_students_attendance_api(request, batch_id):
    """Get students in a batch for attendance marking"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        attendance_date = request.GET.get('date', date.today().strftime('%Y-%m-%d'))
        attendance_service = AttendanceService(tenant)
        
        students_data = attendance_service.get_batch_students_for_attendance(
            batch_id=batch_id,
            attendance_date=attendance_date
        )
        
        return JsonResponse({
            'students': students_data,
            'date': attendance_date
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def attendance_summary_api(request):
    """Get attendance summary statistics"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        batch_id = request.GET.get('batch_id')
        student_id = request.GET.get('student_id')
        month = request.GET.get('month')  # Format: YYYY-MM
        
        attendance_service = AttendanceService(tenant)
        
        if student_id and month:
            summary = attendance_service.get_student_monthly_summary(
                student_id=student_id,
                month=month
            )
        elif batch_id and month:
            summary = attendance_service.get_batch_monthly_summary(
                batch_id=batch_id,
                month=month
            )
        else:
            return JsonResponse({'error': 'Missing required parameters'}, status=400)

        # The service returns rich model instances (student/batch); convert them
        # to JSON-safe dicts at this boundary rather than in the service (whose
        # callers rely on the objects).
        summary = dict(summary)
        for key in ('batch', 'student'):
            obj = summary.get(key)
            if hasattr(obj, 'pk'):
                summary[key] = {
                    'id': str(obj.pk),
                    'name': (obj.name if key == 'batch'
                             else f"{obj.first_name} {obj.last_name}"),
                }

        return JsonResponse(summary)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def batch_monthly_attendance_api(request, batch_id):
    """Return all attendance records for a batch for a given month in one query."""
    import calendar as cal_mod
    from datetime import timedelta as _timedelta
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        today = date.today()
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        days_in_month = cal_mod.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, days_in_month)

        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

        school_calendar = SchoolCalendarService(tenant)
        working_days = school_calendar.get_configured_working_days()
        holidays = {}
        for ev in school_calendar.get_holidays(start, end):
            ev_start = max(ev.start_date.date(), start)
            ev_end = min(ev.end_date.date(), end)
            d = ev_start
            while d <= ev_end:
                holidays[d.strftime('%Y-%m-%d')] = ev.title
                d += _timedelta(days=1)

        batch_students = BatchStudent.objects.filter(
            batch=batch, is_active=True, tenant=tenant
        ).select_related('student').order_by('student__first_name', 'student__last_name')

        records = Attendance.objects.filter(
            batch=batch, tenant=tenant,
            month_date__gte=start, month_date__lte=end
        ).values('student_id', 'month_date', 'forenoon', 'afternoon', 'reason')

        record_map = {}
        for r in records:
            key = (str(r['student_id']), r['month_date'].strftime('%Y-%m-%d'))
            record_map[key] = {
                'forenoon': r['forenoon'],
                'afternoon': r['afternoon'],
                'reason': r['reason'] or '',
            }

        today_str = today.strftime('%Y-%m-%d')
        school_day_dates = set()
        for day in range(1, days_in_month + 1):
            d_date = date(year, month, day)
            ds = d_date.strftime('%Y-%m-%d')
            if d_date.weekday() in working_days and ds not in holidays:
                school_day_dates.add(ds)

        students = []
        for bs in batch_students:
            s = bs.student
            daily = {}
            for day in range(1, days_in_month + 1):
                d = date(year, month, day).strftime('%Y-%m-%d')
                record = record_map.get((str(s.id), d))
                if record is not None:
                    daily[d] = {**record, 'implicit': False}
                elif d <= today_str and d in school_day_dates:
                    # No saved row for a past/today school day: premarked present
                    # (mirrors the teacher portal's default -- attendance is
                    # assumed present until an exception is recorded).
                    daily[d] = {'forenoon': True, 'afternoon': True, 'reason': '', 'implicit': True}
                else:
                    daily[d] = None  # future date or non-school day
            students.append({
                'id': str(s.id),
                'name': f"{s.first_name} {s.last_name}",
                'admission_no': s.admission_no,
                'daily': daily,
            })

        return JsonResponse({
            'students': students,
            'year': year,
            'month': month,
            'days': days_in_month,
            'batch_name': batch.name,
            'working_days': working_days,
            'holidays': holidays,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def export_attendance_report_api(request):
    """Export attendance report as CSV or PDF"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        report_type = request.GET.get('type', 'csv')
        student_id = request.GET.get('student_id')
        batch_id = request.GET.get('batch_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        format_type = request.GET.get('format', 'student')
        
        attendance_service = AttendanceService(tenant)
        
        if format_type == 'student' and student_id:
            report_data = attendance_service.get_student_attendance_report(
                student_id=student_id,
                start_date=start_date,
                end_date=end_date
            )
            filename = f"student_attendance_{student_id}_{start_date}_to_{end_date}"
        elif format_type == 'batch' and batch_id:
            report_data = attendance_service.get_batch_attendance_report(
                batch_id=batch_id,
                start_date=start_date,
                end_date=end_date
            )
            filename = f"batch_attendance_{batch_id}_{start_date}_to_{end_date}"
        else:
            return JsonResponse({'error': 'Invalid parameters for export'}, status=400)
        
        if report_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
            
            import csv
            writer = csv.writer(response)
            
            if format_type == 'student':
                writer.writerow(['Date', 'Forenoon', 'Afternoon', 'Status', 'Reason'])
                for record in report_data['attendance_records']:
                    status = 'Present' if (record['forenoon'] or record['afternoon']) else 'Absent'
                    writer.writerow([
                        record['date'],
                        'Present' if record['forenoon'] else 'Absent',
                        'Present' if record['afternoon'] else 'Absent',
                        status,
                        record['reason'] or 'N/A'
                    ])
            else:  # batch format
                writer.writerow(['Student Name', 'Student ID', 'Present Days', 'Absent Days', 'Attendance %'])
                for student in report_data['student_summaries']:
                    writer.writerow([
                        student['student_name'],
                        student['student_id'],
                        student['present_days'],
                        student['absent_days'],
                        f"{student['attendance_percentage']:.1f}%"
                    ])
            
            return response
            
        else:  # PDF via WeasyPrint
            from django.template.loader import render_to_string
            from weasyprint import HTML
            from weasyprint.text.fonts import FontConfiguration

            html_content = render_to_string('core/reports/attendance_report_pdf.html', {
                'report_data': report_data,
                'format_type': format_type,
                'start_date': start_date,
                'end_date': end_date,
                'tenant': tenant,
            })
            font_config = FontConfiguration()
            pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
            return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class QuickBooksReconciliationView(TemplateView):
    """QuickBooks receipt reconciliation dashboard"""
    template_name = 'core/fees/receipt_reconciliation.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        # Add any initial context data needed for the reconciliation page
        context['page_title'] = 'QuickBooks Receipt Reconciliation'
        
        return context


# Finance Module Views

class FinanceSettingsView(TemplateView):
    """Finance settings and configuration view"""
    template_name = 'core/finance/settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        # Get QuickBooks connection status
        try:
            from core.services.quickbooks_service import QuickBooksService
            qb_service = QuickBooksService(school)
            quickbooks_status = qb_service.get_connection_status()
        except Exception:
            quickbooks_status = {'connected': False, 'status': 'service_unavailable'}
        
        context.update({
            'page_title': 'Finance Settings',
            'quickbooks_status': quickbooks_status,
            'currency_config': getattr(school, 'currency_configuration', None)
        })
        
        return context


class FinanceReportsView(TemplateView):
    """Finance reports and analytics view"""
    template_name = 'core/finance/reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        # Get financial summary data
        from core.services.finance_service import FinanceService
        finance_service = FinanceService(school)
        
        context.update({
            'page_title': 'Finance Reports',
            'financial_summary': finance_service.get_financial_summary(),
            'available_reports': [
                {'name': 'Fee Collection Report', 'url': 'fee_collection_report'},
                {'name': 'Outstanding Fees Report', 'url': 'outstanding_fees_report'},
                {'name': 'Payment Summary Report', 'url': 'payment_summary_report'},
                {'name': 'Transaction Analysis', 'url': 'transaction_analysis_report'},
                {'name': 'QuickBooks Sync Report', 'url': 'quickbooks_sync_report'}
            ]
        })
        
        return context


@require_http_methods(["GET"])
@login_required
def student_academic_report_api(request, student_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        student_service = StudentService(tenant)
        currency_service = CurrencyService(tenant)
        student = student_service.get_by_id(student_id)
        
        # Get academic data
        from .models import BatchStudent
        current_batch = None
        academic_history = []
        
        try:
            # Get current active batch
            current_batch = BatchStudent.objects.filter(
                tenant=tenant,
                student=student
            ).select_related('batch').first()
            
            # Get all batch history for this student
            academic_history = BatchStudent.objects.filter(
                tenant=tenant,
                student=student
            ).select_related('batch', 'batch__course').order_by('-batch__start_date')
        except BatchStudent.DoesNotExist:
            pass
        
        context = {
            'student': student,
            'current_batch': current_batch,
            'academic_history': academic_history,
            'request': request,
        }
        context.update(currency_service.get_currency_context())
        
        html = render_to_string('core/htmx/reports/academic_report.html', context, request=request)
        return HttpResponse(html)
        
    except ServiceException as e:
        return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')


@require_http_methods(["GET"])
@login_required
def student_attendance_report_api(request, student_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        student_service = StudentService(tenant)
        attendance_service = AttendanceService(tenant)
        currency_service = CurrencyService(tenant)
        student = student_service.get_by_id(student_id)

        # Get the student's current active batch
        current_batch = student.student_batches.filter(is_active=True).select_related('batch__academic_year').first()

        # Read optional term_id from query params
        term_id = request.GET.get('term_id')
        selected_term = None
        available_terms = []

        # Determine the date range for the attendance report
        if current_batch and current_batch.batch.academic_year:
            # Fetch available terms
            available_terms = list(Term.objects.filter(tenant=tenant, academic_year=current_batch.batch.academic_year).order_by('order'))

            # If a specific term_id was requested, find it
            if term_id and available_terms:
                try:
                    selected_term = next((t for t in available_terms if str(t.id) == term_id), None)
                except (ValueError, StopIteration):
                    selected_term = None

            # If no valid term_id was given or found, resolve the current/nearest term
            if not selected_term:
                selected_term = ReportGenerationService.resolve_current_term(current_batch.batch.academic_year)

            # Use the term's date range
            if selected_term:
                start_date = selected_term.start_date
                end_date = selected_term.end_date
            else:
                # Fallback to 30-day window if no term exists
                from datetime import timedelta
                end_date = date.today()
                start_date = end_date - timedelta(days=30)
        else:
            # Fallback to 30-day window if no batch or academic year
            from datetime import timedelta
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

        # Get attendance data, scoped to current batch
        attendance_summary = None
        recent_attendance = []

        try:
            report_data = attendance_service.get_student_attendance_report(
                student_id=student_id,
                start_date=start_date,
                end_date=end_date,
                batch_id=str(current_batch.batch_id) if current_batch else None
            )
            attendance_summary = {
                'present_days': report_data.get('present_days', 0),
                'absent_days': report_data.get('absent_days', 0),
                'total_days': report_data.get('total_days', 0),
                'attendance_percentage': report_data.get('attendance_percentage', 0),
            }
            recent_attendance = report_data.get('attendance_records', [])
        except Exception:
            pass

        # Build the response with OOB swap for the summary boxes
        context = {
            'student': student,
            'attendance_summary': attendance_summary,
            'recent_attendance': recent_attendance,
            'selected_term': selected_term,
            'request': request,
        }
        context.update(currency_service.get_currency_context())

        # Render the summary boxes with OOB swap
        summary_html = render_to_string('core/htmx/reports/_attendance_summary_boxes.html', {
            'attendance_summary': attendance_summary,
            'oob': True
        }, request=request)

        # Render the main attendance report
        report_html = render_to_string('core/htmx/reports/attendance_report.html', context, request=request)

        # Combine both responses (OOB + main)
        combined_html = summary_html + report_html
        return HttpResponse(combined_html)

    except ServiceException as e:
        return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')


@require_http_methods(["GET"])
@login_required
def student_fee_report_api(request, student_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .services.finance_service import FinanceService
        from .models import FeeParticular, FeeDiscount, FineSlab, FeeCategory, BatchFeeCategory
        from datetime import date
        from decimal import Decimal
        
        student_service = StudentService(tenant)
        finance_service = FinanceService(tenant)
        currency_service = CurrencyService(tenant)
        
        student = student_service.get_by_id(student_id)
        
        # Get current batch to determine fee categories
        from .models import BatchStudent
        current_batch = None
        try:
            current_batch = BatchStudent.objects.filter(
                tenant=tenant,
                student=student
            ).select_related('batch').first()
        except BatchStudent.DoesNotExist:
            pass
        
        # Get fee particulars for the student
        fee_particulars = []
        current_fee_category = None
        current_fee_collection = None
        
        if current_batch:
            # Get batch fee categories
            batch_fee_categories = BatchFeeCategory.objects.filter(
                tenant=tenant,
                batch=current_batch.batch
            ).select_related('fee_category')
            
            if batch_fee_categories.exists():
                batch_fee_category = batch_fee_categories.first()
                current_fee_category = batch_fee_category.fee_category
                current_fee_collection = batch_fee_category
                
                # Get fee particulars for this category
                fee_particulars = FeeParticular.objects.filter(
                    tenant=tenant,
                    fee_category=current_fee_category,
                    is_active=True
                )
        
        # Calculate fee summary
        total_fees = sum(particular.amount for particular in fee_particulars) or Decimal('0.00')
        if not fee_particulars and current_batch:
            # Fallback to basic fee amount if no particulars exist
            fee_balance = finance_service.get_student_fee_balance(student_id)
            total_fees = abs(fee_balance) if fee_balance else Decimal('0.00')
        
        # Get existing payments
        fee_payments = []
        amount_paid = Decimal('0.00')
        
        try:
            fee_payments = finance_service.get_student_fee_history(student_id)
            amount_paid = sum(
                abs(payment.amount) for payment in fee_payments 
                if hasattr(payment, 'amount') and payment.amount < 0  # Payments are negative
            ) or Decimal('0.00')
        except Exception:
            pass
        
        # Calculate discounts (for now, default to 0)
        total_discount = Decimal('0.00')
        
        # Calculate totals
        amount_to_pay = total_fees - total_discount
        due_amount = amount_to_pay - amount_paid
        
        context = {
            'student': student,
            'current_batch': current_batch,
            'current_fee_category': current_fee_category,
            'current_fee_collection': current_fee_collection,
            'fee_particulars': fee_particulars,
            'total_fees': total_fees,
            'total_discount': total_discount,
            'amount_to_pay': amount_to_pay,
            'amount_paid': amount_paid,
            'due_amount': due_amount,
            'fee_balance': due_amount,  # Keep for backward compatibility
            'today': date.today(),
            'request': request,
        }
        context.update(currency_service.get_currency_context())
        
        html = render_to_string('core/htmx/reports/fee_report.html', context, request=request)
        return HttpResponse(html)
        
    except ServiceException as e:
        return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')
    except Exception as e:
        return HttpResponse(f'<div class="alert alert-danger">Unexpected error: {str(e)}</div>')


@require_http_methods(["POST"])
@login_required
def add_fee_particular_api(request, student_id):
    """Add a new fee particular for a student"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        from .models import FeeParticular, FeeCategory
        import json
        from decimal import Decimal
        
        data = json.loads(request.body)
        particular_name = data.get('name')
        amount = Decimal(str(data.get('amount', '0.00')))
        
        if not particular_name or amount <= 0:
            return JsonResponse({'error': 'Name and amount are required'}, status=400)
        
        from .models import FeeApplicabilityRule

        student_service = StudentService(tenant)
        student = student_service.get_by_id(student_id)

        # Get or create a default fee category for custom particulars
        fee_category, created = FeeCategory.objects.get_or_create(
            tenant=tenant,
            name='Custom Fees',
            defaults={'description': 'Custom fee particulars added individually'}
        )

        # Create targeting rule for this specific student
        rule = FeeApplicabilityRule.objects.create(
            tenant=tenant,
            rule_type='individual_student',
            student=student,
            is_active=True
        )

        # Create the particular
        particular = FeeParticular.objects.create(
            tenant=tenant,
            name=particular_name,
            amount=amount,
            fee_category=fee_category,
            applicability_rule=rule
        )
        
        return JsonResponse({
            'success': True,
            'particular': {
                'id': str(particular.id),
                'name': particular.name,
                'amount': float(particular.amount)
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def add_fee_discount_api(request, student_id):
    """Add a discount for a student's fees"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        import json
        from decimal import Decimal
        
        data = json.loads(request.body)
        discount_name = data.get('name')
        discount_mode = data.get('mode', 'amount')  # 'amount' or 'percentage'
        discount_value = Decimal(str(data.get('value', '0.00')))
        
        if not discount_name or discount_value <= 0:
            return JsonResponse({'error': 'Name and value are required'}, status=400)
        
        # For now, return success but implement actual discount logic later
        return JsonResponse({
            'success': True,
            'discount': {
                'name': discount_name,
                'mode': discount_mode,
                'value': float(discount_value)
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def add_fee_fine_api(request, student_id):
    """Add a fine for a student's fees"""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        import json
        from decimal import Decimal
        
        data = json.loads(request.body)
        fine_amount = Decimal(str(data.get('amount', '0.00')))
        
        if fine_amount <= 0:
            return JsonResponse({'error': 'Fine amount must be greater than 0'}, status=400)
        
        # For now, return success but implement actual fine logic later
        return JsonResponse({
            'success': True,
            'fine': {
                'amount': float(fine_amount),
                'reason': 'Late payment fine'
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def student_profile_report_api(request, student_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        student_service = StudentService(tenant)
        attendance_service = AttendanceService(tenant)
        currency_service = CurrencyService(tenant)
        student = student_service.get_by_id(student_id)

        # Get comprehensive student data
        from .models import BatchStudent
        current_batch = None
        attendance_summary = None

        try:
            # Get current active batch (must filter by is_active)
            current_batch = BatchStudent.objects.filter(
                tenant=tenant,
                student=student,
                is_active=True
            ).select_related('batch').first()

            # Get attendance summary scoped to current batch
            from datetime import timedelta
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            report_data = attendance_service.get_student_attendance_report(
                student_id=student_id,
                start_date=start_date,
                end_date=end_date,
                batch_id=str(current_batch.batch_id) if current_batch else None
            )
            attendance_summary = {
                'present_days': report_data.get('present_days', 0),
                'absent_days': report_data.get('absent_days', 0),
                'attendance_percentage': report_data.get('attendance_percentage', 0),
            }
        except Exception:
            pass
        
        from .services.finance_service import FinanceService
        finance_service = FinanceService(tenant)
        fee_balance = finance_service.get_student_fee_balance(student_id)

        # Parents / guardians (immediate contact first)
        from .models import StudentGuardianRelation
        guardian_relations = (
            StudentGuardianRelation.objects.filter(tenant=tenant, student=student)
            .select_related('guardian', 'guardian__country')
            .order_by('-is_immediate_contact', 'guardian__first_name')
        )

        # Calculate age
        age = None
        if student.date_of_birth:
            from datetime import date
            today = date.today()
            age = today.year - student.date_of_birth.year - ((today.month, today.day) < (student.date_of_birth.month, student.date_of_birth.day))

        context = {
            'student': student,
            'current_batch': current_batch,
            'attendance_summary': attendance_summary,
            'fee_balance': fee_balance,
            'guardian_relations': guardian_relations,
            'age': age,
            'request': request,
        }
        context.update(currency_service.get_currency_context())
        
        html = render_to_string('core/htmx/reports/profile_report.html', context, request=request)
        return HttpResponse(html)
        
    except ServiceException as e:
        return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')


# Subject Center Views
@method_decorator(login_required, name='dispatch')
class SubjectsCenterView(HTMXResponseMixin, TemplateView):
    """Subject Center view with subjects, skill sets, and elective groups management"""
    template_name = 'core/subjects/center.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        
        from .models import SkillSet, ElectiveGroup
        
        # Get all subjects with their relationships
        subjects = Subject.objects.filter(
            tenant=tenant,
            is_deleted=False
        ).select_related('batch', 'elective_group').order_by('name')
        
        # Get all skill sets
        skill_sets = SkillSet.objects.filter(tenant=tenant).order_by('name')
        
        # Get all elective groups with subject counts
        elective_groups = ElectiveGroup.objects.filter(
            tenant=tenant,
            is_deleted=False
        ).select_related('batch').prefetch_related('subjects').order_by('name')
        
        # Get all batches for forms
        batches = Batch.objects.filter(tenant=tenant, is_active=True).order_by('name')
        
        context.update({
            'subjects': subjects,
            'subjects_count': subjects.count(),
            'skill_sets': skill_sets,
            'skill_sets_count': skill_sets.count(),
            'elective_groups': elective_groups,
            'elective_groups_count': elective_groups.count(),
            'batches': batches,
        })
        
        return context


class ClassSubjectsView(HTMXResponseMixin, TemplateView):
    """Class Subjects management view"""
    template_name = 'core/subjects/class_subjects.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        from .models import SkillSet

        courses = Course.objects.filter(tenant=tenant, is_deleted=False).order_by('course_name')
        academic_years = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date')

        selected_course_id = self.request.GET.get('class')
        selected_year_id = self.request.GET.get('year')
        selected_course = None
        subjects = Subject.objects.none()

        # Default to the active academic year when none is selected
        active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
        selected_year = None
        if selected_year_id:
            selected_year = academic_years.filter(id=selected_year_id).first()
        if not selected_year:
            selected_year = active_year

        if selected_course_id:
            try:
                selected_course = Course.objects.get(
                    id=selected_course_id, tenant=tenant, is_deleted=False
                )
                # Filter by course + academic year to avoid showing all years at once
                qs = Subject.objects.filter(
                    tenant=tenant,
                    is_deleted=False,
                    batch__course=selected_course,
                )
                if selected_year:
                    qs = qs.filter(batch__academic_year=selected_year)

                subjects = (
                    qs.select_related('batch', 'batch__academic_year', 'elective_group')
                    .prefetch_related('skill_sets__skill_set')
                    .distinct()
                    .order_by('name')
                )
            except Course.DoesNotExist:
                pass

        skill_sets = SkillSet.objects.filter(tenant=tenant).order_by('name')

        # A subject can live on several sections (batches) of the same class.
        # Collapse those per-batch rows into one row per subject (name + code) so
        # the list shows each subject once, with how many sections carry it.
        sections = []
        if selected_course:
            sect_qs = Batch.objects.filter(
                tenant=tenant, course=selected_course, is_active=True, is_deleted=False,
            )
            if selected_year:
                sect_qs = sect_qs.filter(academic_year=selected_year)
            sections = list(sect_qs.order_by('name'))
        total_sections = len(sections)

        from collections import OrderedDict
        groups = OrderedDict()
        for s in subjects:
            key = ((s.name or '').strip().lower(), (s.code or '').strip().lower())
            g = groups.get(key)
            if g is None:
                first_link = s.skill_sets.all()[0] if s.skill_sets.all() else None
                g = {
                    'name': s.name,
                    'code': s.code,
                    'no_exams': s.no_exams,
                    'max_weekly_classes': s.max_weekly_classes,
                    'skill_set_id': str(first_link.skill_set_id) if first_link else '',
                    'representative_id': str(s.id),
                    'subject_ids': [],
                    'section_count': 0,
                    'batches': [],
                }
                groups[key] = g
            g['subject_ids'].append(str(s.id))
            g['section_count'] += 1
            g['batches'].append({'id': str(s.batch_id), 'name': s.batch.name, 'subject_id': str(s.id)})
        subject_groups = list(groups.values())
        for g in subject_groups:
            g['subject_ids_csv'] = ','.join(g['subject_ids'])

        context.update({
            'courses': courses,
            'academic_years': academic_years,
            'selected_course': selected_course,
            'selected_year': selected_year,
            'subjects': subjects,
            'subject_groups': subject_groups,
            'sections': sections,
            'total_sections': total_sections,
            'skill_sets': skill_sets,
        })

        return context


@method_decorator(login_required, name='dispatch')
class SkillSetsListView(HTMXResponseMixin, ListView):
    """Subject Skill Sets list view"""
    template_name = 'core/subjects/skill_sets_list.html'
    htmx_template_name = 'core/htmx/skill_sets_list_content.html'
    context_object_name = 'skill_sets'
    paginate_by = 10

    def get_queryset(self):
        tenant = self.request.tenant
        from .models import SkillSet, Skill
        from django.db.models import Count

        # Get all skill sets with skill counts
        skill_sets = SkillSet.objects.filter(
            tenant=tenant
        ).annotate(
            skills_count=Count('skills')
        ).order_by('name')

        return skill_sets

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class SkillSetDetailView(HTMXResponseMixin, DetailView):
    """Individual skillset management view"""
    template_name = 'core/subjects/skillset_detail.html'
    htmx_template_name = 'core/htmx/skillset_detail_content.html'
    context_object_name = 'skill_set'
    
    def get_object(self):
        tenant = getattr(self.request, 'tenant', None)
        skill_set_id = self.kwargs.get('pk')
        
        if not tenant or not skill_set_id:
            raise Http404("Skillset not found")
        
        from .models import SkillSet
        try:
            return SkillSet.objects.get(id=skill_set_id, tenant=tenant)
        except SkillSet.DoesNotExist:
            raise Http404("Skillset not found")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        skill_set = self.object
        
        from .models import Skill
        
        # Get all skills for this skillset
        skills = Skill.objects.filter(
            skill_set=skill_set,
            tenant=self.request.tenant,
            is_active=True
        ).prefetch_related('sub_skills').order_by('order', 'name')
        
        context.update({
            'skills': skills,
            'skills_count': skills.count(),
        })
        
        return context


@method_decorator(login_required, name='dispatch')
class LinkBatchesView(HTMXResponseMixin, TemplateView):
    """Link batches to course subjects"""
    template_name = 'core/subjects/link_batches.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        # Get all courses for dropdown
        courses = Course.objects.filter(tenant=tenant, is_deleted=False).order_by('course_name')

        # Get selected course from query parameters
        selected_course_id = self.request.GET.get('class')
        selected_course = None
        subjects_data = []

        selected_year_id = self.request.GET.get('year')
        academic_years = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date')
        active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
        selected_year = academic_years.filter(id=selected_year_id).first() if selected_year_id else active_year

        if selected_course_id:
            try:
                selected_course = Course.objects.get(
                    id=selected_course_id,
                    tenant=tenant,
                    is_deleted=False
                )

                # All batches of this course for the selected year
                batches = Batch.objects.filter(
                    course=selected_course,
                    tenant=tenant,
                    is_active=True,
                ).order_by('name')
                if selected_year:
                    batches = batches.filter(academic_year=selected_year)

                # Build a lookup: (name, code) → set of batch_ids that have that subject
                all_subjects_qs = Subject.objects.filter(
                    tenant=tenant,
                    is_deleted=False,
                    batch__in=batches,
                ).select_related('batch').order_by('name')

                # Deduplicate by (name, code) — keep one representative Subject per pair
                seen = {}
                allocated_map = {}  # (name, code) → set of batch_ids
                for subj in all_subjects_qs:
                    key = (subj.name, subj.code)
                    if key not in seen:
                        seen[key] = subj
                        allocated_map[key] = set()
                    allocated_map[key].add(subj.batch_id)

                batch_list = list(batches)
                total = len(batch_list)
                for key, representative in seen.items():
                    assigned_ids = allocated_map[key]
                    batch_data_list = [
                        {'batch': b, 'is_allocated': b.id in assigned_ids}
                        for b in batch_list
                    ]
                    subjects_data.append({
                        'subject': representative,
                        'assigned_count': len(assigned_ids),
                        'total_count': total,
                        'all_allocated': len(assigned_ids) == total,
                        'batches': batch_data_list,
                    })

            except Course.DoesNotExist:
                pass

        context.update({
            'courses': courses,
            'academic_years': academic_years,
            'selected_year': selected_year,
            'selected_course': selected_course,
            'subjects_data': subjects_data,
        })

        return context


@login_required
def get_subject_api(request, subject_id):
    """API endpoint to fetch a single subject for editing"""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        tenant = request.tenant
        subject = Subject.objects.get(id=subject_id, tenant=tenant, is_deleted=False)
        return JsonResponse({
            'success': True,
            'id': str(subject.id),
            'name': subject.name,
            'code': subject.code,
            'batch': str(subject.batch.id),
            'max_weekly_classes': subject.max_weekly_classes,
            'credit_hours': subject.credit_hours,
            'amount': subject.amount,
            'no_exams': subject.no_exams,
            'language': subject.language,
            'prefer_consecutive': subject.prefer_consecutive,
        })
    except Subject.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Subject not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def create_subject_api(request):
    """API endpoint to create a new subject"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        from .models import SkillSet, SubjectSkillSet

        # Get form data
        subject_name = request.POST.get('subject_name', '').strip()
        subject_code = request.POST.get('subject_code', '').strip()
        weekly_classes = request.POST.get('weekly_classes')
        skill_set_id = request.POST.get('skill_set_id')
        no_exams = request.POST.get('no_exams') == 'on'
        # `batch_id` is the selected Class (Course) id from the class_subjects page,
        # `year` is the selected academic year. The subject must be created on a batch
        # of that course/year, otherwise it won't match the page's filter and will
        # appear to "fail" silently.
        course_id = request.POST.get('batch_id')
        year_id = request.POST.get('year')

        if not subject_name or not subject_code:
            return JsonResponse({'success': False, 'error': 'Subject name and code are required'})

        if not course_id:
            return JsonResponse({'success': False, 'error': 'Please select a class first'})

        try:
            course = Course.objects.get(id=course_id, tenant=tenant, is_deleted=False)
        except Course.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Selected class not found'})

        # Resolve academic year: explicit selection, else the active year.
        selected_year = None
        if year_id:
            selected_year = AcademicYear.objects.filter(id=year_id, tenant=tenant).first()
        if not selected_year:
            selected_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()

        # The clerk selects which sections (batches) of the class get this subject
        # — batches in the same class may legitimately carry different subjects.
        selected_batch_ids = [b for b in request.POST.getlist('batch_ids') if b]
        target_qs = Batch.objects.filter(
            tenant=tenant, course=course, is_active=True, is_deleted=False,
        )
        if selected_year:
            target_qs = target_qs.filter(academic_year=selected_year)
        if selected_batch_ids:
            target_qs = target_qs.filter(id__in=selected_batch_ids)
        target_batches = list(target_qs.order_by('name'))

        if not selected_batch_ids:
            return JsonResponse({
                'success': False,
                'error': 'Please select at least one section/batch to add this subject to.',
            })
        if not target_batches:
            return JsonResponse({
                'success': False,
                'error': 'No matching section/batch found for the selected class and academic year',
            })

        skill_set = None
        if skill_set_id:
            skill_set = SkillSet.objects.filter(id=skill_set_id, tenant=tenant).first()

        created = 0
        skipped = 0
        first_subject_id = None
        for batch in target_batches:
            # Skip a section that already has this subject (by code).
            if Subject.objects.filter(
                tenant=tenant, code=subject_code, is_deleted=False, batch=batch,
            ).exists():
                skipped += 1
                continue

            subject = Subject.objects.create(
                tenant=tenant,
                name=subject_name,
                code=subject_code,
                batch=batch,
                no_exams=no_exams,
                max_weekly_classes=int(weekly_classes) if weekly_classes else None,
            )
            first_subject_id = first_subject_id or str(subject.id)
            if skill_set:
                SubjectSkillSet.objects.create(
                    tenant=tenant, subject=subject, skill_set=skill_set,
                )
            created += 1

        if created == 0:
            return JsonResponse({
                'success': False,
                'error': 'This subject already exists in the selected section(s).',
            })

        return JsonResponse({
            'success': True,
            'subject_id': first_subject_id,
            'created': created,
            'skipped': skipped,
            'sections': len(target_batches),
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def update_subject_api(request):
    """API endpoint to update a subject"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        tenant = request.tenant
        from .models import SkillSet, SubjectSkillSet

        # Get subject ID
        subject_id = request.POST.get('subject_id')
        if not subject_id:
            return JsonResponse({'success': False, 'error': 'Subject ID is required'})

        # Get the subject
        try:
            subject = Subject.objects.get(id=subject_id, tenant=tenant)
        except Subject.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Subject not found'})

        # Get form data
        subject_name = request.POST.get('subject_name', '').strip()
        subject_code = request.POST.get('subject_code', '').strip()
        weekly_classes = request.POST.get('weekly_classes')
        skill_set_id = request.POST.get('skill_set_id')
        is_activity = request.POST.get('is_activity') == 'on'
        no_exams = request.POST.get('no_exams') == 'on'
        exclude_for_total_score = request.POST.get('exclude_for_total_score') == 'on'

        if not subject_name:
            return JsonResponse({'success': False, 'error': 'Subject name is required'})

        # Update subject fields
        subject.name = subject_name
        subject.code = subject_code or subject.code
        subject.is_activity = is_activity
        subject.no_exams = no_exams
        subject.exclude_for_total_score = exclude_for_total_score
        subject.weekly_classes = int(weekly_classes) if weekly_classes else None
        subject.save()

        # Update skill set relationship
        SubjectSkillSet.objects.filter(subject=subject, tenant=tenant).delete()
        if skill_set_id:
            try:
                skill_set = SkillSet.objects.get(id=skill_set_id, tenant=tenant)
                SubjectSkillSet.objects.create(
                    tenant=tenant,
                    subject=subject,
                    skill_set=skill_set
                )
            except SkillSet.DoesNotExist:
                pass

        return JsonResponse({'success': True, 'subject_id': str(subject.id)})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def delete_subject_api(request):
    """API endpoint to delete a subject"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        tenant = request.tenant
        import json

        # Parse JSON data
        data = json.loads(request.body)
        subject_id = data.get('subject_id')

        if not subject_id:
            return JsonResponse({'success': False, 'error': 'Subject ID is required'})

        # Get the subject
        try:
            subject = Subject.objects.get(id=subject_id, tenant=tenant)
        except Subject.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Subject not found'})

        # Soft delete the subject
        subject.is_deleted = True
        subject.save()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def copy_subjects_to_class_api(request):
    """Copy one or more subjects (by ID) into batches of another class."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    try:
        tenant = request.tenant
        subject_ids = [s.strip() for s in request.POST.get('subject_ids', '').split(',') if s.strip()]
        target_batch_ids = request.POST.getlist('target_batch_ids')
        if not subject_ids:
            return JsonResponse({'success': False, 'error': 'No subjects specified'})
        if not target_batch_ids:
            return JsonResponse({'success': False, 'error': 'Please select at least one target batch'})

        sources = list(Subject.objects.filter(id__in=subject_ids, tenant=tenant))
        target_batches = list(Batch.objects.filter(id__in=target_batch_ids, tenant=tenant, is_active=True))
        if not sources:
            return JsonResponse({'success': False, 'error': 'Source subjects not found'})
        if not target_batches:
            return JsonResponse({'success': False, 'error': 'Target batches not found'})

        created = skipped = 0
        for source in sources:
            for batch in target_batches:
                if Subject.objects.filter(tenant=tenant, name__iexact=source.name, batch=batch).exists():
                    skipped += 1
                    continue
                Subject.objects.create(
                    tenant=tenant,
                    name=source.name,
                    code=source.code,
                    batch=batch,
                    no_exams=source.no_exams,
                    max_weekly_classes=source.max_weekly_classes,
                    language=source.language,
                )
                created += 1

        if created == 0:
            return JsonResponse({'success': False, 'error': 'Subject already exists in all selected batches — nothing was copied.'})
        msg = f'{created} subject copy/copies created'
        if skipped:
            msg += f'; {skipped} already existed and were skipped'
        return JsonResponse({'success': True, 'message': msg, 'created': created, 'skipped': skipped})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_class_batches_api(request):
    """Return active batches for a course (used by the copy-to-class modal)."""
    tenant = request.tenant
    course_id = request.GET.get('course_id')
    if not course_id:
        return JsonResponse({'batches': []})
    qs = Batch.objects.filter(tenant=tenant, course_id=course_id, is_active=True).order_by('name')
    return JsonResponse({'batches': [{'id': str(b.id), 'name': b.name} for b in qs]})


@login_required
def create_subject_group_api(request):
    """API endpoint to create a subject group"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        tenant = request.tenant
        from .models import SubjectGroup

        # Get form data
        group_name = request.POST.get('subject_group_name', '').strip()
        calculation_method = request.POST.get('calculation_method', 'calculate')

        if not group_name:
            return JsonResponse({'success': False, 'error': 'Subject group name is required'})

        # Create subject group
        subject_group = SubjectGroup.objects.create(
            tenant=tenant,
            name=group_name,
            calculate_total=calculation_method == 'calculate'
        )

        return JsonResponse({'success': True, 'group_id': str(subject_group.id)})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def create_skill_set_api(request):
    """API endpoint to create a new skill set"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        from .models import SkillSet
        
        # Get form data
        skill_set_name = request.POST.get('skill_set_name', '').strip()
        skill_set_code = request.POST.get('skill_set_code', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not skill_set_name or not skill_set_code:
            return JsonResponse({'success': False, 'error': 'Skill set name and code are required'})
        
        # Check if code already exists
        if SkillSet.objects.filter(tenant=tenant, code=skill_set_code).exists():
            return JsonResponse({'success': False, 'error': 'Skill set code already exists'})
        
        # Create skill set
        skill_set = SkillSet.objects.create(
            tenant=tenant,
            name=skill_set_name,
            code=skill_set_code,
            is_active=is_active
        )
        
        return JsonResponse({'success': True, 'skill_set_id': str(skill_set.id)})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def create_skill_api(request):
    """API endpoint to create a new skill"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        from .models import Skill, SkillSet
        
        # Get form data
        skill_set_id = request.POST.get('skill_set_id', '').strip()
        skill_name = request.POST.get('skill_name', '').strip()
        formula = request.POST.get('formula', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not skill_set_id or not skill_name:
            return JsonResponse({'success': False, 'error': 'Skill set and name are required'})
        
        # Get the skillset
        try:
            skill_set = SkillSet.objects.get(id=skill_set_id, tenant=tenant)
        except SkillSet.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid skill set'})
        
        # Get next order
        last_skill = Skill.objects.filter(skill_set=skill_set, tenant=tenant).order_by('-order').first()
        next_order = (last_skill.order + 1) if last_skill else 1
        
        # Create skill
        skill = Skill.objects.create(
            tenant=tenant,
            skill_set=skill_set,
            name=skill_name,
            formula=formula or None,
            description=description or None,
            order=next_order
        )
        
        return JsonResponse({
            'success': True, 
            'skill_id': str(skill.id),
            'skill_name': skill.name,
            'order': skill.order
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def create_sub_skill_api(request):
    """API endpoint to create a new sub-skill"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        from .models import SubSkill, Skill
        
        # Get form data
        skill_id = request.POST.get('skill_id', '').strip()
        sub_skill_name = request.POST.get('sub_skill_name', '').strip()
        formula = request.POST.get('formula', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not skill_id or not sub_skill_name:
            return JsonResponse({'success': False, 'error': 'Skill and name are required'})
        
        # Get the skill
        try:
            skill = Skill.objects.get(id=skill_id, tenant=tenant)
        except Skill.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid skill'})
        
        # Get next order
        last_sub_skill = SubSkill.objects.filter(skill=skill, tenant=tenant).order_by('-order').first()
        next_order = (last_sub_skill.order + 1) if last_sub_skill else 1
        
        # Create sub-skill
        sub_skill = SubSkill.objects.create(
            tenant=tenant,
            skill=skill,
            name=sub_skill_name,
            formula=formula or None,
            description=description or None,
            order=next_order
        )
        
        return JsonResponse({
            'success': True, 
            'sub_skill_id': str(sub_skill.id),
            'sub_skill_name': sub_skill.name,
            'order': sub_skill.order
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def update_skill_api(request):
    """API endpoint to update a skill"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        from .models import Skill
        
        skill_id = request.POST.get('skill_id', '').strip()
        skill_name = request.POST.get('skill_name', '').strip()
        formula = request.POST.get('formula', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not skill_id or not skill_name:
            return JsonResponse({'success': False, 'error': 'Skill ID and name are required'})
        
        try:
            skill = Skill.objects.get(id=skill_id, tenant=tenant)
        except Skill.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid skill'})
        
        skill.name = skill_name
        skill.formula = formula or None
        skill.description = description or None
        skill.save()
        
        return JsonResponse({'success': True, 'skill_name': skill.name})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def delete_skill_api(request):
    """API endpoint to delete a skill"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        from .models import Skill
        
        skill_id = request.POST.get('skill_id', '').strip()
        
        if not skill_id:
            return JsonResponse({'success': False, 'error': 'Skill ID is required'})
        
        try:
            skill = Skill.objects.get(id=skill_id, tenant=tenant)
        except Skill.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid skill'})
        
        skill.is_active = False
        skill.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def create_elective_group_api(request):
    """API endpoint to create a new elective group"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        from .models import ElectiveGroup
        
        # Get form data
        elective_group_name = request.POST.get('elective_group_name', '').strip()
        allow_floating_subjects = request.POST.get('allow_floating_subjects') == 'on'
        
        if not elective_group_name:
            return JsonResponse({'success': False, 'error': 'Elective group name is required'})
        
        # Get default batch (you might want to make this configurable)
        batch = Batch.objects.filter(tenant=tenant, is_active=True).first()
        if not batch:
            return JsonResponse({'success': False, 'error': 'No active batch found'})
        
        # Create elective group
        elective_group = ElectiveGroup.objects.create(
            tenant=tenant,
            name=elective_group_name,
            batch=batch
        )
        
        return JsonResponse({'success': True, 'elective_group_id': str(elective_group.id)})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def import_subjects_api(request):
    """API endpoint to import subjects from predefined list"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        
        # Get form data
        import_class_id = request.POST.get('import_class')
        selected_subjects = request.POST.getlist('subjects[]')
        
        if not import_class_id:
            return JsonResponse({'success': False, 'error': 'Class selection is required'})
        
        if not selected_subjects:
            return JsonResponse({'success': False, 'error': 'Please select at least one subject'})
        
        # Get the batch
        try:
            batch = Batch.objects.get(id=import_class_id, tenant=tenant)
        except Batch.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Selected class not found'})
        
        # Import subjects
        created_count = 0
        for subject_code in selected_subjects:
            # Convert code to name (basic transformation)
            subject_name = subject_code.replace('_', ' ').title()
            
            # Check if subject already exists
            if not Subject.objects.filter(
                tenant=tenant, 
                batch=batch, 
                code=subject_code.upper()
            ).exists():
                Subject.objects.create(
                    tenant=tenant,
                    name=subject_name,
                    code=subject_code.upper(),
                    batch=batch
                )
                created_count += 1
        
        return JsonResponse({
            'success': True, 
            'message': f'{created_count} subjects imported successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def link_batches_save_api(request):
    """API endpoint to save batch-subject assignments"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        tenant = request.tenant
        import json

        # Get form data
        course_id = request.POST.get('course_id')
        assignments_json = request.POST.get('assignments', '[]')
        removals_json = request.POST.get('removals', '[]')

        if not course_id:
            return JsonResponse({'success': False, 'error': 'Course ID is required'})

        # Parse JSON
        assignments = json.loads(assignments_json)
        removals = json.loads(removals_json)

        # Get the course
        try:
            course = Course.objects.get(id=course_id, tenant=tenant)
        except Course.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Course not found'})

        # Process assignments (create subjects for batches)
        for assignment in assignments:
            subject_id = assignment.get('subject_id')
            batch_id = assignment.get('batch_id')

            # Get the template subject
            try:
                template_subject = Subject.objects.get(id=subject_id, tenant=tenant)
            except Subject.DoesNotExist:
                continue

            # Get the batch
            try:
                batch = Batch.objects.get(id=batch_id, tenant=tenant, course=course)
            except Batch.DoesNotExist:
                continue

            # Check if subject already exists for this batch
            existing = Subject.objects.filter(
                tenant=tenant,
                batch=batch,
                name=template_subject.name,
                code=template_subject.code
            ).first()

            if not existing:
                # Create new subject for this batch
                Subject.objects.create(
                    tenant=tenant,
                    name=template_subject.name,
                    code=template_subject.code,
                    batch=batch,
                    no_exams=template_subject.no_exams,
                    max_weekly_classes=template_subject.max_weekly_classes,
                    elective_group=template_subject.elective_group
                )

        # Process removals (delete subjects from batches)
        for removal in removals:
            subject_id = removal.get('subject_id')
            batch_id = removal.get('batch_id')

            # Get the template subject
            try:
                template_subject = Subject.objects.get(id=subject_id, tenant=tenant)
            except Subject.DoesNotExist:
                continue

            # Delete subjects matching this template for the specified batch
            Subject.objects.filter(
                tenant=tenant,
                batch_id=batch_id,
                name=template_subject.name,
                code=template_subject.code
            ).update(is_deleted=True)

        return JsonResponse({
            'success': True,
            'message': 'Batch assignments saved successfully'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =====================================================
# HELPER CLASSES
# =====================================================

class TempFileResponse(FileResponse):
    """FileResponse that automatically deletes the underlying temporary file when closed."""
    def __init__(self, tmp_path, *args, **kwargs):
        self.tmp_path = tmp_path
        super().__init__(open(tmp_path, 'rb'), *args, **kwargs)
        
    def close(self):
        super().close()
        try:
            if os.path.exists(self.tmp_path):
                os.remove(self.tmp_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file {self.tmp_path}: {e}")


# =====================================================
# REPORT MANAGEMENT VIEWS
# =====================================================

def _filter_reports_qs(tenant, *, batch=None, exam_group=None, status=None, year=None):
    """Apply the Generated Reports page filters to a StudentReport queryset.

    Shared by GeneratedReportsView (page rendering) and the ZIP enqueue API so a
    "select all matching filter" download resolves to exactly the rows the user sees.
    """
    qs = StudentReport.objects.filter(tenant=tenant)
    if batch:      qs = qs.filter(exam_group__batch_id=batch)
    if exam_group: qs = qs.filter(exam_group_id=exam_group)
    if status:     qs = qs.filter(generation_status=status)
    if year:       qs = qs.filter(exam_group__batch__academic_year_id=year)
    return qs


@method_decorator(login_required, name='dispatch')
class GeneratedReportsView(TemplateView):
    """History of all generated student reports with download links."""
    template_name = 'core/reports/generated_reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return context

        batch_id   = self.request.GET.get('batch')
        eg_id      = self.request.GET.get('exam_group')
        status     = self.request.GET.get('status')
        year_id    = self.request.GET.get('year')

        reports_qs = _filter_reports_qs(
            tenant, batch=batch_id, exam_group=eg_id, status=status, year=year_id,
        ).select_related(
            'student', 'template', 'exam_group', 'exam_group__batch',
        ).order_by('-generation_completed_at')

        paginator = Paginator(reports_qs, 20)
        page_obj = paginator.get_page(self.request.GET.get('page', 1))

        context.update({
            'reports': page_obj, 'page_obj': page_obj,
            'batches': Batch.objects.filter(tenant=tenant, is_active=True).order_by('name'),
            'exam_groups': ExamGroup.objects.filter(tenant=tenant).order_by('name'),
            'academic_years': AcademicYear.objects.filter(tenant=tenant).order_by('-start_date'),
            'selected_batch': batch_id, 'selected_eg': eg_id,
            'selected_status': status, 'selected_year': year_id,
            'STATUS_CHOICES': [('completed', 'Completed'), ('failed', 'Failed'), ('generating', 'In Progress'), ('pending', 'Pending')],
        })
        return context


@login_required
@require_http_methods(["POST"])
def bulk_delete_reports_api(request):
    """Hard-delete a list of StudentReport records (and their stored files)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        
    report_ids = body.get('report_ids', [])
    if not report_ids:
        return JsonResponse({'success': False, 'error': 'No report IDs provided'})

    # FIX: Fetch only the paths we need to delete to minimize memory
    reports = StudentReport.objects.filter(
        id__in=report_ids, tenant=tenant
    ).only('id', 'pdf_file_path', 'html_file_path')
    
    paths_to_delete = []
    for r in reports:
        if r.pdf_file_path: paths_to_delete.append(r.pdf_file_path)
        if r.html_file_path: paths_to_delete.append(r.html_file_path)
            
    # FIX: Bulk delete from DB (much faster than looping .delete())
    deleted_count, _ = StudentReport.objects.filter(
        id__in=report_ids, tenant=tenant
    ).delete()
    
    # Delete files from storage
    for path in paths_to_delete:
        try:
            if default_storage.exists(path):
                default_storage.delete(path)
        except Exception as e:
            logger.warning(f"Failed to delete file {path}: {e}")
            
    return JsonResponse({'success': True, 'deleted': deleted_count})


def _check_zip_job_authorization(job, request):
    """Helper to check if user is authorized to access a ZIP job.
    Returns (is_authorized, error_response) tuple."""
    if job.requested_by != request.user and not getattr(request.user, 'is_root', False):
        return False, JsonResponse({'error': 'Unauthorized'}, status=403)
    return True, None


@login_required
@require_http_methods(["POST"])
def enqueue_reports_zip_download_api(request):
    """Enqueue an async task to build a ZIP of selected reports.
    Returns immediately with a job ID for polling."""
    from .models import ReportZipJob
    from .tasks import build_reports_zip_task

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    MAX_ZIP_REPORTS = 2000
    filters = body.get('filters') or {}
    report_ids = body.get('report_ids', [])

    if filters:
        # "Select all matching the current filter" — resolve completed report IDs
        # server-side so the client never has to ship hundreds of UUIDs.
        reports = list(
            _filter_reports_qs(
                tenant,
                batch=filters.get('batch'),
                exam_group=filters.get('exam_group'),
                status=filters.get('status'),
                year=filters.get('year'),
            )
            .filter(generation_status='completed')
            .values_list('id', flat=True)
        )
        if not reports:
            return JsonResponse(
                {'error': 'No completed reports match the selection.'}, status=400
            )
    else:
        if not report_ids:
            return JsonResponse({'success': False, 'error': 'No report IDs provided'}, status=400)

        # Validate all requested reports belong to this tenant and are completed
        reports = list(
            StudentReport.objects.filter(
                id__in=report_ids, tenant=tenant, generation_status='completed'
            ).values_list('id', flat=True)
        )

        if len(reports) != len(report_ids):
            # Some reports were not found or not completed
            return JsonResponse(
                {'error': 'One or more selected reports are not accessible.'},
                status=400
            )

    if len(reports) > MAX_ZIP_REPORTS:
        return JsonResponse(
            {'error': f'Too many reports selected ({len(reports)}). '
                      f'Please narrow the filter to {MAX_ZIP_REPORTS} or fewer.'},
            status=400
        )

    try:
        # Create a job record
        expires_at = timezone.now() + timedelta(hours=24)
        job = ReportZipJob.objects.create(
            tenant=tenant,
            requested_by=request.user,
            total_reports=len(reports),
            expires_at=expires_at,
        )

        # Enqueue the Celery task
        build_reports_zip_task.delay(
            str(tenant.id), str(job.id), [str(rid) for rid in reports]
        )

        return JsonResponse({
            'success': True,
            'job_id': str(job.id),
            'message': 'ZIP build queued',
        }, status=202)

    except Exception as e:
        logger.error(f"Error creating ZIP job: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def reports_zip_status_api(request, job_id):
    """Poll the status of a ZIP build job."""
    from .models import ReportZipJob

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        job = ReportZipJob.objects.get(id=job_id, tenant=tenant)
    except ReportZipJob.DoesNotExist:
        return JsonResponse({'error': 'Job not found'}, status=404)

    # Check authorization using helper
    is_authorized, error_response = _check_zip_job_authorization(job, request)
    if not is_authorized:
        return error_response

    response_data = {
        'job_id': str(job.id),
        'status': job.status,
        'pct': job.pct_complete,
        'total_reports': job.total_reports,
        'processed_reports': job.processed_reports,
    }

    if job.status == 'completed':
        response_data['download_url'] = request.build_absolute_uri(
            f"/api/reports/zip-download/{job.id}/"
        )
    elif job.status == 'failed':
        response_data['error'] = job.error_message

    return JsonResponse(response_data)


@login_required
@require_http_methods(["GET"])
def reports_zip_download_api(request, job_id):
    """Download a finished ZIP file."""
    from .models import ReportZipJob

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        job = ReportZipJob.objects.get(id=job_id, tenant=tenant, status='completed')
    except ReportZipJob.DoesNotExist:
        return JsonResponse({'error': 'Job not found or not completed'}, status=404)

    # Check authorization using helper
    is_authorized, error_response = _check_zip_job_authorization(job, request)
    if not is_authorized:
        return error_response

    if not job.file_path or not default_storage.exists(job.file_path):
        return JsonResponse({'error': 'ZIP file not found in storage'}, status=404)

    try:
        file_obj = default_storage.open(job.file_path, 'rb')
        response = FileResponse(file_obj, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="reports.zip"'
        return response
    except Exception as e:
        logger.error(f"Error downloading ZIP {job_id}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def bulk_download_reports_zip_api(request):
    """[DEPRECATED] Stream selected completed reports as a ZIP archive (synchronous).
    This endpoint performs ZIP generation synchronously and is kept for backwards compatibility only.
    New code should use enqueue_reports_zip_download_api + reports_zip_status_api + reports_zip_download_api
    (async Celery flow with polling) instead."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    report_ids = body.get('report_ids', [])
    if not report_ids:
        return JsonResponse({'success': False, 'error': 'No report IDs provided'})

    reports = StudentReport.objects.filter(
        id__in=report_ids, tenant=tenant, generation_status='completed'
    ).select_related('student').only(
        'id', 'pdf_file_path',
        'student__admission_no', 'student__first_name', 'student__middle_name', 'student__last_name',
    )

    # FIX: Write ZIP to a temporary file on disk to prevent OOM crashes
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
        tmp_path = tmp_zip.name
        
    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for r in reports:
                if r.pdf_file_path:
                    try:
                        with default_storage.open(r.pdf_file_path, 'rb') as f:
                            filename = f'{r.student.admission_no}_{r.student.full_name.replace(" ", "_")}.pdf'
                            zf.writestr(filename, f.read())
                    except Exception as e:
                        logger.warning(f"Failed to add {r.id} to ZIP: {e}")
                        
        # FIX: Use custom response that auto-deletes the temp file after streaming
        response = TempFileResponse(
            tmp_path, content_type='application/zip', as_attachment=True,
            filename='reports.zip'
        )
        return response
        
    except Exception as e:
        # Clean up temp file if an error occurs before returning the response
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        logger.error(f"Error creating ZIP: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to create ZIP archive'}, status=500)


class ReportTemplateListView(LoginRequiredMixin, HTMXResponseMixin, ListView):
    """List view for report templates"""
    template_name = 'core/reports/template_list.html'
    htmx_template_name = 'core/htmx/report_template_list_content.html'
    context_object_name = 'templates'
    paginate_by = 15
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ReportTemplate.objects.none()
        
        queryset = ReportTemplate.objects.filter(
            tenant=tenant
        ).select_related('batch', 'academic_year').order_by('-created_at')
        
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(batch__name__icontains=search_query) |
                Q(term__icontains=search_query)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            from .models import Course
            context['academic_years'] = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date')
            batches = Batch.objects.filter(tenant=tenant, is_deleted=False, is_active=True).select_related('course', 'academic_year').order_by('course__course_name', 'name')
            context['batches'] = batches
            context['courses'] = Course.objects.filter(tenant=tenant, is_deleted=False).order_by('course_name')
            context['grading_scales'] = GradingScale.objects.filter(tenant=tenant, is_active=True).order_by('name')
            context['signatures'] = SchoolSignature.objects.filter(tenant=tenant).order_by('-is_default', 'title', 'name')

            # Embed all batch subjects so the create/edit form can populate the
            # subject-order list client-side without a separate AJAX call.
            subjects_qs = list(Subject.objects.filter(
                tenant=tenant, batch__in=batches
            ).order_by('name').values('id', 'name', 'code', 'batch_id'))

            # Single query: which subject IDs have at least one Exam configured.
            exam_subject_ids = set(
                str(sid) for sid in Exam.objects.filter(
                    tenant=tenant,
                    subject_id__in=[s['id'] for s in subjects_qs],
                ).values_list('subject_id', flat=True).distinct()
            )

            subjects_by_batch: dict = {}
            for s in subjects_qs:
                bid = str(s['batch_id'])
                sid = str(s['id'])
                subjects_by_batch.setdefault(bid, []).append({
                    'id': sid,
                    'name': s['name'],
                    'code': s['code'] or '',
                    'has_exams': sid in exam_subject_ids,
                })
            context['subjects_by_batch_json'] = json.dumps(subjects_by_batch)
        else:
            context['subjects_by_batch_json'] = '{}'

        # Preload all active SkillCategory objects so the form can populate the
        # skill-category ordering list without an extra AJAX request.
        from .models import SkillCategory
        skill_cats = list(
            SkillCategory.objects.filter(tenant=tenant, is_active=True)
            .order_by('display_order', 'name')
            .values('id', 'name')
        )
        context['skill_categories_json'] = json.dumps([
            {'id': str(c['id']), 'name': c['name']} for c in skill_cats
        ])
        return context


class ReportGenerationView(HTMXResponseMixin, TemplateView):
    """View for generating reports"""
    template_name = 'core/reports/generation.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['templates'] = ReportTemplate.objects.filter(tenant=tenant, is_active=True).select_related('batch', 'academic_year').order_by('name')
            context['exam_groups'] = ExamGroup.objects.filter(tenant=tenant, result_published=True).select_related('batch').order_by('-exam_date')
        return context


@login_required
def report_template_preview(request, template_id):
    """Render a report template with sample data so users can see the layout (HTML, no PDF)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return HttpResponse('Tenant not found', status=400)

    template = get_object_or_404(ReportTemplate, id=template_id, tenant=tenant)
    from .services.report_generation_service import ReportGenerationService
    from django.template.loader import render_to_string
    from datetime import date

    svc = ReportGenerationService(tenant=tenant)
    school = svc._get_school_data(template)

    layout = getattr(template, 'layout_type', 'FULL_ACADEMIC') or 'FULL_ACADEMIC'

    sample = {
        'student': {
            'full_name': 'Jane Sample Doe', 'admission_number': 'PW000',
            'class_name': template.batch.name, 'age': '7 years 3 months',
            'class_teachers': [template.batch.employee.full_name] if template.batch.employee else ['—'],
            'average_age_of_grade': 7.2,
        },
        'school': school,
        'template': {
            'name': template.name, 'title': template.report_title,
            'footer_quote': template.footer_quote,
            'primary_color': getattr(template, 'primary_color', '#5a9e2f') or '#5a9e2f',
            'primary_color_light': '#d6efc1',
            'primary_color_dark': '#3f7a23',
            'layout_type': layout,
        },
        'term_info': {'term': template.term, 'academic_year': template.academic_year.name, 'exam_group': f'{template.term} Examinations', 'next_term_start': date.today()},
        'exam_results': [
            {'subject': 'English', 'marks': 78.0, 'percentage': 78, 'grade': 'B', 'is_absent': False, 'attainment': 'B', 'effort': 'A'},
            {'subject': 'Mathematics', 'marks': 91.0, 'percentage': 91, 'grade': 'A', 'is_absent': False, 'attainment': 'A', 'effort': 'A'},
            {'subject': 'Science', 'marks': 64.0, 'percentage': 64, 'grade': 'C', 'is_absent': False, 'attainment': 'C', 'effort': 'B'},
        ],
        'class_averages': {'English': 72, 'Mathematics': 80, 'Science': 67},
        'homework': {'submission': 'Very Good', 'presentation': 'Good', 'effort': 'Very Good'},
        'project_work': {'submission': 'Good', 'presentation': 'Very Good', 'effort': 'Good'},
        'activities': {'clubs': ['Chess Club', 'Drama'], 'sports': ['Football', 'Athletics'], 'other': ['Debate']},
        'attendance': {'days_present': 58, 'days_absent': 2, 'total_days': 60, 'attendance_percentage': 96.7},
        'grading_scale': [
            {'grade': 'A', 'minimum_score': 80, 'description': 'Excellent'},
            {'grade': 'B', 'minimum_score': 65, 'description': 'Good'},
            {'grade': 'C', 'minimum_score': 50, 'description': 'Satisfactory'},
            {'grade': 'D', 'minimum_score': 40, 'description': 'Needs Improvement'},
            {'grade': 'E', 'minimum_score': 0, 'description': 'Fail'},
        ],
        'skills': [
            {'name': 'Language & Literacy', 'skills': [
                {'name': 'Listening', 'level': 'SATISFACTORY'},
                {'name': 'Speaking', 'level': 'GOOD'},
                {'name': 'Reading readiness', 'level': 'BEGINNING'},
                {'name': 'Writing readiness', 'level': 'NOT_YET'},
            ]},
            {'name': 'Numeracy', 'skills': [
                {'name': 'Number recognition', 'level': 'GOOD'},
                {'name': 'Counting', 'level': 'GOOD'},
                {'name': 'Sorting & matching', 'level': 'SATISFACTORY'},
            ]},
        ],
        'ranking': {'position': 3, 'total_pct': 82.3, 'class_size': 20},
    }

    html_template = svc._get_html_template_name(template)
    html = render_to_string(html_template, {'template': template, 'data': sample})

    return render(request, 'core/reports/report_template_preview.html', {
        'template': template,
        'report_html': html,
    })


@login_required
def create_report_template_api(request):
    """API endpoint to create a new report template"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        from django.utils.dateparse import parse_date
        tenant = request.tenant
        name = request.POST.get('name', '').strip()
        batch_id = request.POST.get('batch_id', '').strip()
        course_id = request.POST.get('course_id', '').strip()
        term = request.POST.get('term', '').strip()
        academic_year_id = request.POST.get('academic_year_id', '').strip()
        apply_to_all = (batch_id == '__all__')

        if not all([name, term, academic_year_id, course_id]):
            return JsonResponse({'success': False, 'error': 'Name, class, term and academic year are required'})
        if not apply_to_all and not batch_id:
            return JsonResponse({'success': False, 'error': 'Select a specific batch or choose "All batches in this class"'})

        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id, tenant=tenant)
        except AcademicYear.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid academic year'})

        if apply_to_all:
            batches = list(Batch.objects.filter(course_id=course_id, tenant=tenant))
            if not batches:
                return JsonResponse({'success': False, 'error': 'No batches found for the selected class'})
        else:
            try:
                single_batch = Batch.objects.get(id=batch_id, tenant=tenant)
            except Batch.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid batch'})
            if ReportTemplate.objects.filter(tenant=tenant, batch=single_batch, term=term, academic_year=academic_year).exists():
                return JsonResponse({'success': False, 'error': 'A template already exists for this batch, term, and academic year'})
            batches = [single_batch]
        
        # Load rc_defaults for fallback
        from .models import Configuration
        rc_keys = ['rc_school_name', 'rc_school_address', 'rc_school_contact', 'rc_school_email', 'rc_school_website', 'rc_report_title', 'rc_footer_quote', 'rc_primary_color', 'rc_section_order', 'rc_layout_type', 'rc_include_exam_scores', 'rc_include_homework_assessment', 'rc_include_project_work', 'rc_include_clubs', 'rc_include_sports', 'rc_include_other_activities', 'rc_include_attendance', 'rc_include_grading_scale']
        rc = {c.config_key: c.config_value for c in Configuration.objects.filter(tenant=tenant, config_key__in=rc_keys)}

        def rc_bool(field, form_value):
            if form_value is not None: return form_value == 'on'
            stored = rc.get(f'rc_{field}')
            return stored != 'false' if stored is not None else True

        primary_color = request.POST.get('primary_color', '').strip() or rc.get('rc_primary_color', '') or '#5a9e2f'
        raw_order = request.POST.get('section_order', '')
        try: section_order = json.loads(raw_order) if raw_order else []
        except Exception: section_order = []
        if not section_order and rc.get('rc_section_order'):
            try: section_order = json.loads(rc['rc_section_order'])
            except Exception: section_order = []

        raw_subject_order = request.POST.get('subject_order', '')
        try: subject_order = json.loads(raw_subject_order) if raw_subject_order else []
        except Exception: subject_order = []

        raw_skill_cat_order = request.POST.get('skill_category_order', '')
        try: skill_category_order = json.loads(raw_skill_cat_order) if raw_skill_cat_order else []
        except Exception: skill_category_order = []

        valid_layouts = {c[0] for c in ReportTemplate.LAYOUT_CHOICES}
        layout_type = request.POST.get('layout_type', '').strip()
        if layout_type not in valid_layouts: layout_type = rc.get('rc_layout_type', ReportTemplate.LAYOUT_FULL)
        if layout_type not in valid_layouts: layout_type = ReportTemplate.LAYOUT_FULL

        from .models import GradingScale as GS
        grading_scale_obj = None
        gs_id = request.POST.get('grading_scale_id', '').strip() or rc.get('rc_grading_scale_id', '')
        if gs_id: grading_scale_obj = GS.objects.filter(id=gs_id, tenant=tenant).first()

        signature_obj = None
        sig_id = request.POST.get('report_signature_id', '').strip()
        if sig_id: signature_obj = SchoolSignature.objects.filter(id=sig_id, tenant=tenant).first()

        # The submitted layout_type (already set by the JS from the scheme or the
        # fallback select) is the authoritative value — do not override it here.

        # Fall back to the model field default so a tenant with null profile fields
        # (address/phone/email) never produces a NOT NULL violation on create.
        def field_default(fname):
            return ReportTemplate._meta.get_field(fname).default

        common_kwargs = dict(
            tenant=tenant, term=term, academic_year=academic_year,
            school_name=request.POST.get('school_name', '').strip() or rc.get('rc_school_name', '') or getattr(tenant, 'name', '') or field_default('school_name'),
            school_address=request.POST.get('school_address', '').strip() or rc.get('rc_school_address', '') or getattr(tenant, 'address_line1', '') or field_default('school_address'),
            school_contact=request.POST.get('school_contact', '').strip() or rc.get('rc_school_contact', '') or getattr(tenant, 'phone', '') or field_default('school_contact'),
            school_email=request.POST.get('school_email', '').strip() or rc.get('rc_school_email', '') or getattr(tenant, 'email', '') or field_default('school_email'),
            school_website=request.POST.get('school_website', '').strip() or rc.get('rc_school_website', '') or str(getattr(tenant, 'website', '') or '') or field_default('school_website'),
            report_title=request.POST.get('report_title', '').strip() or rc.get('rc_report_title', '') or 'ASSESSMENT REPORT',
            footer_quote=request.POST.get('footer_quote', '').strip() or rc.get('rc_footer_quote', '') or field_default('footer_quote'),
            primary_color=primary_color, section_order=section_order, subject_order=subject_order,
            skill_category_order=skill_category_order, layout_type=layout_type,
            report_signature=signature_obj, grading_scale=grading_scale_obj,
            next_term_start=parse_date(request.POST.get('next_term_start', '').strip()) if request.POST.get('next_term_start', '').strip() else None,
            include_exam_scores=rc_bool('include_exam_scores', request.POST.get('include_exam_scores')),
            include_homework_assessment=rc_bool('include_homework_assessment', request.POST.get('include_homework_assessment')),
            include_project_work=rc_bool('include_project_work', request.POST.get('include_project_work')),
            include_clubs=rc_bool('include_clubs', request.POST.get('include_clubs')),
            include_sports=rc_bool('include_sports', request.POST.get('include_sports')),
            include_other_activities=rc_bool('include_other_activities', request.POST.get('include_other_activities')),
            include_attendance=rc_bool('include_attendance', request.POST.get('include_attendance')),
            include_grading_scale=rc_bool('include_grading_scale', request.POST.get('include_grading_scale')),
            include_skills=rc_bool('include_skills', request.POST.get('include_skills')),
        )

        created = []
        skipped = []
        for b in batches:
            batch_name = b.name if apply_to_all else ''
            tpl_name = f'{name} — {batch_name}' if apply_to_all else name
            if ReportTemplate.objects.filter(tenant=tenant, batch=b, term=term, academic_year=academic_year).exists():
                skipped.append(b.name)
                continue
            t = ReportTemplate.objects.create(name=tpl_name, batch=b, **common_kwargs)
            created.append({'id': str(t.id), 'name': t.name})

        if not created:
            return JsonResponse({'success': False, 'error': f'Templates already exist for all selected batches ({", ".join(skipped)})'})

        msg = (f'{len(created)} template(s) created' + (f'; {len(skipped)} skipped (already exist)' if skipped else ''))
        first = created[0]
        return JsonResponse({'success': True, 'template_id': first['id'], 'template_name': first['name'],
                             'created_count': len(created), 'message': msg})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def get_report_template_api(request, template_id):
    """Return a template's field values for pre-populating the edit form."""
    tenant = getattr(request, 'tenant', None)
    if not tenant: return JsonResponse({'error': 'Tenant not found'}, status=400)
    template = get_object_or_404(ReportTemplate, id=template_id, tenant=tenant)
    return JsonResponse({
        'id': str(template.id), 'name': template.name,
        'batch_id': str(template.batch_id),
        'course_id': str(template.batch.course_id) if template.batch_id else '',
        'term': template.term, 'academic_year_id': str(template.academic_year_id),
        'primary_color': getattr(template, 'primary_color', '#5a9e2f') or '#5a9e2f',
        'section_order': getattr(template, 'section_order', []) or [],
        'subject_order': getattr(template, 'subject_order', []) or [],
        'skill_category_order': getattr(template, 'skill_category_order', []) or [],
        'layout_type': getattr(template, 'layout_type', ReportTemplate.LAYOUT_FULL),
        'report_signature_id': str(template.report_signature_id) if template.report_signature_id else '',
        'next_term_start': template.next_term_start.isoformat() if template.next_term_start else '',
        'grading_scale_id': str(template.grading_scale_id) if template.grading_scale_id else '',
        'include_exam_scores': template.include_exam_scores, 'include_homework_assessment': template.include_homework_assessment,
        'include_project_work': template.include_project_work, 'include_clubs': template.include_clubs,
        'include_sports': template.include_sports, 'include_other_activities': template.include_other_activities,
        'include_attendance': template.include_attendance, 'include_grading_scale': template.include_grading_scale,
        'include_skills': template.include_skills,
    })


@login_required
def update_report_template_api(request, template_id):
    """Update an existing report template."""
    if request.method != 'POST': return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        tenant = request.tenant
        template = get_object_or_404(ReportTemplate, id=template_id, tenant=tenant)

        name = request.POST.get('name', '').strip()
        batch_id = request.POST.get('batch_id', '').strip()
        term = request.POST.get('term', '').strip()
        academic_year_id = request.POST.get('academic_year_id', '').strip()

        if not all([name, batch_id, term, academic_year_id]):
            return JsonResponse({'success': False, 'error': 'All required fields must be filled'})

        try:
            batch = Batch.objects.get(id=batch_id, tenant=tenant)
            academic_year = AcademicYear.objects.get(id=academic_year_id, tenant=tenant)
        except (Batch.DoesNotExist, AcademicYear.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Invalid batch or academic year'})

        if ReportTemplate.objects.filter(tenant=tenant, batch=batch, term=term, academic_year=academic_year).exclude(id=template_id).exists():
            return JsonResponse({'success': False, 'error': 'Another template already exists for this batch, term, and academic year'})

        primary_color = request.POST.get('primary_color', '').strip() or '#5a9e2f'
        raw_order = request.POST.get('section_order', '')
        try: section_order = json.loads(raw_order) if raw_order else []
        except Exception: section_order = []

        raw_subject_order = request.POST.get('subject_order', '')
        try: subject_order = json.loads(raw_subject_order) if raw_subject_order else []
        except Exception: subject_order = []

        raw_skill_cat_order = request.POST.get('skill_category_order', '')
        try: skill_category_order = json.loads(raw_skill_cat_order) if raw_skill_cat_order else []
        except Exception: skill_category_order = []

        valid_layouts = {c[0] for c in ReportTemplate.LAYOUT_CHOICES}
        layout_type = request.POST.get('layout_type', '').strip()
        if layout_type not in valid_layouts: layout_type = template.layout_type

        template.name = name
        template.batch = batch
        template.term = term
        template.academic_year = academic_year
        template.primary_color = primary_color
        template.section_order = section_order
        template.subject_order = subject_order
        template.skill_category_order = skill_category_order
        template.layout_type = layout_type
        from django.utils.dateparse import parse_date as _parse_date
        _nts = request.POST.get('next_term_start', '').strip()
        template.next_term_start = _parse_date(_nts) if _nts else None

        gs_id_upd = request.POST.get('grading_scale_id', '').strip()
        if gs_id_upd:
            from .models import GradingScale as GS2
            template.grading_scale = GS2.objects.filter(id=gs_id_upd, tenant=tenant).first()
        else:
            template.grading_scale = None

        sig_id_upd = request.POST.get('report_signature_id', '').strip()
        if sig_id_upd:
            template.report_signature = SchoolSignature.objects.filter(id=sig_id_upd, tenant=tenant).first()
        else:
            template.report_signature = None

        # The submitted layout_type (already set by the JS from the scheme or the
        # fallback select) is the authoritative value — do not override it here.

        template.include_skills = request.POST.get('include_skills') == 'on'
        template.include_exam_scores = request.POST.get('include_exam_scores') == 'on'
        template.include_homework_assessment = request.POST.get('include_homework_assessment') == 'on'
        template.include_project_work = request.POST.get('include_project_work') == 'on'
        template.include_clubs = request.POST.get('include_clubs') == 'on'
        template.include_sports = request.POST.get('include_sports') == 'on'
        template.include_other_activities = request.POST.get('include_other_activities') == 'on'
        template.include_attendance = request.POST.get('include_attendance') == 'on'
        template.include_grading_scale = request.POST.get('include_grading_scale') == 'on'
        template.save()

        return JsonResponse({'success': True, 'template_name': template.name})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def delete_report_template_api(request, template_id):
    """Delete a report template. Blocks deletion if completed reports reference it."""
    if request.method != 'POST': return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        tenant = request.tenant
        template = get_object_or_404(ReportTemplate, id=template_id, tenant=tenant)
        completed_count = StudentReport.objects.filter(template=template, tenant=tenant, generation_status='completed').count()
        if completed_count:
            return JsonResponse({'success': False, 'error': f'Cannot delete: {completed_count} completed report(s) reference this template. Delete those reports first.'})
        
        template_name = template.name
        template.delete()
        return JsonResponse({'success': True, 'template_name': template_name})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def set_default_report_template_api(request, template_id):
    """Mark one template as the default for its batch, clearing the flag on all others."""
    try:
        tenant = request.tenant
        template = get_object_or_404(ReportTemplate, id=template_id, tenant=tenant)
        ReportTemplate.objects.filter(
            tenant=tenant, batch=template.batch
        ).exclude(id=template_id).update(is_default=False)
        template.is_default = True
        template.save(update_fields=['is_default'])
        return JsonResponse({'success': True, 'template_name': template.name})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def report_card_defaults_api(request):
    """GET: return stored report-card defaults. POST: save defaults to Configuration."""
    from .models import Configuration
    tenant = request.tenant

    RC_KEYS = ['rc_school_name', 'rc_school_address', 'rc_school_contact', 'rc_school_email', 'rc_school_website', 'rc_report_title', 'rc_footer_quote', 'rc_primary_color', 'rc_section_order', 'rc_layout_type', 'rc_grading_scale_id', 'rc_include_exam_scores', 'rc_include_homework_assessment', 'rc_include_project_work', 'rc_include_clubs', 'rc_include_sports', 'rc_include_other_activities', 'rc_include_attendance', 'rc_include_grading_scale']
    configs = Configuration.objects.filter(tenant=tenant, config_key__in=RC_KEYS)
    rc = {c.config_key: c.config_value for c in configs}

    if request.method == 'GET':
        def rc_bool_val(key):
            stored = rc.get(f'rc_{key}')
            return stored != 'false' if stored is not None else True

        section_order = []
        if rc.get('rc_section_order'):
            try: section_order = json.loads(rc['rc_section_order'])
            except (ValueError, TypeError): section_order = []

        return JsonResponse({
            'school_name': rc.get('rc_school_name', getattr(tenant, 'name', '')),
            'school_address': rc.get('rc_school_address', getattr(tenant, 'address_line1', '')),
            'school_contact': rc.get('rc_school_contact', getattr(tenant, 'phone', '')),
            'school_email': rc.get('rc_school_email', getattr(tenant, 'email', '')),
            'school_website': rc.get('rc_school_website', str(getattr(tenant, 'website', '') or '')),
            'report_title': rc.get('rc_report_title', 'ASSESSMENT REPORT'),
            'footer_quote': rc.get('rc_footer_quote', ''),
            'primary_color': rc.get('rc_primary_color', '#5a9e2f'),
            'section_order': section_order,
            'layout_type': rc.get('rc_layout_type', 'FULL_ACADEMIC'),
            'grading_scale_id': rc.get('rc_grading_scale_id', ''),
            'include_exam_scores': rc_bool_val('include_exam_scores'),
            'include_homework_assessment': rc_bool_val('include_homework_assessment'),
            'include_project_work': rc_bool_val('include_project_work'),
            'include_clubs': rc_bool_val('include_clubs'),
            'include_sports': rc_bool_val('include_sports'),
            'include_other_activities': rc_bool_val('include_other_activities'),
            'include_attendance': rc_bool_val('include_attendance'),
            'include_grading_scale': rc_bool_val('include_grading_scale'),
        })

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    from django.db import transaction
    with transaction.atomic():
        string_fields = {'school_name': 'rc_school_name', 'school_address': 'rc_school_address', 'school_contact': 'rc_school_contact', 'school_email': 'rc_school_email', 'school_website': 'rc_school_website', 'report_title': 'rc_report_title', 'footer_quote': 'rc_footer_quote', 'primary_color': 'rc_primary_color', 'section_order': 'rc_section_order', 'layout_type': 'rc_layout_type', 'grading_scale_id': 'rc_grading_scale_id'}
        for form_field, config_key in string_fields.items():
            value = request.POST.get(form_field, '').strip()
            Configuration.objects.update_or_create(tenant=tenant, config_key=config_key, defaults={'config_value': value})

        bool_fields = ['include_exam_scores', 'include_homework_assessment', 'include_project_work', 'include_clubs', 'include_sports', 'include_other_activities', 'include_attendance', 'include_grading_scale']
        for field in bool_fields:
            value = 'true' if request.POST.get(field) == 'on' else 'false'
            Configuration.objects.update_or_create(tenant=tenant, config_key=f'rc_{field}', defaults={'config_value': value})

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["GET"])
def preflight_report_api(request):
    """Check readiness before triggering report generation."""
    tenant = getattr(request, 'tenant', None)
    if not tenant: return JsonResponse({'error': 'Tenant not found'}, status=400)

    template_id = request.GET.get('template_id')
    exam_group_id = request.GET.get('exam_group_id')

    if not template_id or not exam_group_id:
        return JsonResponse({'error': 'template_id and exam_group_id required'}, status=400)

    try:
        template = ReportTemplate.objects.get(id=template_id, tenant=tenant)
        exam_group = ExamGroup.objects.get(id=exam_group_id, tenant=tenant)
    except (ReportTemplate.DoesNotExist, ExamGroup.DoesNotExist):
        return JsonResponse({'error': 'Template or exam group not found'}, status=404)

    checks = []
    has_logo = bool(getattr(tenant, 'logo', None) and tenant.logo.name)
    checks.append({'label': 'School logo uploaded', 'status': 'ok' if has_logo else 'warn', 'detail': 'Upload via Configuration.' if not has_logo else None})

    # FIX: Use .count() instead of len(list(...)) to avoid loading thousands of UUIDs into memory
    student_count = BatchStudent.objects.filter(batch=exam_group.batch, tenant=tenant, is_active=True).count()
    checks.append({'label': f'{student_count} active student{"s" if student_count != 1 else ""} in batch', 'status': 'ok' if student_count > 0 else 'error', 'detail': 'No active students found in this batch.' if student_count == 0 else None})

    exams = list(Exam.objects.filter(exam_group=exam_group, tenant=tenant).select_related('subject'))
    exam_count = len(exams)
    checks.append({'label': f'{exam_count} exam{"s" if exam_count != 1 else ""} in exam group', 'status': 'ok' if exam_count > 0 else 'warn', 'detail': 'No exams configured for this group.' if exam_count == 0 else None})

    missing_subjects = []
    if exams and student_count > 0:
        # FIX: Single aggregated query instead of N+1 queries
        score_counts = ExamScore.objects.filter(exam__exam_group=exam_group, tenant=tenant).values('exam_id').annotate(scored_count=Count('id'))
        score_map = {str(row['exam_id']): row['scored_count'] for row in score_counts}
        
        for exam in exams:
            scored = score_map.get(str(exam.id), 0)
            if scored < student_count:
                subject_name = exam.subject.name if exam.subject else str(exam.id)
                missing_subjects.append(f'{subject_name} ({student_count - scored} missing)')

    if not missing_subjects:
        checks.append({'label': 'All exam marks entered', 'status': 'ok', 'detail': None})
    else:
        preview = ', '.join(missing_subjects[:5])
        if len(missing_subjects) > 5: preview += f' and {len(missing_subjects) - 5} more'
        checks.append({'label': f'Marks incomplete for {len(missing_subjects)} subject{"s" if len(missing_subjects) != 1 else ""}', 'status': 'warn', 'detail': preview})

    has_custom_scale = GradingLevel.objects.filter(batch=exam_group.batch, tenant=tenant, is_deleted=False).exists()
    checks.append({'label': 'Grading scale', 'status': 'ok', 'detail': 'Custom batch scale configured' if has_custom_scale else 'Using default A–E scale'})

    all_ok = all(c['status'] != 'error' for c in checks)
    return JsonResponse({'checks': checks, 'all_ok': all_ok, 'student_count': student_count})


@login_required
def cancel_report_generation_api(request):
    """Mark pending/generating reports as failed (cancelled by user)."""
    if request.method != 'POST': return JsonResponse({'success': False, 'error': 'Method not allowed'})

    tenant = getattr(request, 'tenant', None)
    if not tenant: return JsonResponse({'error': 'Tenant not found'}, status=400)

    try: body = json.loads(request.body)
    except Exception: body = {}

    exam_group_id = body.get('exam_group_id') or request.POST.get('exam_group_id')
    template_id = body.get('template_id') or request.POST.get('template_id')

    if not exam_group_id: return JsonResponse({'success': False, 'error': 'exam_group_id required'})

    qs = StudentReport.objects.filter(tenant=tenant, exam_group_id=exam_group_id, generation_status__in=['pending', 'generating'])
    if template_id: qs = qs.filter(template_id=template_id)

    # Note: This updates the DB, but running Celery tasks will continue until they finish.
    # To fully cancel, you would need to store the Celery task ID and revoke it.
    count = qs.update(generation_status='failed', generation_error='Cancelled by user')
    return JsonResponse({'success': True, 'cancelled': count})


@login_required
def generate_reports_api(request):
    """API endpoint to trigger report generation"""
    if request.method != 'POST': return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        tenant = request.tenant
        if request.content_type and 'application/json' in request.content_type:
            body = json.loads(request.body)
            template_id = body.get('template_id', '').strip()
            exam_group_id = body.get('exam_group_id', '').strip()
            student_ids = body.get('student_ids', [])
            section_overrides = body.get('section_overrides') or None
        else:
            template_id = request.POST.get('template_id', '').strip()
            exam_group_id = request.POST.get('exam_group_id', '').strip()
            student_ids = request.POST.getlist('student_ids[]')
            section_overrides = None

        if not template_id or not exam_group_id:
            return JsonResponse({'success': False, 'error': 'Template and exam group are required'})

        try:
            template = ReportTemplate.objects.get(id=template_id, tenant=tenant)
            exam_group = ExamGroup.objects.get(id=exam_group_id, tenant=tenant)
        except (ReportTemplate.DoesNotExist, ExamGroup.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Invalid template or exam group'})

        # FIX: If no specific students are selected, fetch all active students in the batch
        if not student_ids:
            student_ids = list(
                BatchStudent.objects.filter(batch=exam_group.batch, tenant=tenant, is_active=True)
                .values_list('student_id', flat=True)
            )
            student_ids = [str(sid) for sid in student_ids]
            
        if not student_ids:
            return JsonResponse({'success': False, 'error': 'No active students found in this batch'})
            
        # FIX: Chunk the students to prevent OOM and timeouts in Celery
        CHUNK_SIZE = 50
        task_ids = []
        
        for i in range(0, len(student_ids), CHUNK_SIZE):
            chunk = student_ids[i:i + CHUNK_SIZE]
            task_result = bulk_generate_reports_task.delay(
                tenant_id=str(tenant.id),
                template_id=template_id,
                exam_group_id=exam_group_id,
                student_ids=chunk,
                section_overrides=section_overrides,
            )
            task_ids.append(task_result.id)
            
        return JsonResponse({
            'success': True, 
            'task_ids': task_ids,
            'message': f'Report generation started in background ({len(task_ids)} tasks queued)'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def generation_poll_api(request):
    """Poll status of StudentReport generation for a given exam_group + template combo."""
    tenant = getattr(request, 'tenant', None)
    if not tenant: return JsonResponse({'error': 'Tenant not found'}, status=400)

    exam_group_id = request.GET.get('exam_group_id')
    template_id   = request.GET.get('template_id')

    if not exam_group_id: return JsonResponse({'error': 'exam_group_id required'}, status=400)

    qs = StudentReport.objects.filter(tenant=tenant, exam_group_id=exam_group_id)
    if template_id: qs = qs.filter(template_id=template_id)

    # FIX: Single aggregated query instead of 4 separate .count() queries
    stats = qs.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(generation_status='completed')),
        failed=Count('id', filter=Q(generation_status='failed')),
        generating=Count('id', filter=Q(generation_status='generating')),
    )
    
    total = stats['total']
    completed = stats['completed']
    failed = stats['failed']
    generating = stats['generating']

    all_done = total > 0 and (completed + failed) == total

    reports_data = []
    if all_done:
        # FIX: Use .only() to minimize DB load while still allowing property access (e.g., pdf_url)
        for r in qs.select_related('student').only('id', 'generation_status', 'generation_error', 'pdf_file_path', 'student__first_name', 'student__last_name').order_by('student__first_name'):
            reports_data.append({
                'student_name': r.student.full_name,
                'status': r.generation_status,
                'pdf_url': r.pdf_url, # Assuming this is a property on the model
                'error': r.generation_error,
            })

    return JsonResponse({
        'total': total, 'completed': completed, 'failed': failed, 'generating': generating,
        'all_done': all_done, 'pct': round(completed / total * 100) if total else 0, 'reports': reports_data,
    })


@login_required
def report_status_api(request, report_id):
    """API endpoint to check report generation status"""
    try:
        tenant = request.tenant
        report = StudentReport.objects.get(id=report_id, tenant=tenant)
        return JsonResponse({
            'success': True, 'status': report.generation_status,
            'started_at': report.generation_started_at.isoformat() if report.generation_started_at else None,
            'completed_at': report.generation_completed_at.isoformat() if report.generation_completed_at else None,
            'error': report.generation_error, 'pdf_path': report.pdf_file_path, 'html_path': report.html_file_path,
        })
    except StudentReport.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Report not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def download_report_api(request, report_id):
    """API endpoint to download generated report"""
    try:
        tenant = request.tenant
        report = StudentReport.objects.get(id=report_id, tenant=tenant)
        
        if report.generation_status != 'completed' or not report.pdf_file_path:
            raise Http404("Report not available for download")
        
        if not default_storage.exists(report.pdf_file_path):
            raise Http404("Report file not found")
        
        file_handle = default_storage.open(report.pdf_file_path)
        response = FileResponse(file_handle, as_attachment=True, filename=f"{report.student.full_name}_Report_{report.template.term}.pdf")
        return response
        
    except StudentReport.DoesNotExist:
        raise Http404("Report not found")
    except Exception as e:
        logger.error(f"Error downloading report {report_id}: {str(e)}")
        raise Http404("Error downloading report")


# Marks Entry Views

@login_required
def legacy_exam_marks_detail_redirect(request, exam_group_id, batch_id):
    """Legacy /marks/<exam_group>/<batch>/ entry grid was consolidated into the
    Gradebook. Redirect to the Gradebook exam-group page (which lists all batches)."""
    from django.shortcuts import redirect
    return redirect('core:exam_group_marks_entry', exam_group_id=exam_group_id)


@method_decorator(login_required, name='dispatch')
class ExamGroupMarksEntryView(TemplateView):
    """View for showing all exams within an exam group for marks entry"""
    template_name = 'core/gradebook/exam_group_marks_entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        exam_group_id = kwargs.get('exam_group_id')

        # Get the exam group
        exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
        batch = exam_group.batch

        # Activation (is_published) is the single source of truth shared with
        # the teacher portal (see ExamService.is_exam_group_activated /
        # portal.selectors.teacher_can_mark_exam) — an unactivated exam plan
        # shows no markable grid here either.
        exam_service = ExamService(tenant)
        is_activated = exam_service.is_exam_group_activated(exam_group)

        # Show only the exams the planner explicitly created for this exam group.
        # Never auto-create: the exam planner is the single source of truth for
        # which subjects belong to an exam group.
        planner_exams = Exam.objects.filter(
            exam_group=exam_group,
            tenant=tenant,
        ).select_related('subject', 'subject__batch').prefetch_related('scores').order_by('subject__name')

        # Filter exams based on batch exam type configuration
        planner_exams = self._filter_enabled_exams(planner_exams, batch, tenant)
        if not is_activated:
            planner_exams = planner_exams.none()

        from core.models import ExamScore as _ES
        student_count = batch.batch_students.filter(is_active=True).count()
        scored_students = (
            _ES.objects.filter(exam__in=planner_exams, tenant=tenant)
            .values('student_id').distinct().count()
            if planner_exams.exists() else 0
        )
        completion_pct = round(scored_students / student_count * 100) if student_count else 0

        has_template = ReportTemplate.objects.filter(
            batch=batch, tenant=tenant, is_active=True
        ).exists()

        # Group the exams by their report section (assessment_slot) so subjects
        # show under headings like Examination / Test, Attainment, Effort, etc.
        slot_labels = dict(Exam.SLOT_CHOICES)
        slot_order = [c[0] for c in Exam.SLOT_CHOICES]
        from portal.models import MarkSubmission
        submission_status_by_exam = dict(
            MarkSubmission.objects.filter(exam__in=planner_exams, tenant=tenant)
            .values_list('exam_id', 'status')
        )
        by_slot = {}
        for exam in planner_exams:
            exam.mark_submission_status = submission_status_by_exam.get(exam.id)
            exam.display_score_count = exam.scores.count()
            # Skills (LEVEL-scale) exams also have a separate portal flow
            # (Skills Assessment) that tracks its own submission per
            # batch+term in SkillsSubmission rather than MarkSubmission —
            # that table is the only place a portal submission shows up, so
            # without this the badge stayed "Not Submitted" even after a
            # teacher genuinely submitted through the portal. Staff can still
            # mark it done directly from this page (existing ExamScore-based
            # inference below), this only adds the portal's signal on top.
            if exam.mark_submission_status != MarkSubmission.STATUS_SUBMITTED and exam_service.is_skills_exam(exam):
                from portal.models import SkillsSubmission
                skills_info = exam_service.get_skills_submission_info(exam, batch)
                if skills_info['status'] == SkillsSubmission.STATUS_SUBMITTED:
                    exam.mark_submission_status = MarkSubmission.STATUS_SUBMITTED
                    exam.display_score_count = skills_info['score_count'] or exam.display_score_count
            # Some exams (e.g. activity-planner-created rows, or scores
            # entered directly via Django admin) never get a MarkSubmission
            # or SkillsSubmission row at all, yet the badge below still
            # infers "Submitted" once every student has a score. The Undo
            # button must cover that case too, or it silently never renders
            # even though the badge claims the row is done.
            inferred_submitted = (
                not exam.mark_submission_status
                and exam.display_score_count >= student_count
                and exam.display_score_count > 0
            )
            exam.is_undoable = (
                exam.mark_submission_status == MarkSubmission.STATUS_SUBMITTED or inferred_submitted
            )
            by_slot.setdefault(exam.assessment_slot or 'EXAM', []).append(exam)
        exam_sections = [
            {'slot': slot, 'title': slot_labels.get(slot, slot), 'exams': by_slot[slot]}
            for slot in slot_order if slot in by_slot
        ]
        # Any non-standard slots (defensive) keep their raw value as the heading.
        for slot, exams in by_slot.items():
            if slot not in slot_order:
                exam_sections.append({'slot': slot, 'title': slot, 'exams': exams})

        batch_exam_data = []
        if planner_exams.exists():
            from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
            assignment_svc = ClassTeacherAssignmentService(tenant)
            class_teacher_groups = []
            overview = assignment_svc.batch_assignment_overview(batch)
            groups_by_teacher = {}
            for row in overview:
                emp = row['employee']
                if emp:
                    emp_key = str(emp.id)
                    if emp_key not in groups_by_teacher:
                        groups_by_teacher[emp_key] = {'employee': emp, 'students': []}
                    groups_by_teacher[emp_key]['students'].append(row['student'])
                else:
                    if 'UNASSIGNED' not in groups_by_teacher:
                        groups_by_teacher['UNASSIGNED'] = {'employee': None, 'students': []}
                    groups_by_teacher['UNASSIGNED']['students'].append(row['student'])
            class_teacher_groups = list(groups_by_teacher.values())

            batch_exam_data.append({
                'batch': batch,
                'exams': planner_exams,
                'exam_sections': exam_sections,
                'student_count': student_count,
                'scored_students': scored_students,
                'completion_pct': completion_pct,
                'auto_created_count': 0,
                'has_template': has_template,
                'class_teacher_groups': class_teacher_groups,
            })

        logger.debug("ExamGroupMarksEntry: %d planner-selected exams for %s",
                     planner_exams.count(), exam_group.name)

        # Get overall student count for the course
        total_student_count = sum([data['student_count'] for data in batch_exam_data])

        # Determine exam type classification and whether this is activity-based
        is_activity_exam = exam_group.exam_type.lower() == 'activity'

        if is_activity_exam:
            exam_type_display = "Activity Exams"
        else:
            exam_type_display = "Subject Exams"

        # Batch switcher: every batch of this course (same academic year) that has
        # a sibling planner of the same name, so the clerk can jump between
        # classes without leaving the marks page. (Course-level planners create
        # one ExamGroup per batch — see propagate_plan_exams.)
        batch_switcher = []
        if batch:
            course_batches = Batch.objects.filter(
                tenant=tenant, course=batch.course, academic_year=batch.academic_year,
                is_active=True, is_deleted=False,
            ).order_by('name')
            sibling_groups = {
                g.batch_id: g for g in ExamGroup.objects.filter(
                    tenant=tenant, name=exam_group.name, batch__in=course_batches,
                )
            }
            for b in course_batches:
                g = sibling_groups.get(b.id)
                batch_switcher.append({
                    'batch_name': b.name,
                    'exam_group_id': str(g.id) if g else '',
                    'is_current': b.id == batch.id,
                })

        # Layout context vars
        back_url = reverse('core:class_exam_planner', args=[batch.course.id])
        crumbs = [
            {'label': 'Gradebook', 'url': reverse('core:gradebook_management')},
            {'label': 'Manage Gradebook', 'url': reverse('core:gradebook_management')},
            {'label': batch.course.course_name, 'url': reverse('core:class_exam_planner', args=[batch.course.id])},
            {'label': exam_group.name},
        ]

        context.update({
            'exam_group': exam_group,
            'is_activated': is_activated,
            'batch_exam_data': batch_exam_data,
            'course': batch.course,
            'total_student_count': student_count,
            'exam_type_display': exam_type_display,
            'is_activity_exam': is_activity_exam,
            'planner_exams': planner_exams,
            'batch_switcher': batch_switcher,
            'current_batch': batch,
            'back_url': back_url,
            'crumbs': crumbs,
        })

        return context

    def _filter_enabled_exams(self, exams, batch, tenant):
        """Keep only exams whose type is enabled for the batch (all pass when
        the batch has no exam-type configuration)."""
        from core.models import BatchExamTypeConfiguration
        return BatchExamTypeConfiguration.filter_enabled_exams(exams, batch, tenant)


@method_decorator(login_required, name='dispatch')
class SingleExamMarksEntryView(TemplateView):
    """View for entering marks for a single subject exam"""
    template_name = 'core/gradebook/single_exam_marks_entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        exam_id = kwargs.get('exam_id')

        # Get the specific exam
        exam = get_object_or_404(Exam, id=exam_id, tenant=tenant)
        exam_group = exam.exam_group
        batch = exam_group.batch

        # Same activation rule as the teacher portal (ExamService.is_exam_group_activated) —
        # an unactivated exam plan is not markable here either.
        is_activated = ExamService(tenant).is_exam_group_activated(exam_group)

        # Get students only from the specific batch that this exam's subject belongs to
        exam_subject_batch = exam.subject.batch

        logger.debug("SingleExamMarksEntry: exam=%s batch=%s", exam.subject.name, exam_subject_batch.name)

        # Get all active students from this specific batch only
        batch_students = BatchStudent.objects.filter(
            batch=exam_subject_batch,
            is_active=True,
            tenant=tenant
        ).select_related('student').order_by('student__first_name', 'student__last_name')

        students = [bs.student for bs in batch_students]

        # If no active students, include inactive as a fallback
        if not students:
            all_batch_students = BatchStudent.objects.filter(
                batch=exam_subject_batch,
                tenant=tenant
            ).select_related('student').order_by('student__first_name', 'student__last_name')
            students = [bs.student for bs in all_batch_students]

        logger.debug("SingleExamMarksEntry: %d students loaded", len(students))

        # Get existing exam scores for this specific exam
        existing_scores = ExamScore.objects.filter(
            exam=exam,
            student__in=students,
            tenant=tenant
        ).select_related('student', 'grade_value')

        # Determine scoring type from the exam's grading scale / maximum_marks
        grading_scale = exam.get_grading_scale()
        is_level_scale = bool(grading_scale and grading_scale.scale_type == 'LEVEL')

        if is_level_scale:
            scoring_type = 'levels'
        elif exam.maximum_marks == 0:
            scoring_type = 'grades'
        elif grading_scale:
            scoring_type = 'marks_and_grades'
        else:
            scoring_type = 'marks'

        grade_values = list(
            grading_scale.grade_values.filter(tenant=tenant).order_by('display_order')
        ) if grading_scale and scoring_type in ('grades', 'marks_and_grades', 'levels') else []

        # Build grade_values JSON for JavaScript (id, name, code, is_passing)
        import json as _json
        grade_values_json = _json.dumps([
            {'id': str(gv.id), 'name': gv.name, 'code': getattr(gv, 'code', gv.name), 'is_passing': gv.is_passing}
            for gv in grade_values
        ])

        # Create a list of students with their scores
        students_with_scores = []
        for student in students:
            score = existing_scores.filter(student=student).first()
            students_with_scores.append({
                'student': student,
                'score': score,
                'grade_value_id': str(score.grade_value_id) if score and score.grade_value_id else '',
            })

        # Determine exam type display
        exam_type_display = "Subject Exams"
        if 'SKILL' in exam_group.exam_type.upper():
            exam_type_display = "Subject Skill Exams"
        elif 'PROJECT' in exam_group.exam_type.upper() or 'ACTIVITY' in exam_group.exam_type.upper():
            exam_type_display = "Activity Exams"
        elif 'ATTRIBUTE' in exam_group.exam_type.upper():
            exam_type_display = "Attribute Exams"

        # Layout context vars
        back_url = reverse('core:exam_group_marks_entry', args=[exam_group.id])
        mark_entry_description = f"Mark entry — {exam_group.name} · {batch.course.course_name} / {batch.name}"
        crumbs = [
            {'label': 'Gradebook', 'url': reverse('core:gradebook_management')},
            {'label': 'Manage Gradebook', 'url': reverse('core:gradebook_management')},
            {'label': batch.course.course_name, 'url': reverse('core:class_exam_planner', args=[batch.course.id])},
            {'label': exam_group.name, 'url': reverse('core:exam_group_marks_entry', args=[exam_group.id])},
            {'label': 'Mark Entry'},
        ]

        context.update({
            'exam': exam,
            'exam_group': exam_group,
            'is_activated': is_activated,
            'batch': exam_subject_batch,
            'students_with_scores': students_with_scores,
            'exam_type_display': exam_type_display,
            'scoring_type': scoring_type,
            'grade_values': grade_values,
            'grade_values_json': grade_values_json,
            'back_url': back_url,
            'mark_entry_description': mark_entry_description,
            'crumbs': crumbs,
        })

        # For LEVEL-type (skills assessment) exams, load skill items
        if is_level_scale:
            from .models import SkillCategory, SkillItem, AcademicYear as _AY

            def _normalize(s):
                return s.strip().lower().replace('_', ' ').replace('-', ' ')

            subject_norm = _normalize(exam.subject.name)
            skill_category = None
            skill_items = []

            all_categories = list(SkillCategory.objects.filter(tenant=tenant, is_active=True))
            for cat in all_categories:
                cat_name_norm = _normalize(cat.name)
                cat_code_norm = _normalize(cat.code)
                if (subject_norm == cat_name_norm
                        or subject_norm == cat_code_norm
                        or subject_norm in cat_name_norm
                        or cat_name_norm in subject_norm
                        or subject_norm in cat_code_norm
                        or cat_code_norm in subject_norm):
                    skill_category = cat
                    break

            if skill_category:
                # Only this batch's activities plus shared ones (no batches attached).
                items_qs = _skill_items_for_batch(
                    SkillItem.objects.filter(
                        category=skill_category, is_active=True, tenant=tenant,
                    ),
                    exam_subject_batch,
                )
                skill_items = list(items_qs.order_by('display_order'))
            else:
                # No match — show ALL categories so teacher can still assess, still
                # scoped to this batch's activities plus shared ones.
                from django.db.models import Prefetch as _Prefetch
                items_pf = _skill_items_for_batch(
                    SkillItem.objects.filter(is_active=True, tenant=tenant),
                    exam_subject_batch,
                ).order_by('display_order')
                all_categories = list(
                    SkillCategory.objects.filter(tenant=tenant, is_active=True)
                    .prefetch_related(
                        _Prefetch('skill_items', queryset=items_pf, to_attr='active_items')
                    ).order_by('display_order')
                )

            academic_years = _AY.objects.filter(tenant=tenant).order_by('-start_date')
            term_name = exam.term.name if exam.term_id else ''

            skill_items_json = _json.dumps([
                {'id': str(item.id), 'description': item.description or ''}
                for item in skill_items
            ])
            all_skill_cats_json = _json.dumps([
                {
                    'name': cat.name,
                    'items': [{'id': str(item.id), 'description': item.description or ''} for item in cat.active_items],
                }
                for cat in (all_categories if not skill_category else [])
            ])

            context.update({
                'skill_category': skill_category,
                'skill_items': skill_items,
                'skill_items_json': skill_items_json,
                'all_skill_cats_json': all_skill_cats_json,
                'all_skill_categories': all_categories if not skill_category else [],
                'academic_years': academic_years,
                'active_year': academic_years.filter(is_active=True).first(),
                'term_name': term_name,
            })

        return context


@method_decorator(login_required, name='dispatch')
class ManageClassBatchView(TemplateView):
    """View for managing class batches from settings menu"""
    template_name = 'core/settings/manage_class_batch.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        # Get all courses (classes)
        courses = Course.objects.filter(tenant=tenant, is_deleted=False).order_by('course_name')

        # Get selected course from request
        selected_course_id = self.request.GET.get('course_id')
        selected_course = None

        if selected_course_id:
            try:
                selected_course = courses.get(id=selected_course_id)
            except Course.DoesNotExist:
                selected_course = courses.first() if courses.exists() else None
        else:
            selected_course = courses.first() if courses.exists() else None

        # Get batches for selected course
        active_batches = []
        inactive_batches = []

        if selected_course:
            all_batches = Batch.objects.filter(
                course=selected_course,
                tenant=tenant
            ).order_by('name')

            active_batches = all_batches.filter(is_active=True)
            inactive_batches = all_batches.filter(is_active=False)

        context.update({
            'courses': courses,
            'selected_course': selected_course,
            'active_batches': active_batches,
            'inactive_batches': inactive_batches,
            'active_academic_year': AcademicYear.objects.filter(tenant=tenant, is_active=True).first(),
            'enrollment_conflict_count': StudentService(tenant).get_enrollment_conflict_count(),
        })

        return context


@method_decorator(login_required, name='dispatch')
class EnrollmentConflictsView(TemplateView):
    """Review students enrolled in more than one class within the same academic
    year, and resolve each by choosing the class to keep."""
    template_name = 'core/settings/enrollment_conflicts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        all_conflicts = StudentService(tenant).get_enrollment_conflicts()

        # Only show conflicts for the active academic year
        active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()

        if active_year:
            conflicts = [c for c in all_conflicts if c['academic_year'].id == active_year.id]
            conflict_years = [active_year]
            selected_year = active_year
        else:
            conflicts = []
            conflict_years = []
            selected_year = None

        context.update({
            'conflicts': conflicts,
            'conflict_count': len(conflicts),
            'conflict_years': conflict_years,
            'selected_year': selected_year,
            'total_conflict_count': len(conflicts),
        })
        return context


@require_http_methods(["POST"])
@login_required
def resolve_enrollment_conflict_api(request):
    """Keep one class for a student in an academic year and deactivate the rest."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        student_id = request.POST.get('student_id')
        academic_year_id = request.POST.get('academic_year_id')
        keep_batch_id = request.POST.get('keep_batch_id')
        if not all([student_id, academic_year_id, keep_batch_id]):
            return JsonResponse({'error': 'student_id, academic_year_id and keep_batch_id are required'}, status=400)

        deactivated = StudentService(tenant).resolve_enrollment_conflict(
            student_id=student_id,
            academic_year_id=academic_year_id,
            keep_batch_id=keep_batch_id,
            user=request.user,
        )
        return JsonResponse({
            'success': True,
            'deactivated': deactivated,
            'message': f'Kept the selected class and removed {deactivated} duplicate enrolment(s).',
        })
    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception:
        logger.exception("resolve_enrollment_conflict_api failed")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@require_http_methods(["POST"])
@login_required
def course_create_api(request):
    """Create a new class/course from the Manage Class/Batch page."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        academic_service = AcademicService(tenant)

        course_name = request.POST.get('course_name', '').strip()
        code = request.POST.get('code', '').strip()
        section_name = request.POST.get('section_name', '').strip() or None
        grading_type = request.POST.get('grading_type', '').strip() or None

        errors = {}
        if not course_name:
            errors['course_name'] = ['Class/Course name is required']
        if not code:
            errors['code'] = ['Code is required']
        if errors:
            return JsonResponse(errors, status=400)

        course = academic_service.create_course(
            course_name=course_name,
            code=code,
            section_name=section_name,
            grading_type=grading_type,
            user=request.user,
        )
        return JsonResponse({'success': True, 'id': str(course.id), 'name': course.course_name})

    except ServiceException as e:
        # Covers duplicate code / validation errors raised by the service.
        return JsonResponse({'error': str(e)}, status=400)
    except Exception:
        logger.exception("course_create_api failed")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@require_http_methods(["POST"])
@login_required
def course_update_api(request, course_id):
    """Edit a class/course from the Manage Class/Batch page."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        academic_service = AcademicService(tenant)

        course_name = request.POST.get('course_name', '').strip()
        code = request.POST.get('code', '').strip()
        section_name = request.POST.get('section_name', '').strip() or None
        grading_type = request.POST.get('grading_type', '').strip() or None

        errors = {}
        if not course_name:
            errors['course_name'] = ['Class/Course name is required']
        if not code:
            errors['code'] = ['Code is required']
        if errors:
            return JsonResponse(errors, status=400)

        course = academic_service.update(
            course_id,
            course_name=course_name,
            code=code,
            section_name=section_name,
            grading_type=grading_type,
        )
        return JsonResponse({'success': True, 'id': str(course.id), 'name': course.course_name})

    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception:
        logger.exception("course_update_api failed")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@require_http_methods(["POST"])
@login_required
def batch_quick_update_api(request, batch_id):
    """Edit a batch's name / grading type from the Manage Class/Batch page.

    Reuses AcademicService.update_batch with only the changed scalar fields, so
    the batch's course, academic year and dates are preserved.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        academic_service = AcademicService(tenant)

        name = request.POST.get('name', '').strip()
        grading_type = request.POST.get('grading_type', '').strip() or None
        if not name:
            return JsonResponse({'name': ['Batch name is required']}, status=400)

        batch = academic_service.update_batch(
            batch_id, name=name, grading_type=grading_type, user=request.user,
        )
        return JsonResponse({'success': True, 'id': str(batch.id), 'name': batch.name})

    except ServiceException as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception:
        logger.exception("batch_quick_update_api failed")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@require_http_methods(['POST'])
@login_required
def toggle_batch_status_api(request):
    """API endpoint to toggle batch active/inactive status"""
    try:
        import json
        data = json.loads(request.body)
        batch_id = data.get('batch_id')
        is_active = data.get('is_active')

        if not batch_id:
            return JsonResponse({'success': False, 'error': 'Batch ID is required'})

        if is_active is None:
            return JsonResponse({'success': False, 'error': 'is_active parameter is required'})

        tenant = request.tenant

        try:
            batch = Batch.objects.get(id=batch_id, tenant=tenant)
        except Batch.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Batch not found'})

        # Update batch status
        batch.is_active = is_active
        batch.save()

        action = 'activated' if is_active else 'deactivated'

        return JsonResponse({
            'success': True,
            'message': f'Batch {batch.name} has been {action} successfully'
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@method_decorator(login_required, name='dispatch')
class BatchTransferListView(TemplateView):
    """View for transferring students between batches with full control"""
    template_name = 'core/batch_transfer/batch_transfer_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        # Get all active batches
        all_batches = Batch.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('course').order_by('course__course_name', 'name')

        # Get selected source and destination batches
        source_batch_id = self.request.GET.get('source_batch_id')
        dest_batch_id = self.request.GET.get('dest_batch_id')

        source_batch = None
        dest_batch = None
        batch_students = []

        if source_batch_id:
            try:
                source_batch = Batch.objects.get(id=source_batch_id, tenant=tenant)
                batch_students = BatchStudent.objects.filter(
                    batch=source_batch,
                    is_active=True,
                    tenant=tenant
                ).select_related('student').order_by('student__first_name', 'student__last_name')
            except Batch.DoesNotExist:
                pass

        if dest_batch_id:
            try:
                dest_batch = Batch.objects.get(id=dest_batch_id, tenant=tenant)
            except Batch.DoesNotExist:
                pass

        context.update({
            'all_batches': all_batches,
            'source_batch': source_batch,
            'dest_batch': dest_batch,
            'batch_students': batch_students,
            'no_students_message': f"No active students found in {source_batch.name}." if source_batch else '',
            'batch_list_url': reverse('core:batch_list'),
        })

        return context


@method_decorator(login_required, name='dispatch')
class BatchTransferDetailView(TemplateView):
    """View for transferring students from one batch to another"""
    template_name = 'core/batch_transfer/batch_transfer_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        batch_id = kwargs.get('batch_id')

        try:
            source_batch = Batch.objects.get(id=batch_id, tenant=tenant)
        except Batch.DoesNotExist:
            raise Http404("Batch not found")

        # Get students in the source batch
        batch_students = BatchStudent.objects.filter(
            batch=source_batch,
            is_active=True,
            tenant=tenant
        ).select_related('student').order_by('student__first_name', 'student__last_name')

        # Get available target batches (same course, different batch)
        target_batches = Batch.objects.filter(
            course=source_batch.course,
            tenant=tenant,
            is_active=True
        ).exclude(id=source_batch.id).order_by('name')

        # Check for students with unpaid fees (placeholder logic)
        students_with_unpaid_fees = []
        for batch_student in batch_students:
            # This is a simplified check - you might want to implement actual fee checking logic
            # For now, we'll simulate some students having unpaid fees
            students_with_unpaid_fees.append(batch_student.student.id)

        context.update({
            'source_batch': source_batch,
            'batch_students': batch_students,
            'target_batches': target_batches,
            'students_with_unpaid_fees': students_with_unpaid_fees,
            'course': source_batch.course,
            'no_students_message': f"No active students found in {source_batch.name}.",
        })

        return context


@require_http_methods(['POST'])
@login_required
def batch_transfer_api(request):
    """API endpoint to transfer students from one batch to another"""
    try:
        import json
        data = json.loads(request.body)
        source_batch_id = data.get('source_batch_id')
        target_batch_id = data.get('target_batch_id')

        if not source_batch_id or not target_batch_id:
            return JsonResponse({'success': False, 'error': 'Both source and target batch IDs are required'})

        tenant = request.tenant

        try:
            source_batch = Batch.objects.get(id=source_batch_id, tenant=tenant)
            target_batch = Batch.objects.get(id=target_batch_id, tenant=tenant)
        except Batch.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'One or both batches not found'})

        # Check that both batches belong to the same course
        if source_batch.course != target_batch.course:
            return JsonResponse({'success': False, 'error': 'Batches must belong to the same course'})

        # Active students in the source batch — optionally narrowed to a selected
        # subset so the clerk can move specific students instead of the whole batch.
        batch_students = BatchStudent.objects.filter(
            batch=source_batch,
            is_active=True,
            tenant=tenant
        )

        student_ids = data.get('student_ids') or []
        if student_ids:
            batch_students = batch_students.filter(student_id__in=student_ids)

        if not batch_students.exists():
            return JsonResponse({
                'success': False,
                'error': 'No students selected to transfer' if student_ids
                         else 'No active students found in the source batch',
            })

        # Perform the transfer
        transferred_count = 0
        for batch_student in batch_students:
            # Deactivate the student from source batch
            batch_student.is_active = False
            batch_student.save()

            # Create or reactivate student in target batch
            target_batch_student, created = BatchStudent.objects.get_or_create(
                student=batch_student.student,
                batch=target_batch,
                tenant=tenant,
                defaults={
                    'is_active': True
                }
            )

            if not created:
                # If the relationship already exists, just reactivate it
                target_batch_student.is_active = True
                target_batch_student.save()

            transferred_count += 1

        return JsonResponse({
            'success': True,
            'message': f'Successfully transferred {transferred_count} students from {source_batch.name} to {target_batch.name}'
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def validate_batch_marks_api(request, exam_group_id, batch_id):
    """Check whether all students in a batch have marks for all exams. No side effects."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

    exams = Exam.objects.filter(exam_group=exam_group, subject__batch=batch, tenant=tenant)
    batch_student_ids = list(
        BatchStudent.objects.filter(batch=batch, tenant=tenant, is_active=True)
        .values_list('student_id', flat=True)
    )
    student_count = len(batch_student_ids)

    missing = []
    for exam in exams:
        scored = set(
            ExamScore.objects.filter(exam=exam, tenant=tenant, student_id__in=batch_student_ids)
            .values_list('student_id', flat=True)
        )
        not_scored = student_count - len(scored)
        if not_scored > 0:
            missing.append({
                'subject': exam.subject.name if exam.subject else str(exam.id),
                'exam_id': str(exam.id),
                'missing_count': not_scored,
                'total': student_count,
            })

    return JsonResponse({
        'complete': len(missing) == 0,
        'missing': missing,
        'total_exams': exams.count(),
        'student_count': student_count,
    })


@login_required
@require_http_methods(["POST"])
def generate_batch_reports_api(request, exam_group_id, batch_id):
    """Generate PDF reports for all students in a batch using ReportGenerationService."""
    try:
        tenant = request.tenant
        exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

        from .models import BatchStudent, ExamScore
        from .services.report_generation_service import ReportGenerationService

        batch_students = BatchStudent.objects.filter(
            batch=batch, tenant=tenant, is_active=True
        ).select_related('student')
        students = [bs.student for bs in batch_students]

        if not students:
            return JsonResponse({'success': False, 'error': 'No active students in this batch.'})

        # Prefer the template explicitly marked as default for this batch;
        # fall back to the most-recently created active template.
        qs = ReportTemplate.objects.filter(tenant=tenant, batch=batch, is_active=True)
        template = qs.filter(is_default=True).first() or qs.order_by('-created_at').first()

        if not template:
            # Derive the report layout from the grading scale linked to the batch,
            # or fall back to the course name when no scale is configured.
            from .models import GradingScale as _GS
            auto_layout = ReportTemplate.LAYOUT_FULL
            auto_grading_scale = None

            # 1. Try the batch's default grading scale
            batch_scale = getattr(batch, 'default_grading_scale', None)
            if batch_scale and batch_scale.report_layout:
                auto_layout = batch_scale.report_layout
                auto_grading_scale = batch_scale
            else:
                # 2. Derive from the course name
                course_upper = batch.course.course_name.upper()
                if any(kw in course_upper for kw in ('RECEPTION', 'BEGINNERS', 'MIDDLE CLASS', 'NURSERY', 'PRE-SCHOOL', 'PREP')):
                    auto_layout = ReportTemplate.LAYOUT_SKILLS
                    auto_grading_scale = _GS.objects.filter(
                        tenant=tenant, code='SKILL_LEVELS', is_active=True
                    ).first()
                elif any(kw in course_upper for kw in ('GRADE 1', 'GRADE 2', 'YEAR 1', 'YEAR 2')):
                    auto_layout = ReportTemplate.LAYOUT_SIMPLE
                    auto_grading_scale = _GS.objects.filter(
                        tenant=tenant, code='LETTER_4POINT', is_active=True
                    ).first()
                else:
                    auto_layout = ReportTemplate.LAYOUT_FULL
                    auto_grading_scale = _GS.objects.filter(
                        tenant=tenant, code='LETTER_GRADES', is_active=True
                    ).first()

            auto_term = ReportGenerationService.resolve_exam_group_term(exam_group)
            template = ReportTemplate.objects.create(
                tenant=tenant,
                batch=batch,
                term=auto_term,
                academic_year=batch.academic_year,
                name=f"{batch.name} — {exam_group.name}",
                school_name=tenant.name,
                school_address=f"{tenant.address_line1 or ''} {tenant.city or ''}".strip(),
                school_contact=tenant.phone or '',
                school_email=tenant.email or '',
                school_website=str(tenant.website or ''),
                layout_type=auto_layout,
                grading_scale=auto_grading_scale,
            )

        svc = ReportGenerationService(tenant=tenant)
        generated, failed = [], []

        for student in students:
            try:
                report = svc.generate_student_report(
                    student_id=str(student.id),
                    template_id=str(template.id),
                    exam_group_id=str(exam_group.id),
                )
                # report.pdf_url resolves to /media/ locally or CloudFront on S3
                url = report.pdf_url
                if url and url.startswith('/'):
                    url = request.build_absolute_uri(url)
                generated.append({
                    'student_id': str(student.id),
                    'student_name': student.full_name,
                    'report_url': url,
                    'report_id': str(report.id),
                })
            except Exception as e:
                failed.append({
                    'student_id': str(student.id),
                    'student_name': student.full_name,
                    'error': str(e),
                })

        return JsonResponse({
            'success': True,
            'message': f'Generated {len(generated)} of {len(students)} reports.',
            'generated_reports': generated,
            'failed_reports': failed,
            'total_students': len(students),
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def batch_activities_api(request, exam_group_id, batch_id):
    """Return each active student in a batch with their homework / project ratings
    and clubs/sports/other, for the Activities & Assessments modal."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    from .models import HomeworkAssessment
    from .services.report_generation_service import ReportGenerationService
    from .services.activities_service import ActivitiesService

    exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
    term = ReportGenerationService.resolve_exam_group_term(exam_group)
    ay = batch.academic_year

    rows = ActivitiesService.roster_rows(batch, term, ay)
    for row in rows:
        row['id'] = row.pop('student_id')

    return JsonResponse({
        'term': term,
        'academic_year': ay.name if ay else '',
        'grades': [g[0] for g in HomeworkAssessment.ASSESSMENT_GRADES],
        'activity_options': ActivitiesService.activity_options(tenant),
        'homework_enabled': ActivitiesService.homework_enabled(batch),
        'activities_enabled': ActivitiesService.activities_enabled(batch),
        'students': rows,
    })


@login_required
@require_http_methods(["POST"])
def save_batch_activities_api(request, exam_group_id, batch_id):
    """Save homework/project ratings and clubs/sports/other for a batch's students."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    from .services.report_generation_service import ReportGenerationService
    from .services.activities_service import ActivitiesService

    exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
    term = ReportGenerationService.resolve_exam_group_term(exam_group)
    ay = batch.academic_year

    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    students_payload = payload.get('students', [])
    saved = ActivitiesService.save_roster_rows(batch, term, ay, students_payload)

    has_ratings = any(('homework' in row) or ('project' in row) for row in students_payload)
    has_activities = any(('clubs' in row) or ('sports' in row) or ('other' in row) for row in students_payload)
    ActivitiesService.mark_saved(batch, exam_group, ratings=has_ratings, activities=has_activities)

    return JsonResponse({'success': True, 'message': f'Saved for {saved} student(s).'})


@login_required
@require_http_methods(["POST"])
def save_marks_api(request):
    """API endpoint to save marks for students.

    Saves are per-row/best-effort, not all-or-nothing: one student's invalid
    grade/marks must not block the rest of the class from saving. `success`
    is only True when every row saved; callers must check `failed_count`
    (not just `success`) to know whether a partial save happened.
    """
    try:
        tenant = request.tenant
        data = json.loads(request.body)

        exam_id = data.get('exam_id')
        marks_data = data.get('marks', [])  # List of {student_id, marks, is_absent, remarks}

        exam = get_object_or_404(Exam, id=exam_id, tenant=tenant)

        try:
            ExamService(tenant).assert_exam_markable(exam)
        except ValidationException as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=403)

        from .models import ExamScore
        saved_count = 0
        errors = []

        grading_scale = exam.get_grading_scale()
        is_grade_only = exam.maximum_marks == 0 or bool(grading_scale and grading_scale.scale_type == 'LEVEL')

        for mark_entry in marks_data:
            student_id = mark_entry.get('student_id')
            marks = mark_entry.get('marks')
            is_absent = mark_entry.get('is_absent', False)
            remarks = mark_entry.get('remarks', '')
            grade_value_id = mark_entry.get('grade_value_id')

            try:
                student = get_object_or_404(Student, id=student_id, tenant=tenant)

                grade_value = None
                if is_grade_only:
                    # Grade-only exam: resolve the selected GradeValue, scoped to
                    # this exam's own grading scale (a stale/foreign id must not
                    # silently match a same-tenant value from a different scale).
                    if not is_absent and grade_value_id:
                        from .models import GradeValue
                        try:
                            grade_value = GradeValue.objects.get(
                                id=grade_value_id, tenant=tenant, grading_scale=grading_scale,
                            )
                        except GradeValue.DoesNotExist:
                            errors.append(f"Invalid grade for {student.full_name}")
                            continue
                    marks = None
                else:
                    # Numeric marks exam: validate the numeric value
                    if not is_absent and marks is not None:
                        marks = Decimal(str(marks))
                        if marks < 0 or marks > exam.maximum_marks:
                            errors.append(f"Invalid marks for {student.full_name}: {marks}")
                            continue

                # Get or create exam score
                exam_score, created = ExamScore.objects.get_or_create(
                    exam=exam,
                    student=student,
                    tenant=tenant,
                    defaults={
                        'marks': marks if not is_absent else None,
                        'is_absent': is_absent,
                        'remarks': remarks,
                        'grade_value': grade_value,
                    }
                )

                if not created:
                    exam_score.marks = marks if not is_absent else None
                    exam_score.is_absent = is_absent
                    exam_score.remarks = remarks
                    exam_score.grade_value = grade_value
                    exam_score.save()

                saved_count += 1

            except Exception as e:
                errors.append(f"Error saving marks for student {student_id}: {str(e)}")

        attempted_count = len(marks_data)
        failed_count = attempted_count - saved_count

        if failed_count == 0 and attempted_count > 0:
            from portal.models import MarkSubmission
            MarkSubmission.objects.update_or_create(
                exam=exam,
                defaults={
                    'tenant': tenant,
                    'status': MarkSubmission.STATUS_SUBMITTED,
                    'submitted_by': request.user,
                    'submitted_at': timezone.now(),
                },
            )

        return JsonResponse({
            'success': failed_count == 0,
            'attempted_count': attempted_count,
            'saved_count': saved_count,
            'failed_count': failed_count,
            'errors': errors,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def submit_exam_marks_api(request):
    """API endpoint to submit/publish exam marks and trigger report generation.

    Publishing is not gated on marks/activities/signature completeness —
    staff can publish (and re-publish) at any time.
    """
    try:
        tenant = request.tenant
        data = json.loads(request.body)

        exam_group_id = data.get('exam_group_id')
        batch_id = data.get('batch_id')

        exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

        exam_service = ExamService(tenant)

        if not exam_service.is_exam_group_activated(exam_group):
            return JsonResponse({
                'success': False,
                'error': "This exam plan has not been activated yet — marks cannot be submitted.",
            }, status=403)

        # Mark exam group as published
        exam_group.result_published = True
        exam_group.save()

        # Trigger report generation for all students in the batch
        from .tasks import bulk_generate_reports_task
        from .models import BatchStudent

        # Get students in this batch
        batch_students = BatchStudent.objects.filter(batch=batch, tenant=tenant)
        student_ids = [str(bs.student.id) for bs in batch_students]

        # Get default report template (or first available)
        default_template = ReportTemplate.objects.filter(tenant=tenant, is_active=True).first()

        message_parts = ['Marks submitted successfully.']

        if default_template and student_ids:
            # Trigger background task for report generation
            task = bulk_generate_reports_task.delay(
                tenant_id=str(tenant.id),
                student_ids=student_ids,
                template_id=str(default_template.id),
                exam_group_id=str(exam_group.id)
            )

            return JsonResponse({
                'success': True,
                'message': ' '.join(message_parts) + f' Report generation started for {len(student_ids)} students.',
                'task_id': task.id,
                'student_count': len(student_ids),
            })
        else:
            return JsonResponse({
                'success': True,
                'message': ' '.join(message_parts),
                'warning': 'No report template found or no students to generate reports for.',
            })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def undo_marks_submission_api(request, exam_id):
    """Admin action to reopen a subject's submitted marks for editing.

    Flips the exam's MarkSubmission back to draft (clearing the submission
    stamp) without touching any ExamScore rows already entered. Skills
    (LEVEL-scale, e.g. Reception/Nursery) exams never get a MarkSubmission
    row at all — their submission lives in the portal's SkillsSubmission
    (keyed by batch+term) instead — so when no MarkSubmission is submitted,
    this also tries reopening any submitted SkillsSubmission for the exam's
    batch+term before giving up. If the exam's ExamGroup has already been
    published, undoing either kind also unpublishes it — since
    result_published is the single flag gating parent-facing results
    (portal/selectors.py) and the report-generation picker — so previously
    generated reports are treated as stale until the class is republished.
    """
    try:
        tenant = request.tenant
        exam = get_object_or_404(Exam, id=exam_id, tenant=tenant)
        exam_service = ExamService(tenant)

        from django.db import transaction
        from portal.models import MarkSubmission
        submission = MarkSubmission.objects.filter(exam=exam, tenant=tenant).first()

        undone_marks = False
        undone_skills = False
        with transaction.atomic():
            if submission is not None and submission.status == MarkSubmission.STATUS_SUBMITTED:
                submission.status = MarkSubmission.STATUS_DRAFT
                submission.submitted_by = None
                submission.submitted_at = None
                submission.save()
                undone_marks = True
            elif exam_service.is_skills_exam(exam):
                undone_skills = exam_service.undo_skills_submission(exam, exam.exam_group.batch)

            if not undone_marks and not undone_skills:
                # Some exams (activity-planner-created rows, or scores
                # entered directly via Django admin) never get a
                # MarkSubmission/SkillsSubmission row at all, yet the badge
                # still infers "Submitted" once every student has a score —
                # matching ExamGroupMarksEntryView's own inferred-submitted
                # condition. There's nothing to flip in that case since no
                # submission record ever existed; create one as draft so the
                # badge stops claiming this row is submitted.
                student_count = exam.exam_group.batch.batch_students.filter(
                    is_active=True, tenant=tenant
                ).count()
                score_count = exam.scores.count()
                if score_count >= student_count and score_count > 0:
                    MarkSubmission.objects.update_or_create(
                        exam=exam, tenant=tenant,
                        defaults={
                            'status': MarkSubmission.STATUS_DRAFT,
                            'submitted_by': None,
                            'submitted_at': None,
                        },
                    )
                    undone_marks = True

            if not undone_marks and not undone_skills:
                return JsonResponse({
                    'success': False,
                    'error': 'Marks for this subject have not been submitted.',
                })

            was_published = exam.exam_group.result_published
            if was_published:
                exam.exam_group.result_published = False
                exam.exam_group.save()

        logging.getLogger("portal.audit").info(
            "marks.undo user=%s tenant=%s exam=%s was_published=%s skills=%s",
            request.user.id, tenant.schema_name, exam.id, was_published, undone_skills,
        )

        message = 'Submission reopened for editing.'
        if was_published:
            message = 'Submission reopened. Report cards for this class have also been unpublished.'

        return JsonResponse({'success': True, 'message': message, 'was_published': was_published})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_teacher_comments_api(request):
    """Upsert teacher comments (and shared signature) for a batch within an exam group.

    Shared verbatim between the staff exam-group page (session auth) and the
    teacher portal (JWT auth) — any authenticated user, tenant-scoped only, no
    role-specific restrictions. The portal UI already only exposes this step
    to class teachers; this endpoint trusts callers the same way the staff
    exam-group page always has.

    Storage routing (which table the rows land in) is decided by
    TeacherCommentService: SKILLS-layout batches share one batch+term-keyed
    row set with the portal skills wizard, so edits from either surface are
    immediately visible on the other.

    Accepts:
    - signature_image: string (legacy, single signature for all students)
    - signatures: dict { employee_id: dataURL } (new, per-teacher signatures)

    When signatures are provided (multi-teacher batch), comments are grouped
    by the student's current class_teacher assignment and saved per-group."""
    from core.services.teacher_comment_service import TeacherCommentService
    from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
    try:
        tenant = request.tenant
        body = request.data
        exam_group_id = body.get('exam_group_id')
        comments = body.get('comments', [])
        # Legacy: batch-level signature (all students get same image)
        signature_image = (body.get('signature_image') or '').strip()
        # New: per-teacher signatures { employee_id: dataURL }
        signatures = body.get('signatures', {})

        exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
        batch = exam_group.batch

        valid_student_ids = {
            str(sid) for sid in Student.objects.filter(
                tenant=tenant,
                id__in=[e.get('student_id') for e in comments if e.get('student_id')],
            ).values_list('id', flat=True)
        }

        svc = TeacherCommentService(tenant=tenant)
        route = svc.resolve_route(exam_group)
        total_saved = 0

        # If per-teacher signatures provided, group comments by assigned teacher
        if signatures:
            from django.db import transaction
            assignment_svc = ClassTeacherAssignmentService(tenant)
            # Group comments by teacher
            by_teacher = {}
            for comment in comments:
                sid = str(comment.get('student_id') or '')
                if not sid or sid not in valid_student_ids:
                    continue
                emp = assignment_svc.get_assigned_employee(sid, batch)
                emp_id = str(emp.id) if emp else 'UNASSIGNED'
                if emp_id not in by_teacher:
                    by_teacher[emp_id] = []
                by_teacher[emp_id].append(comment)

            # Save each teacher's group with their signature
            with transaction.atomic():
                for emp_id, group_comments in by_teacher.items():
                    sig = signatures.get(emp_id, '')
                    saved = svc.save_comments(
                        route,
                        group_comments,
                        sig,
                        clear_signature=bool(body.get('clear_signature')),
                        valid_student_ids=valid_student_ids,
                    )
                    total_saved += saved
        else:
            # Legacy: single signature for all
            total_saved = svc.save_comments(
                route,
                comments,
                signature_image,
                clear_signature=bool(body.get('clear_signature')),
                valid_student_ids=valid_student_ids,
            )

        return Response({'success': True, 'saved_count': total_saved})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_teacher_comments_api(request, exam_group_id):
    """Return saved teacher comments for all students in an exam group's batch.

    Shared verbatim between the staff exam-group page and the teacher portal —
    see save_teacher_comments_api above. Reads the same canonical rows the
    save endpoint writes (routing via TeacherCommentService), so this always
    reflects the latest edit from either portal.

    For multi-teacher batches, extends response with:
    - teachers: [{ id, name, signature_image }, ...]
    - assignments: { student_id: { employee_id, employee_name }, ... }"""
    from core.services.teacher_comment_service import TeacherCommentService
    from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
    try:
        tenant = request.tenant
        exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
        batch = exam_group.batch

        svc = TeacherCommentService(tenant=tenant)
        data = svc.get_comments(svc.resolve_route(exam_group))

        # Get per-student comment map and teacher pool
        comments_map = svc.get_comments_map(svc.resolve_route(exam_group))

        # Build teacher pool: class_teachers or fallback to primary employee
        pool = list(batch.class_teachers.all()) if batch.class_teachers.exists() else (
            [batch.employee] if batch.employee else []
        )

        # Collect signature per teacher: prioritize any row's signature_image,
        # else fall back to employee.signature_image
        teacher_sigs = {}
        for t in pool:
            t_sig = next((
                c.get('signature_image') for c in comments_map.values()
                if c.get('class_teacher_id') == str(t.id) and c.get('signature_image')
            ), None)
            teacher_sigs[str(t.id)] = t_sig or t.signature_image

        # Build teachers list
        teachers = [{
            'id': str(t.id),
            'name': t.full_name,
            'signature_image': teacher_sigs.get(str(t.id), ''),
        } for t in pool]

        # Build assignments: student_id -> { employee_id, employee_name }
        assignment_svc = ClassTeacherAssignmentService(tenant)
        overview = assignment_svc.batch_assignment_overview(batch)
        assignments = {}
        for row in overview:
            emp = row['employee']
            assignments[str(row['student'].id)] = {
                'employee_id': str(emp.id) if emp else None,
                'employee_name': emp.full_name if emp else 'Unassigned',
            }

        return Response({
            'success': True,
            'comments': data['comments'],
            'signature_image': data['signature_image'],
            'teachers': teachers,
            'assignments': assignments,
        })
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Gradebook Management Views

@method_decorator(login_required, name='dispatch')
class ExamIndexView(TemplateView):
    """Exam section landing page."""
    template_name = 'core/gradebook/exam_index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse('core:dashboard')
        context['dashboard_tiles'] = [
            {'icon': 'fa-cog', 'title': 'Settings', 'description': 'Manage Grading Levels, Ranking Levels and Class Designations', 'url': reverse('core:grading_settings')},
            {'icon': 'fa-chart-bar', 'title': 'Generate Reports', 'description': 'Generates Student Reports for Grouped Exams', 'url': reverse('core:comprehensive_reports')},
            {'icon': 'fa-laptop', 'title': 'Online Exam', 'description': 'Manage Online Exam System', 'url': reverse('core:gradebook_management')},
            {'icon': 'fa-tasks', 'title': 'Exam Management', 'description': 'Create new exams, enter marks', 'url': reverse('core:gradebook_management')},
            {'icon': 'fa-folder-open', 'title': 'Reports center', 'description': 'View Student Reports', 'url': reverse('core:generated_reports')},
        ]
        return context


@method_decorator(login_required, name='dispatch')
class GradebookIndexView(TemplateView):
    """Gradebook main index page with menu options"""
    template_name = 'core/gradebook/gradebook_index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['header_actions'] = [
            {'label': 'Dashboard', 'variant': 'outline', 'icon': 'fa-arrow-left', 'url': reverse('core:dashboard')},
        ]
        context['dashboard_tiles'] = [
            {'icon': 'fa-clipboard-list', 'title': 'Exam Planners', 'description': 'Create terms and add exam types for the academic year', 'url': reverse('core:exam_planners_list')},
            {'icon': 'fa-table', 'title': 'Manage Gradebook', 'description': 'Schedule exams, enter marks and generate reports for classes', 'url': reverse('core:gradebook_management')},
            {'icon': 'fa-keyboard', 'title': 'Enhanced Score Entry', 'description': 'Multi-dimensional score entry supporting all grading systems', 'url': reverse('core:enhanced_score_entry')},
            {'icon': 'fa-check-double', 'title': 'Skills Assessment', 'description': 'Early childhood skills evaluation with developmental tracking', 'url': reverse('core:skills_assessment_index')},
            {'icon': 'fa-chart-line', 'title': 'Comprehensive Reports', 'description': 'Generate academic, skills-based and comparative reports', 'url': reverse('core:comprehensive_reports')},
            {'icon': 'fa-sliders-h', 'title': 'Grading Settings', 'description': 'Configure grading types, levels and assessment parameters', 'url': reverse('core:grading_settings')},
        ]
        return context


@method_decorator(login_required, name='dispatch')
class ExamPlannersListView(TemplateView):
    """Exam planners list view showing all exam plans"""
    template_name = 'core/gradebook/exam_planners_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        # Get academic years
        academic_years = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date')

        # Get selected academic year from query params or default to active one
        selected_academic_year_id = self.request.GET.get('academic_year')
        if selected_academic_year_id:
            selected_academic_year = get_object_or_404(
                AcademicYear,
                id=selected_academic_year_id,
                tenant=tenant
            )
        else:
            # Always default to active academic year first
            selected_academic_year = academic_years.filter(is_active=True).first()
            if not selected_academic_year:
                # If no active year, fall back to most recent
                selected_academic_year = academic_years.first()

        # Get exam planners for the selected academic year
        exam_planners = []
        if selected_academic_year:
            # Get batches for this academic year and then their exam groups
            batches = Batch.objects.filter(
                tenant=tenant,
                academic_year=selected_academic_year
            )

            # Get all exam groups for these batches
            exam_groups = ExamGroup.objects.filter(
                tenant=tenant,
                batch__in=batches
            ).select_related('batch__course').distinct().order_by('name')

            # A planner spans a whole course: sibling ExamGroups (one per batch)
            # share a (course, name). Collapse them to one row, keyed on that, and
            # link to the batch group that holds the most exams (the definition).
            seen = {}
            for exam_group in exam_groups:
                course = exam_group.batch.course if exam_group.batch else None
                key = (course.id if course else None, exam_group.name)
                eg_exams = exam_group.exams.count()

                entry = seen.get(key)
                if entry is None:
                    # classes_linked_count starts at 1 (this ExamGroup) and is
                    # incremented below as more sibling ExamGroups for the same
                    # (course, name) are found — reflects actual included
                    # batches, not every batch in the course.
                    seen[key] = {
                        'id': exam_group.id,
                        'name': exam_group.name,
                        'course_name': course.course_name if course else '',
                        'classes_linked_count': 1,
                        'terms_count': selected_academic_year.terms_by_year.count(),
                        'exams_count': eg_exams,
                        '_rep_exams': eg_exams,
                    }
                else:
                    entry['classes_linked_count'] += 1
                    if eg_exams > entry['_rep_exams']:
                        # Prefer the batch group with the most exams as the representative.
                        entry['_rep_exams'] = eg_exams
                        entry['id'] = exam_group.id
                        entry['terms_count'] = selected_academic_year.terms_by_year.count()
                        entry['exams_count'] = eg_exams

            exam_planners = list(seen.values())

        create_exam_plan_url = reverse('core:create_exam_plan')
        context.update({
            'academic_years': academic_years,
            'selected_academic_year': selected_academic_year,
            'exam_planners': exam_planners,
            'create_exam_plan_url': create_exam_plan_url,
            'table_columns': ['Plan Name', 'Classes Linked', 'Terms', 'Exams', ''],
            'header_actions': [
                {'label': 'Import Planner', 'variant': 'outline', 'icon': 'fa-upload',
                 'attrs': 'data-bs-toggle="modal" data-bs-target="#importPlannerModal"'},
                {'label': 'Create Exam Plan', 'variant': 'primary', 'icon': 'fa-plus', 'url': create_exam_plan_url},
            ],
            'import_planner_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Import Planner', 'variant': 'primary', 'icon': 'fa-upload', 'attrs': 'onclick="importPlanner()"'},
            ],
        })
        return context


@method_decorator(login_required, name='dispatch')
class ExamPlanDetailView(TemplateView):
    """Exam plan detail view showing terms and exams"""
    template_name = 'core/gradebook/exam_plan_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        exam_plan_id = kwargs.get('pk')

        # Get the exam plan (using ExamGroup for now)
        exam_plan = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)

        # Get year-scoped terms (not per-batch, since Phase 3)
        academic_year = exam_plan.batch.academic_year
        if academic_year:
            terms = Term.objects.filter(
                tenant=tenant, academic_year=academic_year
            ).order_by('order')
        else:
            terms = Term.objects.none()

        # If no terms exist for this year, create default ones (for backward compatibility)
        if not terms.exists() and academic_year:
            # Create default 3 terms for this academic year
            for i in range(1, 4):
                Term.objects.get_or_create(
                    tenant=tenant,
                    academic_year=academic_year,
                    name=f'TERM {i} {academic_year.name}',
                    defaults={
                        'start_date': academic_year.start_date,
                        'end_date': academic_year.end_date,
                        'order': i,
                    }
                )
            # Refresh the queryset
            terms = Term.objects.filter(
                tenant=tenant, academic_year=academic_year
            ).order_by('order')

        # Get all exams and assign them to terms using the direct relationship
        all_exams_in_group = exam_plan.exams.all()

        # Group exams by exam groups instead of terms
        # Get all exam groups that have exams for this exam plan's batch
        exam_groups = ExamGroup.objects.filter(
            tenant=tenant,
            batch=exam_plan.batch,
            exams__isnull=False  # Only get exam groups that have exams
        ).distinct().order_by('exam_date', 'name')

        exam_groups_data = []
        for group in exam_groups:
            # Get all exams for this exam group
            group_exams_queryset = group.exams.all().order_by('start_time')
            group_exams = list(group_exams_queryset)

            exam_groups_data.append({
                'id': group.id,
                'name': group.name,
                'exam_type': group.exam_type,
                'exam_date': group.exam_date,
                'is_published': group.is_published,
                'is_final_exam': group.is_final_exam,
                'exams': group_exams,
                'exams_count': len(group_exams)
            })

        # Also create terms data for backward compatibility with modal forms
        terms_data = []
        for term in terms:
            # Get exams directly associated with this term
            term_exams_queryset = exam_plan.exams.filter(term=term).select_related('subject', 'grading_scale').order_by('start_time')
            term_exams = list(term_exams_queryset)  # Convert QuerySet to list

            # For backward compatibility, also include exams without term assignment
            # that fall within the term's date range
            if not term_exams:
                all_unassigned_exams = exam_plan.exams.filter(term__isnull=True).select_related('subject', 'grading_scale').order_by('start_time')
                for exam in all_unassigned_exams:
                    exam_date = exam.start_time.date()
                    if term.start_date <= exam_date <= term.end_date:
                        term_exams.append(exam)

            terms_data.append({
                'id': term.id,
                'name': term.name,
                'start_date': term.start_date,
                'end_date': term.end_date,
                # Group per-subject exam rows into one row per exam (matches the
                # exam planner UI — exams are shown, not individual subjects)
                'exams': self._group_term_exams(term_exams),
            })

        # Covered classes = batches that actually have a sibling ExamGroup for
        # this planner (name-matched), not just every batch of the course —
        # a batch excluded via Manage Classes has no such ExamGroup anymore.
        course = exam_plan.batch.course if exam_plan.batch else None
        if exam_plan.batch:
            sibling_batches = _planner_sibling_batches(exam_plan.batch)
            covered_classes = 1 + ExamGroup.objects.filter(
                tenant=tenant, name=exam_plan.name, batch__in=sibling_batches,
            ).count()
        else:
            covered_classes = 0

        # Add mock data to exam plan
        exam_plan.terms_count = len(terms_data)
        exam_plan.classes_linked_count = covered_classes
        exam_plan.academic_year = exam_plan.batch.academic_year if exam_plan.batch else None
        exam_plan.start_date = exam_plan.academic_year.start_date if exam_plan.academic_year else None
        exam_plan.end_date = exam_plan.academic_year.end_date if exam_plan.academic_year else None

        # Report configuration: which exams feed which report section, driven by
        # the grade-level report format.
        report_config = self._build_report_config(exam_plan, terms_data, tenant)

        # Layout context vars
        back_url = reverse('core:exam_planners_list')
        crumbs = [
            {'label': 'Gradebook', 'url': reverse('core:gradebook_management')},
            {'label': 'Exam Planners', 'url': reverse('core:exam_planners_list')},
            {'label': exam_plan.name},
        ]

        context.update({
            'exam_plan': exam_plan,
            'terms': terms_data,
            'exam_groups': exam_groups_data,
            'report_config': report_config,
            'planner_course': course,
            'covered_classes': covered_classes,
            'back_url': back_url,
            'crumbs': crumbs,
        })
        return context

    def _build_report_config(self, exam_plan, terms_data, tenant):
        """Build the Report Configuration panel data for the exam plan.

        Resolves the report format (an existing ReportTemplate's layout_type wins
        over the inferred default), then groups the plan's exams under the report
        sections valid for that format. For SKILLS plans, returns the skill
        categories and the include_skills flag instead of exam sections.
        """
        from collections import defaultdict
        from core.models import SkillCategory
        from core.grading_utils import (
            infer_report_layout, report_sections_for_layout, valid_slots_for_layout,
        )

        batch = exam_plan.batch
        academic_year = batch.academic_year if batch else None

        # An existing template for this batch+year is the source of truth for the
        # chosen format; otherwise infer it from the grade level.
        template = None
        if batch and academic_year:
            tpl_qs = ReportTemplate.objects.filter(
                tenant=tenant, batch=batch, academic_year=academic_year
            )
            template = tpl_qs.filter(is_default=True).first() or tpl_qs.order_by('-created_at').first()

        if template:
            layout = template.layout_type
            include_skills = template.include_skills
        else:
            layout, _scale = infer_report_layout(batch) if batch else ('FULL_ACADEMIC', None)
            include_skills = True

        config = {
            'layout_type': layout,
            'layout_choices': ReportTemplate.LAYOUT_CHOICES,
            'is_skills': layout == ReportTemplate.LAYOUT_SKILLS,
            'sections': [],
            'unassigned': [],
            'skill_categories': [],
            'include_skills': include_skills,
        }

        if config['is_skills']:
            config['skill_categories'] = list(
                SkillCategory.objects.filter(tenant=tenant, is_active=True)
                .order_by('display_order', 'name')
                .values_list('name', flat=True)
            )
            return config

        # Group every exam in the plan (across all terms) by assessment_slot,
        # reusing the per-exam → per-exam-row grouping.
        all_exams = list(
            exam_plan.exams.select_related('subject', 'grading_scale').order_by('start_time')
        )
        grouped = self._group_term_exams(all_exams)

        valid = valid_slots_for_layout(layout)
        by_slot = defaultdict(list)
        for g in grouped:
            slot = g.get('assessment_slot') or 'EXAM'
            if slot in valid:
                by_slot[slot].append(g)
            else:
                config['unassigned'].append(g)

        for slot, title in report_sections_for_layout(layout):
            config['sections'].append({
                'slot': slot,
                'title': title,
                'exams': by_slot.get(slot, []),
            })

        # All exam options for the "assign" dropdowns (one entry per grouped exam).
        config['all_exams'] = [
            {'name': g['name'], 'exam_ids_csv': g['exam_ids_csv']} for g in grouped
        ]
        return config

    @staticmethod
    def _group_term_exams(term_exams):
        """Collapse per-subject Exam rows into one row per logical exam.

        Exams created together share the same exam_name/exam_code (one Exam is
        stored per subject). The planner displays the exam, not each subject, so
        we group on (exam_name, exam_code) and pre-compute the display labels the
        template needs (mode badge, scoring badge, report-column display).
        """
        grouped = {}
        for exam in term_exams:
            if exam.exam_name and exam.exam_code:
                key = f"{exam.exam_name}|{exam.exam_code}"
                display_name = exam.display_name or exam.exam_name
            else:
                # Legacy data without exam_name/code: fall back to the subject
                key = f"subject|{exam.subject_id}"
                display_name = exam.subject.name

            group = grouped.get(key)
            if group is None:
                subject_name = exam.subject.name or ''
                if exam.subject.no_exams or 'Activity' in subject_name:
                    exam_mode = 'Activity Exams'
                elif 'ATTRIBUTE' in subject_name.upper():
                    exam_mode = 'Attribute Exams'
                elif 'SKILL' in subject_name.upper() or 'SKILL' in (exam.exam_name or '').upper():
                    exam_mode = 'Subject Skill Exams'
                else:
                    exam_mode = 'Subject Exams'

                # Scoring badge — mirrors the per-exam logic the template used
                gs = exam.grading_scale
                if gs and gs.scale_type == 'LEVEL':
                    scoring = 'Skills Assessment'
                elif exam.maximum_marks and exam.maximum_marks > 0:
                    if gs:
                        scoring = 'Marks and Grades'
                    else:
                        marks = exam.maximum_marks
                        marks = int(marks) if marks == int(marks) else marks
                        scoring = f'{marks} marks'
                else:
                    scoring = 'Grades'

                slot_display = (
                    exam.get_assessment_slot_display()
                    if exam.assessment_slot and exam.assessment_slot != 'EXAM'
                    else None
                )

                group = {
                    'name': display_name,
                    'exam_name': exam.exam_name or '',  # raw field used for API lookups
                    'exam_code': exam.exam_code or '',
                    'exam_mode': exam_mode,
                    'scoring': scoring,
                    'slot_display': slot_display,
                    'assessment_slot': exam.assessment_slot or 'EXAM',
                    'start_time': exam.start_time,
                    'representative_id': exam.id,
                    'exam_ids': [],
                    'subjects': [],
                    'subject_ids': [],
                }
                grouped[key] = group

            group['exam_ids'].append(str(exam.id))
            group['subjects'].append(exam.subject.name)
            group['subject_ids'].append(str(exam.subject_id))

        # Expose ids as comma-separated strings and subject_ids as JSON for the template/JS
        import json as _json
        result = list(grouped.values())
        for group in result:
            group['exam_ids_csv'] = ','.join(group['exam_ids'])
            group['subject_count'] = len(group['subjects'])
            group['subject_ids_json'] = _json.dumps(group['subject_ids'])
        return result


@method_decorator(login_required, name='dispatch')
class CreateExamPlanView(TemplateView):
    """Create new exam plan view"""
    template_name = 'core/gradebook/create_exam_plan.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        # Exam plans are always created in the tenant's active academic year
        # (enforced server-side in create_exam_plan_api) — shown read-only here.
        active_academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()

        # Get all courses for class selection
        courses = Course.objects.filter(tenant=tenant, is_deleted=False).order_by('course_name')

        # Get existing terms from active academic year (admin selects from these)
        available_terms = []
        if active_academic_year:
            available_terms = list(
                Term.objects.filter(
                    tenant=tenant,
                    academic_year=active_academic_year
                ).order_by('order')
            )

        context.update({
            'active_academic_year': active_academic_year,
            'courses': courses,
            'available_terms': available_terms,
            'course_options': [{'value': '', 'label': 'Select Class / Course'}] + [
                {'value': c.id, 'label': c.course_name} for c in courses
            ],
        })
        return context


@method_decorator(login_required, name='dispatch')
class ManageExamPlanClassesView(TemplateView):
    """Manage classes (batches) linked to an exam plan"""
    template_name = 'core/gradebook/manage_exam_plan_classes.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        exam_plan_id = kwargs.get('pk')

        # Get the exam plan
        exam_plan = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)

        # Get the batch linked to this exam plan
        linked_batch = exam_plan.batch
        course = linked_batch.course if linked_batch else None

        # Every batch of this planner's course + academic year is a candidate for
        # inclusion. A batch is "included" when a sibling ExamGroup sharing this
        # planner's name already exists for it.
        course_batches = []
        if linked_batch:
            course_batches = list(
                Batch.objects.filter(
                    tenant=tenant,
                    course=course,
                    academic_year=linked_batch.academic_year,
                    is_active=True,
                    is_deleted=False,
                ).order_by('name')
            )

        existing_groups = ExamGroup.objects.filter(
            tenant=tenant, name=exam_plan.name, batch__in=course_batches,
        ).annotate(exams_count=Count('exams'))
        group_by_batch = {g.batch_id: g for g in existing_groups}

        class_rows = []
        for batch in course_batches:
            group = group_by_batch.get(batch.id)
            class_rows.append({
                'batch': batch,
                'included': group is not None,
                'is_primary': batch.id == linked_batch.id,
                'exam_group_id': group.id if group else None,
                'exams_count': group.exams_count if group else 0,
            })

        # Get the academic year for the exam plan
        academic_year = linked_batch.academic_year if linked_batch else None
        if not academic_year:
            academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()

        description_parts = [exam_plan.name]
        if course:
            description_parts.append(course.course_name)
        if academic_year:
            description_parts.append(academic_year.name)

        context.update({
            'exam_plan': exam_plan,
            'linked_batch': linked_batch,
            'course': course,
            'class_rows': class_rows,
            'academic_year': academic_year,
            'manage_classes_description': ' · '.join(description_parts),
        })
        return context


@method_decorator(login_required, name='dispatch')
class GradebookManagementView(TemplateView):
    """Main gradebook management view showing classes with exams"""
    template_name = 'core/gradebook/gradebook_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(
            tenant=tenant,
            is_active=True
        ).first()

        # Get selected academic year from query params or use current
        selected_academic_year_id = self.request.GET.get('academic_year')
        if selected_academic_year_id:
            try:
                selected_academic_year = AcademicYear.objects.get(
                    id=selected_academic_year_id,
                    tenant=tenant
                )
            except AcademicYear.DoesNotExist:
                selected_academic_year = current_academic_year
        else:
            selected_academic_year = current_academic_year

        # Get all courses with their batch statistics for the selected academic year
        courses = Course.objects.filter(tenant=tenant, is_deleted=False).order_by('course_name')

        class_data = []
        # course_name → index in class_data; used to deduplicate same-named courses
        # that arise from the Fedena migration producing duplicate Course rows.
        seen_course_names = {}

        from django.utils import timezone
        now = timezone.now()

        for course in courses:
            course_batches = Batch.objects.filter(
                tenant=tenant,
                course=course,
                academic_year=selected_academic_year,
                is_active=True
            )

            if not course_batches.exists():
                continue

            active_exam_groups = ExamGroup.objects.filter(
                tenant=tenant,
                batch__in=course_batches,
                is_published=True
            ).count()

            upcoming_exams = Exam.objects.filter(
                tenant=tenant,
                exam_group__batch__in=course_batches,
                start_time__gt=now
            ).count()

            entry = {
                'course': course,
                'batch_count': course_batches.count(),
                'active_exams': active_exam_groups,
                'upcoming_exams': upcoming_exams,
                'batches': course_batches,
            }

            name = course.course_name
            if name in seen_course_names:
                # Prefer the entry whose course record holds more exam data
                existing_idx = seen_course_names[name]
                if active_exam_groups > class_data[existing_idx]['active_exams']:
                    class_data[existing_idx] = entry
            else:
                seen_course_names[name] = len(class_data)
                class_data.append(entry)
        
        # Get all academic years for the change year modal
        all_academic_years = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date')

        # Summary stats for the header cards
        total_classes = len(class_data)
        total_active = sum(c['active_exams'] for c in class_data)
        total_upcoming = sum(c['upcoming_exams'] for c in class_data)

        from django.urls import reverse
        context.update({
            'class_data': class_data,
            'current_academic_year': current_academic_year,
            'selected_academic_year': selected_academic_year,
            'all_academic_years': all_academic_years,
            'crumbs': [
                {'label': 'Home', 'url': reverse('core:dashboard')},
                {'label': 'Gradebook', 'url': reverse('core:gradebook_index')},
                {'label': 'Manage Gradebook'},
            ],
            'table_columns': ['Class', 'Batches', 'Active Exams', 'Upcoming Exam', ''],
            'stats': [
                {'label': 'Total Classes', 'value': total_classes},
                {'label': 'Active Exams', 'value': total_active},
                {'label': 'Upcoming', 'value': total_upcoming},
                {'label': 'Academic Year', 'value': selected_academic_year.name if selected_academic_year else '—', 'small': True},
            ],
            'change_year_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Set as Active Year', 'variant': 'primary', 'icon': 'fa-save', 'attrs': 'id="saveAcademicYear"'},
            ],
        })

        return context


@method_decorator(login_required, name='dispatch')
class ClassExamPlannerView(TemplateView):
    """View for managing exams for a specific class (course)"""
    template_name = 'core/gradebook/class_exam_planner.html'

    def get(self, request, *args, **kwargs):
        """Redirect to the sibling Course record that holds the real exam data when
        the requested Course has no ExamGroups but a same-named Course does.

        The Fedena migration can produce two Course rows with identical names but
        different PKs. Batches and ExamGroups may end up under either. Without
        a database merge, the cleanest UX fix is a transparent redirect so the
        user always lands on the Course that has content.
        """
        tenant = request.tenant
        course_id = kwargs.get('course_id')
        course = get_object_or_404(Course, id=course_id, tenant=tenant)

        has_groups = ExamGroup.objects.filter(tenant=tenant, batch__course=course).exists()
        if not has_groups:
            alt_courses = (
                Course.objects
                .filter(tenant=tenant, course_name=course.course_name, is_deleted=False)
                .exclude(id=course.id)
                .filter(batches__exam_groups__isnull=False)
                .distinct()
            )
            if alt_courses.count() == 1:
                from django.shortcuts import redirect as _redirect
                from django.urls import reverse as _reverse
                return _redirect(
                    _reverse('core:class_exam_planner', kwargs={'course_id': alt_courses.first().id})
                )

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        course_id = kwargs.get('course_id')

        course = get_object_or_404(Course, id=course_id, tenant=tenant)

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(
            tenant=tenant,
            is_active=True
        ).first()

        # Get all batches for this course in the current academic year
        batches = Batch.objects.filter(
            tenant=tenant,
            course=course,
            academic_year=current_academic_year
        ).order_by('name')

        # Get the primary batch (first one) for display purposes
        primary_batch = batches.first() if batches.exists() else None

        # Get all exam groups (exam planners) for batches in this course
        # ExamGroup is the correct model that contains actual exams from exam planners
        all_exam_groups = ExamGroup.objects.filter(
            tenant=tenant,
            batch__course=course
        ).order_by('name')

        # Prefer current academic year, but only when those groups actually contain
        # exams. Empty current-year groups (created as side-effects of sibling sync
        # or planner navigation) must not shadow older groups that hold real data.
        if current_academic_year:
            academic_year_filtered = all_exam_groups.filter(
                batch__academic_year=current_academic_year
            )
            if academic_year_filtered.filter(exams__isnull=False).exists():
                all_exam_groups = academic_year_filtered

        # Build exam planner data - each ExamGroup represents an exam planner like "TERM 2 2025"
        exam_planners = []
        for exam_group in all_exam_groups:
            # Get all exams in this exam group
            all_exams = exam_group.exams.all().order_by('exam_name', 'exam_code', 'subject__name')

            # Group exams by exam_name and exam_code
            # Exams with the same name/code are part of the same exam (different subjects)
            grouped_exams = {}
            for exam in all_exams:
                # Use exam_name and exam_code to create a unique key
                if exam.exam_name and exam.exam_code:
                    # Format: "EXAMINATION/TEST MARK (EM2)"
                    exam_display_name = f"{exam.exam_name} ({exam.exam_code})"
                    exam_key = f"{exam.exam_name}_{exam.exam_code}"
                else:
                    # Fallback to subject name if exam_name/code not set (legacy data)
                    exam_display_name = exam.subject.name
                    exam_key = f"subject_{exam.subject.id}"

                if exam_key not in grouped_exams:
                    # Determine exam mode based on subject type
                    if exam.subject.no_exams or 'Activity' in exam.subject.name:
                        exam_mode = 'Activity Exams'
                    elif 'ATTRIBUTE' in exam.subject.name.upper():
                        exam_mode = 'Attribute Exams'
                    elif 'SKILL' in exam.subject.name.upper():
                        exam_mode = 'Subject Skill Exams'
                    else:
                        exam_mode = 'Subject Exams'

                    grouped_exams[exam_key] = {
                        'id': exam.id,
                        'name': exam_display_name,
                        'exam_name': exam.exam_name or '',
                        'exam_code': exam.exam_code or '',
                        'exam_mode': exam_mode,
                        'is_active': exam_group.is_published,
                        'term': exam.term.name if exam.term else 'N/A',
                        'subject_count': 0,
                        'subjects': []
                    }

                # Add subject to this exam
                grouped_exams[exam_key]['subject_count'] += 1
                grouped_exams[exam_key]['subjects'].append(exam.subject.name)

            # Convert grouped exams dict to list
            exams_list = list(grouped_exams.values())

            exam_planners.append({
                'id': exam_group.id,
                'name': exam_group.name,  # This is like "TERM 2 2025"
                'exam_type': exam_group.exam_type,
                'is_published': exam_group.is_published,
                'batch': exam_group.batch,
                'exams_list': exams_list,  # List of grouped exams
                'total_exams': len(exams_list),
                'exam_date': exam_group.exam_date
            })

        # Legacy: Keep terms variable for backward compatibility (empty for now)
        terms = []

        # Get subjects for this course (through batches)
        subjects = Subject.objects.filter(
            tenant=tenant,
            batch__course=course,
            batch__academic_year=current_academic_year,
            is_deleted=False
        ).distinct().order_by('name')

        logger.debug(
            "Class exam planner: course=%s year=%s batches=%s planners=%s",
            course.course_name, current_academic_year, batches.count(), len(exam_planners),
        )

        # Calculate statistics
        total_exam_planners = len(exam_planners)

        # Calculate student count (sum of all batches)
        total_students = 0
        for batch in batches:
            student_count = batch.batch_students.filter(is_active=True).count()
            total_students += student_count

        # Count total exams across all planners
        total_exams = sum(planner['total_exams'] for planner in exam_planners)

        # Count different types of exams from actual Exam objects
        all_exams = Exam.objects.filter(
            tenant=tenant,
            exam_group__batch__course=course,
            exam_group__batch__academic_year=current_academic_year
        )

        subject_exams_count = all_exams.filter(
            subject__no_exams=False
        ).exclude(
            subject__name__icontains='Activity'
        ).count()

        activity_exams_count = all_exams.filter(
            subject__no_exams=True
        ).count() + all_exams.filter(
            subject__name__icontains='Activity'
        ).count()

        all_course_batches_count = Batch.objects.filter(tenant=tenant, course=course).count()

        context.update({
            'course': course,
            'primary_batch': primary_batch,
            'batches': batches,
            'related_batches_count': batches.count(),
            'all_course_batches_count': all_course_batches_count,
            'total_students': total_students,
            'exam_planners': exam_planners,
            'total_exam_planners': total_exam_planners,
            'total_exams': total_exams,
            'terms': terms,
            'subjects': subjects,
            'current_academic_year': current_academic_year,
            'subject_exams_count': subject_exams_count,
            'activity_exams_count': activity_exams_count,
            'attribute_exams_count': 0,
            'derived_exams_count': 0,
            'class_planner_description': f"Class exam planner — {current_academic_year.name if current_academic_year else ''}",
            'header_actions': [
                {'label': 'Exam Planner', 'variant': 'outline', 'icon': 'fa-calendar-alt', 'url': reverse('core:exam_planners_list')},
            ],
        })

        return context
    
    def _get_term_from_exam_group(self, exam_group):
        """Extract term information from exam group"""
        exam_type = exam_group.exam_type.upper()
        year = exam_group.exam_date.year
        
        if 'TERM 1' in exam_type or 'T1' in exam_type:
            return f'TERM 1 {year}'
        elif 'TERM 2' in exam_type or 'T2' in exam_type:
            return f'TERM 2 {year}'
        elif 'TERM 3' in exam_type or 'T3' in exam_type:
            return f'TERM 3 {year}'
        else:
            return f'{exam_type} {year}'


@method_decorator(login_required, name='dispatch')
class CreateExamView(TemplateView):
    """View for creating new exams"""
    template_name = 'core/gradebook/create_exam.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        batch_id = kwargs.get('batch_id')

        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant) if batch_id else None

        # Get all batches for selection
        batches = Batch.objects.filter(tenant=tenant, is_active=True).order_by('name')

        # Get subjects for the selected batch or all subjects
        if batch:
            subjects = Subject.objects.filter(
                tenant=tenant,
                batch=batch
            ).order_by('name')
        else:
            subjects = Subject.objects.filter(tenant=tenant).order_by('name')

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(
            tenant=tenant,
            is_active=True
        ).first()

        # Compute back URL
        if batch and batch.course:
            back_url = reverse('core:class_exam_planner', args=[batch.course.id])
        else:
            back_url = reverse('core:gradebook_management')

        # Build breadcrumb trail
        crumbs = [
            {'label': 'Gradebook', 'url': reverse('core:gradebook_management')},
        ]
        if batch and batch.course:
            crumbs.append({'label': batch.name, 'url': reverse('core:class_exam_planner', args=[batch.course.id])})
        crumbs.append({'label': 'Create Exam'})

        context.update({
            'batch': batch,
            'batches': batches,
            'subjects': subjects,
            'current_academic_year': current_academic_year,
            'back_url': back_url,
            'crumbs': crumbs,
        })

        return context


@method_decorator(login_required, name='dispatch')
class EditTermExamView(TemplateView):
    """View for editing term exams and final scores"""
    template_name = 'core/gradebook/edit_term_exam.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        exam_group_id = kwargs.get('exam_group_id')
        
        exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
        
        # Get exams in this group
        exams = Exam.objects.filter(
            tenant=tenant,
            exam_group=exam_group
        ).order_by('subject__name')
        
        # Check if this is a final exam (term exam)
        is_final_exam = exam_group.is_final_exam
        
        planner_url = reverse('core:class_exam_planner', args=[exam_group.batch.course.id]) if exam_group.batch and exam_group.batch.course else ''

        context.update({
            'exam_group': exam_group,
            'exams': exams,
            'is_final_exam': is_final_exam,
            'edit_exam_description': f"{exam_group.name} - {exam_group.batch.name}" if exam_group.batch else exam_group.name,
            'planner_url': planner_url,
        })

        return context


@login_required
@require_http_methods(["POST"])
def create_exam_api(request):
    """API endpoint to create a new exam"""
    try:
        tenant = request.tenant
        data = json.loads(request.body)
        
        # Extract exam data
        exam_name = data.get('exam_name')
        exam_code = data.get('exam_code')
        display_name = data.get('display_name')
        exam_type = data.get('exam_type', 'Subject Exams')
        batch_id = data.get('batch_id')
        subjects = data.get('subjects', [])
        maximum_marks = data.get('maximum_marks', 100)
        pass_criteria = data.get('pass_criteria', 50)
        exam_date = data.get('exam_date')
        grading_scale_id = data.get('grading_scale_id')

        # Optional settings
        enable_skill_entry = data.get('enable_skill_entry', False)
        enable_attendance = data.get('enable_attendance', False)
        disable_scheduling = data.get('disable_scheduling', False)

        # Get grading scale if provided
        grading_scale = None
        if grading_scale_id:
            from core.models import GradingScale
            try:
                grading_scale = GradingScale.objects.get(id=grading_scale_id, tenant=tenant)
            except GradingScale.DoesNotExist:
                pass

        # Get batch
        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
        
        # Create exam group
        exam_group = ExamGroup.objects.create(
            tenant=tenant,
            name=exam_name,
            batch=batch,
            exam_type=exam_type,
            exam_date=exam_date,
            is_published=False,
            result_published=False
        )
        
        # Create individual exams for each subject
        created_exams = []
        for subject_id in subjects:
            subject = get_object_or_404(Subject, id=subject_id, tenant=tenant)

            exam = Exam.objects.create(
                tenant=tenant,
                exam_group=exam_group,
                subject=subject,
                start_time=timezone.now(),  # Default, can be updated later
                end_time=timezone.now(),    # Default, can be updated later
                maximum_marks=maximum_marks,
                minimum_marks=pass_criteria,
                grading_scale=grading_scale  # Set grading scale if provided
            )
            created_exams.append(exam)
        
        return JsonResponse({
            'success': True,
            'message': f'Created {len(created_exams)} exams for {exam_name}',
            'exam_group_id': str(exam_group.id),
            'exams_created': len(created_exams)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_term_exam_api(request, exam_group_id):
    """API endpoint to update term exam settings"""
    try:
        tenant = request.tenant
        data = json.loads(request.body)
        exam_name = data.get('exam_name')
        display_name = data.get('display_name')
        selected_exams = data.get('selected_exams', [])
        
        exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)
        
        # Update exam group details
        if exam_name:
            exam_group.name = exam_name
        
        # Mark as final exam
        exam_group.is_final_exam = True
        exam_group.save()
        
        # Update selected exams to be included in final calculation
        for exam_data in selected_exams:
            exam_id = exam_data.get('exam_id')
            max_marks = exam_data.get('max_marks')
            
            try:
                exam = Exam.objects.get(id=exam_id, tenant=tenant)
                if max_marks:
                    exam.maximum_marks = max_marks
                    exam.save()
            except Exam.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': 'Term exam updated successfully',
            'exam_group_id': str(exam_group.id)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_batch_subjects_api(request, batch_id):
    """API endpoint to get subjects for a specific batch"""
    try:
        tenant = request.tenant
        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

        subjects = Subject.objects.filter(
            tenant=tenant,
            batch=batch
        ).order_by('name')

        subjects_data = [{
            'id': str(subject.id),
            'name': subject.name,
            'code': subject.code or '',
        } for subject in subjects]

        return JsonResponse({
            'success': True,
            'subjects': subjects_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def import_exam_planner_api(request):
    """API endpoint to import exam planner from file"""
    try:
        tenant = request.tenant

        if 'file' not in request.FILES or 'name' not in request.POST:
            return JsonResponse({'success': False, 'error': 'File and name are required'})

        uploaded_file = request.FILES['file']
        planner_name = request.POST['name']

        # For now, just create a basic exam group
        # You would implement actual file parsing logic here
        # Always the tenant's active year — no fallback to "most recent" — so
        # imported planners can't silently land on a stale year.
        current_academic_year = AcademicYear.objects.filter(
            tenant=tenant,
            is_active=True
        ).first()

        if not current_academic_year:
            return JsonResponse({'success': False, 'error': 'No active academic year is configured.'})

        # Get a default batch for this academic year
        default_batch = Batch.objects.filter(
            tenant=tenant,
            academic_year=current_academic_year
        ).first()

        if not default_batch:
            return JsonResponse({'success': False, 'error': 'No batches found for the current academic year'})

        # Create exam group (representing exam planner)
        exam_group = ExamGroup.objects.create(
            tenant=tenant,
            name=planner_name,
            batch=default_batch,
            exam_type='IMPORTED',
            exam_date=current_academic_year.start_date,
            is_published=False
        )

        return JsonResponse({
            'success': True,
            'message': f'Exam planner "{planner_name}" imported successfully',
            'planner_id': str(exam_group.id)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_exam_plan_api(request):
    """API endpoint to create a new exam plan"""
    try:
        tenant = request.tenant

        name = request.POST.get('name')
        enable_gpa = request.POST.get('enable_gpa') == 'on'

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})

        # Exam plans are always created against the tenant's active academic
        # year — never a year picked from the request — so a stale page or a
        # deliberate other-year choice can't silently attach terms to the
        # wrong year.
        academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
        if not academic_year:
            return JsonResponse({'success': False, 'error': 'No active academic year is configured.'})

        # A planner is anchored to a course; its exams propagate to every active
        # batch of that course in this academic year. The "primary" batch is just
        # the one the planner page edits.
        course_id = request.POST.get('course_id')
        batch_id = request.POST.get('batch_id')
        if batch_id:
            batch = get_object_or_404(Batch, id=batch_id, tenant=tenant, academic_year=academic_year)
        elif course_id:
            batch = Batch.objects.filter(
                tenant=tenant, course_id=course_id, academic_year=academic_year,
                is_active=True, is_deleted=False,
            ).order_by('name').first()
            if not batch:
                return JsonResponse({'success': False, 'error': 'The selected class has no active batch for this academic year. Create a batch first.'})
        else:
            # Fallback: first batch for this academic year
            batch = Batch.objects.filter(
                tenant=tenant,
                academic_year=academic_year
            ).first()

            if not batch:
                return JsonResponse({'success': False, 'error': 'No batches found for the selected academic year. Please create a batch first.'})

        if ExamGroup.objects.filter(tenant=tenant, batch=batch, name=name, exam_type='PLANNER').exists():
            return JsonResponse({'success': False, 'error': f'An exam plan named "{name}" already exists for this batch.'})

        # Create exam group (representing exam planner)
        exam_group = ExamGroup.objects.create(
            tenant=tenant,
            name=name,
            batch=batch,
            exam_type='PLANNER',
            exam_date=academic_year.start_date,
            is_published=False
        )

        # Admin must select existing terms from the active academic year
        # No automatic term creation — terms must be created separately via Academic Year management
        selected_term_ids = request.POST.getlist('term_ids[]')
        if selected_term_ids:
            # Validate that selected terms belong to this academic year
            valid_terms = Term.objects.filter(
                tenant=tenant,
                academic_year=academic_year,
                id__in=selected_term_ids
            )
            if valid_terms.count() != len(selected_term_ids):
                return JsonResponse({
                    'success': False,
                    'error': 'One or more selected terms do not belong to the active academic year'
                })

        return JsonResponse({
            'success': True,
            'message': f'Exam plan "{name}" created successfully',
            'planner_id': str(exam_group.id)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@method_decorator(login_required, name='dispatch')
class AcademicYearListView(TemplateView):
    """Academic year management view"""
    template_name = 'core/academic/academic_years.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        academic_years = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date')

        context.update({
            'academic_years': academic_years,
        })
        return context


@login_required
@require_http_methods(["POST"])
def set_active_academic_year_api(request):
    """API endpoint to set an academic year as active"""
    try:
        tenant = request.tenant
        academic_year_id = request.POST.get('academic_year_id')

        if not academic_year_id:
            return JsonResponse({'success': False, 'error': 'Academic year ID is required'})

        # Get the academic year
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id, tenant=tenant)

        # The save method will automatically handle deactivating others
        academic_year.is_active = True
        academic_year.save()

        return JsonResponse({
            'success': True,
            'message': f'"{academic_year.name}" has been set as the active academic year',
            'active_year_id': str(academic_year.id),
            'active_year_name': academic_year.name
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_academic_year_api(request):
    """API endpoint to create a new academic year"""
    try:
        tenant = request.tenant

        name = request.POST.get('name')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        is_active = request.POST.get('is_active') == 'true'
        admission_start_date = request.POST.get('admission_start_date') or None
        admission_end_date = request.POST.get('admission_end_date') or None

        if not all([name, start_date, end_date]):
            return JsonResponse({
                'success': False,
                'error': 'Name, start date, and end date are required'
            })

        # Create the academic year
        academic_year = AcademicYear.objects.create(
            tenant=tenant,
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            admission_start_date=admission_start_date,
            admission_end_date=admission_end_date
        )

        return JsonResponse({
            'success': True,
            'message': f'Academic year "{name}" created successfully',
            'academic_year_id': str(academic_year.id),
            'is_active': academic_year.is_active
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def get_academic_year_api(request, year_id):
    """API endpoint to get a single academic year's details"""
    try:
        tenant = request.tenant
        academic_year = get_object_or_404(AcademicYear, id=year_id, tenant=tenant)
        return JsonResponse({
            'success': True,
            'academic_year': {
                'id': str(academic_year.id),
                'name': academic_year.name,
                'start_date': str(academic_year.start_date),
                'end_date': str(academic_year.end_date),
                'is_active': academic_year.is_active,
                'admission_start_date': str(academic_year.admission_start_date) if academic_year.admission_start_date else '',
                'admission_end_date': str(academic_year.admission_end_date) if academic_year.admission_end_date else '',
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_academic_year_api(request, year_id):
    """API endpoint to update an existing academic year"""
    try:
        tenant = request.tenant
        academic_year = get_object_or_404(AcademicYear, id=year_id, tenant=tenant)

        name = request.POST.get('name')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        admission_start_date = request.POST.get('admission_start_date') or None
        admission_end_date = request.POST.get('admission_end_date') or None

        if not all([name, start_date, end_date]):
            return JsonResponse({'success': False, 'error': 'Name, start date, and end date are required'})

        academic_year.name = name
        academic_year.start_date = start_date
        academic_year.end_date = end_date
        academic_year.admission_start_date = admission_start_date
        academic_year.admission_end_date = admission_end_date
        academic_year.save()

        return JsonResponse({
            'success': True,
            'message': f'Academic year "{name}" updated successfully',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_academic_year_api(request, year_id):
    """API endpoint to delete an academic year"""
    try:
        tenant = request.tenant
        academic_year = get_object_or_404(AcademicYear, id=year_id, tenant=tenant)

        if academic_year.is_active:
            return JsonResponse({'success': False, 'error': 'Cannot delete the active academic year. Please activate another year first.'})

        name = academic_year.name
        academic_year.delete()

        return JsonResponse({'success': True, 'message': f'Academic year "{name}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def get_exam_plan_subjects_api(request):
    """API endpoint to get subjects for an exam plan"""
    try:
        tenant = request.tenant
        exam_plan_id = request.GET.get('exam_plan_id')

        if not exam_plan_id:
            return JsonResponse({'success': False, 'error': 'Missing exam_plan_id'})

        # Get the exam plan (ExamGroup)
        exam_group = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)

        # Get the batch associated with this exam group
        primary_batch = exam_group.batch
        if not primary_batch:
            return JsonResponse({'success': False, 'error': 'No batch associated with this exam plan'})

        # A planner applies to the whole course, so offer every subject assigned to
        # ANY active batch of the course (same academic year), not just the primary
        # batch. Subjects are matched across batches by name during propagation, so
        # we de-duplicate by name and let the primary batch's row win — that keeps
        # the created exam anchored to the primary batch.
        course_batches = [primary_batch] + list(_planner_sibling_batches(primary_batch))

        # All non-deleted subjects across the course batches.  The no_exams flag
        # is not a visibility criterion (subject center and batch details pages
        # show these subjects too), so we do not filter on it here.
        subjects = Subject.objects.filter(
            tenant=tenant,
            batch__in=course_batches,
            is_deleted=False,
        ).order_by('name')

        # De-duplicate by name (case-insensitive); prefer the primary batch's row.
        subjects_by_name = {}
        for subject in subjects:
            key = (subject.name or '').strip().lower()
            existing = subjects_by_name.get(key)
            if existing is None or (subject.batch_id == primary_batch.id
                                    and existing.batch_id != primary_batch.id):
                subjects_by_name[key] = subject

        subjects_data = [
            {
                'id': str(subject.id),
                'name': subject.name,
                'code': subject.code or subject.name[:3].upper(),
            }
            for subject in sorted(subjects_by_name.values(), key=lambda s: s.name.lower())
        ]

        return JsonResponse({
            'success': True,
            'subjects': subjects_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_exam_edit_subjects_api(request):
    """Subjects list for the Edit Subjects modal on the exam plan detail page.

    Unlike get_exam_plan_subjects_api (which queries the batch's subject table),
    this endpoint derives the *current* selection directly from the Exam records
    themselves.  That means subjects are always shown as checked even if they
    were soft-deleted by the dedup migration or carry no_exams=True — the exams
    already exist, so the modal must reflect them.

    Response shape per subject:
      { id, name, code, is_current: true|false }
    """
    try:
        tenant = request.tenant
        exam_plan_id = request.GET.get('exam_plan_id')
        term_id      = request.GET.get('term_id')
        exam_name    = (request.GET.get('exam_name') or '').strip()
        exam_code    = (request.GET.get('exam_code') or '').strip()

        if not all([exam_plan_id, term_id, exam_name]):
            return JsonResponse({'success': False,
                                 'error': 'exam_plan_id, term_id, and exam_name are required'})

        exam_group = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)
        term       = get_object_or_404(Term,      id=term_id,      tenant=tenant)

        # Currently-assigned subjects — derived from real Exam rows so that
        # soft-deleted or no_exams=True subjects are never lost from the list.
        # exam_code may be stored as NULL when the template sent an empty string,
        # so match both '' and NULL when exam_code is blank.
        from django.db.models import Q as _Q
        _ec_filter = (
            _Q(exam_code=exam_code)
            if exam_code
            else (_Q(exam_code='') | _Q(exam_code__isnull=True))
        )
        current_exams = list(
            Exam.objects.filter(
                _ec_filter,
                tenant=tenant,
                exam_group=exam_group,
                term=term,
                exam_name=exam_name,
            ).select_related('subject')
        )

        result      = []
        seen_names  = set()   # lower-cased names already added to result
        current_ids = set()   # subject UUIDs already in the exam

        for e in sorted(current_exams, key=lambda x: (x.subject.name or '').lower()):
            name_key = (e.subject.name or '').strip().lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            current_ids.add(e.subject_id)
            result.append({
                'id':         str(e.subject_id),
                'name':       e.subject.name,
                'code':       e.subject.code or '',
                'is_current': True,
            })

        # Available subjects — only from the PRIMARY batch so that every subject
        # returned here can actually be added to this ExamGroup's exams.
        # Sibling-batch subjects cannot be added to the primary group (no target
        # subject would exist there), so offering them only causes silent no-ops.
        primary_batch = exam_group.batch

        available_qs = Subject.objects.filter(
            tenant=tenant,
            batch=primary_batch,
            is_deleted=False,
        ).exclude(id__in=list(current_ids)).order_by('name')

        for s in available_qs:
            key = (s.name or '').strip().lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            result.append({
                'id':         str(s.id),
                'name':       s.name,
                'code':       s.code or '',
                'is_current': False,
            })

        return JsonResponse({'success': True, 'subjects': result})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ---- Course-level exam-planner propagation -------------------------------
# A planner is shown as one ExamGroup (the "primary", bound to one batch), but
# conceptually applies to the whole course. These helpers replicate the planner's
# exams to every active batch of the same course in the same academic year, so a
# gradebook is consistent across all classes of a course.

def _exam_name_q(field, value):
    """Return a Q that matches both NULL and '' for exam_name / exam_code fields.

    The model allows null=True, blank=True, so values can arrive as either NULL
    or empty-string depending on how the exam was created. Treating them as
    equivalent prevents the duplicate-check from missing existing rows and
    creating duplicates on subsequent syncs.
    """
    from django.db.models import Q
    if not value:  # None or ''
        return Q(**{f'{field}__isnull': True}) | Q(**{field: ''})
    return Q(**{field: value})


def _planner_sibling_batches(primary_batch):
    """Active, non-deleted batches of the primary batch's course in the same
    academic year, excluding the primary batch itself."""
    if not primary_batch or not primary_batch.academic_year_id:
        return Batch.objects.none()
    return Batch.objects.filter(
        tenant=primary_batch.tenant,
        course=primary_batch.course,
        academic_year=primary_batch.academic_year,
        is_active=True,
        is_deleted=False,
    ).exclude(id=primary_batch.id)


def _matching_subject(batch, subject):
    """Find the subject in `batch` that matches `subject` by name (fallback code).
    Mirrors the source subject's activity flag so exams land on the right kind."""
    base = Subject.objects.filter(tenant=batch.tenant, batch=batch, is_deleted=False)
    match = base.filter(name__iexact=subject.name).first()
    if not match and subject.code:
        match = base.filter(code__iexact=subject.code).first()
    return match


def _propagate_exams_to_batch(primary_group, batch, exams=None):
    """Replicate the primary group's exams into a single sibling batch.

    Idempotent: an exam is only created when no exam with the same
    (exam_group, subject, exam_name, exam_code, term) already exists.
    Returns (created_count, skipped_list) where skipped is [{batch, subject}].

    Phase 3: Terms are no longer per-batch; uses year-scoped Term lookups.
    """
    tenant = primary_group.tenant

    if exams is None:
        exams = list(primary_group.exams.select_related('subject', 'grading_scale', 'term').all())
    else:
        exams = list(exams)

    created = 0
    skipped = []  # [{batch, subject}]

    # Phase 3: Create sibling exam group but don't mirror terms
    # (terms are now year-scoped, not per-batch)
    sibling_group = ExamGroup.objects.filter(
        tenant=tenant, batch=batch, name=primary_group.name,
    ).first()
    if sibling_group is None:
        sibling_group = ExamGroup.objects.create(
            tenant=tenant, batch=batch, name=primary_group.name,
            exam_type=primary_group.exam_type or 'PLANNER',
            exam_date=primary_group.exam_date,
            is_published=False,
        )

    for exam in exams:
        src_subject = exam.subject
        is_activity = src_subject.no_exams or 'Activity' in (src_subject.name or '')

        if is_activity:
            # Activity subjects are system-generated — safe to create per batch.
            target_subject = Subject.objects.filter(
                tenant=tenant, batch=batch, name=src_subject.name, is_deleted=False,
            ).first()
            if target_subject is None:
                target_subject = Subject.objects.create(
                    tenant=tenant, batch=batch, name=src_subject.name,
                    code=src_subject.code or (src_subject.name or 'ACT')[:10].upper(),
                    no_exams=True,
                )
        else:
            target_subject = _matching_subject(batch, src_subject)
            if not target_subject:
                # Mirror the subject into this sibling batch so propagation
                # can complete rather than silently skipping the exam.
                try:
                    target_subject = Subject.objects.create(
                        tenant=tenant,
                        batch=batch,
                        name=src_subject.name,
                        code=src_subject.code or (src_subject.name or 'SUB')[:10].upper(),
                        no_exams=src_subject.no_exams,
                    )
                except Exception:
                    skipped.append({'batch': batch.name, 'subject': src_subject.name})
                    continue

        # Phase 3: Look up year-scoped term directly (not per-batch)
        target_term = None
        if exam.term_id:
            target_term = Term.objects.filter(
                tenant=tenant,
                academic_year=batch.academic_year,
                name=exam.term.name,
            ).first()

        exists = (
            Exam.objects
            .filter(tenant=tenant, exam_group=sibling_group, subject=target_subject, term=target_term)
            .filter(_exam_name_q('exam_name', exam.exam_name))
            .filter(_exam_name_q('exam_code', exam.exam_code))
            .exists()
        )
        if exists:
            continue

        # Normalize to None so the DB stores NULL consistently.
        norm_name = exam.exam_name or None
        norm_code = exam.exam_code or None

        # One bad row shouldn't abort the whole sync.
        try:
            Exam.objects.create(
                tenant=tenant,
                exam_group=sibling_group,
                subject=target_subject,
                term=target_term,
                exam_name=norm_name,
                exam_code=norm_code,
                display_name=exam.display_name,
                start_time=exam.start_time,
                end_time=exam.end_time,
                maximum_marks=exam.maximum_marks,
                minimum_marks=exam.minimum_marks,
                weightage=exam.weightage,
                grading_scale=exam.grading_scale,
                assessment_slot=exam.assessment_slot,
            )
            created += 1
        except Exception:
            logger.exception(
                "Failed to propagate exam %s to batch %s", exam.id, batch.id
            )
            skipped.append({'batch': batch.name, 'subject': src_subject.name})

    return created, skipped


def propagate_plan_exams(primary_group, exams=None, user=None):
    """Replicate the primary group's exams to every sibling batch of the course.

    Idempotent — see _propagate_exams_to_batch. Returns a coverage report dict.
    """
    primary_batch = primary_group.batch
    siblings = list(_planner_sibling_batches(primary_batch))

    if exams is None:
        exams = list(primary_group.exams.select_related('subject', 'grading_scale', 'term').all())
    else:
        exams = list(exams)

    created = 0
    skipped = []  # [{batch, subject}]

    for batch in siblings:
        batch_created, batch_skipped = _propagate_exams_to_batch(primary_group, batch, exams)
        created += batch_created
        skipped.extend(batch_skipped)

    return {
        'created': created,
        'skipped': skipped,
        'classes_covered': len(siblings) + 1,  # siblings + primary
    }


@login_required
@require_http_methods(["POST"])
def create_term_exams_api(request):
    """API endpoint to create exams for a specific term"""
    try:
        import json
        from datetime import datetime, timedelta

        tenant = request.tenant

        term_id = request.POST.get('term_id')
        exam_plan_id = request.POST.get('exam_plan_id')
        subjects_json = request.POST.get('subjects')
        exam_type = request.POST.get('exam_type', 'subject')  # 'subject' or 'activity'
        skill_sets_json = request.POST.get('skill_sets')

        # Get exam name, code, and display name. Normalize to None so the DB
        # stores NULL consistently (model is null=True, blank=True for both).
        exam_name = request.POST.get('exam_name') or None
        exam_code = request.POST.get('exam_code') or None
        display_name = request.POST.get('display_name', '')

        # Get scoring type and marks
        scoring_type = request.POST.get('scoring_type', 'marks')  # 'marks', 'grades', or 'marks_and_grades'
        maximum_marks = request.POST.get('maximum_marks', '100')
        max_marks = int(maximum_marks) if maximum_marks else 100

        # Assessment slot for report column mapping
        assessment_slot = request.POST.get('assessment_slot', 'EXAM')

        # For grades-only and skills assessment exams, set max_marks to 0
        # Grade-type slots (ATTAINMENT, EFFORT, CLASSWORK) are always grade-only
        if scoring_type in ('grades', 'skills') or assessment_slot in ('ATTAINMENT', 'EFFORT', 'CLASSWORK'):
            max_marks = 0
            scoring_type = 'grades'

        grading_scale_id = request.POST.get('grading_scale_id')

        # Get grading scale if provided
        grading_scale = None
        if grading_scale_id:
            from core.models import GradingScale
            try:
                grading_scale = GradingScale.objects.get(id=grading_scale_id, tenant=tenant)
            except GradingScale.DoesNotExist:
                pass

        if not all([term_id, exam_plan_id]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        # Check if we have either subjects or skill sets based on exam type
        if exam_type == 'activity' and not skill_sets_json:
            return JsonResponse({'success': False, 'error': 'Missing skill sets for activity exam'})
        elif exam_type == 'subject' and not subjects_json:
            return JsonResponse({'success': False, 'error': 'Missing subjects for subject exam'})

        # Get the term and exam plan
        term = get_object_or_404(Term, id=term_id, tenant=tenant)
        exam_group = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)

        # Use default datetime (can be updated later per subject)
        from django.utils import timezone
        exam_start_datetime = timezone.now()
        exam_end_datetime = exam_start_datetime + timedelta(hours=2)

        created_exams = []
        primary_exams = []  # actual Exam objects, used to propagate across the course
        batches_with_new_exams = set()

        if exam_type == 'activity':
            # Handle skill-based exams
            selected_skill_sets = json.loads(skill_sets_json)

            # For skill-based exams, we'll create a general subject or use existing ones
            # Get the batch to find or create subjects for skill sets
            batch = exam_group.batch

            for skill_set_id in selected_skill_sets:
                try:
                    # Create or get a subject for this skill set
                    subject_name = f"Activity - {skill_set_id.replace('_', ' ').title()}"
                    subject, created = Subject.objects.get_or_create(
                        tenant=tenant,
                        batch=batch,
                        name=subject_name,
                        defaults={
                            'code': skill_set_id.upper()[:10],
                            'no_exams': True  # Mark as activity exam
                        }
                    )

                    # Update existing subjects to mark as activity
                    if not created and not subject.no_exams:
                        subject.no_exams = True
                        subject.save()

                    # Create the exam
                    exam = Exam.objects.create(
                        tenant=tenant,
                        exam_group=exam_group,
                        subject=subject,
                        term=term,  # Associate with the specific term
                        exam_name=exam_name,
                        exam_code=exam_code,
                        display_name=display_name,
                        start_time=exam_start_datetime,
                        end_time=exam_end_datetime,
                        maximum_marks=0,  # No numeric marks for skill-based assessment
                        minimum_marks=0,
                        weightage=100,
                        grading_scale=grading_scale  # Set grading scale if provided
                    )


                    primary_exams.append(exam)
                    created_exams.append({
                        'id': str(exam.id),
                        'subject': subject.name,
                        'skill_set': skill_set_id,
                        'start_time': exam.start_time.strftime('%Y-%m-%d %H:%M'),
                        'type': 'activity'
                    })

                except Exception as e:
                    return JsonResponse({'success': False, 'error': f'Failed to create activity exam for {skill_set_id}: {str(e)}'})

        else:
            # Handle regular subject exams.
            # Create exams directly on each batch that owns the selected subject,
            # rather than anchoring everything to the primary batch first.
            selected_subjects = json.loads(subjects_json)
            primary_batch = exam_group.batch

            all_course_batches = [primary_batch] + list(_planner_sibling_batches(primary_batch))

            # Phase 3: Pre-build sibling exam groups (not term maps, since terms are year-scoped)
            sibling_cache = {}  # batch_id -> sibling_group
            for _batch in all_course_batches:
                if _batch.id != primary_batch.id:
                    _sg = ExamGroup.objects.filter(
                        tenant=tenant, batch=_batch, name=exam_group.name,
                    ).first()
                    if _sg is None:
                        _sg = ExamGroup.objects.create(
                            tenant=tenant, batch=_batch, name=exam_group.name,
                            exam_type=exam_group.exam_type or 'PLANNER',
                            exam_date=exam_group.exam_date,
                            is_published=False,
                        )
                    sibling_cache[_batch.id] = _sg

            batches_with_new_exams = set()

            for subject_id in selected_subjects:
                try:
                    src_subject = get_object_or_404(Subject, id=subject_id, tenant=tenant)

                    for batch in all_course_batches:
                        if batch.id == primary_batch.id:
                            target_group = exam_group
                            target_term = term
                            target_subject = (
                                src_subject if src_subject.batch_id == batch.id
                                else _matching_subject(batch, src_subject)
                            )
                        else:
                            # Phase 3: Look up year-scoped term directly
                            target_group = sibling_cache[batch.id]
                            target_term = Term.objects.filter(
                                tenant=tenant,
                                academic_year=batch.academic_year,
                                name=term.name,
                            ).first() if term else None
                            target_subject = _matching_subject(batch, src_subject)

                        if not target_subject:
                            # Subject doesn't exist in this batch yet — mirror it
                            # so that the exam is visible on every batch's planner.
                            target_subject = Subject.objects.create(
                                tenant=tenant,
                                batch=batch,
                                name=src_subject.name,
                                code=src_subject.code or (src_subject.name or 'SUB')[:10].upper(),
                                no_exams=src_subject.no_exams,
                            )

                        # Idempotent: skip if the exam already exists on this batch.
                        # Use _exam_name_q to treat NULL and '' as equivalent so
                        # we don't create duplicates regardless of how prior rows
                        # were stored.
                        if (
                            Exam.objects
                            .filter(tenant=tenant, exam_group=target_group, subject=target_subject, term=target_term)
                            .filter(_exam_name_q('exam_name', exam_name))
                            .filter(_exam_name_q('exam_code', exam_code))
                            .exists()
                        ):
                            continue

                        exam = Exam.objects.create(
                            tenant=tenant,
                            exam_group=target_group,
                            subject=target_subject,
                            term=target_term,
                            exam_name=exam_name,
                            exam_code=exam_code,
                            display_name=display_name,
                            start_time=exam_start_datetime,
                            end_time=exam_end_datetime,
                            maximum_marks=max_marks,
                            minimum_marks=max_marks * 0.4,
                            weightage=100,
                            grading_scale=grading_scale,
                            assessment_slot=assessment_slot,
                        )

                        batches_with_new_exams.add(batch.name)
                        if batch.id == primary_batch.id:
                            primary_exams.append(exam)
                            created_exams.append({
                                'id': str(exam.id),
                                'subject': target_subject.name,
                                'start_time': exam.start_time.strftime('%Y-%m-%d %H:%M'),
                                'max_marks': exam.maximum_marks,
                                'type': 'subject',
                            })

                except Exception as e:
                    return JsonResponse({'success': False, 'error': f'Failed to create exam for {subject_id}: {str(e)}'})

        classes_covered = sorted(batches_with_new_exams)
        message = f'Successfully created {len(created_exams)} exams for {term.name}'
        if len(classes_covered) > 1:
            message += f' across {len(classes_covered)} class(es)'

        return JsonResponse({
            'success': True,
            'message': message,
            'exams': created_exams,
            'term_name': term.name,
            'term_id': term.id,
            'classes_covered': classes_covered,
            'debug_info': {
                'exam_group_id': str(exam_group.id),
                'total_exams_in_group': exam_group.exams.count()
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def propagate_exam_plan_api(request, exam_plan_id):
    """Sync to all classes: replicate every exam in this planner to all active
    batches of the course in the same academic year. Idempotent — re-running only
    fills gaps. Returns a coverage report."""
    try:
        tenant = request.tenant
        exam_group = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)

        report = propagate_plan_exams(exam_group, exams=None, user=request.user)

        skipped_classes = sorted({s['batch'] for s in report['skipped']})
        message = (
            f"Synced to {report['classes_covered'] - 1} other class(es); "
            f"{report['created']} exam(s) added."
        )
        if skipped_classes:
            message += f' Skipped (missing subject): {", ".join(skipped_classes)}'
        return JsonResponse({
            'success': True,
            'message': message,
            'created': report['created'],
            'classes_covered': report['classes_covered'],
            'skipped_classes': skipped_classes,
        })
    except Exception as e:
        logger.exception("propagate_exam_plan_api failed")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_exam_plan_api(request, exam_plan_id):
    """Delete an exam planner. Because a planner is course-wide (one ExamGroup per
    batch sharing a name), this removes the planner from every batch of the course
    for that academic year. Cascades to terms, exams and entered scores."""
    try:
        tenant = request.tenant
        exam_group = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)

        # All sibling planner groups (this batch + the rest of the course/year).
        batch_ids = [exam_group.batch_id] + list(
            _planner_sibling_batches(exam_group.batch).values_list('id', flat=True)
        )
        groups = ExamGroup.objects.filter(
            tenant=tenant, name=exam_group.name, batch_id__in=batch_ids,
        )
        deleted_count = groups.count()
        groups.delete()  # cascades Term, Exam, ExamScore

        return JsonResponse({
            'success': True,
            'message': f'Deleted the planner from {deleted_count} class(es).',
        })
    except Exception as e:
        logger.exception("delete_exam_plan_api failed")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_term_api(request, term_id):
    """Delete a term and the exams scheduled under it. Other terms are untouched."""
    try:
        tenant = request.tenant
        term = get_object_or_404(Term, id=term_id, tenant=tenant)

        # Remove exams scheduled with this term first (Exam.term is SET_NULL).
        Exam.objects.filter(tenant=tenant, term=term).delete()
        term.delete()

        return JsonResponse({'success': True, 'message': 'Term deleted.'})
    except Exception as e:
        logger.exception("delete_term_api failed")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_term_api(request, term_id):
    """Update a term's name/start_date/end_date within this planner.

    NOTE: renaming does NOT re-scope existing HomeworkAssessment/
    ProjectWorkAssessment/StudentActivity records that store the term name as a
    string, nor attendance reports already generated against the old date
    range. That historical re-scoping is intentionally out of scope here (see
    the fix_*_term_scoping management commands for the repair path).
    """
    try:
        tenant = request.tenant
        term = get_object_or_404(Term, id=term_id, tenant=tenant)

        name = (request.POST.get('name') or '').strip()
        start_date = (request.POST.get('start_date') or '').strip()
        end_date = (request.POST.get('end_date') or '').strip()

        if not name:
            return JsonResponse({'success': False, 'error': 'Term name is required.'})
        if not start_date or not end_date:
            return JsonResponse({'success': False, 'error': 'Start and end dates are required.'})
        try:
            sd = date.fromisoformat(start_date)
            ed = date.fromisoformat(end_date)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid date format.'})
        if sd >= ed:
            return JsonResponse({'success': False, 'error': 'Start date must be before end date.'})

        term.name = name
        term.start_date = sd
        term.end_date = ed
        term.save(update_fields=['name', 'start_date', 'end_date'])

        return JsonResponse({'success': True, 'message': 'Term updated.'})
    except Exception as e:
        logger.exception("update_term_api failed")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def assign_exam_slot_api(request):
    """Assign every per-subject exam in a grouped exam to a report section (slot).

    Used by the Report Configuration panel on the exam-planner page. Mirrors the
    grade-only marks rule from ``create_term_exams_api``: ATTAINMENT/EFFORT/
    CLASSWORK slots carry a grade only, so numeric marks are zeroed.
    """
    try:
        tenant = request.tenant
        exam_ids = [e for e in (request.POST.get('exam_ids', '') or '').split(',') if e.strip()]
        assessment_slot = (request.POST.get('assessment_slot') or '').strip().upper()

        if not exam_ids:
            return JsonResponse({'success': False, 'error': 'No exams specified'})

        valid_slots = {c[0] for c in Exam.SLOT_CHOICES}
        if assessment_slot not in valid_slots:
            return JsonResponse({'success': False, 'error': 'Invalid report section'})

        exams = list(Exam.objects.filter(id__in=exam_ids, tenant=tenant))
        if not exams:
            return JsonResponse({'success': False, 'error': 'Exams not found'})

        grade_only = assessment_slot in ('ATTAINMENT', 'EFFORT', 'CLASSWORK')
        for exam in exams:
            exam.assessment_slot = assessment_slot
            if grade_only:
                exam.maximum_marks = 0
                exam.minimum_marks = 0
            exam.save(update_fields=['assessment_slot', 'maximum_marks', 'minimum_marks'])

        return JsonResponse({'success': True, 'updated': len(exams)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def set_report_format_api(request):
    """Set the report format (layout) and skills inclusion for an exam plan.

    The format is a grade-level property, so it is applied to every ReportTemplate
    for the plan's batch + academic year. When none exist yet, one representative
    template is created (mirroring the lazy-create in ``generate_class_reports``)
    so report generation honours the choice.
    """
    try:
        tenant = request.tenant
        exam_group = get_object_or_404(ExamGroup, id=request.POST.get('exam_plan_id'), tenant=tenant)
        batch = exam_group.batch
        academic_year = batch.academic_year if batch else None
        if not batch or not academic_year:
            return JsonResponse({'success': False, 'error': 'Exam plan has no batch or academic year'})

        layout_type = (request.POST.get('layout_type') or '').strip()
        include_skills_raw = request.POST.get('include_skills')

        update_fields = {}
        if layout_type:
            valid_layouts = {c[0] for c in ReportTemplate.LAYOUT_CHOICES}
            if layout_type not in valid_layouts:
                return JsonResponse({'success': False, 'error': 'Invalid report format'})
            update_fields['layout_type'] = layout_type
        if include_skills_raw is not None:
            update_fields['include_skills'] = include_skills_raw in ('true', 'on', '1', 'True')

        if not update_fields:
            return JsonResponse({'success': False, 'error': 'Nothing to update'})

        templates = ReportTemplate.objects.filter(
            tenant=tenant, batch=batch, academic_year=academic_year
        )
        if templates.exists():
            templates.update(**update_fields)
        else:
            def field_default(fname):
                return ReportTemplate._meta.get_field(fname).default

            from .services.report_generation_service import ReportGenerationService
            auto_term = ReportGenerationService.resolve_exam_group_term(exam_group)
            ReportTemplate.objects.create(
                tenant=tenant, batch=batch, term=auto_term, academic_year=academic_year,
                name=f"{batch.name} — {exam_group.name}",
                school_name=getattr(tenant, 'name', '') or field_default('school_name'),
                school_address=getattr(tenant, 'address_line1', '') or field_default('school_address'),
                school_contact=getattr(tenant, 'phone', '') or field_default('school_contact'),
                school_email=getattr(tenant, 'email', '') or field_default('school_email'),
                school_website=str(getattr(tenant, 'website', '') or '') or field_default('school_website'),
                layout_type=update_fields.get('layout_type', field_default('layout_type')),
                include_skills=update_fields.get('include_skills', True),
            )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_exam_details_api(request, exam_id):
    """API endpoint to get exam details for editing"""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        tenant = request.tenant
        exam = get_object_or_404(Exam, id=exam_id, tenant=tenant)

        return JsonResponse({
            'success': True,
            'exam': {
                'id': str(exam.id),
                'subject_id': str(exam.subject.id),
                'subject_name': exam.subject.name,
                'exam_date': exam.start_time.strftime('%Y-%m-%d'),
                'exam_time': exam.start_time.strftime('%H:%M'),
                'duration': int((exam.end_time - exam.start_time).total_seconds() / 60),
                'maximum_marks': float(exam.maximum_marks),
                'minimum_marks': float(exam.minimum_marks),
                'grading_scale_id': str(exam.grading_scale.id) if exam.grading_scale else None,
                'grading_scale_name': exam.grading_scale.name if exam.grading_scale else None,
                'is_activity': exam.subject.no_exams or 'Activity' in exam.subject.name,
                'scoring_type': (
                    'skills' if (exam.grading_scale and exam.grading_scale.scale_type == 'LEVEL')
                    else 'grades' if exam.maximum_marks == 0
                    else 'marks_and_grades' if exam.grading_scale
                    else 'marks'
                ),
                'assessment_slot': exam.assessment_slot,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def update_exam_api(request, exam_id):
    """API endpoint to update an exam"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        import json
        from datetime import datetime, timedelta
        from decimal import Decimal, InvalidOperation
        from django.utils.dateparse import parse_date, parse_time

        tenant = request.tenant
        data = json.loads(request.body)

        exam = get_object_or_404(Exam, id=exam_id, tenant=tenant)

        # Extract data
        exam_date = data.get('exam_date')
        exam_time = data.get('exam_time', '09:00')
        scoring_type = data.get('scoring_type', 'marks')
        maximum_marks = data.get('maximum_marks', '100')
        pass_criteria = data.get('pass_criteria', '40')
        grading_scale_id = data.get('grading_scale_id')

        def _to_decimal(value, fallback):
            """Parse a marks value as Decimal (the model field type), tolerating
            blanks/decimals so a bad value never crashes the whole save."""
            if value is None or value == '':
                return fallback
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                return fallback

        try:
            duration = int(float(data.get('duration', 60)))
        except (TypeError, ValueError):
            duration = 60

        # Marks only apply to marks-based scoring; grade/skills exams carry no marks.
        # The scoring type is authoritative here — the report column (assessment_slot)
        # does NOT zero marks, otherwise marks entered for a slot like Attainment
        # would be silently discarded on save.
        if scoring_type in ('grades', 'skills'):
            max_marks = Decimal('0')
            min_marks = Decimal('0')
        else:
            max_marks = _to_decimal(maximum_marks, exam.maximum_marks)
            min_marks = _to_decimal(pass_criteria, exam.minimum_marks)

        # Get grading scale if provided
        grading_scale = None
        if grading_scale_id:
            from core.models import GradingScale
            try:
                grading_scale = GradingScale.objects.get(id=grading_scale_id, tenant=tenant)
            except GradingScale.DoesNotExist:
                pass

        # Update exam
        if exam_date and exam_time:
            exam_date_obj = parse_date(exam_date)
            exam_time_obj = parse_time(exam_time)
            exam_start_datetime = datetime.combine(exam_date_obj, exam_time_obj)
            exam_end_datetime = exam_start_datetime + timedelta(minutes=duration)

            exam.start_time = exam_start_datetime
            exam.end_time = exam_end_datetime

        exam.maximum_marks = max_marks
        exam.minimum_marks = min_marks
        exam.grading_scale = grading_scale

        # Update the report column if provided (does not affect marks — see above).
        new_slot = data.get('assessment_slot')
        if new_slot in ('EXAM', 'ATTAINMENT', 'EFFORT', 'CLASSWORK', 'TEST'):
            exam.assessment_slot = new_slot

        exam.save()

        return JsonResponse({
            'success': True,
            'message': f'Successfully updated exam for {exam.subject.name}'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def delete_exam_api(request, exam_id):
    """API endpoint to delete an exam"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        tenant = request.tenant
        exam = get_object_or_404(Exam, id=exam_id, tenant=tenant)

        subject_name = exam.subject.name
        exam.delete()

        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted exam for {subject_name}'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_exam_type_api(request):
    """Delete all Exam records for a given exam_name/code within an ExamGroup.
    Used from the class gradebook page to remove an entire exam type (e.g. ATTAINMENT)
    across all subjects in one action.
    """
    try:
        tenant = request.tenant
        exam_group_id = request.POST.get('exam_group_id')
        exam_name = request.POST.get('exam_name', '').strip()
        exam_code = request.POST.get('exam_code', '').strip()

        if not exam_group_id:
            return JsonResponse({'success': False, 'error': 'exam_group_id required'})

        exam_group = get_object_or_404(ExamGroup, id=exam_group_id, tenant=tenant)

        qs = Exam.objects.filter(tenant=tenant, exam_group=exam_group)
        if exam_name:
            qs = qs.filter(exam_name=exam_name)
        if exam_code:
            qs = qs.filter(exam_code=exam_code)
        # Safety: if neither name nor code given, refuse to delete everything
        if not exam_name and not exam_code:
            return JsonResponse({'success': False, 'error': 'exam_name or exam_code required'})

        deleted_count, _ = qs.delete()
        return JsonResponse({
            'success': True,
            'message': f'Deleted {deleted_count} exam record(s) for "{exam_name or exam_code}"',
            'deleted_count': deleted_count,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def edit_exam_subjects_api(request):
    """Add/remove subjects from an existing exam group on the planner.

    Identifies the exam group by (exam_plan_id, term_id, exam_name, exam_code)
    on the primary batch. Compares the desired subject_ids (full desired set)
    against the current exams and:
    - Creates Exam records for newly added subjects (on all matching batches).
    - Deletes Exam records for removed subjects (on all sibling batches too).
    """
    import json as _json
    from django.utils import timezone
    from datetime import timedelta

    try:
        tenant = request.tenant
        exam_plan_id = request.POST.get('exam_plan_id')
        term_id = request.POST.get('term_id')
        exam_name = request.POST.get('exam_name', '').strip()
        exam_code = request.POST.get('exam_code', '').strip()
        desired_ids = set(_json.loads(request.POST.get('subject_ids', '[]')))

        if not all([exam_plan_id, term_id, exam_name]):
            return JsonResponse({'success': False, 'error': 'exam_plan_id, term_id and exam_name are required'})

        exam_group = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)
        term = get_object_or_404(Term, id=term_id, tenant=tenant)
        primary_batch = exam_group.batch

        all_course_batches = [primary_batch] + list(_planner_sibling_batches(primary_batch))

        # Phase 3: Pre-build sibling exam groups (not term maps)
        sibling_cache = {}
        for _b in all_course_batches:
            if _b.id != primary_batch.id:
                _sg = ExamGroup.objects.filter(
                    tenant=tenant, batch=_b, name=exam_group.name,
                ).first()
                if _sg is None:
                    _sg = ExamGroup.objects.create(
                        tenant=tenant, batch=_b, name=exam_group.name,
                        exam_type=exam_group.exam_type or 'PLANNER',
                        exam_date=exam_group.exam_date,
                        is_published=False,
                    )
                sibling_cache[_b.id] = _sg

        # exam_code may be stored as NULL when the template passed an empty string.
        from django.db.models import Q as _Q
        _ec_q = (
            _Q(exam_code=exam_code)
            if exam_code
            else (_Q(exam_code='') | _Q(exam_code__isnull=True))
        )

        # Fetch config from any existing exam in this group
        ref_exam = Exam.objects.filter(
            _ec_q,
            tenant=tenant, exam_group=exam_group,
            exam_name=exam_name, term=term,
        ).select_related('grading_scale').first()

        if not ref_exam:
            return JsonResponse({'success': False, 'error': 'Exam group not found on this plan/term'})

        exam_start = ref_exam.start_time or timezone.now()
        exam_end = ref_exam.end_time or (exam_start + timedelta(hours=2))

        # Current subjects on the PRIMARY batch exam group
        current_exams = list(Exam.objects.filter(
            _ec_q,
            tenant=tenant, exam_group=exam_group,
            exam_name=exam_name, term=term,
        ).select_related('subject'))
        current_ids = {str(e.subject_id) for e in current_exams}

        to_add = desired_ids - current_ids
        to_remove = current_ids - desired_ids

        added = removed = 0

        # ---- Add subjects ------------------------------------------------
        for subject_id in to_add:
            src = Subject.objects.filter(id=subject_id, tenant=tenant).first()
            if not src:
                continue

            for batch in all_course_batches:
                if batch.id == primary_batch.id:
                    tgt_group = exam_group
                    tgt_term = term
                    tgt_subject = src if src.batch_id == batch.id else _matching_subject(batch, src)
                else:
                    # Phase 3: Look up year-scoped term directly
                    tgt_group = sibling_cache[batch.id]
                    tgt_term = Term.objects.filter(
                        tenant=tenant,
                        academic_year=batch.academic_year,
                        name=term.name,
                    ).first() if term else None
                    tgt_subject = _matching_subject(batch, src)

                if not tgt_subject:
                    continue

                if Exam.objects.filter(
                    _ec_q,
                    tenant=tenant, exam_group=tgt_group, subject=tgt_subject,
                    exam_name=exam_name, term=tgt_term,
                ).exists():
                    continue

                Exam.objects.create(
                    tenant=tenant, exam_group=tgt_group, subject=tgt_subject,
                    term=tgt_term, exam_name=exam_name, exam_code=ref_exam.exam_code,
                    display_name=ref_exam.display_name,
                    start_time=exam_start, end_time=exam_end,
                    maximum_marks=ref_exam.maximum_marks,
                    minimum_marks=ref_exam.minimum_marks,
                    weightage=ref_exam.weightage,
                    grading_scale=ref_exam.grading_scale,
                    assessment_slot=ref_exam.assessment_slot,
                )

                if batch.id == primary_batch.id:
                    added += 1

        # ---- Remove subjects ---------------------------------------------
        for subject_id in to_remove:
            # Use all_objects to find soft-deleted subjects — they can still be
            # removed from an exam even if the subject itself was soft-deleted.
            src = Subject.all_objects.filter(id=subject_id, tenant=tenant).first()
            if not src:
                continue

            for batch in all_course_batches:
                if batch.id == primary_batch.id:
                    tgt_group = exam_group
                    tgt_term = term
                    tgt_subject = src if src.batch_id == batch.id else _matching_subject(batch, src)
                else:
                    tgt_group_obj = ExamGroup.objects.filter(
                        tenant=tenant, batch=batch, name=exam_group.name,
                    ).first()
                    if not tgt_group_obj:
                        continue
                    # Phase 3: Look up year-scoped term directly (not per-batch)
                    tgt_term = Term.objects.filter(
                        tenant=tenant,
                        academic_year=batch.academic_year,
                        name=term.name,
                    ).first() if term else None
                    tgt_group = tgt_group_obj
                    tgt_subject = _matching_subject(batch, src)

                if not tgt_subject:
                    continue

                Exam.objects.filter(
                    _ec_q,
                    tenant=tenant, exam_group=tgt_group, subject=tgt_subject,
                    exam_name=exam_name, term=tgt_term,
                ).delete()

            removed += 1

        parts = []
        if added:
            parts.append(f'{added} subject(s) added')
        if removed:
            parts.append(f'{removed} removed')
        message = ', '.join(parts) if parts else 'No changes made'

        return JsonResponse({'success': True, 'message': message, 'added': added, 'removed': removed})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def include_exam_plan_class_api(request, exam_plan_id):
    """Include a batch (class) in this exam plan: creates that batch's sibling
    ExamGroup (matched by name) if missing and propagates the primary batch's
    terms/exams into it. Only batches of the planner's own course + academic
    year are eligible."""
    try:
        import json
        tenant = request.tenant
        data = json.loads(request.body)
        batch_id = data.get('batch_id')

        if not batch_id:
            return JsonResponse({'success': False, 'error': 'Batch ID is required'})

        exam_plan = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)
        primary_batch = exam_plan.batch
        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

        if not primary_batch or batch.course_id != primary_batch.course_id or \
                batch.academic_year_id != primary_batch.academic_year_id:
            return JsonResponse({
                'success': False,
                'error': 'That class does not belong to this planner\'s course/academic year.',
            })

        created, skipped = _propagate_exams_to_batch(exam_plan, batch)

        message = f'{batch.name} included in the plan; {created} exam(s) added.'
        if skipped:
            message += f' Skipped (missing subject): {", ".join(s["subject"] for s in skipped)}'

        return JsonResponse({'success': True, 'message': message})

    except Exception as e:
        logger.exception("include_exam_plan_class_api failed")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def exclude_exam_plan_class_api(request, exam_plan_id):
    """Exclude a batch (class) from this exam plan: permanently deletes that
    batch's ExamGroup for this planner, cascading its Terms, Exams and scores.
    The primary batch (the one this planner page represents) cannot be excluded
    here — change the primary batch first."""
    try:
        import json
        tenant = request.tenant
        data = json.loads(request.body)
        batch_id = data.get('batch_id')

        if not batch_id:
            return JsonResponse({'success': False, 'error': 'Batch ID is required'})

        exam_plan = get_object_or_404(ExamGroup, id=exam_plan_id, tenant=tenant)

        if str(exam_plan.batch_id) == str(batch_id):
            return JsonResponse({
                'success': False,
                'error': 'Cannot exclude the primary batch for this plan.',
            })

        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
        group = ExamGroup.objects.filter(tenant=tenant, name=exam_plan.name, batch=batch).first()
        if group is None:
            return JsonResponse({'success': False, 'error': f'{batch.name} is not part of this plan.'})

        group.delete()  # cascades Term, Exam, ExamScore for this batch only

        return JsonResponse({
            'success': True,
            'message': f'{batch.name} excluded from the plan.',
        })

    except Exception as e:
        logger.exception("exclude_exam_plan_class_api failed")
        return JsonResponse({'success': False, 'error': str(e)})


# Enhanced Grading System Views

@method_decorator(login_required, name='dispatch')
class GradingSettingsView(TemplateView):
    """Enhanced grading settings management"""
    template_name = 'core/gradebook/grading_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        from .models import GradingType, GradingLevel, CoScholasticAssessment, SubjectGradingSettings, Configuration, ReportTemplate, GradingScale

        grading_types = GradingType.objects.filter(tenant=tenant)
        grading_levels = GradingLevel.objects.filter(tenant=tenant).order_by('grading_type', 'min_score')
        coscholastic_assessments = CoScholasticAssessment.objects.filter(tenant=tenant)
        subject_settings = SubjectGradingSettings.objects.filter(tenant=tenant).select_related('subject', 'grading_type')
        grading_scales = GradingScale.objects.filter(tenant=tenant, is_active=True).prefetch_related('grade_values').order_by('name')

        # Report-card defaults stored in Configuration
        rc_keys = [
            'rc_school_name', 'rc_school_address', 'rc_school_contact',
            'rc_school_email', 'rc_school_website',
            'rc_report_title', 'rc_footer_quote', 'rc_primary_color',
            'rc_section_order', 'rc_layout_type',
            'rc_grading_scale_id',
            'rc_include_exam_scores', 'rc_include_homework_assessment',
            'rc_include_project_work', 'rc_include_clubs', 'rc_include_sports',
            'rc_include_other_activities', 'rc_include_attendance',
            'rc_include_grading_scale',
        ]
        rc_configs = Configuration.objects.filter(tenant=tenant, config_key__in=rc_keys)
        rc_defaults = {c.config_key: c.config_value for c in rc_configs}

        report_templates = ReportTemplate.objects.filter(
            tenant=tenant
        ).select_related('batch', 'academic_year', 'grading_scale').order_by('-academic_year__start_date', 'batch__name', 'term')

        academic_years = AcademicYear.objects.filter(tenant=tenant).order_by('-start_date')

        # Layout context vars
        back_url = reverse('core:gradebook_management')
        crumbs = [
            {'label': 'Gradebook', 'url': reverse('core:gradebook_management')},
            {'label': 'Grading Settings'},
        ]

        context.update({
            'grading_types': grading_types,
            'grading_levels': grading_levels,
            'coscholastic_assessments': coscholastic_assessments,
            'subject_settings': subject_settings,
            'batches': Batch.objects.filter(tenant=tenant, is_active=True).order_by('name'),
            'grading_scales': grading_scales,
            'signatures': SchoolSignature.objects.filter(tenant=tenant).order_by('-is_default', 'title', 'name'),
            'academic_years': academic_years,
            'report_templates': report_templates,
            'rc_defaults': rc_defaults,
            'layout_choices': ReportTemplate.LAYOUT_CHOICES,
            'scale_type_choices': GradingScale.SCALE_TYPES,
            'back_url': back_url,
            'crumbs': crumbs,
        })
        return context


@method_decorator(login_required, name='dispatch')
class SkillsAssessmentIndexView(TemplateView):
    """Skills assessment interface for early childhood development"""
    template_name = 'core/gradebook/skills_assessment_index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        from .models import SkillCategory, SkillItem, Student

        # SkillCategory has no age_group field — just load all active categories.
        skill_categories = SkillCategory.objects.filter(tenant=tenant, is_active=True)
        age_groups = {'all': skill_categories}

        # Get students in early years classes (related name is student_batches)
        early_years_students = Student.objects.filter(
            tenant=tenant,
            student_batches__batch__name__icontains='nursery'
        ) | Student.objects.filter(
            tenant=tenant,
            student_batches__batch__name__icontains='kg'
        ) | Student.objects.filter(
            tenant=tenant,
            student_batches__batch__name__icontains='reception'
        )

        # Pick a default batch for the "Class Assessment" quick-link.
        # Prefer an active early-years batch; fall back to any active batch.
        batches = Batch.objects.filter(tenant=tenant, is_active=True).order_by('name')
        early_batch = (
            batches.filter(name__icontains='reception').first()
            or batches.filter(name__icontains='nursery').first()
            or batches.filter(name__icontains='kg').first()
            or batches.first()
        )

        context.update({
            'age_groups': age_groups,
            'early_years_students': early_years_students.distinct(),
            'first_batch': early_batch,
            'batches': batches,
        })
        context['back_url'] = reverse('core:gradebook_index')
        context['dashboard_tiles'] = [
            {'icon': 'fa-running', 'title': 'Motor Skills', 'description': 'Physical development and coordination activities', 'url': reverse('core:skills_category_view', args=['MOTOR_SKILLS'])},
            {'icon': 'fa-brain', 'title': 'Conceptual Skills', 'description': 'Cognitive development and understanding activities', 'url': reverse('core:skills_category_view', args=['CONCEPTUAL_SKILLS'])},
            {'icon': 'fa-comments', 'title': 'Communication Skills', 'description': 'Language development and expression activities', 'url': reverse('core:skills_category_view', args=['COMMUNICATION_SKILLS'])},
            {'icon': 'fa-palette', 'title': 'Creative Skills', 'description': 'Imagination, art and expressive activities', 'url': reverse('core:skills_category_view', args=['CREATIVE_SKILLS'])},
            {'icon': 'fa-users', 'title': 'Social Skills', 'description': 'Personal and social development activities', 'url': reverse('core:skills_category_view', args=['SOCIAL_SKILLS'])},
            {'icon': 'fa-bullseye', 'title': 'Concentration Skills', 'description': 'Attention, persistence and focus activities', 'url': reverse('core:skills_category_view', args=['CONCENTRATION_SKILLS'])},
        ]
        return context


@method_decorator(login_required, name='dispatch')
class EnhancedScoreEntryView(TemplateView):
    """Enhanced score entry supporting multiple assessment types"""
    template_name = 'core/gradebook/enhanced_score_entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        from .models import ExamGroup, GradingType, CoScholasticAssessment

        # Get active exam groups
        active_academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
        exam_groups = ExamGroup.objects.filter(
            tenant=tenant,
            batch__academic_year=active_academic_year
        ).select_related('batch')

        grading_types = GradingType.objects.filter(tenant=tenant, is_active=True)
        coscholastic_assessments = CoScholasticAssessment.objects.filter(tenant=tenant, is_active=True)

        # Layout context vars
        back_url = reverse('core:gradebook_management')
        crumbs = [
            {'label': 'Gradebook', 'url': reverse('core:gradebook_management')},
            {'label': 'Enhanced Score Entry'},
        ]

        context.update({
            'exam_groups': exam_groups,
            'grading_types': grading_types,
            'coscholastic_assessments': coscholastic_assessments,
            'active_academic_year': active_academic_year,
            'back_url': back_url,
            'crumbs': crumbs,
        })
        return context


@method_decorator(login_required, name='dispatch')
class ComprehensiveReportsView(TemplateView):
    """Comprehensive report generation with multiple templates"""
    template_name = 'core/gradebook/comprehensive_reports.html'

    def get_context_data(self, **kwargs):
        from .models import ReportTemplate, ExamGroup as _ExamGroup
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        active_academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
        batches = Batch.objects.filter(tenant=tenant, academic_year=active_academic_year)
        # Phase 3: Terms are year-scoped, not per-exam_group__batch
        terms = Term.objects.filter(
            tenant=tenant,
            academic_year=active_academic_year
        ) if active_academic_year else Term.objects.none()
        report_templates = ReportTemplate.objects.filter(tenant=tenant).order_by('name')
        exam_groups = _ExamGroup.objects.filter(
            tenant=tenant,
            batch__academic_year=active_academic_year
        ).select_related('batch').order_by('name') if active_academic_year else _ExamGroup.objects.none()

        # Layout context vars
        back_url = reverse('core:gradebook_management')
        crumbs = [
            {'label': 'Gradebook', 'url': reverse('core:gradebook_management')},
            {'label': 'Comprehensive Reports'},
        ]

        context.update({
            'batches': batches,
            'terms': terms,
            'active_academic_year': active_academic_year,
            'report_templates': report_templates,
            'exam_groups': exam_groups,
            'section_flags': [
                ('include_exam_scores',          'Exam Scores'),
                ('include_homework_assessment',  'Homework'),
                ('include_project_work',         'Project Work'),
                ('include_clubs',                'Clubs'),
                ('include_sports',               'Sports'),
                ('include_other_activities',     'Other Activities'),
                ('include_attendance',           'Attendance'),
                ('include_grading_scale',        'Grading Scale'),
            ],
            'back_url': back_url,
            'crumbs': crumbs,
        })
        return context


# Enhanced Grading System API Endpoints

@login_required
@require_http_methods(["POST"])
def create_grading_type_api(request):
    """API endpoint to create a new grading type"""
    try:
        from .models import GradingType

        tenant = request.tenant
        name = request.POST.get('name')
        code = request.POST.get('code')
        description = request.POST.get('description', '')
        gpa_scale = request.POST.get('gpa_scale')
        cce_scholastic_weight = request.POST.get('cce_scholastic_weight', 70.00)
        cce_coscholastic_weight = request.POST.get('cce_coscholastic_weight', 30.00)

        if not all([name, code]):
            return JsonResponse({
                'success': False,
                'error': 'Name and code are required'
            })

        grading_type = GradingType.objects.create(
            tenant=tenant,
            name=name,
            code=code,
            description=description,
            gpa_scale=gpa_scale if gpa_scale else None,
            cce_scholastic_weight=cce_scholastic_weight,
            cce_coscholastic_weight=cce_coscholastic_weight,
            is_active=True
        )

        return JsonResponse({
            'success': True,
            'message': f'Grading type "{name}" created successfully',
            'grading_type_id': str(grading_type.id)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def get_exam_score_entry_details_api(request):
    """API endpoint to get exam details for score entry"""
    try:
        from .models import Exam, Student, BatchStudent

        tenant = request.tenant
        exam_id = request.GET.get('exam_id')

        if not exam_id:
            return JsonResponse({'success': False, 'error': 'Exam ID is required'})

        exam = get_object_or_404(Exam, id=exam_id, tenant=tenant)

        # Get students in the batch
        students = Student.objects.filter(
            tenant=tenant,
            student_batches__batch=exam.exam_group.batch,
            student_batches__is_active=True
        ).order_by('first_name', 'last_name')

        student_data = [{
            'id': str(student.id),
            'name': f"{student.first_name} {student.last_name}",
            'admission_no': student.admission_no,
        } for student in students]

        # Grade thresholds from the exam's actual configured scale (Exam ->
        # Subject -> Batch hierarchy), so the client-side live grade preview
        # matches what /gradebook/grading-settings/ configured instead of a
        # hardcoded band.
        grading_scale = exam.get_grading_scale()
        grade_scale_data = []
        if grading_scale:
            grade_scale_data = [
                {'grade': gv.name, 'min_percentage': float(gv.min_percentage)}
                for gv in grading_scale.grade_values.filter(
                    tenant=tenant, min_percentage__isnull=False
                ).order_by('-min_percentage')
            ]

        return JsonResponse({
            'success': True,
            'exam': {
                'id': str(exam.id),
                'subject': exam.subject.name,
                'maximum_marks': str(exam.maximum_marks),
                'minimum_marks': str(exam.minimum_marks),
                'start_time': exam.start_time.strftime('%Y-%m-%d %H:%M'),
                'grade_scale': grade_scale_data,
            },
            'students': student_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def save_exam_scores_api(request):
    """API endpoint to save enhanced exam scores"""
    try:
        import json
        from decimal import Decimal
        from .models import Exam, Student, EnhancedExamScore

        tenant = request.tenant
        exam_id = request.POST.get('exam_id')
        scores_json = request.POST.get('scores')

        if not all([exam_id, scores_json]):
            return JsonResponse({'success': False, 'error': 'Exam ID and scores are required'})

        exam = get_object_or_404(Exam, id=exam_id, tenant=tenant)
        scores_data = json.loads(scores_json)

        saved_count = 0
        for score_data in scores_data:
            student_id = score_data.get('student_id')
            total_marks = score_data.get('total_marks')

            if not student_id or total_marks is None:
                continue

            student = get_object_or_404(Student, id=student_id, tenant=tenant)

            obtained = score_data.get('obtained_marks')
            enhanced_score, created = EnhancedExamScore.objects.update_or_create(
                tenant=tenant,
                exam=exam,
                student=student,
                subject=exam.subject,
                defaults={
                    'obtained_marks': Decimal(str(obtained)) if obtained is not None else None,
                    'total_marks': Decimal(str(total_marks)),
                    'internal_marks': score_data.get('internal_marks'),
                    'external_marks': score_data.get('external_marks'),
                    'formative_marks': score_data.get('formative_marks'),
                    'summative_marks': score_data.get('summative_marks'),
                    'is_absent': score_data.get('is_absent', False),
                    'remarks': score_data.get('remarks', ''),
                }
            )
            saved_count += 1

        return JsonResponse({
            'success': True,
            'message': f'Successfully saved scores for {saved_count} students'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def save_skills_assessment_api(request):
    """API endpoint to save skills assessment"""
    try:
        import json
        from datetime import date as _date
        from .models import Student, SkillsAssessment, SkillItem, SkillAssessmentResult

        tenant = request.tenant
        student_id = request.POST.get('student_id')
        assessment_data_json = request.POST.get('assessment_data')
        academic_year_id = request.POST.get('academic_year_id')
        term_name = request.POST.get('term_name', '').strip()

        if not all([student_id, assessment_data_json, academic_year_id]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        student = get_object_or_404(Student, id=student_id, tenant=tenant)
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id, tenant=tenant)
        assessment_data = json.loads(assessment_data_json)

        # Block saves for classes where skills assessment is switched off.
        from .models import BatchExamTypeConfiguration
        active_enrollment = student.student_batches.filter(is_active=True).select_related('batch').first()
        if active_enrollment and not BatchExamTypeConfiguration.skills_assessment_enabled(
            active_enrollment.batch, tenant
        ):
            return JsonResponse({
                'success': False,
                'error': f'Skills assessment is not enabled for {active_enrollment.batch.name}.',
            }, status=403)

        term_obj = None
        if term_name:
            # Phase 3: Look up year-scoped term
            if active_enrollment:
                term_obj = Term.objects.filter(
                    tenant=tenant, name__iexact=term_name,
                    academic_year=active_enrollment.batch.academic_year,
                ).first()
            if term_obj is None:
                # Fallback: any term with this name in the same tenant
                term_obj = Term.objects.filter(tenant=tenant, name__iexact=term_name).first()

        today = _date.today()
        skills_assessment, _ = SkillsAssessment.objects.update_or_create(
            tenant=tenant,
            student=student,
            academic_year=academic_year,
            term=term_obj,
            defaults={
                'assessment_date': today,
                'assessor': request.user if request.user.is_authenticated else None,
            }
        )

        skill_scores = assessment_data.get('skill_scores', [])
        for skill_score in skill_scores:
            skill_item = get_object_or_404(SkillItem, id=skill_score['skill_item_id'], tenant=tenant)
            SkillAssessmentResult.objects.update_or_create(
                assessment=skills_assessment,
                skill_item=skill_item,
                defaults={
                    'level': skill_score.get('level', 'NOT_YET'),
                    'assessment_date': today,
                    'tenant': tenant,
                }
            )

        return JsonResponse({
            'success': True,
            'message': f'Assessment saved for {student.first_name} {student.last_name}',
            'assessment_id': str(skills_assessment.id),
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def load_skills_assessment_api(request):
    """Return existing skill assessment results for a student."""
    try:
        from .models import Student, SkillsAssessment, SkillAssessmentResult

        tenant = request.tenant
        student_id = request.GET.get('student_id')
        academic_year_id = request.GET.get('academic_year_id')
        term_name = request.GET.get('term_name', '').strip()

        if not all([student_id, academic_year_id]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        student = get_object_or_404(Student, id=student_id, tenant=tenant)
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id, tenant=tenant)

        active_enrollment = student.student_batches.filter(is_active=True).select_related('batch').first()

        term_obj = None
        if term_name:
            # Phase 3: Look up year-scoped term
            if active_enrollment:
                term_obj = Term.objects.filter(
                    tenant=tenant, name__iexact=term_name,
                    academic_year=active_enrollment.batch.academic_year,
                ).first()
            if term_obj is None:
                # Fallback: any term with this name in the same tenant
                term_obj = Term.objects.filter(tenant=tenant, name__iexact=term_name).first()

        try:
            assessment = SkillsAssessment.objects.get(
                tenant=tenant, student=student,
                academic_year=academic_year, term=term_obj,
            )
            levels = {
                str(r.skill_item_id): r.level
                for r in SkillAssessmentResult.objects.filter(
                    assessment=assessment
                ).select_related('skill_item')
            }
            return JsonResponse({
                'success': True,
                'assessment_id': str(assessment.id),
                'levels': levels,
            })
        except SkillsAssessment.DoesNotExist:
            return JsonResponse({'success': True, 'assessment_id': None, 'levels': {}})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def generate_comprehensive_report_api(request):
    """API endpoint to generate comprehensive reports"""
    try:
        import json
        from .grading_utils import ComprehensiveReportGenerator

        tenant = request.tenant
        batch_id = request.POST.get('batch_id')
        term_id = request.POST.get('term_id')
        report_type = request.POST.get('report_type', 'academic')
        student_ids_json = request.POST.get('student_ids')

        if not all([batch_id, term_id]):
            return JsonResponse({'success': False, 'error': 'Batch and term are required'})

        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
        term = get_object_or_404(Term, id=term_id, tenant=tenant)

        student_ids = json.loads(student_ids_json) if student_ids_json else []

        # Generate report
        report_generator = ComprehensiveReportGenerator(tenant)

        if report_type == 'skills':
            report_data = report_generator.generate_skills_report(batch, term, student_ids)
        else:
            report_data = report_generator.generate_academic_report(batch, term, student_ids)

        return JsonResponse({
            'success': True,
            'message': f'Report generated successfully for {len(report_data)} students',
            'report_data': report_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# Additional Skills Assessment Views

@method_decorator(login_required, name='dispatch')
class ClassSkillsAssessmentView(TemplateView):
    """Class-based skills assessment view for a specific batch"""
    template_name = 'core/gradebook/class_skills_assessment.html'

    def dispatch(self, request, *args, **kwargs):
        from .models import BatchExamTypeConfiguration
        tenant = request.tenant
        batch = get_object_or_404(Batch, id=kwargs.get('batch_id'), tenant=tenant)
        if not BatchExamTypeConfiguration.skills_assessment_enabled(batch, tenant):
            messages.warning(request, f'Skills assessment is not enabled for {batch.name}.')
            return redirect('core:exam_index')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Prefetch, Q
        from .models import SkillCategory, SkillItem

        tenant = self.request.tenant
        batch_id = self.kwargs.get('batch_id')

        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
        students = Student.objects.filter(
            tenant=tenant,
            student_batches__batch=batch,
            student_batches__is_active=True
        ).order_by('first_name', 'last_name')

        # Shared activities (no batches attached) + those attached to this batch.
        items_qs = SkillItem.objects.filter(
            is_active=True,
        ).filter(Q(batches__isnull=True) | Q(batches=batch)).distinct().order_by('display_order')
        skill_categories = SkillCategory.objects.filter(
            tenant=tenant, is_active=True
        ).prefetch_related(
            Prefetch('skill_items', queryset=items_qs)
        ).order_by('display_order')

        academic_years = AcademicYear.objects.filter(
            tenant=tenant
        ).order_by('-start_date')

        context.update({
            'batch': batch,
            'students': students,
            'skill_categories': skill_categories,
            'academic_years': academic_years,
            'active_year': academic_years.filter(is_active=True).first(),
            'skills_assessment_title': f"Skills Assessment — {batch.name}",
            'back_url': reverse('core:skills_assessment_index'),
        })
        return context


@method_decorator(login_required, name='dispatch')
class NewSkillsAssessmentView(TemplateView):
    """Create new skills assessment for students"""
    template_name = 'core/gradebook/new_skills_assessment.html'

    def dispatch(self, request, *args, **kwargs):
        from .models import BatchExamTypeConfiguration
        tenant = request.tenant
        batch = get_object_or_404(Batch, id=kwargs.get('batch_id'), tenant=tenant)
        if not BatchExamTypeConfiguration.skills_assessment_enabled(batch, tenant):
            messages.warning(request, f'Skills assessment is not enabled for {batch.name}.')
            return redirect('core:exam_index')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        batch_id = kwargs.get('batch_id')

        from .models import SkillCategory, SkillItem
        from django.db.models import Q, Prefetch

        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
        # Shared activities (no batches attached) + those attached to this batch.
        items_qs = SkillItem.objects.filter(
            tenant=tenant, is_active=True,
        ).filter(Q(batches__isnull=True) | Q(batches=batch)).distinct().order_by('display_order', 'description')
        skill_categories = SkillCategory.objects.filter(tenant=tenant, is_active=True).prefetch_related(
            Prefetch('skill_items', queryset=items_qs)
        )

        context.update({
            'batch': batch,
            'skill_categories': skill_categories,
            'header_description': f"Create new skills assessment for {batch.name}",
            'back_url': reverse('core:class_skills_assessment', args=[batch.id]),
        })
        return context


@method_decorator(login_required, name='dispatch')
class IndividualSkillsAssessmentView(TemplateView):
    """Individual student skills assessment interface"""
    template_name = 'core/gradebook/individual_skills_assessment.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse('core:skills_assessment_index')
        context['save_assessment_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Save Assessment', 'variant': 'primary', 'attrs': 'id="saveAssessmentBtn"'},
        ]
        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        from .models import SkillCategory

        skill_categories = SkillCategory.objects.filter(tenant=tenant).prefetch_related('skill_items')
        active_academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()

        context.update({
            'skill_categories': skill_categories,
            'active_academic_year': active_academic_year,
        })
        return context


@method_decorator(login_required, name='dispatch')
class SkillsAssessmentReportsView(TemplateView):
    """Skills assessment reports for a specific batch"""
    template_name = 'core/gradebook/skills_assessment_reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        batch_id = kwargs.get('batch_id')

        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
        students = Student.objects.filter(
            tenant=tenant,
            student_batches__batch=batch,
            student_batches__is_active=True
        ).order_by('first_name', 'last_name')

        context.update({
            'batch': batch,
            'students': students,
            'reports_description': f"View and generate skills assessment reports for {batch.name}",
            'back_url': reverse('core:skills_assessment_index'),
            'report_preview_footer': [
                {'label': 'Close', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Download Report', 'variant': 'primary'},
            ],
        })
        return context


@method_decorator(login_required, name='dispatch')
class SkillsProgressTrackingView(TemplateView):
    """Skills progress tracking overview"""
    template_name = 'core/gradebook/skills_progress_tracking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        active_academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
        batches = Batch.objects.filter(tenant=tenant, academic_year=active_academic_year)

        context.update({
            'batches': batches,
            'active_academic_year': active_academic_year,
            'back_url': reverse('core:skills_assessment_index'),
        })
        return context


# ---- Skill activity (SkillItem) management -------------------------------

def _pregrade_batches(tenant):
    """Active batches (current academic year) used to attach skill activities.
    Prefers pre-grade classes (Beginners / Middle Class / Reception …); falls
    back to all active batches if none match the keywords."""
    from core.grading_utils import _SKILLS_COURSE_KEYWORDS
    active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
    qs = Batch.objects.filter(tenant=tenant, is_active=True, is_deleted=False)
    if active_year:
        qs = qs.filter(academic_year=active_year)
    batches = list(qs.select_related('course').order_by('course__course_name', 'name'))
    pregrade = [b for b in batches if any(kw in (b.course.course_name or '').upper()
                                          for kw in _SKILLS_COURSE_KEYWORDS)]
    return pregrade or batches


def _skill_items_for_batch(qs, batch):
    """Filter a SkillItem queryset to those shared (no batches attached) OR
    attached to the given batch."""
    from django.db.models import Q
    if batch is None:
        return qs
    return qs.filter(Q(batches__isnull=True) | Q(batches=batch)).distinct()


@require_http_methods(["POST"])
@login_required
def create_skill_item_api(request):
    """Create a skill activity under a category, attached to zero or more batches."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import SkillCategory, SkillItem
    try:
        category = get_object_or_404(SkillCategory, id=request.POST.get('category_id'), tenant=tenant)
        description = (request.POST.get('description') or '').strip()
        if not description:
            return JsonResponse({'success': False, 'error': 'Activity description is required'}, status=400)

        batch_ids = [b for b in request.POST.getlist('batch_ids') if b]
        batches = list(Batch.objects.filter(id__in=batch_ids, tenant=tenant)) if batch_ids else []

        order = request.POST.get('display_order')
        if order:
            order = int(order)
        else:
            last = SkillItem.objects.filter(category=category, tenant=tenant).order_by('-display_order').first()
            order = (last.display_order + 1) if last else 1

        item = SkillItem.objects.create(
            tenant=tenant, category=category, description=description,
            display_order=order, is_active=True,
        )
        if batches:
            item.batches.set(batches)
        saved_batches = [{'id': str(b.id), 'name': b.name} for b in item.batches.all()]
        return JsonResponse({'success': True, 'id': str(item.id), 'batches': saved_batches})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def update_skill_item_api(request, item_id):
    """Edit a skill activity's description / attached batches / active state."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import SkillItem
    try:
        item = get_object_or_404(SkillItem, id=item_id, tenant=tenant)

        description = (request.POST.get('description') or '').strip()
        if not description:
            return JsonResponse({'success': False, 'error': 'Activity description is required'}, status=400)
        item.description = description

        if 'is_active' in request.POST:
            item.is_active = request.POST.get('is_active') in ('true', 'on', '1', 'True')

        item.save(update_fields=['description', 'is_active'])

        batch_ids = [b for b in request.POST.getlist('batch_ids') if b]
        batches = list(Batch.objects.filter(id__in=batch_ids, tenant=tenant)) if batch_ids else []
        item.batches.set(batches)
        saved_batches = [{'id': str(b.id), 'name': b.name} for b in item.batches.all()]
        return JsonResponse({'success': True, 'id': str(item.id), 'batches': saved_batches})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def delete_skill_item_api(request, item_id):
    """Soft-delete a skill activity (is_active=False), preserving past results."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import SkillItem
    try:
        item = get_object_or_404(SkillItem, id=item_id, tenant=tenant)
        item.is_active = False
        item.save(update_fields=['is_active'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def reorder_skill_items_api(request):
    """Update display_order for a list of skill items given as an ordered array of IDs."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import SkillItem
    try:
        ids = json.loads(request.body).get('ids', [])
        for order, item_id in enumerate(ids, start=1):
            SkillItem.objects.filter(id=item_id, tenant=tenant, is_active=True).update(display_order=order)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@method_decorator(login_required, name='dispatch')
class SkillsCategoryView(TemplateView):
    """Skills category detailed view"""
    template_name = 'core/gradebook/skills_category_view.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        category_code = kwargs.get('category_code')

        from .models import SkillCategory

        skill_category = get_object_or_404(SkillCategory, tenant=tenant, code=category_code)

        batches = _pregrade_batches(tenant)

        # Optional ?batch= filter: a batch id (show shared + that batch's items)
        # or 'shared' (only shared activities). Default: show all activities.
        selected_batch_id = (self.request.GET.get('batch') or '').strip()
        from .models import SkillItem
        skill_items = (
            SkillItem.objects.filter(
                tenant=tenant,
                category=skill_category,
                is_active=True,
            )
            .prefetch_related('batches__course')
            .order_by('display_order', 'description')
        )
        if selected_batch_id == 'shared':
            skill_items = skill_items.filter(batches__isnull=True)
        elif selected_batch_id:
            selected_batch = next((b for b in batches if str(b.id) == selected_batch_id), None)
            if selected_batch:
                skill_items = _skill_items_for_batch(skill_items, selected_batch)

        import json
        batches_list = list(batches)
        batches_json = json.dumps([
            {'id': str(b.id), 'name': b.name} for b in batches_list
        ])

        context.update({
            'skill_category': skill_category,
            'skill_items': skill_items,
            'batches': batches_list,
            'selected_batch_id': selected_batch_id,
            'batches_json': batches_json,
            'skill_category_description': skill_category.description or "Manage skill activities for this category",
            'back_url': reverse('core:skills_assessment_index'),
            'skill_item_edit_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Save Changes', 'variant': 'primary', 'icon': 'fa-save', 'attrs': 'id="saveEditBtn" onclick="saveEdit()"'},
            ],
        })
        return context


@method_decorator(login_required, name='dispatch')
class BulkSkillsAssessmentView(TemplateView):
    """Bulk skills assessment interface"""
    template_name = 'core/gradebook/bulk_skills_assessment.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        from .models import SkillCategory

        active_academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
        batches = Batch.objects.filter(tenant=tenant, academic_year=active_academic_year)
        skill_categories = SkillCategory.objects.filter(tenant=tenant)

        context.update({
            'batches': batches,
            'skill_categories': skill_categories,
            'active_academic_year': active_academic_year,
            'back_url': reverse('core:skills_assessment_index'),
        })
        return context


# Additional Grading API Endpoints

@login_required
@require_http_methods(["GET"])
def get_grading_levels_api(request):
    """API endpoint to get grading levels for a grading type"""
    try:
        from .models import GradingLevel

        tenant = request.tenant
        grading_type_id = request.GET.get('grading_type_id')

        if not grading_type_id:
            return JsonResponse({'success': False, 'error': 'Grading type ID is required'})

        grading_levels = GradingLevel.objects.filter(
            tenant=tenant,
            grading_type_id=grading_type_id
        ).order_by('min_score')

        levels_data = [{
            'id': str(level.id),
            'name': level.name,
            'min_score': str(level.min_score),
            'max_score': str(level.max_score),
            'credit_points': str(level.credit_points) if level.credit_points else None,
        } for level in grading_levels]

        return JsonResponse({
            'success': True,
            'grading_levels': levels_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_grading_level_api(request):
    """API endpoint to create a new grading level"""
    try:
        from .models import GradingLevel, GradingType

        tenant = request.tenant
        grading_type_id = request.POST.get('grading_type_id')
        name = request.POST.get('name')
        min_score = request.POST.get('min_score')
        max_score = request.POST.get('max_score')
        credit_points = request.POST.get('credit_points')

        if not all([grading_type_id, name, min_score, max_score]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        grading_type = get_object_or_404(GradingType, id=grading_type_id, tenant=tenant)

        grading_level = GradingLevel.objects.create(
            tenant=tenant,
            grading_type=grading_type,
            name=name,
            min_score=min_score,
            max_score=max_score,
            credit_points=credit_points if credit_points else None,
        )

        return JsonResponse({
            'success': True,
            'message': f'Grading level "{name}" created successfully',
            'grading_level_id': str(grading_level.id)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# Missing API endpoints for enhanced grading system

@login_required
@require_http_methods(["DELETE"])
def delete_grading_type_api(request, grading_type_id):
    """API endpoint to delete a grading type"""
    try:
        from .models import GradingType

        tenant = request.tenant
        grading_type = get_object_or_404(GradingType, id=grading_type_id, tenant=tenant)

        grading_type_name = grading_type.name
        grading_type.delete()

        return JsonResponse({
            'success': True,
            'message': f'Grading type "{grading_type_name}" deleted successfully'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def get_grade_levels_api(request, batch_id):
    """API endpoint to get grade levels for a batch"""
    try:
        from .models import GradingType, GradingLevel

        tenant = request.tenant
        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

        # Get grading type for the batch (assuming default grading type for now)
        grading_type = GradingType.objects.filter(tenant=tenant, is_active=True).first()

        if grading_type:
            grade_levels = GradingLevel.objects.filter(
                tenant=tenant,
                grading_type=grading_type
            ).order_by('min_score')

            levels_data = [{
                'id': str(level.id),
                'name': level.name,
                'min_score': str(level.min_score),
                'max_score': str(level.max_score),
                'credit_points': str(level.credit_points) if level.credit_points else None,
            } for level in grade_levels]
        else:
            levels_data = []

        return JsonResponse({
            'success': True,
            'grade_levels': levels_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def batch_grading_scale_api(request, batch_id):
    """Return GradingLevel records configured for a specific batch (report-card scale)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
    levels = GradingLevel.objects.filter(
        batch=batch, tenant=tenant, is_deleted=False
    ).order_by('-min_score')
    DEFAULT = [
        {'grade': 'A', 'min_score': 80, 'description': 'Very Good'},
        {'grade': 'B', 'min_score': 60, 'description': 'Good'},
        {'grade': 'C', 'min_score': 50, 'description': 'Satisfactory'},
        {'grade': 'D', 'min_score': 40, 'description': 'Weak'},
        {'grade': 'E', 'min_score': 0,  'description': 'Very Weak'},
    ]
    if levels.exists():
        data = [{'id': str(l.id), 'grade': l.name, 'min_score': l.min_score,
                 'description': l.description or ''} for l in levels]
        using_default = False
    else:
        data = DEFAULT
        using_default = True
    return JsonResponse({'levels': data, 'using_default': using_default})


@login_required
@require_http_methods(["POST"])
def add_batch_grading_level_api(request, batch_id):
    """Add a GradingLevel to a batch's report-card grading scale."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
    try:
        body = json.loads(request.body)
    except Exception:
        body = {}
    grade = (body.get('grade') or '').strip()
    min_score = body.get('min_score')
    description = (body.get('description') or '').strip()
    if not grade or min_score is None:
        return JsonResponse({'success': False, 'error': 'Grade and min_score are required'})
    try:
        min_score = int(min_score)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'min_score must be a whole number'})
    existing_count = GradingLevel.objects.filter(batch=batch, tenant=tenant, is_deleted=False).count()
    level = GradingLevel.objects.create(
        tenant=tenant, batch=batch, name=grade, min_score=min_score,
        order=existing_count + 1, description=description or None,
    )
    return JsonResponse({'success': True,
                         'level': {'id': str(level.id), 'grade': level.name,
                                   'min_score': level.min_score, 'description': level.description or ''}})


@login_required
@require_http_methods(["POST"])
def update_grading_level_api(request, level_id):
    """Update a single GradingLevel record."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    level = get_object_or_404(GradingLevel, id=level_id, tenant=tenant, is_deleted=False)
    try:
        body = json.loads(request.body)
    except Exception:
        body = {}
    grade = (body.get('grade') or '').strip()
    min_score = body.get('min_score')
    description = (body.get('description') or '').strip()
    if not grade or min_score is None:
        return JsonResponse({'success': False, 'error': 'Grade and min_score are required'})
    try:
        min_score = int(min_score)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'min_score must be a whole number'})
    level.name = grade
    level.min_score = min_score
    level.description = description or None
    level.save()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def delete_grading_level_api(request, level_id):
    """Soft-delete a GradingLevel record."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    level = get_object_or_404(GradingLevel, id=level_id, tenant=tenant, is_deleted=False)
    level.is_deleted = True
    level.save()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def reset_batch_grading_scale_api(request, batch_id):
    """Delete all custom GradingLevel records for a batch (revert to default A–E)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
    GradingLevel.objects.filter(batch=batch, tenant=tenant, is_deleted=False).update(is_deleted=True)
    return JsonResponse({'success': True, 'message': 'Reset to default A–E scale'})


@login_required
@require_http_methods(["GET"])
def get_subject_settings_api(request):
    """API endpoint to get subject grading settings"""
    try:
        from .models import SubjectGradingSettings

        tenant = request.tenant
        subject_id = request.GET.get('subject_id')

        if subject_id:
            settings = SubjectGradingSettings.objects.filter(
                tenant=tenant,
                subject_id=subject_id
            ).select_related('subject', 'grading_type').first()

            if settings:
                settings_data = {
                    'id': str(settings.id),
                    'subject': settings.subject.name,
                    'grading_type': settings.grading_type.name if settings.grading_type else None,
                    'pass_marks': str(settings.pass_marks) if settings.pass_marks else None,
                    'is_graded': settings.is_graded,
                }
            else:
                settings_data = None
        else:
            settings = SubjectGradingSettings.objects.filter(tenant=tenant).select_related('subject', 'grading_type')
            settings_data = [{
                'id': str(setting.id),
                'subject': setting.subject.name,
                'grading_type': setting.grading_type.name if setting.grading_type else None,
                'pass_marks': str(setting.pass_marks) if setting.pass_marks else None,
                'is_graded': setting.is_graded,
            } for setting in settings]

        return JsonResponse({
            'success': True,
            'settings': settings_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def get_grading_type_api(request, grading_type_id):
    """Return a single GradingType's field values for pre-populating the edit form."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import GradingType
    gt = get_object_or_404(GradingType, id=grading_type_id, tenant=tenant)
    return JsonResponse({
        'id': str(gt.id),
        'name': gt.name,
        'code': gt.code,
        'description': gt.description or '',
        'is_active': gt.is_active,
        'gpa_scale': str(gt.gpa_scale) if gt.gpa_scale else '',
        'cce_scholastic_weight': str(gt.cce_scholastic_weight),
        'cce_coscholastic_weight': str(gt.cce_coscholastic_weight),
    })


@login_required
@require_http_methods(["POST"])
def update_grading_type_api(request, grading_type_id):
    """Update an existing GradingType."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import GradingType
    gt = get_object_or_404(GradingType, id=grading_type_id, tenant=tenant)
    try:
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        gpa_scale = request.POST.get('gpa_scale') or None
        cce_scholastic = request.POST.get('cce_scholastic_weight', 70)
        cce_coscholastic = request.POST.get('cce_coscholastic_weight', 30)
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})
        gt.name = name
        gt.description = description or None
        gt.is_active = is_active
        gt.gpa_scale = gpa_scale
        gt.cce_scholastic_weight = cce_scholastic
        gt.cce_coscholastic_weight = cce_coscholastic
        gt.save()
        return JsonResponse({'success': True, 'name': gt.name})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_coscholastic_api(request):
    """Create a CoScholasticAssessment record."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import CoScholasticAssessment
    try:
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        description = request.POST.get('description', '').strip()
        max_score = request.POST.get('max_score', 100)
        if not name or not code:
            return JsonResponse({'success': False, 'error': 'Name and type are required'})
        if CoScholasticAssessment.objects.filter(tenant=tenant, code=code).exists():
            return JsonResponse({'success': False, 'error': 'An assessment of this type already exists'})
        obj = CoScholasticAssessment.objects.create(
            tenant=tenant, name=name, code=code,
            description=description or None, max_score=max_score,
        )
        return JsonResponse({
            'success': True,
            'assessment': {
                'id': str(obj.id), 'name': obj.name,
                'code': obj.get_code_display(), 'max_score': str(obj.max_score),
                'is_active': obj.is_active,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_coscholastic_api(request, assessment_id):
    """Delete a CoScholasticAssessment record."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import CoScholasticAssessment
    obj = get_object_or_404(CoScholasticAssessment, id=assessment_id, tenant=tenant)
    obj.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["GET"])
def get_coscholastic_api(request, assessment_id):
    """Fetch a single CoScholasticAssessment for edit form."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import CoScholasticAssessment
    obj = get_object_or_404(CoScholasticAssessment, id=assessment_id, tenant=tenant)
    return JsonResponse({
        'id': str(obj.id),
        'name': obj.name,
        'code': obj.code,
        'description': obj.description or '',
        'max_score': str(obj.max_score),
        'is_active': obj.is_active,
    })


@login_required
@require_http_methods(["POST"])
def update_coscholastic_api(request, assessment_id):
    """Update an existing CoScholasticAssessment."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import CoScholasticAssessment
    obj = get_object_or_404(CoScholasticAssessment, id=assessment_id, tenant=tenant)
    try:
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        max_score = request.POST.get('max_score', 100)
        is_active = request.POST.get('is_active') == 'on'
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})
        obj.name = name
        obj.description = description or None
        obj.max_score = max_score
        obj.is_active = is_active
        obj.save()
        return JsonResponse({'success': True, 'name': obj.name})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_subject_grading_settings_api(request, setting_id):
    """Update internal/external weight and credit hours for a SubjectGradingSettings record."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import SubjectGradingSettings
    setting = get_object_or_404(SubjectGradingSettings, id=setting_id, tenant=tenant)
    try:
        body = json.loads(request.body)
    except Exception:
        body = {}
    try:
        internal = float(body.get('internal_assessment_weight', setting.internal_assessment_weight))
        external = float(body.get('external_assessment_weight', setting.external_assessment_weight))
        credit_hours = float(body.get('credit_hours', setting.credit_hours))
        if round(internal + external, 2) != 100.0:
            return JsonResponse({'success': False, 'error': 'Internal + external weights must sum to 100'})
        setting.internal_assessment_weight = internal
        setting.external_assessment_weight = external
        setting.credit_hours = credit_hours
        setting.save()
        return JsonResponse({'success': True})
    except (ValueError, TypeError) as e:
        return JsonResponse({'success': False, 'error': f'Invalid value: {e}'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ── Grading Scale CRUD ────────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def create_grading_scale_api(request):
    """Create a new GradingScale."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    name = data.get('name', '').strip()
    code = data.get('code', '').strip().upper()
    scale_type = data.get('scale_type', 'LETTER')
    description = data.get('description', '')
    is_default = bool(data.get('is_default', False))
    report_layout = data.get('report_layout') or ''
    if not name or not code:
        return JsonResponse({'success': False, 'error': 'Name and code are required'}, status=400)
    from .models import GradingScale
    if GradingScale.objects.filter(tenant=tenant, code=code).exists():
        return JsonResponse({'success': False, 'error': f'A grading scale with code "{code}" already exists'}, status=400)
    if is_default:
        GradingScale.objects.filter(tenant=tenant, is_default=True).update(is_default=False)
    scale = GradingScale.objects.create(
        tenant=tenant, name=name, code=code, scale_type=scale_type,
        description=description, is_default=is_default, report_layout=report_layout, is_active=True,
    )
    return JsonResponse({'success': True, 'scale': {
        'id': str(scale.id), 'name': scale.name, 'code': scale.code,
        'scale_type': scale.scale_type, 'is_default': scale.is_default,
    }})


@login_required
@require_http_methods(["GET"])
def get_grading_scale_api(request, scale_id):
    """Return a GradingScale and its GradeValues."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import GradingScale
    scale = get_object_or_404(GradingScale, id=scale_id, tenant=tenant)
    grade_values = []
    for gv in scale.grade_values.order_by('display_order', 'name'):
        grade_values.append({
            'id': str(gv.id), 'name': gv.name, 'code': gv.code,
            'min_percentage': float(gv.min_percentage) if gv.min_percentage is not None else None,
            'max_percentage': float(gv.max_percentage) if gv.max_percentage is not None else None,
            'gpa_value': float(gv.gpa_value) if gv.gpa_value is not None else None,
            'display_order': gv.display_order, 'is_passing': gv.is_passing,
            'color_code': gv.color_code or '#808080',
        })
    return JsonResponse({'success': True, 'scale': {
        'id': str(scale.id), 'name': scale.name, 'code': scale.code,
        'scale_type': scale.scale_type, 'description': scale.description or '',
        'is_default': scale.is_default, 'report_layout': scale.report_layout or '',
    }, 'grade_values': grade_values})


@login_required
@require_http_methods(["POST"])
def update_grading_scale_api(request, scale_id):
    """Update a GradingScale."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    from .models import GradingScale
    scale = get_object_or_404(GradingScale, id=scale_id, tenant=tenant)
    name = data.get('name', scale.name).strip()
    code = data.get('code', scale.code).strip().upper()
    if not name or not code:
        return JsonResponse({'success': False, 'error': 'Name and code are required'}, status=400)
    if GradingScale.objects.filter(tenant=tenant, code=code).exclude(id=scale_id).exists():
        return JsonResponse({'success': False, 'error': f'Code "{code}" is already used by another scale'}, status=400)
    is_default = bool(data.get('is_default', scale.is_default))
    if is_default and not scale.is_default:
        GradingScale.objects.filter(tenant=tenant, is_default=True).update(is_default=False)
    scale.name = name
    scale.code = code
    scale.scale_type = data.get('scale_type', scale.scale_type)
    scale.description = data.get('description', scale.description or '')
    scale.is_default = is_default
    scale.report_layout = data.get('report_layout') or ''
    scale.save()
    return JsonResponse({'success': True, 'message': f'"{scale.name}" updated'})


@login_required
@require_http_methods(["POST"])
def delete_grading_scale_api(request, scale_id):
    """Soft-delete a GradingScale (is_active=False). Rejects if scale is referenced."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import GradingScale, Exam, Subject
    scale = get_object_or_404(GradingScale, id=scale_id, tenant=tenant)
    exam_count = Exam.objects.filter(tenant=tenant, grading_scale=scale).count()
    subject_count = Subject.objects.filter(tenant=tenant, grading_scale=scale).count()
    if exam_count or subject_count:
        return JsonResponse({
            'success': False,
            'error': f'Cannot delete: scale is used by {exam_count} exam(s) and {subject_count} subject(s). Remove those references first.',
        }, status=409)
    scale.is_active = False
    scale.save(update_fields=['is_active'])
    return JsonResponse({'success': True, 'message': f'"{scale.name}" deleted'})


@login_required
@require_http_methods(["POST"])
def create_grade_value_api(request, scale_id):
    """Add a GradeValue to a GradingScale."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import GradingScale, GradeValue
    scale = get_object_or_404(GradingScale, id=scale_id, tenant=tenant)
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    name = data.get('name', '').strip()
    code = data.get('code', '').strip()
    if not name or not code:
        return JsonResponse({'success': False, 'error': 'Name and code are required'}, status=400)
    min_pct = data.get('min_percentage')
    max_pct = data.get('max_percentage')
    gpa_value = data.get('gpa_value')
    display_order = int(data.get('display_order', scale.grade_values.count()))
    gv = GradeValue.objects.create(
        tenant=tenant, grading_scale=scale, name=name, code=code,
        min_percentage=min_pct if min_pct not in (None, '') else None,
        max_percentage=max_pct if max_pct not in (None, '') else None,
        gpa_value=gpa_value if gpa_value not in (None, '') else None,
        display_order=display_order,
        is_passing=bool(data.get('is_passing', True)),
        color_code=data.get('color_code') or '#808080',
    )
    return JsonResponse({'success': True, 'grade_value': {
        'id': str(gv.id), 'name': gv.name, 'code': gv.code,
        'min_percentage': float(gv.min_percentage) if gv.min_percentage is not None else None,
        'max_percentage': float(gv.max_percentage) if gv.max_percentage is not None else None,
        'gpa_value': float(gv.gpa_value) if gv.gpa_value is not None else None,
        'display_order': gv.display_order, 'is_passing': gv.is_passing, 'color_code': gv.color_code or '#808080',
    }})


@login_required
@require_http_methods(["POST"])
def update_grade_value_api(request, value_id):
    """Update a GradeValue."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import GradeValue
    gv = get_object_or_404(GradeValue, id=value_id, tenant=tenant)
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    name = data.get('name', gv.name).strip()
    code = data.get('code', gv.code).strip()
    if name:
        gv.name = name
    if code:
        gv.code = code
    min_pct = data.get('min_percentage')
    max_pct = data.get('max_percentage')
    gpa_value = data.get('gpa_value')
    if min_pct not in (None, ''):
        gv.min_percentage = min_pct
    if max_pct not in (None, ''):
        gv.max_percentage = max_pct
    if gpa_value not in (None, ''):
        gv.gpa_value = gpa_value
    if 'display_order' in data:
        gv.display_order = int(data['display_order'])
    if 'is_passing' in data:
        gv.is_passing = bool(data['is_passing'])
    if 'color_code' in data and data['color_code']:
        gv.color_code = data['color_code']
    gv.save()
    return JsonResponse({'success': True, 'message': f'Grade "{gv.name}" updated'})


@login_required
@require_http_methods(["POST"])
def delete_grade_value_api(request, value_id):
    """Delete a GradeValue. Rejects if any ExamScore already references it —
    a mid-term hard delete would silently null those scores (SET_NULL) and,
    worse, invalidate the grade_value_id already rendered on any open
    marks-entry page, causing in-flight submissions to fail silently."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import GradeValue, ExamScore
    gv = get_object_or_404(GradeValue, id=value_id, tenant=tenant)
    score_count = ExamScore.objects.filter(tenant=tenant, grade_value=gv).count()
    if score_count:
        return JsonResponse({
            'success': False,
            'error': f'Cannot delete: grade "{gv.name}" is used by {score_count} exam score(s). Remove those references first.',
        }, status=409)
    name = gv.name
    gv.delete()
    return JsonResponse({'success': True, 'message': f'Grade "{name}" deleted'})


@login_required
@require_http_methods(["POST"])
def reorder_grade_values_api(request, scale_id):
    """Accept an ordered list of GradeValue IDs and update display_order."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    from .models import GradingScale, GradeValue
    get_object_or_404(GradingScale, id=scale_id, tenant=tenant)
    try:
        data = json.loads(request.body)
        ordered_ids = data.get('ordered_ids', [])
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    for idx, value_id in enumerate(ordered_ids):
        GradeValue.objects.filter(id=value_id, tenant=tenant, grading_scale_id=scale_id).update(display_order=idx)
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["GET"])
def get_students_api(request):
    """API endpoint to get students list"""
    try:
        tenant = request.tenant
        batch_id = request.GET.get('batch_id')
        exam_group_id = request.GET.get('exam_group_id')

        if exam_group_id:
            from .models import ExamGroup as _EG
            eg = get_object_or_404(_EG, id=exam_group_id, tenant=tenant)
            students = Student.objects.filter(
                tenant=tenant,
                student_batches__batch=eg.batch,
                student_batches__is_active=True
            ).order_by('first_name', 'last_name')
        elif batch_id:
            students = Student.objects.filter(
                tenant=tenant,
                student_batches__batch_id=batch_id,
                student_batches__is_active=True
            ).order_by('first_name', 'last_name')
        else:
            students = Student.objects.filter(tenant=tenant).order_by('first_name', 'last_name')

        students_data = [{
            'id': str(student.id),
            'first_name': student.first_name,
            'last_name': student.last_name or '',
            'name': f"{student.first_name} {student.last_name or ''}".strip(),
            'admission_no': student.admission_no,
        } for student in students]

        return JsonResponse({
            'success': True,
            'students': students_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def get_terms_api(request):
    """API endpoint to get terms list.

    Phase 3: Returns year-scoped Terms (not per-batch). Now functional
    with Phase 1's academic_year field (was broken pre-Phase 1).
    """
    try:
        tenant = request.tenant
        academic_year_id = request.GET.get('academic_year_id')

        if academic_year_id:
            terms = Term.objects.filter(
                tenant=tenant,
                academic_year_id=academic_year_id
            ).order_by('start_date')
        else:
            # Get terms for active academic year
            active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
            if active_year:
                terms = Term.objects.filter(
                    tenant=tenant,
                    academic_year=active_year
                ).order_by('start_date')
            else:
                terms = Term.objects.none()

        terms_data = [{
            'id': str(term.id),
            'name': term.name,
            'start_date': term.start_date.strftime('%Y-%m-%d') if term.start_date else None,
            'end_date': term.end_date.strftime('%Y-%m-%d') if term.end_date else None,
        } for term in terms]

        return JsonResponse({
            'success': True,
            'terms': terms_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def download_reports_api(request):
    """API endpoint to download generated reports"""
    try:
        import json

        tenant = request.tenant
        report_ids = json.loads(request.POST.get('report_ids', '[]'))
        format_type = request.POST.get('format', 'pdf')

        if not report_ids:
            return JsonResponse({'success': False, 'error': 'No reports selected'})

        # Simulate report download preparation
        download_url = f"/media/reports/bulk_download_{len(report_ids)}_reports.{format_type}"

        return JsonResponse({
            'success': True,
            'message': f'Prepared {len(report_ids)} reports for download',
            'download_url': download_url
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def export_skills_assessment_api(request):
    """API endpoint to export skills assessment data"""
    try:
        import json

        tenant = request.tenant
        batch_ids = json.loads(request.POST.get('batch_ids', '[]'))
        export_format = request.POST.get('format', 'excel')
        period = request.POST.get('period', 'current')

        if not batch_ids:
            return JsonResponse({'success': False, 'error': 'No batches selected'})

        # Simulate export preparation
        export_filename = f"skills_assessment_export_{period}_{len(batch_ids)}_batches.{export_format}"
        export_url = f"/media/exports/{export_filename}"

        return JsonResponse({
            'success': True,
            'message': f'Skills assessment data exported successfully',
            'export_url': export_url,
            'filename': export_filename
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# Enhanced Attendance API Endpoints for Reporting

@login_required
@require_http_methods(["GET"])
def get_student_attendance_summary_api(request, student_id):
    """API endpoint to get student attendance summary for reports"""
    try:
        from .attendance_utils import AttendanceCalculator, AttendanceReportGenerator

        tenant = request.tenant
        student = get_object_or_404(Student, id=student_id, tenant=tenant)

        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        term_id = request.GET.get('term_id')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        term = None
        if term_id:
            term = get_object_or_404(Term, id=term_id, tenant=tenant)

        # Generate report
        report_generator = AttendanceReportGenerator(tenant)
        report_data = report_generator.generate_student_report(
            student, term=term
        )

        if not report_data:
            return JsonResponse({
                'success': False,
                'error': 'No attendance data found for student'
            })

        # Format response data
        response_data = {
            'student': {
                'id': str(student.id),
                'name': f"{student.first_name} {student.last_name}",
                'admission_no': student.admission_no,
            },
            'attendance_summary': report_data['attendance_summary'],
            'monthly_summaries': [{
                'period': f"{summary.period_start.strftime('%B %Y')}",
                'attendance_percentage': float(summary.attendance_percentage),
                'status': summary.status_text,
                'status_color': summary.status_color,
                'present_days': summary.present_days,
                'total_days': summary.total_days,
            } for summary in report_data['monthly_summaries']],
            'period': {
                'start_date': report_data['period']['start_date'].strftime('%Y-%m-%d'),
                'end_date': report_data['period']['end_date'].strftime('%Y-%m-%d'),
            }
        }

        return JsonResponse({
            'success': True,
            'data': response_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def get_batch_attendance_report_api(request, batch_id):
    """API endpoint to get batch attendance report"""
    try:
        from .attendance_utils import AttendanceCalculator

        tenant = request.tenant
        batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)

        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            # Default to current academic year
            academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
            start_date = academic_year.start_date if academic_year else date.today().replace(month=1, day=1)

        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            # Default to current academic year
            academic_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
            end_date = academic_year.end_date if academic_year else date.today()

        # Get batch attendance data
        report_data = AttendanceCalculator.get_attendance_report_data(
            batch, start_date, end_date
        )

        # Format for API response
        students_data = []
        for student_data in report_data['students']:
            student = student_data['student']
            attendance = student_data['attendance']

            students_data.append({
                'id': str(student.id),
                'name': f"{student.first_name} {student.last_name}",
                'admission_no': student.admission_no,
                'attendance': {
                    'percentage': attendance['attendance_percentage'],
                    'status': attendance['status'],
                    'status_color': attendance['status_color'],
                    'total_days': attendance['total_days'],
                    'present_days': attendance['present_days'],
                    'absent_days': attendance['absent_days'],
                    'half_day_present': attendance['half_day_present']
                }
            })

        response_data = {
            'batch': {
                'id': str(batch.id),
                'name': batch.name,
            },
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
            },
            'statistics': report_data['statistics'],
            'students': students_data
        }

        return JsonResponse({
            'success': True,
            'data': response_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_attendance_summaries_api(request):
    """API endpoint to update attendance summaries for reporting"""
    try:
        from .attendance_utils import update_attendance_summaries

        tenant = request.tenant
        period_type = request.POST.get('period_type', 'MONTHLY')

        # Update summaries
        updated_count = update_attendance_summaries(tenant, period_type)

        return JsonResponse({
            'success': True,
            'message': f'Updated {updated_count} attendance summaries',
            'updated_count': updated_count
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def export_attendance_report_enhanced_api(request):
    """Enhanced export: batch/student/low-attendance → CSV or PDF download."""
    import csv as csv_mod
    from .attendance_utils import AttendanceReportGenerator

    try:
        tenant = request.tenant
        export_type = request.POST.get('export_type', 'batch')
        format_type = request.POST.get('format', 'csv')
        batch_ids = json.loads(request.POST.get('batch_ids', '[]'))
        student_ids = json.loads(request.POST.get('student_ids', '[]'))
        raw_start = request.POST.get('start_date')
        raw_end = request.POST.get('end_date')
        start_date = datetime.strptime(raw_start, '%Y-%m-%d').date() if raw_start else None
        end_date = datetime.strptime(raw_end, '%Y-%m-%d').date() if raw_end else None

        report_generator = AttendanceReportGenerator(tenant)
        rows = []   # [{student_name, student_id, present_days, absent_days, pct}]

        if export_type == 'batch' and batch_ids:
            for batch_id in batch_ids:
                batch = get_object_or_404(Batch, id=batch_id, tenant=tenant)
                data = report_generator.generate_batch_report(batch, start_date, end_date)
                for s in data.get('student_summaries', []):
                    rows.append({
                        'batch': batch.name,
                        'student_name': s['student_name'],
                        'student_id': s.get('student_id', ''),
                        'present_days': s['present_days'],
                        'absent_days': s['absent_days'],
                        'attendance_percentage': s['attendance_percentage'],
                    })

        elif export_type == 'student' and student_ids:
            for student_id in student_ids:
                student = get_object_or_404(Student, id=student_id, tenant=tenant)
                data = report_generator.generate_student_report(student)
                rows.append({
                    'batch': '',
                    'student_name': student.full_name,
                    'student_id': student.admission_no,
                    'present_days': data.get('present_days', ''),
                    'absent_days': data.get('absent_days', ''),
                    'attendance_percentage': data.get('attendance_percentage', ''),
                })

        elif export_type == 'low_attendance':
            threshold = int(request.POST.get('threshold', 75))
            data = report_generator.generate_low_attendance_report(threshold)
            for s in data.get('students', []):
                rows.append({
                    'batch': s.get('batch', ''),
                    'student_name': s['student_name'],
                    'student_id': s.get('student_id', ''),
                    'present_days': s.get('present_days', ''),
                    'absent_days': s.get('absent_days', ''),
                    'attendance_percentage': s.get('attendance_percentage', ''),
                })

        filename = f"attendance_{export_type}_{date.today()}"

        if format_type in ('csv', 'excel'):
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
            writer = csv_mod.DictWriter(
                response,
                fieldnames=['batch', 'student_name', 'student_id', 'present_days', 'absent_days', 'attendance_percentage']
            )
            writer.writeheader()
            writer.writerows(rows)
            return response

        else:  # pdf
            from django.template.loader import render_to_string
            from weasyprint import HTML
            from weasyprint.text.fonts import FontConfiguration

            html = render_to_string('core/reports/attendance_report_pdf.html', {
                'report_data': {'student_summaries': rows, 'batch_summary': None},
                'format_type': 'batch',
                'start_date': raw_start or '',
                'end_date': raw_end or '',
                'tenant': tenant,
            })
            pdf_bytes = HTML(string=html).write_pdf(font_config=FontConfiguration())
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
            return response

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
