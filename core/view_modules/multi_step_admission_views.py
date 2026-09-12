"""
Multi-step admission form API views (8-step Django parity)
"""
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from datetime import date

from core.models import (
    ExtendedAdmissionApplication, AcademicYear, Course, Country, StudentCategory,
    AdmissionDocument, AdmissionTerms, AdditionalField
)
from core.serializers.multi_step_admission_serializers import (
    AdmissionStep1Serializer, AdmissionStep2Serializer, AdmissionStep3Serializer,
    AdmissionStep4Serializer, AdmissionStep5Serializer, AdmissionStep6Serializer,
    AdmissionStep8Serializer, AdmissionProgressSerializer, AdmissionTermsSerializer,
    AdditionalFieldLookupSerializer, ExtendedAdmissionApplicationSerializer,
    AcademicYearSerializer, CourseSerializer, CountrySerializer, StudentCategorySerializer,
    AdmissionDocumentSerializer, BulkAdmissionStatusSerializer, AdmissionSubmissionSerializer
)
from core.permissions import IsAdminUser
from core.api_views import TenantAwareViewSetMixin, StandardResultsSetPagination


class MultiStepAdmissionViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    Multi-step admission application viewset
    """
    queryset = ExtendedAdmissionApplication.objects.all()
    serializer_class = ExtendedAdmissionApplicationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by tenant"""
        return self.queryset.filter(tenant=self.request.tenant)
    
    @action(detail=False, methods=['post'])
    def start_application(self, request):
        """
        Start a new admission application
        """
        with transaction.atomic():
            # Generate application number
            tenant = request.tenant
            year = date.today().year
            count = ExtendedAdmissionApplication.objects.filter(
                tenant=tenant,
                application_date__year=year
            ).count() + 1
            
            application_number = f"{tenant.code}-{year}-{count:04d}"
            
            application = ExtendedAdmissionApplication.objects.create(
                tenant=tenant,
                application_number=application_number,
                current_step=1,
                status='draft'
            )
            
            serializer = self.get_serializer(application)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def _step_action(self, request, pk, step_num, serializer_class, prior_step_required=None):
        """Generic handler for all step actions (GET/POST)"""
        application = get_object_or_404(
            ExtendedAdmissionApplication.objects.filter(tenant=request.tenant),
            pk=pk
        )

        # Check if prior step is complete (if required)
        if prior_step_required and not getattr(application, f'is_step{prior_step_required}_complete'):
            return Response(
                {'error': f'Step {prior_step_required} must be completed first'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.method == 'GET':
            serializer = serializer_class(application, context={'request': request})
            return Response(serializer.data)

        elif request.method == 'POST':
            serializer = serializer_class(
                application,
                data=request.data,
                context={'request': request},
                partial=True
            )

            if serializer.is_valid():
                with transaction.atomic():
                    application = serializer.save()
                    is_step_complete = getattr(application, f'is_step{step_num}_complete')
                    if is_step_complete:
                        application.current_step = max(application.current_step, step_num + 1)
                        application.status = f'step{step_num}_completed'
                        application.save()

                    return Response(serializer.data, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def step1(self, request, pk=None):
        """Step 1: Terms and Conditions"""
        return self._step_action(request, pk, 1, AdmissionStep1Serializer)

    @action(detail=True, methods=['get', 'post'])
    def step2(self, request, pk=None):
        """Step 2: Academic Year & Course"""
        return self._step_action(request, pk, 2, AdmissionStep2Serializer, prior_step_required=1)

    @action(detail=True, methods=['get', 'post'])
    def step3(self, request, pk=None):
        """Step 3: Student Personal Details & Health"""
        return self._step_action(request, pk, 3, AdmissionStep3Serializer, prior_step_required=2)

    @action(detail=True, methods=['get', 'post'])
    def step4(self, request, pk=None):
        """Step 4: Guardian 1"""
        return self._step_action(request, pk, 4, AdmissionStep4Serializer, prior_step_required=3)

    @action(detail=True, methods=['get', 'post'])
    def step5(self, request, pk=None):
        """Step 5: Guardian 2 & Emergency Contact"""
        return self._step_action(request, pk, 5, AdmissionStep5Serializer, prior_step_required=4)

    @action(detail=True, methods=['get', 'post'])
    def step6(self, request, pk=None):
        """Step 6: Student Address, Previous School, Additional Information"""
        return self._step_action(request, pk, 6, AdmissionStep6Serializer, prior_step_required=5)

    @action(detail=True, methods=['get', 'post'])
    def step8(self, request, pk=None):
        """Step 8: Declaration & Submission"""
        return self._step_action(request, pk, 8, AdmissionStep8Serializer, prior_step_required=6)
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get admission application progress (all 8 steps)"""
        application = get_object_or_404(
            ExtendedAdmissionApplication.objects.filter(tenant=request.tenant),
            pk=pk
        )

        serializer = AdmissionProgressSerializer(application)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Submit completed admission application
        """
        application = get_object_or_404(
            ExtendedAdmissionApplication.objects.filter(tenant=request.tenant),
            pk=pk
        )
        
        serializer = AdmissionSubmissionSerializer(
            data=request.data,
            context={'application': application}
        )
        
        if serializer.is_valid():
            if not application.can_submit():
                return Response(
                    {'error': 'Application is not complete or cannot be submitted'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                application.status = 'submitted'
                application.current_step = 6
                application.save()
            
            response_serializer = self.get_serializer(application)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def my_applications(self, request):
        """
        Get current user's admission applications
        """
        # For now, return all applications for the tenant
        # In a real application, you'd filter by user
        applications = self.get_queryset()
        page = self.paginate_queryset(applications)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(applications, many=True)
        return Response(serializer.data)


class AdmissionDocumentViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    Document upload viewset for admission applications
    """
    queryset = AdmissionDocument.objects.all()
    serializer_class = AdmissionDocumentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by tenant and application"""
        queryset = self.queryset.filter(tenant=self.request.tenant)
        
        application_id = self.request.query_params.get('application_id')
        if application_id:
            queryset = queryset.filter(application__id=application_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create document with application and tenant context"""
        application_id = self.request.data.get('application_id')
        if not application_id:
            raise serializers.ValidationError({'application_id': 'This field is required'})
        
        try:
            application = ExtendedAdmissionApplication.objects.get(
                id=application_id,
                tenant=self.request.tenant
            )
        except ExtendedAdmissionApplication.DoesNotExist:
            raise serializers.ValidationError({'application_id': 'Invalid application ID'})
        
        serializer.save(
            tenant=self.request.tenant,
            application=application
        )
    
    @action(detail=False, methods=['get'])
    def required_documents(self, request):
        """
        Get list of required document types
        """
        required_docs = [
            {
                'type': doc_type,
                'display_name': display_name,
                'required': True
            }
            for doc_type, display_name in AdmissionDocument.DOCUMENT_TYPES
            if doc_type in ['immunization_record', 'birth_certificate', 'utility_bill', 'parent1_id', 'parent2_id']
        ]
        
        optional_docs = [
            {
                'type': doc_type,
                'display_name': display_name,
                'required': False
            }
            for doc_type, display_name in AdmissionDocument.DOCUMENT_TYPES
            if doc_type not in ['immunization_record', 'birth_certificate', 'utility_bill', 'parent1_id', 'parent2_id']
        ]
        
        return Response({
            'required': required_docs,
            'optional': optional_docs
        })


class AdmissionLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewsets for admission form dropdowns
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def academic_years(self, request):
        """Get active academic years"""
        academic_years = AcademicYear.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).order_by('-start_date')
        
        serializer = AcademicYearSerializer(academic_years, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def courses(self, request):
        """Get available courses"""
        courses = Course.objects.filter(
            tenant=request.tenant,
            is_deleted=False
        ).order_by('course_name')
        
        serializer = CourseSerializer(courses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def countries(self, request):
        """Get all countries"""
        countries = Country.objects.all().order_by('name')
        serializer = CountrySerializer(countries, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def student_categories(self, request):
        """Get student categories"""
        categories = StudentCategory.objects.filter(
            tenant=request.tenant,
            is_deleted=False
        ).order_by('name')

        serializer = StudentCategorySerializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def terms(self, request):
        """Get active admission terms and conditions (with fallback to default)"""
        terms = AdmissionTerms.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).order_by('order')

        serializer = AdmissionTermsSerializer(terms, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def additional_fields(self, request):
        """Get dynamic additional fields for admission applications"""
        fields = AdditionalField.objects.filter(
            tenant=request.tenant,
            applies_to='admission',
            is_active=True
        ).order_by('sort_order', 'name')

        serializer = AdditionalFieldLookupSerializer(fields, many=True)
        return Response(serializer.data)


class AdmissionAdminViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    Admin viewset for managing admission applications
    """
    queryset = ExtendedAdmissionApplication.objects.all()
    serializer_class = ExtendedAdmissionApplicationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        """Filter by tenant with admin filters"""
        queryset = self.queryset.filter(tenant=self.request.tenant)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by academic year
        academic_year = self.request.query_params.get('academic_year')
        if academic_year:
            queryset = queryset.filter(academic_year__id=academic_year)
        
        # Filter by course
        course = self.request.query_params.get('course')
        if course:
            queryset = queryset.filter(course_applied__id=course)
        
        return queryset.order_by('-application_date')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve admission application"""
        application = get_object_or_404(self.get_queryset(), pk=pk)
        
        with transaction.atomic():
            application.status = 'approved'
            application.reviewed_by = request.user
            application.reviewed_at = datetime.now()
            application.save()
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject admission application"""
        application = get_object_or_404(self.get_queryset(), pk=pk)
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response(
                {'error': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            application.status = 'rejected'
            application.remarks = reason
            application.reviewed_by = request.user
            application.reviewed_at = datetime.now()
            application.save()
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_status_update(self, request):
        """Bulk update application status"""
        serializer = BulkAdmissionStatusSerializer(data=request.data)
        
        if serializer.is_valid():
            application_ids = serializer.validated_data['application_ids']
            new_status = serializer.validated_data['status']
            reason = serializer.validated_data.get('reason', '')
            
            applications = self.get_queryset().filter(id__in=application_ids)
            
            with transaction.atomic():
                for application in applications:
                    application.status = new_status
                    if reason:
                        application.remarks = reason
                    application.reviewed_by = request.user
                    application.reviewed_at = datetime.now()
                    application.save()
            
            return Response({
                'message': f'{len(applications)} applications updated successfully',
                'updated_count': len(applications)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)