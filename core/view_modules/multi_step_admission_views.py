"""
Multi-step admission form API views (8-step Django parity)
"""
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import date, datetime
import logging

from core.models import (
    ExtendedAdmissionApplication, AcademicYear, Course, Country, StudentCategory,
    AdmissionDocument, AdmissionTerms, AdditionalField
)
from core.serializers.multi_step_admission_serializers import (
    AdmissionStep1Serializer, AdmissionStep2Serializer, AdmissionStep3Serializer,
    AdmissionStep4Serializer, AdmissionStep5Serializer, AdmissionStep6Serializer,
    AdmissionStep8Serializer, AdmissionProgressSerializer, AdmissionTermsSerializer,
    AdditionalFieldLookupSerializer, ExtendedAdmissionApplicationSerializer,
    AdmissionApplicationDetailSerializer, AcademicYearSerializer, CourseSerializer,
    CountrySerializer, StudentCategorySerializer, AdmissionDocumentSerializer,
    BulkAdmissionStatusSerializer, AdmissionSubmissionSerializer
)
from core.api_views import TenantAwareViewSetMixin, StandardResultsSetPagination

logger = logging.getLogger(__name__)


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
    permission_classes = [IsAuthenticated]

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

    def get_serializer_class(self):
        """Use detail serializer for single-record retrieve"""
        if self.action == 'retrieve':
            return AdmissionApplicationDetailSerializer
        return self.serializer_class

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve admission application"""
        application = get_object_or_404(self.get_queryset(), pk=pk)

        with transaction.atomic():
            application.status = 'approved'
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
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
            application.reviewed_at = timezone.now()
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
                    application.reviewed_at = timezone.now()
                    application.save()

            return Response({
                'message': f'{len(applications)} applications updated successfully',
                'updated_count': len(applications)
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def admit(self, request, pk=None):
        """Admit application: create student, assign to batch, provision parent account"""
        from core.models import Student, Batch, BatchStudent
        from core.services.portal_account_service import PortalAccountService
        from django.utils import timezone
        from datetime import date as date_type
        import logging

        logger = logging.getLogger(__name__)
        application = get_object_or_404(self.get_queryset(), pk=pk)

        batch_id = request.data.get('batch_id')
        admission_number = (request.data.get('admission_number') or '').strip()
        admission_date_str = request.data.get('admission_date')
        remarks = request.data.get('remarks', '')

        if not batch_id:
            return Response(
                {'error': 'Batch is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not application.first_name or not application.last_name:
            return Response(
                {'error': 'Application missing student name'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not application.date_of_birth:
            return Response(
                {'error': 'Application missing date of birth'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            batch = Batch.objects.get(id=batch_id, tenant=request.tenant)
        except Batch.DoesNotExist:
            return Response(
                {'error': 'Batch not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Auto-generate admission number if not provided
        if not admission_number:
            batch_prefix = batch.name[:3].upper()
            year_suffix = str(timezone.now().year)[-2:]
            base_pattern = f"{batch_prefix}{year_suffix}"
            existing = set(
                Student.objects.filter(tenant=request.tenant, admission_no__startswith=base_pattern)
                .values_list('admission_no', flat=True)
            )
            next_num = 1
            while True:
                candidate = f"{base_pattern}{str(next_num).zfill(3)}"
                if candidate not in existing:
                    admission_number = candidate
                    break
                next_num += 1

        # Check uniqueness
        if Student.objects.filter(tenant=request.tenant, admission_no=admission_number).exists():
            return Response(
                {'error': f'Admission number "{admission_number}" already in use'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse admission date
        admission_date = timezone.now().date()
        if admission_date_str:
            try:
                admission_date = date_type.fromisoformat(admission_date_str)
            except ValueError:
                pass

        gender = application.gender if application.gender in ('male', 'female', 'other') else 'other'

        try:
            with transaction.atomic():
                from core.models import Guardian, StudentGuardianRelation

                student = Student.objects.create(
                    tenant=request.tenant,
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

                BatchStudent.objects.create(
                    tenant=request.tenant,
                    batch=batch,
                    student=student,
                    is_active=True,
                )

                # Create guardian2 directly (no portal account provisioning for legacy parity)
                if application.guardian2_first_name:
                    guardian2 = Guardian.objects.create(
                        tenant=request.tenant,
                        first_name=application.guardian2_first_name,
                        last_name=application.guardian2_last_name or '',
                        relation=application.guardian2_relation or 'guardian',
                        email=application.guardian2_email or None,
                        mobile_phone=application.guardian2_mobile or None,
                        occupation=getattr(application, 'guardian2_occupation', None),
                        is_active=True,
                    )
                    StudentGuardianRelation.objects.create(
                        tenant=request.tenant,
                        student=student,
                        guardian=guardian2,
                        relation=guardian2.relation,
                        is_immediate_contact=False,
                        school=request.tenant,
                    )

                application.status = 'admitted'
                application.admitted_student = student
                if remarks:
                    application.remarks = remarks
                application.save()
        except Exception as e:
            logger.error(f"Error admitting application {pk}: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Try to provision parent account (non-blocking failure)
        parent_account = {
            'status': 'skipped',
            'reason': 'No guardian details on application',
        }
        try:
            parent_account = PortalAccountService(request.tenant).provision_parent_account_from_application(
                application, student
            )
        except Exception as e:
            logger.error(f"Parent account provisioning failed for {pk}: {e}", exc_info=True)
            parent_account = {
                'status': 'skipped',
                'reason': 'Parent account creation failed',
            }

        serializer = self.get_serializer(application)
        return Response({
            'success': True,
            'message': f'Student admitted and assigned to {batch.name}',
            'student_id': str(student.id),
            'admission_number': student.admission_no,
            'parent_account': parent_account,
            'application': serializer.data
        })

    @action(detail=True, methods=['delete'])
    def delete(self, request, pk=None):
        """Delete an admission application"""
        application = get_object_or_404(self.get_queryset(), pk=pk)

        try:
            application.delete()
            return Response(
                {'success': True, 'message': 'Application deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate an admission application"""
        import uuid
        from datetime import datetime as datetime_type

        application = get_object_or_404(self.get_queryset(), pk=pk)

        try:
            new_application = ExtendedAdmissionApplication.objects.create(
                tenant=request.tenant,
                application_number=f"{application.application_number}-COPY-{uuid.uuid4().hex[:6].upper()}",
                status='draft',
                current_step=1,
                # Copy personal fields
                first_name=application.first_name,
                middle_name=application.middle_name,
                last_name=application.last_name,
                date_of_birth=application.date_of_birth,
                gender=application.gender,
                nationality=application.nationality,
                religion=application.religion,
                birth_place=application.birth_place,
                mother_tongue=application.mother_tongue,
                email=application.email,
                mobile=application.mobile,
                phone=application.phone,
                address=application.address,
                address_line1=application.address_line1,
                address_line2=application.address_line2,
                city=application.city,
                country=application.country,
                student_category=application.student_category,
                # Copy guardian fields
                guardian1_first_name=application.guardian1_first_name,
                guardian1_last_name=application.guardian1_last_name,
                guardian1_relation=application.guardian1_relation,
                guardian1_mobile=application.guardian1_mobile,
                guardian1_email=application.guardian1_email,
                guardian1_occupation=application.guardian1_occupation,
                guardian2_first_name=application.guardian2_first_name,
                guardian2_last_name=application.guardian2_last_name,
                guardian2_relation=application.guardian2_relation,
                guardian2_mobile=application.guardian2_mobile,
                guardian2_email=application.guardian2_email,
                guardian2_occupation=application.guardian2_occupation,
                # Copy academic fields
                academic_year=application.academic_year,
                course_applied=application.course_applied,
            )

            serializer = self.get_serializer(new_application)
            return Response(
                {'success': True, 'message': 'Application duplicated successfully', 'data': serializer.data},
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def generate_admission_number(self, request, pk=None):
        """Generate a new admission number for the application"""
        from django.utils import timezone
        from core.models import Batch, Student

        batch_id = request.query_params.get('batch_id')
        if not batch_id:
            return Response(
                {'error': 'batch_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            batch = Batch.objects.get(id=batch_id, tenant=request.tenant)
        except Batch.DoesNotExist:
            return Response(
                {'error': 'Batch not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        batch_prefix = batch.name[:3].upper()
        year_suffix = str(timezone.now().year)[-2:]
        base_pattern = f"{batch_prefix}{year_suffix}"
        existing = set(
            Student.objects.filter(tenant=request.tenant, admission_no__startswith=base_pattern)
            .values_list('admission_no', flat=True)
        )
        next_num = 1
        while True:
            candidate = f"{base_pattern}{str(next_num).zfill(3)}"
            if candidate not in existing:
                admission_number = candidate
                break
            next_num += 1

        return Response({
            'admission_number': admission_number,
            'batch_id': str(batch_id),
            'batch_name': batch.name
        })

    @action(detail=False, methods=['post'])
    def validate_admission_number(self, request):
        """Check if an admission number is unique"""
        from core.models import Student

        admission_number = (request.data.get('admission_number') or '').strip()
        if not admission_number:
            return Response(
                {'error': 'admission_number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        exists = Student.objects.filter(
            tenant=request.tenant,
            admission_no=admission_number
        ).exists()

        return Response({
            'admission_number': admission_number,
            'is_unique': not exists,
            'is_available': not exists
        })

    @action(detail=False, methods=['get'])
    def active_batches(self, request):
        """Get active batches for admission, optionally filtered by course"""
        from core.models import Batch

        course_id = request.query_params.get('course_id')
        batches = Batch.objects.filter(
            tenant=request.tenant,
            is_deleted=False,
            is_active=True
        )

        if course_id:
            batches = batches.filter(course__id=course_id)

        batches = batches.order_by('name')
        batch_data = [
            {
                'id': str(b.id),
                'name': b.name,
                'course_id': str(b.course.id) if b.course else None,
                'course_name': b.course.course_name if b.course else None,
            }
            for b in batches
        ]

        return Response({'results': batch_data})

    @action(detail=True, methods=['post'])
    def assign_batch(self, request, pk=None):
        """Assign a batch to an already-admitted student"""
        from core.models import Batch, BatchStudent, Student

        application = get_object_or_404(self.get_queryset(), pk=pk)

        if application.status != 'admitted':
            return Response(
                {'error': 'Application must be in admitted status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not application.admitted_student:
            return Response(
                {'error': 'No student record associated with this application'},
                status=status.HTTP_404_NOT_FOUND
            )

        batch_id = request.data.get('batch_id')
        roll_number = request.data.get('roll_number', '')
        remarks = request.data.get('remarks', '')

        if not batch_id:
            return Response(
                {'error': 'Batch is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            batch = Batch.objects.get(id=batch_id, tenant=request.tenant)
        except Batch.DoesNotExist:
            return Response(
                {'error': 'Batch not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            with transaction.atomic():
                # Check if student already has an active batch assignment
                existing = BatchStudent.objects.filter(
                    tenant=request.tenant,
                    student=application.admitted_student,
                    is_active=True
                ).first()

                if existing:
                    # Deactivate the old assignment
                    existing.is_active = False
                    existing.save()

                # Create new assignment
                batch_student = BatchStudent.objects.create(
                    tenant=request.tenant,
                    batch=batch,
                    student=application.admitted_student,
                    roll_number=roll_number if roll_number else None,
                    is_active=True
                )

                if remarks:
                    application.remarks = remarks
                    application.save()

            serializer = self.get_serializer(application)
            return Response({
                'success': True,
                'message': f'Assigned to {batch.name} successfully',
                'batch_student_id': str(batch_student.id),
                'application': serializer.data
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def export_pdf(self, request, pk=None):
        """Export application as PDF"""
        from django.http import HttpResponse
        from io import BytesIO

        application = get_object_or_404(self.get_queryset(), pk=pk)

        # For now, return a simple placeholder response
        # In production, integrate with a PDF library like reportlab or weasyprint
        try:
            # Try to import and use weasyprint if available
            try:
                from weasyprint import HTML, CSS
                from django.template.loader import render_to_string

                context = {'application': application}
                html_string = render_to_string('admissions/application_pdf.html', context)
                html = HTML(string=html_string)
                pdf_bytes = html.write_pdf()

                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="application_{application.application_number}.pdf"'
                return response
            except (ImportError, Exception):
                # Fallback: return JSON response indicating PDF export is not yet implemented
                return Response({
                    'message': 'PDF export requires additional dependencies',
                    'application_number': application.application_number,
                    'application_id': str(application.id),
                    'status': 'not_implemented'
                }, status=status.HTTP_501_NOT_IMPLEMENTED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )