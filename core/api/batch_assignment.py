"""
Batch assignment and student conversion DRF API
"""
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, models
from django.shortcuts import get_object_or_404
from datetime import datetime
import random
import string
import logging

from core.models import (
    ExtendedAdmissionApplication, Batch, BatchStudent, Student,
    Country, StudentCategory, Guardian, StudentGuardianRelation
)
from core.serializers.batch_assignment_serializers import (
    BatchAssignmentApplicationSerializer,
    BatchSerializer,
    SingleAssignmentSerializer,
    BulkAssignmentSerializer,
    BatchStudentSerializer,
    AssignmentResultSerializer,
    BulkAssignmentResultSerializer,
    AdmissionStatsSerializer,
    DiagnosticsResultSerializer,
)
from core.api_views import TenantAwareViewSetMixin

logger = logging.getLogger(__name__)


class BatchAssignmentViewSet(TenantAwareViewSetMixin, viewsets.ViewSet):
    """
    ViewSet for batch assignment of approved/admitted applications
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get approved/admitted applications for the tenant"""
        return ExtendedAdmissionApplication.objects.filter(
            tenant=self.request.tenant,
            status__in=['approved', 'admitted']
        )

    @action(detail=False, methods=['get'])
    def applications(self, request):
        """
        List all approved/admitted applications
        """
        queryset = self.get_queryset()

        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Search by application number or name
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(application_number__icontains=search) |
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search)
            )

        # Pagination
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 25)

        try:
            page = int(page)
            page_size = int(page_size)
        except ValueError:
            page = 1
            page_size = 25

        start = (page - 1) * page_size
        end = start + page_size

        count = queryset.count()
        results = queryset[start:end]

        serializer = BatchAssignmentApplicationSerializer(results, many=True)
        return Response({
            'count': count,
            'page': page,
            'page_size': page_size,
            'results': serializer.data
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get admission statistics
        """
        queryset = ExtendedAdmissionApplication.objects.filter(tenant=request.tenant)

        stats = {
            'total_applications': queryset.count(),
            'approved_applications': queryset.filter(status='approved').count(),
            'admitted_applications': queryset.filter(status='admitted').count(),
            'rejected_applications': queryset.filter(status='rejected').count(),
            'pending_review': queryset.filter(status='under_review').count(),
            'students_admitted_total': Student.objects.filter(
                tenant=request.tenant,
                is_deleted=False
            ).count(),
            'batches_available': Batch.objects.filter(
                tenant=request.tenant,
                is_deleted=False,
                is_active=True
            ).count(),
        }

        serializer = AdmissionStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def batches(self, request):
        """
        Get available batches for assignment
        """
        batches = Batch.objects.filter(
            tenant=request.tenant,
            is_deleted=False,
            is_active=True
        ).order_by('name')

        serializer = BatchSerializer(batches, many=True)
        return Response({'results': serializer.data})

    @action(detail=False, methods=['post'])
    def assign_single(self, request):
        """
        Assign a single application to a batch
        """
        serializer = SingleAssignmentSerializer(
            data=request.data,
            context={'tenant': request.tenant}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                application = serializer.validated_data['application']
                batch = serializer.validated_data['batch']
                roll_number = serializer.validated_data.get('roll_number', '')

                # If application is already admitted, find existing student
                if application.status == 'admitted':
                    student = Student.objects.filter(
                        tenant=request.tenant,
                        first_name__iexact=application.first_name,
                        last_name__iexact=application.last_name,
                        date_of_birth=application.date_of_birth
                    ).first()

                    if not student:
                        return Response(
                            {'error': 'Student record not found for admitted application'},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    # Check if student already has a batch assignment
                    existing_assignment = BatchStudent.objects.filter(
                        tenant=request.tenant,
                        student=student,
                        is_active=True
                    ).first()

                    if existing_assignment:
                        return Response(
                            {'error': f'Student already assigned to {existing_assignment.batch.name}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    # Create new student for approved application
                    student = self._create_student_from_application(
                        application,
                        request.tenant
                    )
                    application.status = 'admitted'
                    application.admitted_student = student
                    application.save()

                batch_student = BatchStudent.objects.create(
                    tenant=request.tenant,
                    batch=batch,
                    student=student,
                    roll_number=roll_number if roll_number else None,
                    is_active=True
                )

                result = {
                    'success': True,
                    'message': f'Assigned {student.full_name} to {batch.name}',
                    'student_id': student.id,
                    'batch_student_id': batch_student.id,
                    'application_id': application.id
                }

                result_serializer = AssignmentResultSerializer(result)
                return Response(result_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error assigning single application: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def assign_bulk(self, request):
        """
        Assign multiple applications to batches
        """
        serializer = BulkAssignmentSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        try:
            with transaction.atomic():
                for assignment in serializer.validated_data['assignments']:
                    try:
                        application_id = assignment['application_id']
                        batch_id = assignment['batch_id']
                        roll_number = assignment.get('roll_number', '')

                        application = ExtendedAdmissionApplication.objects.get(
                            id=application_id,
                            tenant=request.tenant,
                            status__in=['approved', 'admitted']
                        )

                        batch = Batch.objects.get(
                            id=batch_id,
                            tenant=request.tenant,
                            is_deleted=False,
                            is_active=True
                        )

                        # Handle admitted applications
                        if application.status == 'admitted':
                            student = Student.objects.filter(
                                tenant=request.tenant,
                                first_name__iexact=application.first_name,
                                last_name__iexact=application.last_name,
                                date_of_birth=application.date_of_birth
                            ).first()

                            if not student:
                                results['failed'] += 1
                                results['errors'].append(
                                    f"Student not found for {application.application_number}"
                                )
                                continue

                            existing_assignment = BatchStudent.objects.filter(
                                tenant=request.tenant,
                                student=student,
                                is_active=True
                            ).first()

                            if existing_assignment:
                                results['failed'] += 1
                                results['errors'].append(
                                    f"{student.full_name} already in {existing_assignment.batch.name}"
                                )
                                continue
                        else:
                            # Create new student for approved application
                            student = self._create_student_from_application(
                                application,
                                request.tenant
                            )
                            application.status = 'admitted'
                            application.admitted_student = student
                            application.save()

                        BatchStudent.objects.create(
                            tenant=request.tenant,
                            batch=batch,
                            student=student,
                            roll_number=roll_number if roll_number else None,
                            is_active=True
                        )

                        results['successful'] += 1

                    except ExtendedAdmissionApplication.DoesNotExist:
                        results['failed'] += 1
                        results['errors'].append(f"Application {application_id} not found")
                    except Batch.DoesNotExist:
                        results['failed'] += 1
                        results['errors'].append(f"Batch {batch_id} not found or not active")
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(str(e))

        except Exception as e:
            logger.error(f"Error in bulk assignment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        result_serializer = BulkAssignmentResultSerializer(results)
        return Response(result_serializer.data, status=status.HTTP_200_OK)

    def _create_student_from_application(
        self,
        application: ExtendedAdmissionApplication,
        tenant
    ) -> Student:
        """
        Create a Student record from an ExtendedAdmissionApplication
        """
        admission_number = self._generate_admission_number(tenant)

        student = Student.objects.create(
            tenant=tenant,
            admission_number=admission_number,
            admission_date=application.application_date.date(),
            first_name=application.first_name,
            middle_name=application.middle_name or '',
            last_name=application.last_name,
            date_of_birth=application.date_of_birth,
            gender=application.gender or '',
            nationality=application.nationality or '',
            religion=application.religion or '',
            birth_place=application.birth_place or '',
            mother_tongue=application.mother_tongue or '',
            email=application.email or '',
            phone=application.phone or '',
            mobile=application.mobile or '',
            address=application.address or '',
            address_line1=application.address_line1 or '',
            address_line2=application.address_line2 or '',
            city=application.city or '',
            country=application.country,
            guardian1_first_name=application.guardian1_first_name or '',
            guardian1_last_name=application.guardian1_last_name or '',
            guardian1_relation=application.guardian1_relation or '',
            guardian1_occupation=application.guardian1_occupation or '',
            guardian1_office_address_line1=application.guardian1_office_address_line1 or '',
            guardian1_office_city=application.guardian1_office_city or '',
            guardian1_office_phone1=application.guardian1_office_phone1 or '',
            guardian1_mobile=application.guardian1_mobile or '',
            guardian1_email=application.guardian1_email or '',
            guardian2_first_name=application.guardian2_first_name or '',
            guardian2_last_name=application.guardian2_last_name or '',
            guardian2_relation=application.guardian2_relation or '',
            guardian2_occupation=application.guardian2_occupation or '',
            guardian2_office_address_line1=application.guardian2_office_address_line1 or '',
            guardian2_office_city=application.guardian2_office_city or '',
            guardian2_office_phone1=application.guardian2_office_phone1 or '',
            guardian2_mobile=application.guardian2_mobile or '',
            guardian2_email=application.guardian2_email or '',
            previous_school_name=application.previous_school_name or '',
            previous_school_address=application.previous_school_address or '',
            previous_school_phone=application.previous_school_phone or '',
            previous_school_email=application.previous_school_email or '',
            has_medical_problems=application.has_medical_problems or False,
            recent_hospitalization=application.recent_hospitalization or False,
            has_allergies=application.has_allergies or False,
            medical_details=application.medical_details or '',
            student_category=application.student_category,
            religious_observances=application.religious_observances or '',
            background_information=application.background_information or '',
            is_active=True,
            is_deleted=False,
            status='active'
        )

        logger.info(f"Created student {student.admission_number} from {application.application_number}")

        # Create Guardian records from application data
        self._create_guardians_from_application(student, application, tenant)

        return student

    def _create_guardians_from_application(self, student: Student, application: ExtendedAdmissionApplication, tenant) -> None:
        """
        Create Guardian records from application guardian data
        """
        # Guardian 1 (Primary/Immediate contact)
        if application.guardian1_first_name and application.guardian1_last_name:
            guardian1, _ = Guardian.objects.get_or_create(
                tenant=tenant,
                first_name=application.guardian1_first_name,
                last_name=application.guardian1_last_name,
                defaults={
                    'relation': application.guardian1_relation or 'Parent',
                    'email': application.guardian1_email or '',
                    'mobile_phone': application.guardian1_mobile or '',
                    'office_phone': application.guardian1_office_phone1 or '',
                    'office_address_line1': application.guardian1_office_address_line1 or '',
                    'office_address_line2': '',
                    'city': application.guardian1_office_city or '',
                    'occupation': application.guardian1_occupation or '',
                    'is_active': True,
                }
            )

            StudentGuardianRelation.objects.create(
                tenant=tenant,
                student=student,
                guardian=guardian1,
                relation=application.guardian1_relation or 'Parent',
                is_immediate_contact=True,
                school=student.school if hasattr(student, 'school') else tenant,
            )

        # Guardian 2 (Secondary/Optional)
        if application.guardian2_first_name and application.guardian2_last_name:
            guardian2, _ = Guardian.objects.get_or_create(
                tenant=tenant,
                first_name=application.guardian2_first_name,
                last_name=application.guardian2_last_name,
                defaults={
                    'relation': application.guardian2_relation or 'Guardian',
                    'email': application.guardian2_email or '',
                    'mobile_phone': application.guardian2_mobile or '',
                    'office_phone': application.guardian2_office_phone1 or '',
                    'office_address_line1': application.guardian2_office_address_line1 or '',
                    'office_address_line2': '',
                    'city': application.guardian2_office_city or '',
                    'occupation': application.guardian2_occupation or '',
                    'is_active': True,
                }
            )

            StudentGuardianRelation.objects.create(
                tenant=tenant,
                student=student,
                guardian=guardian2,
                relation=application.guardian2_relation or 'Guardian',
                is_immediate_contact=False,
                school=student.school if hasattr(student, 'school') else tenant,
            )

    def _generate_admission_number(self, tenant) -> str:
        """
        Generate a unique admission number
        """
        year = datetime.now().year

        while True:
            random_part = ''.join(random.choices(string.digits, k=4))
            admission_number = f"ADM-{year}-{random_part}"

            if not Student.objects.filter(
                tenant=tenant,
                admission_number=admission_number
            ).exists():
                return admission_number


    @action(detail=True, methods=['get'])
    def application_detail(self, request, pk=None):
        """
        Get a single application detail with assignment info
        """
        queryset = self.get_queryset()
        try:
            application = queryset.get(pk=pk)
        except ExtendedAdmissionApplication.DoesNotExist:
            return Response(
                {'error': 'Application not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BatchAssignmentApplicationSerializer(application)

        # Get available batches
        available_batches = Batch.objects.filter(
            tenant=request.tenant,
            is_deleted=False,
            is_active=True
        ).order_by('name')

        batch_data = [
            {
                'id': str(b.id),
                'name': b.name,
                'course_id': str(b.course.id) if b.course else None,
                'course_name': b.course.course_name if b.course else None,
            }
            for b in available_batches
        ]

        return Response({
            'application': serializer.data,
            'available_batches': batch_data
        })


class AdmissionReportViewSet(TenantAwareViewSetMixin, viewsets.ViewSet):
    """
    ViewSet for admission reports and analytics
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get admission report summary with stats, filters, and breakdowns
        """
        from django.db.models import Count, Q

        queryset = ExtendedAdmissionApplication.objects.filter(tenant=request.tenant)

        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        academic_year = request.query_params.get('academic_year')
        if academic_year:
            queryset = queryset.filter(academic_year__id=academic_year)

        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(application_date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(application_date__lte=date_to)

        total_count = queryset.count()
        approved_count = queryset.filter(status='approved').count()
        admitted_count = queryset.filter(status='admitted').count()
        rejected_count = queryset.filter(status='rejected').count()
        pending_count = queryset.filter(status__in=['draft', 'submitted', 'under_review']).count()

        # Approval rate
        eligible = queryset.exclude(status='draft').count()
        approval_rate = (approved_count + admitted_count) / eligible * 100 if eligible > 0 else 0

        # By status breakdown
        by_status = [
            {
                'status': 'submitted',
                'label': 'Submitted',
                'count': queryset.filter(status='submitted').count()
            },
            {
                'status': 'under_review',
                'label': 'Under Review',
                'count': queryset.filter(status='under_review').count()
            },
            {
                'status': 'approved',
                'label': 'Approved',
                'count': approved_count
            },
            {
                'status': 'admitted',
                'label': 'Admitted',
                'count': admitted_count
            },
            {
                'status': 'rejected',
                'label': 'Rejected',
                'count': rejected_count
            },
        ]

        # By course breakdown
        by_course_qs = queryset.values('course_applied__id', 'course_applied__course_name').annotate(count=Count('id')).order_by('course_applied__course_name')
        by_course = [
            {
                'course_id': str(item['course_applied__id']) if item['course_applied__id'] else None,
                'course_name': item['course_applied__course_name'] or 'Unknown',
                'count': item['count']
            }
            for item in by_course_qs
        ]

        return Response({
            'stat_strip': {
                'total': total_count,
                'approved': approved_count,
                'admitted': admitted_count,
                'rejected': rejected_count,
                'pending': pending_count,
            },
            'approval_rate': round(approval_rate, 2),
            'by_status': by_status,
            'by_course': by_course,
            'filtered_count': total_count
        })


class AdmissionDiagnosticsViewSet(TenantAwareViewSetMixin, viewsets.ViewSet):
    """
    ViewSet for admission system diagnostics
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Check admission system readiness
        """
        from core.view_modules.admission_diagnostics import check_admission_prerequisites

        try:
            tenant = request.tenant
            prereq_check = check_admission_prerequisites(tenant)

            result = {
                'school_code': tenant.code,
                'school_name': tenant.name,
                'ready_for_admissions': prereq_check['ready'],
                'missing_requirements': prereq_check['missing'],
                'warnings': prereq_check['warnings'],
                'data_counts': prereq_check['counts']
            }

            serializer = DiagnosticsResultSerializer(result)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error checking admission status: {str(e)}")
            return Response(
                {'error': str(e), 'ready_for_admissions': False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
