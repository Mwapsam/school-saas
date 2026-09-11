from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q, Count, F
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from datetime import datetime, timedelta
import json
import csv
import io
from typing import Dict, Any

from ..models import (
    ApplicantEnquiry,
    ApplicantEnquiryStage,
    ApplicantEnquiryFormField,
    EnquiryStageLog,
    EnquiryStageLogNote,
    EnquiryFollowUp,
    Course,
    AcademicYear,
    Employee,
)
from ..forms import (
    ApplicantEnquiryForm,
    EnquiryFilterForm,
    EnquiryFollowUpForm,
    EnquiryStageLogNoteForm,
    EnquiryBulkActionForm,
)
from ..serializers.enquiry_serializers import (
    ApplicantEnquiryListSerializer,
    ApplicantEnquiryDetailSerializer,
    ApplicantEnquiryCreateSerializer,
    ApplicantEnquiryUpdateSerializer,
    ApplicantEnquiryStageSerializer,
    EnquiryStatsSerializer,
    EnquiryFollowUpSerializer,
)
from django.contrib.auth.mixins import LoginRequiredMixin


class EnquiryDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard showing enquiry statistics and overview"""
    template_name = 'core/enquiry/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        # Get enquiry statistics — single query with conditional aggregation
        # instead of four separate COUNT round-trips.
        this_month = timezone.now().replace(day=1)
        stats = ApplicantEnquiry.objects.filter(tenant=tenant).aggregate(
            total=Count('id'),
            processed=Count('id', filter=Q(is_processed=True)),
            rejected=Count('id', filter=Q(is_rejected=True)),
            this_month=Count('id', filter=Q(created_at__gte=this_month)),
        )
        total_enquiries = stats['total']
        processed_enquiries = stats['processed']
        pending_enquiries = total_enquiries - processed_enquiries
        rejected_enquiries = stats['rejected']
        this_month_enquiries = stats['this_month']

        # Stage breakdown
        stage_breakdown = ApplicantEnquiry.objects.filter(tenant=tenant).values(
            'stage__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')

        # Course breakdown
        course_breakdown = ApplicantEnquiry.objects.filter(tenant=tenant).values(
            'course__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')

        # Recent enquiries
        recent_enquiries = ApplicantEnquiry.objects.filter(tenant=tenant).order_by('-created_at')[:10]

        # Follow-ups due today
        today = timezone.now().date()
        follow_ups_due = EnquiryFollowUp.objects.filter(
            tenant=tenant,
            scheduled_date__date=today,
            status='planned'
        ).select_related('enquiry', 'assigned_to')

        context.update({
            'total_enquiries': total_enquiries,
            'processed_enquiries': processed_enquiries,
            'pending_enquiries': pending_enquiries,
            'rejected_enquiries': rejected_enquiries,
            'this_month_enquiries': this_month_enquiries,
            'stage_breakdown': stage_breakdown,
            'course_breakdown': course_breakdown,
            'recent_enquiries': recent_enquiries,
            'follow_ups_due': follow_ups_due,
        })

        return context


class ApplicantEnquiryListView(LoginRequiredMixin, ListView):
    """List view for applicant enquiries"""
    model = ApplicantEnquiry
    template_name = 'core/enquiry/list.html'
    context_object_name = 'enquiries'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'course', 'academic_year', 'stage', 'counselor'
        ).order_by('-created_at')

        # Apply filters
        form = EnquiryFilterForm(self.request.GET, tenant=self.request.tenant)
        if form.is_valid():
            search = form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(email__icontains=search) |
                    Q(phone__icontains=search) |
                    Q(enquiry_number__icontains=search)
                )

            stage = form.cleaned_data.get('stage')
            if stage:
                queryset = queryset.filter(stage=stage)

            course = form.cleaned_data.get('course')
            if course:
                queryset = queryset.filter(course=course)

            academic_year = form.cleaned_data.get('academic_year')
            if academic_year:
                queryset = queryset.filter(academic_year=academic_year)

            counselor = form.cleaned_data.get('counselor')
            if counselor:
                queryset = queryset.filter(counselor=counselor)

            is_processed = form.cleaned_data.get('is_processed')
            if is_processed == 'yes':
                queryset = queryset.filter(is_processed=True)
            elif is_processed == 'no':
                queryset = queryset.filter(is_processed=False)

            date_from = form.cleaned_data.get('date_from')
            if date_from:
                queryset = queryset.filter(enquired_date__gte=date_from)

            date_to = form.cleaned_data.get('date_to')
            if date_to:
                queryset = queryset.filter(enquired_date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = EnquiryFilterForm(self.request.GET, tenant=self.request.tenant)
        context['bulk_action_form'] = EnquiryBulkActionForm(tenant=self.request.tenant)
        return context


class ApplicantEnquiryDetailView(LoginRequiredMixin, DetailView):
    """Detail view for applicant enquiries"""
    model = ApplicantEnquiry
    template_name = 'core/enquiry/detail.html'
    context_object_name = 'enquiry'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'course', 'academic_year', 'stage', 'counselor'
        ).prefetch_related('stage_logs__stage', 'stage_logs__notes', 'follow_ups')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enquiry = self.get_object()

        # Mark as viewed
        if not enquiry.is_viewed:
            enquiry.is_viewed = True
            enquiry.save(update_fields=['is_viewed'])

        # Get stage logs with notes
        stage_logs = enquiry.stage_logs.all().order_by('-created_at')

        # Get follow-ups
        follow_ups = enquiry.follow_ups.all().order_by('scheduled_date')

        # Forms for adding data
        context.update({
            'stage_logs': stage_logs,
            'follow_ups': follow_ups,
            'follow_up_form': EnquiryFollowUpForm(tenant=self.request.tenant),
            'note_form': EnquiryStageLogNoteForm(),
        })

        return context


class ApplicantEnquiryCreateView(LoginRequiredMixin, CreateView):
    """Create view for applicant enquiries"""
    model = ApplicantEnquiry
    form_class = ApplicantEnquiryForm
    template_name = 'core/enquiry/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        form.instance.tenant = self.request.tenant

        # Set default stage if not provided
        if not form.instance.stage:
            default_stage = ApplicantEnquiryStage.objects.filter(
                tenant=self.request.tenant,
                is_default=True
            ).first()
            if default_stage:
                form.instance.stage = default_stage

        response = super().form_valid(form)

        # Create initial stage log
        if self.object.stage:
            EnquiryStageLog.objects.create(
                tenant=self.request.tenant,
                enquiry=self.object,
                stage=self.object.stage
            )

        messages.success(self.request, f'Enquiry {self.object.enquiry_number} created successfully.')
        return response

    def get_success_url(self):
        return reverse_lazy('core:enquiry_detail', kwargs={'pk': self.object.pk})


class ApplicantEnquiryUpdateView(LoginRequiredMixin, UpdateView):
    """Update view for applicant enquiries"""
    model = ApplicantEnquiry
    form_class = ApplicantEnquiryForm
    template_name = 'core/enquiry/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        old_stage = self.object.stage
        response = super().form_valid(form)
        new_stage = self.object.stage

        # Create stage log if stage changed
        if old_stage != new_stage and new_stage:
            EnquiryStageLog.objects.create(
                tenant=self.request.tenant,
                enquiry=self.object,
                stage=new_stage,
                changed_by=getattr(self.request.user, 'employee_profile', None)
            )

        messages.success(self.request, f'Enquiry {self.object.enquiry_number} updated successfully.')
        return response

    def get_success_url(self):
        return reverse_lazy('core:enquiry_detail', kwargs={'pk': self.object.pk})


# API Views
class ApplicantEnquiryViewSet(viewsets.ModelViewSet):
    """API ViewSet for applicant enquiries"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ApplicantEnquiry.objects.filter(
            tenant=self.request.tenant
        ).select_related('course', 'academic_year', 'stage', 'counselor')

    def get_serializer_class(self):
        if self.action == 'list':
            return ApplicantEnquiryListSerializer
        elif self.action == 'create':
            return ApplicantEnquiryCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ApplicantEnquiryUpdateSerializer
        return ApplicantEnquiryDetailSerializer

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get enquiry statistics"""
        tenant = request.tenant

        this_month = timezone.now().replace(day=1)
        counts = ApplicantEnquiry.objects.filter(tenant=tenant).aggregate(
            total=Count('id'),
            processed=Count('id', filter=Q(is_processed=True)),
            rejected=Count('id', filter=Q(is_rejected=True)),
            this_month=Count('id', filter=Q(created_at__gte=this_month)),
        )
        total_enquiries = counts['total']
        processed_enquiries = counts['processed']
        pending_enquiries = total_enquiries - processed_enquiries
        rejected_enquiries = counts['rejected']
        this_month_enquiries = counts['this_month']

        stage_breakdown = dict(ApplicantEnquiry.objects.filter(tenant=tenant).values_list(
            'stage__name'
        ).annotate(count=Count('id')))

        course_breakdown = dict(ApplicantEnquiry.objects.filter(tenant=tenant).values_list(
            'course__name'
        ).annotate(count=Count('id')))

        source_breakdown = dict(ApplicantEnquiry.objects.filter(tenant=tenant).values_list(
            'source_of_info'
        ).annotate(count=Count('id')))

        stats = {
            'total_enquiries': total_enquiries,
            'processed_enquiries': processed_enquiries,
            'pending_enquiries': pending_enquiries,
            'rejected_enquiries': rejected_enquiries,
            'this_month_enquiries': this_month_enquiries,
            'stage_breakdown': stage_breakdown,
            'course_breakdown': course_breakdown,
            'source_breakdown': source_breakdown,
        }

        serializer = EnquiryStatsSerializer(data=stats)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def change_stage(self, request, pk=None):
        """Change enquiry stage"""
        enquiry = self.get_object()
        stage_id = request.data.get('stage_id')

        try:
            stage = ApplicantEnquiryStage.objects.get(
                id=stage_id,
                tenant=request.tenant
            )

            old_stage = enquiry.stage
            enquiry.stage = stage
            enquiry.save(update_fields=['stage'])

            # Create stage log
            EnquiryStageLog.objects.create(
                tenant=request.tenant,
                enquiry=enquiry,
                stage=stage,
                changed_by=getattr(request.user, 'employee_profile', None)
            )

            return Response({
                'success': True,
                'message': f'Stage changed from {old_stage.name if old_stage else "None"} to {stage.name}'
            })

        except ApplicantEnquiryStage.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Invalid stage'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk actions on enquiries"""
        enquiry_ids = request.data.get('enquiry_ids', [])
        action_type = request.data.get('action')

        if not enquiry_ids:
            return Response({
                'success': False,
                'message': 'No enquiries selected'
            }, status=status.HTTP_400_BAD_REQUEST)

        enquiries = self.get_queryset().filter(id__in=enquiry_ids)

        if action_type == 'change_stage':
            stage_id = request.data.get('stage_id')
            try:
                stage = ApplicantEnquiryStage.objects.get(
                    id=stage_id,
                    tenant=request.tenant
                )
                for enquiry in enquiries:
                    enquiry.stage = stage
                    enquiry.save(update_fields=['stage'])

                    # Create stage log
                    EnquiryStageLog.objects.create(
                        tenant=request.tenant,
                        enquiry=enquiry,
                        stage=stage,
                        changed_by=getattr(request.user, 'employee_profile', None)
                    )

                return Response({
                    'success': True,
                    'message': f'{len(enquiries)} enquiries updated'
                })

            except ApplicantEnquiryStage.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Invalid stage'
                }, status=status.HTTP_400_BAD_REQUEST)

        elif action_type == 'assign_counselor':
            counselor_id = request.data.get('counselor_id')
            try:
                counselor = Employee.objects.get(
                    id=counselor_id,
                    tenant=request.tenant
                )
                enquiries.update(counselor=counselor)

                return Response({
                    'success': True,
                    'message': f'{len(enquiries)} enquiries assigned to {counselor.full_name}'
                })

            except Employee.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Invalid counselor'
                }, status=status.HTTP_400_BAD_REQUEST)

        elif action_type == 'mark_processed':
            enquiries.update(is_processed=True)
            return Response({
                'success': True,
                'message': f'{len(enquiries)} enquiries marked as processed'
            })

        elif action_type == 'mark_unprocessed':
            enquiries.update(is_processed=False)
            return Response({
                'success': True,
                'message': f'{len(enquiries)} enquiries marked as unprocessed'
            })

        elif action_type == 'delete':
            count = len(enquiries)
            enquiries.delete()
            return Response({
                'success': True,
                'message': f'{count} enquiries deleted'
            })

        return Response({
            'success': False,
            'message': 'Invalid action'
        }, status=status.HTTP_400_BAD_REQUEST)


