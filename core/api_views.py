"""
DRF API Views using services and serializers
Following TDD approach with comprehensive API endpoints
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Count, Q

from core.authz.drf import ModuleEnabled, HasPermission

from .models import (
    Student, User, Course, Batch, Subject, AdmissionApplication, BatchStudent,
    StudentDocument, DocumentCategory, StudentGuardianRelation, Term, Attendance
)
from .serializers import (
    # Student serializers
    StudentSerializer, StudentListSerializer, StudentDetailSerializer,
    StudentBulkCreateSerializer, StudentSearchSerializer,
    StudentDocumentSerializer, DocumentCategorySerializer,
    GuardianAttachSerializer, GuardianAttachResponseSerializer,
    FeeBalanceResponseSerializer, AttendanceSummaryResponseSerializer,
    
    # User serializers
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    UserProfileSerializer, PasswordChangeSerializer,
    
    # Academic serializers
    CourseSerializer, BatchSerializer, SubjectSerializer,
    BatchStudentSerializer, BatchListSerializer, AcademicReportSerializer,
    BatchTransferSerializer,
    
    # Admission serializers
    AdmissionApplicationSerializer, AdmissionApplicationListSerializer,
    AdmissionApprovalSerializer, AdmissionInterviewSerializer,
    AdmissionBulkApprovalSerializer, AdmissionReportSerializer,
    AdmissionSearchSerializer
)
from .services.exceptions import ServiceException, ValidationException, NotFoundException
from .services.finance_service import FinanceService
from .services.report_generation_service import ReportGenerationService
from .permissions import (
    TenantAccessPermission,
    CanManageAdmissions,
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination class for API views"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class TenantAwareViewSetMixin:
    """Mixin to provide tenant context to serializers"""
    
    def get_serializer_context(self):
        """Add tenant to serializer context"""
        context = super().get_serializer_context()
        context['tenant'] = getattr(self.request, 'tenant', None)
        context['user'] = self.request.user
        return context
    
    def handle_service_exception(self, exc):
        """Convert service exceptions to appropriate API responses"""
        if isinstance(exc, ValidationException):
            return Response(
                {'detail': str(exc), 'errors': getattr(exc, 'details', {})},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif isinstance(exc, NotFoundException):
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_404_NOT_FOUND
            )
        else:
            return Response(
                {'detail': 'An error occurred processing your request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===== STUDENT API VIEWS =====

class StudentViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet for student management operations
    Provides full CRUD operations for students
    """
    serializer_class = StudentSerializer
    # Superseded 2026-09-12: CanManageStudents (is_admin/is_teacher flags) replaced
    # by the RBAC capability system used across every other domain. is_root users
    # bypass this entirely (see core.authz.access._compute), so no separate
    # migration was needed for the platform's only existing admin account.
    permission_classes = [
        IsAuthenticated,
        TenantAccessPermission,
        ModuleEnabled,
        HasPermission(read="students.view", write="students.manage"),
    ]
    module = "academics"
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['gender', 'is_active', 'admission_date']
    search_fields = ['first_name', 'last_name', 'admission_no', 'middle_name']
    ordering_fields = ['first_name', 'last_name', 'admission_date', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get students filtered by tenant"""
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Student.objects.none()
        
        return Student.objects.filter(tenant=tenant).select_related(
            'nationality', 'student_category'
        ).prefetch_related(
            'student_batches__batch__course',
            'guardian_relations__guardian'
        )
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return StudentListSerializer
        elif self.action == 'retrieve':
            return StudentDetailSerializer
        elif self.action == 'bulk_create':
            return StudentBulkCreateSerializer
        return StudentSerializer
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create students"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
            
            return Response({
                'message': f'Successfully created {len(result)} students',
                'created_count': len(result),
                'students': StudentListSerializer(result, many=True, context=self.get_serializer_context()).data
            }, status=status.HTTP_201_CREATED)
            
        except ServiceException as e:
            return self.handle_service_exception(e)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search students with advanced options"""
        try:
            serializer = StudentSearchSerializer(data=request.query_params, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            results = serializer.search()
            
            page = self.paginate_queryset(results)
            if page is not None:
                student_serializer = StudentListSerializer(page, many=True, context=self.get_serializer_context())
                return self.get_paginated_response(student_serializer.data)
            
            student_serializer = StudentListSerializer(results, many=True, context=self.get_serializer_context())
            return Response(student_serializer.data)
            
        except ServiceException as e:
            return self.handle_service_exception(e)
    
    @action(detail=True, methods=['get'])
    def age(self, request, pk=None):
        """Get student's current age"""
        try:
            student = self.get_object()
            serializer = self.get_serializer(student)
            age = serializer.get_age(student)
            return Response({'age': age})
            
        except ServiceException as e:
            return self.handle_service_exception(e)
    
    @action(detail=False, methods=['post'])
    def bulk_actions(self, request):
        """Perform bulk actions on students"""
        try:
            student_ids = request.data.get('student_ids', [])
            action_type = request.data.get('action')
            
            if not student_ids or not action_type:
                return Response(
                    {'detail': 'student_ids and action are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # This would use a bulk action serializer if we had one
            # For now, we'll handle it directly
            tenant = getattr(request, 'tenant', None)
            from .services.student_service import StudentService
            service = StudentService(tenant)
            
            results = []
            for student_id in student_ids:
                try:
                    if action_type == 'activate':
                        student = service.reactivate_student(student_id)
                    elif action_type == 'deactivate':
                        student = service.deactivate_student(student_id)
                    else:
                        return Response(
                            {'detail': f'Unknown action: {action_type}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    results.append({
                        'id': str(student.id),
                        'success': True,
                        'name': f'{student.first_name} {student.last_name}'
                    })
                except ServiceException as e:
                    results.append({
                        'id': student_id,
                        'success': False,
                        'error': str(e)
                    })
            
            return Response({
                'results': results,
                'total_processed': len(student_ids),
                'successful': len([r for r in results if r['success']])
            })
            
        except ServiceException as e:
            return self.handle_service_exception(e)

    @action(detail=True, methods=['get'])
    def fee_balance(self, request, pk=None):
        """Get student fee balance"""
        try:
            student = self.get_object()
            tenant = getattr(request, 'tenant', None)
            finance_service = FinanceService(tenant)

            balance = finance_service.get_student_fee_balance(str(student.id))

            serializer = FeeBalanceResponseSerializer(
                data={
                    'student_id': str(student.id),
                    'balance': balance
                }
            )
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)

        except ServiceException as e:
            return self.handle_service_exception(e)

    @action(detail=True, methods=['get'])
    def attendance_summary(self, request, pk=None):
        """Get student attendance summary (optionally for a specific term)"""
        try:
            student = self.get_object()
            tenant = getattr(request, 'tenant', None)
            term_id = request.query_params.get('term_id')

            report_service = ReportGenerationService(tenant)

            # Resolve attendance range based on term
            if term_id:
                term = Term.objects.get(id=term_id, tenant=tenant)
                start_date = term.start_date
                end_date = term.end_date
            else:
                # Use current batch's term or date range
                active_batch = student.student_batches.filter(is_active=True).first()
                if active_batch:
                    start_date = active_batch.batch.start_date.date() if hasattr(active_batch.batch.start_date, 'date') else active_batch.batch.start_date
                    end_date = active_batch.batch.end_date.date() if hasattr(active_batch.batch.end_date, 'date') else active_batch.batch.end_date
                else:
                    return Response({'detail': 'No active batch found'}, status=status.HTTP_400_BAD_REQUEST)

            # Get attendance records
            records = Attendance.objects.filter(
                student=student,
                attendance_date__gte=start_date,
                attendance_date__lte=end_date,
                tenant=tenant
            ).order_by('attendance_date')

            # Compute summary
            summary = report_service._compute_attendance_summary(
                list(records),
                start_date,
                end_date,
                student.student_batches.filter(is_active=True).first().batch if student.student_batches.filter(is_active=True).exists() else None
            )

            # Get available terms for the student's current batch
            available_terms = []
            if active_batch:
                batch_year = active_batch.batch.academic_year
                terms = Term.objects.filter(academic_year=batch_year, tenant=tenant).order_by('start_date')
                available_terms = [
                    {
                        'id': str(t.id),
                        'name': t.name,
                        'start_date': t.start_date,
                        'end_date': t.end_date
                    }
                    for t in terms
                ]

            response_data = {
                'student_id': str(student.id),
                'total_days': summary.get('total_days', 0),
                'present_days': summary.get('days_present', 0),  # Remap from days_present
                'absent_days': summary.get('days_absent', 0),    # Remap from days_absent
                'attendance_percentage': summary.get('attendance_percentage', 0),
                'available_terms': available_terms,
                'current_term_id': str(term_id) if term_id else None
            }

            serializer = AttendanceSummaryResponseSerializer(response_data)
            return Response(serializer.data)

        except ServiceException as e:
            return self.handle_service_exception(e)

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """List student documents"""
        try:
            student = self.get_object()
            documents = StudentDocument.objects.filter(
                student=student,
                tenant=getattr(request, 'tenant', None)
            ).select_related('category').order_by('-uploaded_at')

            serializer = StudentDocumentSerializer(documents, many=True, context=self.get_serializer_context())
            return Response({
                'results': serializer.data,
                'count': len(serializer.data)
            })

        except ServiceException as e:
            return self.handle_service_exception(e)

    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        """Upload a new student document"""
        try:
            student = self.get_object()
            tenant = getattr(request, 'tenant', None)

            category_id = request.POST.get('category_id')
            file = request.FILES.get('file')
            note = request.POST.get('note', '')

            if not category_id or not file:
                return Response(
                    {'detail': 'category_id and file are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            category = DocumentCategory.objects.get(id=category_id, tenant=tenant)

            doc = StudentDocument.objects.create(
                student=student,
                category=category,
                file=file,
                original_filename=file.name,
                note=note,
                uploaded_by_id=request.user.id,
                tenant=tenant
            )

            serializer = StudentDocumentSerializer(doc, context=self.get_serializer_context())
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ServiceException as e:
            return self.handle_service_exception(e)

    @action(detail=True, methods=['delete'])
    def delete_document(self, request, pk=None):
        """Delete a student document"""
        try:
            student = self.get_object()
            tenant = getattr(request, 'tenant', None)
            doc_id = request.query_params.get('doc_id')

            if not doc_id:
                return Response(
                    {'detail': 'doc_id query parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            doc = StudentDocument.objects.get(id=doc_id, student=student, tenant=tenant)

            # Delete the file
            if doc.file:
                doc.file.delete()

            doc.delete()

            return Response({'message': 'Document deleted successfully'})

        except StudentDocument.DoesNotExist:
            return Response({'detail': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        except ServiceException as e:
            return self.handle_service_exception(e)

    @action(detail=True, methods=['get'])
    def guardians(self, request, pk=None):
        """List student guardians"""
        try:
            student = self.get_object()
            tenant = getattr(request, 'tenant', None)

            relations = StudentGuardianRelation.objects.filter(
                student=student,
                tenant=tenant
            ).select_related('guardian')

            guardian_data = [
                {
                    'id': str(r.guardian.id),
                    'name': f"{r.guardian.first_name} {r.guardian.last_name}",
                    'relation': r.relation,
                    'phone': r.guardian.phone1,
                    'email': r.guardian.email,
                    'is_immediate_contact': r.is_immediate_contact
                }
                for r in relations
            ]

            return Response({'results': guardian_data, 'count': len(guardian_data)})

        except ServiceException as e:
            return self.handle_service_exception(e)

    @action(detail=True, methods=['get'])
    def generate_report(self, request, pk=None):
        """Generate a student report (academic, attendance, fees, or profile)"""
        try:
            student = self.get_object()
            tenant = getattr(request, 'tenant', None)
            report_type = request.query_params.get('type', 'profile')

            if report_type not in ['academic', 'attendance', 'fees', 'profile']:
                return Response(
                    {'detail': f'Invalid report type. Must be one of: academic, attendance, fees, profile'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # TODO: Call appropriate report generation service method
            # This is a placeholder that returns success response

            return Response({
                'message': f'{report_type} report generated successfully',
                'report_type': report_type,
                'student_id': str(student.id)
            })

        except ServiceException as e:
            return self.handle_service_exception(e)


# ===== USER API VIEWS =====

class UserViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet for user management operations
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, TenantAccessPermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_admin']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering_fields = ['username', 'first_name', 'last_name', 'created_at']
    ordering = ['username']
    
    def get_queryset(self):
        """Get users filtered by tenant access"""
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return User.objects.none()

        # Annotate tenant count so the list serializer doesn't COUNT per user.
        return User.objects.filter(tenants=tenant).annotate(
            tenant_count_anno=Count('tenants', distinct=True)
        )
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer
    
    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """Change user password"""
        try:
            user = self.get_object()
            serializer = PasswordChangeSerializer(
                data=request.data,
                context={**self.get_serializer_context(), 'user': user}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            return Response({'message': 'Password changed successfully'})
            
        except ServiceException as e:
            return self.handle_service_exception(e)
    
    @action(detail=False, methods=['get', 'patch'])
    def profile(self, request):
        """Get or update current user's profile"""
        try:
            if request.method == 'GET':
                serializer = UserProfileSerializer(
                    request.user,
                    context=self.get_serializer_context()
                )
                return Response(serializer.data)
            
            elif request.method == 'PATCH':
                serializer = UserProfileSerializer(
                    request.user,
                    data=request.data,
                    partial=True,
                    context=self.get_serializer_context()
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(serializer.data)
                
        except ServiceException as e:
            return self.handle_service_exception(e)


# ===== ACADEMIC API VIEWS =====

class CourseViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet for course management operations
    """
    serializer_class = CourseSerializer
    permission_classes = [
        IsAuthenticated,
        TenantAccessPermission,
        ModuleEnabled,
        HasPermission(read="academics.courses.view", write="academics.courses.manage"),
    ]
    module = "academics"
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['course_name', 'code', 'section_name']
    ordering_fields = ['course_name', 'code', 'created_at']
    ordering = ['course_name']
    
    def get_queryset(self):
        """Get courses filtered by tenant"""
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Course.objects.none()

        # Annotate counts so the serializer reads them off the row instead of
        # firing a COUNT query per course.
        return Course.objects.filter(tenant=tenant, is_deleted=False).annotate(
            batch_count_anno=Count('batches', distinct=True),
            active_batch_count_anno=Count(
                'batches', filter=Q(batches__is_active=True), distinct=True
            ),
        )
    
    @action(detail=True, methods=['get'])
    def batches(self, request, pk=None):
        """Get batches for a course"""
        course = self.get_object()
        batches = course.batches.filter(tenant=course.tenant)
        serializer = BatchListSerializer(batches, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


class BatchViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet for batch management operations
    """
    serializer_class = BatchSerializer
    permission_classes = [
        IsAuthenticated,
        TenantAccessPermission,
        ModuleEnabled,
        HasPermission(read="academics.batches.view", write="academics.batches.manage"),
    ]
    module = "academics"
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'course']
    search_fields = ['name', 'course__course_name']
    ordering_fields = ['name', 'start_date', 'created_at']
    ordering = ['-start_date']
    
    def get_queryset(self):
        """Get batches filtered by tenant"""
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Batch.objects.none()

        # Annotate counts (distinct to avoid join multiplication) so list/detail
        # serializers don't fire a COUNT query per batch.
        return Batch.objects.filter(tenant=tenant).select_related('course').annotate(
            student_count_anno=Count('batch_students', distinct=True),
            active_student_count_anno=Count(
                'batch_students', filter=Q(batch_students__is_active=True), distinct=True
            ),
            subject_count_anno=Count('subjects', distinct=True),
        )
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return BatchListSerializer
        return BatchSerializer
    
    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        """Get students enrolled in a batch"""
        batch = self.get_object()
        batch_students = BatchStudent.objects.filter(
            batch=batch,
            tenant=batch.tenant,
            is_active=True
        ).select_related('student')
        
        serializer = BatchStudentSerializer(batch_students, many=True, context=self.get_serializer_context())
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def transfer_student(self, request):
        """Transfer student between batches"""
        try:
            serializer = BatchTransferSerializer(data=request.data, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
            
            return Response({
                'message': 'Student transferred successfully',
                'transfer': result
            })
            
        except ServiceException as e:
            return self.handle_service_exception(e)


class SubjectViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet for subject management operations
    """
    serializer_class = SubjectSerializer
    permission_classes = [
        IsAuthenticated,
        TenantAccessPermission,
        ModuleEnabled,
        HasPermission(read="academics.subjects.view", write="academics.subjects.manage"),
    ]
    module = "academics"
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['batch', 'no_exams']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Get subjects filtered by tenant"""
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Subject.objects.none()
        
        return Subject.objects.filter(tenant=tenant, is_deleted=False).select_related('batch__course')


# ===== ADMISSION API VIEWS =====

class AdmissionApplicationViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet for admission application management
    """
    serializer_class = AdmissionApplicationSerializer
    # CanManageAdmissions permits reads for any tenant user but restricts writes
    # (including approve/bulk-approval actions) to admins.
    permission_classes = [IsAuthenticated, TenantAccessPermission, CanManageAdmissions]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'gender', 'course_applied']
    search_fields = ['first_name', 'last_name', 'application_number', 'guardian_name']
    ordering_fields = ['application_date', 'first_name', 'last_name']
    ordering = ['-application_date']

    def get_queryset(self):
        """Get admission applications filtered by tenant"""
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return AdmissionApplication.objects.none()

        return AdmissionApplication.objects.filter(tenant=tenant).select_related('course_applied')
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return AdmissionApplicationListSerializer
        return AdmissionApplicationSerializer
    
    @action(detail=False, methods=['post'])
    def approve_application(self, request):
        """Approve an admission application"""
        try:
            serializer = AdmissionApprovalSerializer(data=request.data, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
            
            return Response({
                'message': 'Application processed successfully',
                'result': result
            })
            
        except ServiceException as e:
            return self.handle_service_exception(e)
    
    @action(detail=False, methods=['post'])
    def bulk_approval(self, request):
        """Bulk approve or reject applications"""
        try:
            serializer = AdmissionBulkApprovalSerializer(data=request.data, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            results = serializer.save()
            
            return Response({
                'message': 'Bulk operation completed',
                'results': results
            })
            
        except ServiceException as e:
            return self.handle_service_exception(e)
    
    @action(detail=False, methods=['post'])
    def schedule_interview(self, request):
        """Schedule interview for application"""
        try:
            serializer = AdmissionInterviewSerializer(data=request.data, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
            
            return Response({
                'message': 'Interview scheduled successfully',
                'interview': result
            })
            
        except ServiceException as e:
            return self.handle_service_exception(e)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search admission applications"""
        try:
            serializer = AdmissionSearchSerializer(data=request.query_params, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            results = serializer.search()
            
            page = self.paginate_queryset(results)
            if page is not None:
                app_serializer = AdmissionApplicationListSerializer(page, many=True, context=self.get_serializer_context())
                return self.get_paginated_response(app_serializer.data)
            
            app_serializer = AdmissionApplicationListSerializer(results, many=True, context=self.get_serializer_context())
            return Response(app_serializer.data)
            
        except ServiceException as e:
            return self.handle_service_exception(e)


# ===== REPORT API VIEWS =====

class AcademicReportsAPIView(TenantAwareViewSetMixin, generics.CreateAPIView):
    """
    API view for generating academic reports
    """
    serializer_class = AcademicReportSerializer
    permission_classes = [IsAuthenticated, TenantAccessPermission]
    
    def create(self, request, *args, **kwargs):
        """Generate academic report"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            report_data = serializer.generate_report()
            
            return Response(report_data)
            
        except ServiceException as e:
            return self.handle_service_exception(e)


class AdmissionReportsAPIView(TenantAwareViewSetMixin, generics.CreateAPIView):
    """
    API view for generating admission reports
    """
    serializer_class = AdmissionReportSerializer
    permission_classes = [IsAuthenticated, TenantAccessPermission]
    
    def create(self, request, *args, **kwargs):
        """Generate admission report"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            report_data = serializer.generate_report()
            
            return Response(report_data)
            
        except ServiceException as e:
            return self.handle_service_exception(e)


# ===== PUBLIC API VIEWS (No authentication required) =====

class PublicAdmissionApplicationCreateView(TenantAwareViewSetMixin, generics.CreateAPIView):
    """
    Public API view for creating admission applications
    No authentication required - for public admission forms
    """
    serializer_class = AdmissionApplicationSerializer
    permission_classes = []  # No authentication required
    
    def get_serializer_context(self):
        """Add tenant to serializer context"""
        context = super().get_serializer_context()
        context['tenant'] = getattr(self.request, 'tenant', None)
        return context


class PublicAdmissionStatusView(generics.RetrieveAPIView):
    """
    Public API view to check admission application status
    No authentication required
    """
    permission_classes = []  # No authentication required
    lookup_field = 'application_number'
    
    def get_object(self):
        """Get application by application number"""
        tenant = getattr(self.request, 'tenant', None)
        application_number = self.kwargs.get('application_number')
        
        if not tenant or not application_number:
            raise NotFoundException("Application not found")
        
        from .services.admission_service import AdmissionService
        service = AdmissionService(tenant)
        return service.get_application_by_number(application_number)
    
    def retrieve(self, request, *args, **kwargs):
        """Return application status information"""
        try:
            application = self.get_object()
            
            return Response({
                'application_number': application.application_number,
                'applicant_name': f"{application.first_name} {application.last_name}",
                'application_date': application.application_date,
                'status': application.status,
                'course_applied': application.course_applied.course_name if application.course_applied else None,
                'remarks': application.remarks or ''
            })
            
        except NotFoundException as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except ServiceException as e:
            return Response(
                {'detail': 'An error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )