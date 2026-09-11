"""
DRF API URL configuration following REST best practices.

Structure:
    /api/v1/                        — API root + bootstrap endpoint
    /api/v1/students/               — Students CRUD
    /api/v1/batches/                — Batches CRUD
    /api/v1/courses/                — Courses CRUD
    /api/v1/subjects/               — Subjects CRUD
    /api/v1/finance/invoices/       — Finance domain (when ported)
    /api/v1/hr/employees/           — HR domain (when ported)
    /api/v1/hostel/assignments/     — Hostel domain (when ported)
    /api/v1/schema/                 — OpenAPI schema (redoc, swagger, openapi.json)

Each domain module (students.py, finance.py, hr.py, etc.) contains:
- Serializers: request/response models
- ViewSets: CRUD + custom actions with permission checks
- DRF-spectacular decorators: API documentation

See core/api/students.py for the reference implementation pattern.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api.grading_api import (
    get_subject_grades,
    get_assessment_grades,
    get_batch_grading_scales,
    get_available_grading_scales,
)
from .api_views import (
    StudentViewSet,
    UserViewSet,
    CourseViewSet,
    BatchViewSet,
    SubjectViewSet,
    AdmissionApplicationViewSet,
    AcademicReportsAPIView,
    AdmissionReportsAPIView,
    PublicAdmissionApplicationCreateView,
    PublicAdmissionStatusView,
)

from .api.finance import (
    FeeCategoryViewSet,
    FeeDiscountViewSet,
    FineSlabViewSet,
    FinanceTransactionCategoryViewSet,
    FinanceTransactionViewSet,
    StudentFeeViewSet,
    InvoiceViewSet,
)

from .api.hr import (
    EmployeeViewSet,
    EmployeeQualificationViewSet,
    EmployeeDocumentViewSet,
    EmployeeContractViewSet,
    LeaveTypeViewSet,
    AttendanceViewSet,
    PerformanceReviewViewSet,
    TrainingRecordViewSet,
    EmployeeExitViewSet,
)

from .api.admissions import (
    AdmissionApplicationViewSet,
)

from .api.hostel import (
    HostelRoomViewSet,
    HostelFeeViewSet,
)

from .api.transport import (
    TransportRouteViewSet,
    TransportRouteStopViewSet,
    TransportStaffViewSet,
    TransportFeeViewSet,
)

from .api.library import (
    LibraryViewSet,
    LibraryStaffViewSet,
)

from .view_modules.multi_step_admission_views import (
    MultiStepAdmissionViewSet,
    AdmissionDocumentViewSet,
    AdmissionLookupViewSet,
    AdmissionAdminViewSet
)

# Create router for ViewSets
router = DefaultRouter()

# Register ViewSets with the router
router.register(r'students', StudentViewSet, basename='student')
router.register(r'users', UserViewSet, basename='user')
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'batches', BatchViewSet, basename='batch')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'admissions', AdmissionApplicationViewSet, basename='admission')

# Multi-step admission endpoints
router.register(r'admission-multistep', MultiStepAdmissionViewSet, basename='admission-multistep')
router.register(r'admission-documents', AdmissionDocumentViewSet, basename='admission-documents')
router.register(r'admission-lookups', AdmissionLookupViewSet, basename='admission-lookups')
router.register(r'admission-admin', AdmissionAdminViewSet, basename='admission-admin')

# Finance domain endpoints
router.register(r'fee-categories', FeeCategoryViewSet, basename='fee-category')
router.register(r'fee-discounts', FeeDiscountViewSet, basename='fee-discount')
router.register(r'fine-slabs', FineSlabViewSet, basename='fine-slab')
router.register(r'transaction-categories', FinanceTransactionCategoryViewSet, basename='transaction-category')
router.register(r'transactions', FinanceTransactionViewSet, basename='transaction')
router.register(r'student-fees', StudentFeeViewSet, basename='student-fee')
router.register(r'invoices', InvoiceViewSet, basename='invoice')

# HR domain endpoints
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'employee-qualifications', EmployeeQualificationViewSet, basename='employee-qualification')
router.register(r'employee-documents', EmployeeDocumentViewSet, basename='employee-document')
router.register(r'employee-contracts', EmployeeContractViewSet, basename='employee-contract')
router.register(r'leave-types', LeaveTypeViewSet, basename='leave-type')
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'performance-reviews', PerformanceReviewViewSet, basename='performance-review')
router.register(r'training-records', TrainingRecordViewSet, basename='training-record')
router.register(r'employee-exits', EmployeeExitViewSet, basename='employee-exit')

# Admissions domain endpoints
router.register(r'admission-applications', AdmissionApplicationViewSet, basename='admission-application')

# Hostel domain endpoints
router.register(r'hostel-rooms', HostelRoomViewSet, basename='hostel-room')
router.register(r'hostel-fees', HostelFeeViewSet, basename='hostel-fee')

# Transport domain endpoints
router.register(r'routes', TransportRouteViewSet, basename='route')
router.register(r'route-stops', TransportRouteStopViewSet, basename='route-stop')
router.register(r'transport-staff', TransportStaffViewSet, basename='transport-staff')
router.register(r'transport-fees', TransportFeeViewSet, basename='transport-fee')

# Library domain endpoints
router.register(r'libraries', LibraryViewSet, basename='library')
router.register(r'library-staff', LibraryStaffViewSet, basename='library-staff')

# Bootstrap endpoint — tenant configuration contract for frontend
from .api.bootstrap import bootstrap

# API URL patterns
urlpatterns = [
    # Include all ViewSet routes
    path('v1/', include(router.urls)),

    # Bootstrap endpoint — tenant config, user, capabilities, terminology, modules
    path('v1/bootstrap/', bootstrap, name='bootstrap'),

    # Report endpoints (non-ViewSet based)
    path('v1/reports/academic/', AcademicReportsAPIView.as_view(), name='academic-reports'),
    path('v1/reports/admission/', AdmissionReportsAPIView.as_view(), name='admission-reports'),
    
    # Public endpoints (no authentication required)
    path('public/admission/apply/', PublicAdmissionApplicationCreateView.as_view(), name='public-admission-apply'),
    path('public/admission/status/<str:application_number>/', PublicAdmissionStatusView.as_view(), name='public-admission-status'),

    # Grading API endpoints
    path('grading/subject/<uuid:subject_id>/grades/', get_subject_grades, name='subject-grades'),
    path('grading/assessment/<uuid:assessment_id>/<str:assessment_type>/grades/', get_assessment_grades, name='assessment-grades'),
    path('grading/batch/<uuid:batch_id>/scales/', get_batch_grading_scales, name='batch-grading-scales'),
    path('grading/scales/', get_available_grading_scales, name='available-grading-scales'),

    # DRF authentication endpoints
    path('auth/', include('rest_framework.urls')),
]

# Add API root view for better discoverability
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse

@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """
    API Root endpoint providing links to all available endpoints
    """
    return Response({
        'message': 'Welcome to School Management API',
        'version': 'v1',
        'endpoints': {
            'students': reverse('student-list', request=request, format=format),
            'users': reverse('user-list', request=request, format=format),
            'courses': reverse('course-list', request=request, format=format),
            'batches': reverse('batch-list', request=request, format=format),
            'subjects': reverse('subject-list', request=request, format=format),
            'admissions': reverse('admission-list', request=request, format=format),
            'admission_multistep': reverse('admission-multistep-list', request=request, format=format),
            'admission_documents': reverse('admission-documents-list', request=request, format=format),
            'admission_lookups': reverse('admission-lookups-academic-years', request=request, format=format),
            'admission_admin': reverse('admission-admin-list', request=request, format=format),
            'reports': {
                'academic': reverse('academic-reports', request=request, format=format),
                'admission': reverse('admission-reports', request=request, format=format),
            },
            'public': {
                'admission_apply': reverse('public-admission-apply', request=request, format=format),
                'admission_status': request.build_absolute_uri('/api/public/admission/status/{application_number}/'),
            },
            'documentation': reverse('schema-redoc', request=request, format=format) if reverse('schema-redoc', request=request, format=format) else '/api/v1/schema/redoc/',
        }
    })

# Insert API root at the beginning
urlpatterns.insert(0, path('', api_root, name='api-root'))