# Helper views and functions
@login_required
@require_http_methods(["POST"])
def add_follow_up(request, enquiry_id):
    """Add follow-up to an enquiry"""
    enquiry = get_object_or_404(ApplicantEnquiry, id=enquiry_id, tenant=request.tenant)

    form = EnquiryFollowUpForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        follow_up = form.save(commit=False)
        follow_up.tenant = request.tenant
        follow_up.enquiry = enquiry
        follow_up.save()

        messages.success(request, 'Follow-up added successfully.')
    else:
        messages.error(request, 'Error adding follow-up. Please check the form.')

    return redirect('core:enquiry_detail', pk=enquiry_id)


@login_required
@require_http_methods(["POST"])
def add_stage_note(request, stage_log_id):
    """Add note to stage log"""
    stage_log = get_object_or_404(EnquiryStageLog, id=stage_log_id, tenant=request.tenant)

    form = EnquiryStageLogNoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.tenant = request.tenant
        note.stage_log = stage_log
        note.created_by = getattr(request.user, 'employee_profile', None)
        note.save()

        messages.success(request, 'Note added successfully.')
    else:
        messages.error(request, 'Error adding note. Please check the form.')

    return redirect('core:enquiry_detail', pk=stage_log.enquiry.pk)


@login_required
def export_enquiries(request):
    """Export enquiries to CSV"""
    tenant = request.tenant

    # Get filtered queryset
    queryset = ApplicantEnquiry.objects.filter(tenant=tenant).select_related(
        'course', 'academic_year', 'stage', 'counselor'
    )

    # Apply filters from GET parameters
    form = EnquiryFilterForm(request.GET, tenant=tenant)
    if form.is_valid():
        # Apply same filters as list view
        search = form.cleaned_data.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(enquiry_number__icontains=search)
            )

        stage = form.cleaned_data.get('stage')
        if stage:
            queryset = queryset.filter(stage=stage)

        course = form.cleaned_data.get('course')
        if course:
            queryset = queryset.filter(course=course)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="enquiries_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)

    # Write header
    writer.writerow([
        'Enquiry Number', 'First Name', 'Last Name', 'Email', 'Phone',
        'Course', 'Academic Year', 'Stage', 'Counselor', 'Enquired Date',
        'Is Processed', 'Source', 'Guardian Name', 'Guardian Phone'
    ])

    # Write data
    for enquiry in queryset:
        writer.writerow([
            enquiry.enquiry_number,
            enquiry.first_name,
            enquiry.last_name,
            enquiry.email or '',
            enquiry.phone or '',
            enquiry.course.name if enquiry.course else '',
            enquiry.academic_year.name if enquiry.academic_year else '',
            enquiry.stage.name if enquiry.stage else '',
            enquiry.counselor.full_name if enquiry.counselor else '',
            enquiry.enquired_date.strftime('%Y-%m-%d'),
            'Yes' if enquiry.is_processed else 'No',
            enquiry.source_of_info or '',
            enquiry.guardian_full_name or '',
            enquiry.guardian_phone or '',
        ])

    return response


class ApplicantEnquiryDeleteView(LoginRequiredMixin, DeleteView):
    """Delete enquiry view"""
    model = ApplicantEnquiry
    template_name = 'core/enquiry/confirm_delete.html'
    success_url = reverse_lazy('core:enquiry_list')

    def get_queryset(self):
        return ApplicantEnquiry.objects.filter(tenant=self.request.tenant)

    def delete(self, request, *args, **kwargs):
        enquiry = self.get_object()
        messages.success(request, f'Enquiry {enquiry.enquiry_number} deleted successfully.')
        return super().delete(request, *args, **kwargs)


@login_required
@require_http_methods(["POST"])
def enquiry_bulk_action(request):
    """Handle bulk actions on enquiries"""
    action = request.POST.get('action')
    enquiry_ids = request.POST.getlist('enquiry_ids')

    if not enquiry_ids:
        messages.error(request, 'No enquiries selected.')
        return redirect('core:enquiry_list')

    queryset = ApplicantEnquiry.objects.filter(
        tenant=request.tenant,
        id__in=enquiry_ids
    )

    if action == 'delete':
        count = queryset.count()
        queryset.delete()
        messages.success(request, f'{count} enquiries deleted successfully.')

    elif action == 'mark_processed':
        count = queryset.update(is_processed=True)
        messages.success(request, f'{count} enquiries marked as processed.')

    elif action == 'mark_unprocessed':
        count = queryset.update(is_processed=False)
        messages.success(request, f'{count} enquiries marked as unprocessed.')

    elif action == 'export':
        # Redirect to export with selected IDs
        ids_param = ','.join(enquiry_ids)
        return redirect(f"{reverse('core:enquiry_export')}?ids={ids_param}")

    else:
        messages.error(request, 'Invalid action selected.')

    return redirect('core:enquiry_list')