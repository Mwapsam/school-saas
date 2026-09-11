"""
Portal API views.

Thin controllers: resolve role/profile, delegate reads to ``selectors``,
delegate serialization to ``serializers``, and own only request/response shape
+ authorization + write transactions. Two fully-wired vertical slices are
implemented end-to-end (parent academic results, teacher attendance register);
dashboards aggregate the same selectors.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from decimal import Decimal, InvalidOperation

from django.utils import timezone

from core.models import (
    Attendance,
    Batch,
    Book,
    BookMovement,
    Course,
    Exam,
    ExamGroup,
    ExamScore,
    GradeValue,
    HomeworkAssessment,
    SkillAssessmentResult,
    SkillItem,
    SkillsAssessment,
    Student,
)
from rest_framework.permissions import AllowAny

from .models import MarkSubmission, SkillsSubmission
from . import selectors
from .permissions import (
    IsParent, IsPortalUser, IsTeacher, IsLibrarian, PortalFeatureRequired,
)
from .client_gate import check_client_app
from .serializers import (
    AttendanceSummarySerializer,
    BookCategorySerializer,
    BookMovementSerializer,
    BookSerializer,
    ChildSerializer,
    FamilyInvoiceSerializer,
    FirstTimePasswordChangeSerializer,
    LibrarySerializer,
    LibrarianDashboardSerializer,
    MarkableExamSerializer,
    MarkSheetEntrySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PortalTokenObtainSerializer,
    ProfileSerializer,
    ReceiptSummarySerializer,
    RegisterEntrySerializer,
    ResultGroupSerializer,
    SaveActivitiesSerializer,
    SaveAttendanceSerializer,
    SaveMarksSerializer,
    SaveSkillsSerializer,
    SkillCategorySerializer,
    StudentReportSerializer,
    TeacherBatchSerializer,
)
from core.services.user_service import UserService
from core.services.exceptions import NotFoundException, BusinessLogicException, ValidationException, DuplicateException
from core.services.activities_service import ActivitiesService
from core.services.calendar_service import SchoolCalendarService
from core.services.teacher_comment_service import (
    SkillsLockedException,
    TeacherCommentService,
)
from core.services.attendance_semantics import NOT_SCHOOL_DAY_MESSAGE, LOCKED_MESSAGE, NO_ACTIVE_TERM_MESSAGE

audit = logging.getLogger("portal.audit")


# ── Auth ─────────────────────────────────────────────────────────────────────

class PortalTokenObtainView(TokenObtainPairView):
    """POST username/password -> {access, refresh, role, user}."""

    serializer_class = PortalTokenObtainSerializer

    def post(self, request, *args, **kwargs):
        blocked = check_client_app(request)
        if blocked is not None:
            return blocked
        return super().post(request, *args, **kwargs)


class PortalTokenRefreshView(TokenRefreshView):
    """Stock refresh + the same X-Client-App gate as login, so disabling a
    client app also ends its existing sessions on their next refresh."""

    def post(self, request, *args, **kwargs):
        blocked = check_client_app(request)
        if blocked is not None:
            return blocked
        return super().post(request, *args, **kwargs)


class MeView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        tenant = request.tenant if hasattr(request, 'tenant') else None

        if not tenant:
            return Response(
                {"detail": "Could not determine tenant context."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_service = UserService(tenant)
        reset_url_template = request.build_absolute_uri('/portal/reset-password?token={token}')

        try:
            user_service.request_password_reset(email, reset_url_template)
            return Response(
                {"detail": "If an account with this email exists, a password reset link has been sent."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            audit.error(f"Password reset request failed: {str(e)}")
            return Response(
                {"detail": "If an account with this email exists, a password reset link has been sent."},
                status=status.HTTP_200_OK
            )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        tenant = request.tenant if hasattr(request, 'tenant') else None

        if not tenant:
            return Response(
                {"detail": "Could not determine tenant context."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_service = UserService(tenant)

        try:
            user = user_service.confirm_password_reset(token, new_password)
            audit.info(f"Password reset confirmed for user: {user.username}")
            return Response(
                {"detail": "Password has been reset successfully. You can now log in with your new password."},
                status=status.HTTP_200_OK
            )
        except NotFoundException as e:
            return Response(
                {"detail": str(e.message)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValidationException as e:
            return Response(
                {"detail": str(e.message)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            audit.error(f"Password reset confirmation failed: {str(e)}")
            return Response(
                {"detail": "An error occurred while resetting your password."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FirstTimePasswordChangeView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def post(self, request):
        serializer = FirstTimePasswordChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.password_change_required:
            return Response(
                {"detail": "Password change is not required for your account."},
                status=status.HTTP_400_BAD_REQUEST
            )

        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        if not request.user.check_password(current_password):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            request.user.set_password(new_password)
            request.user.password_change_required = False
            request.user.save(update_fields=['password', 'password_change_required'])
            audit.info(f"First-time password change completed for user: {request.user.username}")
            return Response(
                {"detail": "Password changed successfully. Please log in again with your new password."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            audit.error(f"First-time password change failed for user {request.user.username}: {str(e)}")
            return Response(
                {"detail": "An error occurred while changing your password."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChangePasswordView(APIView):
    """Authenticated user changing their password."""

    permission_classes = [IsAuthenticated, IsPortalUser]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        if not request.user.check_password(current_password):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            request.user.set_password(new_password)
            request.user.save(update_fields=['password'])
            audit.info(f"Password changed for user: {request.user.username}")
            return Response(
                {"detail": "Password changed successfully."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            audit.error(f"Password change failed for user {request.user.username}: {str(e)}")
            return Response(
                {"detail": "An error occurred while changing your password."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ── Parent slice ─────────────────────────────────────────────────────────────

class ChildrenView(APIView):
    permission_classes = [IsAuthenticated, IsParent]

    def get(self, request):
        guardian = request.role_context.profile
        children = selectors.children_for_guardian(guardian)
        context = {"guardian": guardian}
        return Response(ChildSerializer(children, many=True, context=context).data)


def _results_locked_response(student):
    """A student's exam results/report cards are withheld until their
    visible fee balance is settled - the response shape callers use to
    signal that, distinct from a plain 404/empty result set."""
    balance = selectors.outstanding_balance_for_student(student)
    return Response({
        "detail": "Results are locked until outstanding fees are settled.",
        "code": "fees_outstanding",
        "outstanding_balance": str(balance),
    }, status=status.HTTP_402_PAYMENT_REQUIRED)


class _ChildScopedView(APIView):
    """Shared 404/authorization for endpoints addressing a specific child."""

    permission_classes = [IsAuthenticated, IsParent, PortalFeatureRequired]
    required_feature: str | None = None

    def get_child(self, request, student_id) -> Student | None:
        guardian = request.role_context.profile
        if not selectors.guardian_owns_student(guardian, student_id):
            return None
        return Student.objects.filter(id=student_id).first()


class ChildResultsView(_ChildScopedView):
    required_feature = "results"

    def get(self, request, student_id):
        child = self.get_child(request, student_id)
        if child is None:
            return Response(
                {"detail": "Child not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if selectors.results_locked_for_student(child):
            return _results_locked_response(child)
        groups = selectors.results_for_student(child)
        return Response(ResultGroupSerializer(groups, many=True).data)


class ChildReportCardsView(_ChildScopedView):
    """List a child's generated PDF report cards (completed + published only)."""

    required_feature = "results"

    def get(self, request, student_id):
        child = self.get_child(request, student_id)
        if child is None:
            return Response(
                {"detail": "Child not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if selectors.results_locked_for_student(child):
            return _results_locked_response(child)
        reports = selectors.report_cards_for_student(child)
        return Response(StudentReportSerializer(reports, many=True).data)


class ChildReportCardPDFView(_ChildScopedView):
    """Stream the PDF of one of the guardian's child's report cards.

    Ownership is checked via the selector query itself (scoped to the
    guardian's own child, and to completed + published reports) - a parent
    can never fetch another family's report card by guessing an id.
    """

    required_feature = "results"

    def get(self, request, student_id, report_id):
        from django.core.files.storage import default_storage
        from django.http import FileResponse, Http404

        guardian = request.role_context.profile
        report = selectors.report_card_for_guardian(guardian, student_id, report_id)
        if report is None or not report.pdf_file_path:
            raise Http404("Report card not found.")

        if selectors.results_locked_for_student(report.student):
            return _results_locked_response(report.student)

        if not default_storage.exists(report.pdf_file_path):
            raise Http404("Report card file not found.")

        file_handle = default_storage.open(report.pdf_file_path)
        return FileResponse(
            file_handle, as_attachment=True,
            filename=f"{report.student.full_name}_Report.pdf",
        )


class ChildAttendanceView(_ChildScopedView):
    required_feature = "attendance"

    def get(self, request, student_id):
        child = self.get_child(request, student_id)
        if child is None:
            return Response(
                {"detail": "Child not found."}, status=status.HTTP_404_NOT_FOUND
            )
        start = parse_date(request.query_params.get("start", "")) or None
        end = parse_date(request.query_params.get("end", "")) or None
        summary = selectors.attendance_summary_for_student(child, start, end)
        return Response(AttendanceSummarySerializer(summary).data)


class ChildFeesView(_ChildScopedView):
    """Read-only fee statement for a child, scoped to an academic year.

    Payments are recorded manually by staff; the parent view is informational
    (charges, payments, discounts/fines, outstanding balance) reusing the same
    FeeReportingService that powers the staff statement.
    """

    required_feature = "fees"

    def get(self, request, student_id):
        child = self.get_child(request, student_id)
        if child is None:
            return Response({"detail": "Child not found."}, status=status.HTTP_404_NOT_FOUND)

        years = selectors.academic_years_for_student(child)
        selected = selectors.resolve_student_fee_year(
            child, request.query_params.get("academic_year")
        )
        statement = selectors.fee_statement_for_student(child, selected)
        return Response({
            "student": ChildSerializer(child).data,
            "academic_years": [{"id": str(ay.id), "name": ay.name} for ay in years],
            "selected_year": {"id": str(selected.id), "name": selected.name} if selected else None,
            "statement": statement,
        })


class ParentInvoicesView(APIView):
    """List the authenticated guardian's consolidated FamilyInvoice rows."""

    permission_classes = [IsAuthenticated, IsParent, PortalFeatureRequired]
    required_feature = "invoices"

    def get(self, request):
        guardian = request.role_context.profile
        invoices = selectors.family_invoices_for_guardian(guardian)
        return Response(FamilyInvoiceSerializer(invoices, many=True).data)


class ParentInvoicePDFView(APIView):
    """Stream a PDF of one of the guardian's own invoices.

    Ownership is checked via the selector query itself (scoped to
    ``guardian``) - a parent can never fetch another family's invoice by
    guessing an id.
    """

    permission_classes = [IsAuthenticated, IsParent, PortalFeatureRequired]
    required_feature = "invoices"

    def get(self, request, invoice_id):
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.services.invoice_service import build_invoice_pdf_context

        guardian = request.role_context.profile
        invoice = selectors.family_invoice_for_guardian(guardian, invoice_id)
        if invoice is None:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        html_content = render_to_string('core/finance/invoice_pdf.html', build_invoice_pdf_context(invoice))
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice_{invoice.invoice_number}.pdf"'
        return response


class ParentReceiptsView(APIView):
    """List the authenticated guardian's payment receipts, across all their
    children. Unlike invoices, receipts require no publish step - a payment
    shows up here the moment it's recorded."""

    permission_classes = [IsAuthenticated, IsParent, PortalFeatureRequired]
    required_feature = "fees"

    def get(self, request):
        guardian = request.role_context.profile
        receipts = selectors.receipts_for_guardian(guardian)
        return Response(ReceiptSummarySerializer(receipts, many=True).data)


class ParentReceiptPDFView(APIView):
    """Stream a PDF of one of the guardian's own payment receipts.

    Ownership is checked via the selector query itself (scoped to the
    guardian's children) - a parent can never fetch another family's
    receipt by guessing a reference number.
    """

    permission_classes = [IsAuthenticated, IsParent, PortalFeatureRequired]
    required_feature = "fees"

    def get(self, request, reference_number):
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.services.currency_service import CurrencyService
        from core.utils.number_to_words import amount_to_words

        guardian = request.role_context.profile
        receipt = selectors.receipt_for_guardian(guardian, reference_number)
        if receipt is None:
            return Response({"detail": "Receipt not found."}, status=status.HTTP_404_NOT_FOUND)

        html_content = render_to_string('core/fees/portal_receipt_pdf.html', {
            'school': guardian.tenant,
            'receipt': receipt,
            'amount_in_words': amount_to_words(receipt['amount']),
            'currency_symbol': CurrencyService(guardian.tenant).get_currency_symbol(),
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt_{reference_number}.pdf"'
        return response


class AnnouncementsView(APIView):
    """School announcements / newsletters visible to a parent."""
    permission_classes = [IsAuthenticated, IsParent, PortalFeatureRequired]
    required_feature = "announcements"

    def get(self, request):
        guardian = request.role_context.profile
        items = selectors.announcements_for_tenant(guardian.tenant)
        return Response([
            {
                "id": str(n.id),
                "title": n.title,
                "content": n.content,
                "author": n.author,
                "created_at": n.created_at,
                "document_url": n.document.url if n.document else None,
            }
            for n in items
        ])


class ParentDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsParent]

    def get(self, request):
        guardian = request.role_context.profile
        children = selectors.children_for_guardian(guardian)
        cards = []
        for child in children:
            summary = selectors.attendance_summary_for_student(child)
            balance = selectors.outstanding_balance_for_student(child)
            locked = selectors.results_locked_for_student(child)
            results = [] if locked else selectors.results_for_student(child)
            latest = results[-1] if results else None
            cards.append(
                {
                    "child": ChildSerializer(child).data,
                    "attendance": AttendanceSummarySerializer(summary).data,
                    "latest_result": ResultGroupSerializer(latest).data if latest else None,
                    "published_result_count": len(results),
                    "results_locked": locked,
                    "outstanding_balance": str(balance) if locked else None,
                }
            )
        return Response({"children": cards})


# ── Teacher slice ────────────────────────────────────────────────────────────

class TeacherClassesView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        employee = request.role_context.profile
        batches = selectors.batches_for_teacher(employee)
        return Response(TeacherBatchSerializer(batches, many=True, context={"request": request}).data)


class TeacherDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        employee = request.role_context.profile
        batches = selectors.batches_for_teacher(employee)
        today = timezone.localdate()
        total_students = 0
        marked_today = 0
        for batch in batches:
            roster = selectors.roster_for_batch(batch, employee=employee)
            total_students += len(roster)
            attendance = selectors.attendance_map_for_batch(batch, today)
            if attendance:
                marked_today += 1
        return Response(
            {
                "class_count": len(batches),
                "student_count": total_students,
                "classes_marked_today": marked_today,
                "classes": TeacherBatchSerializer(batches, many=True, context={"request": request}).data,
            }
        )


class AttendanceRegisterView(GenericAPIView):
    """
    GET  /teacher/classes/{batch_id}/register/?date=YYYY-MM-DD
         -> roster with each student's status for that day
    POST /teacher/classes/{batch_id}/register/
         -> save statuses (idempotent upsert per student/day)
    """

    permission_classes = [IsAuthenticated, IsTeacher]
    serializer_class = SaveAttendanceSerializer

    def _get_batch(self, request, batch_id) -> Batch | None:
        employee = request.role_context.profile
        batch = Batch.objects.filter(id=batch_id).first()
        if (
            batch is None
            or not selectors.is_class_teacher_for_batch(employee, batch)
            or not selectors.batch_in_active_academic_year(batch)
        ):
            return None
        return batch

    def get(self, request, batch_id):
        batch = self._get_batch(request, batch_id)
        if batch is None:
            return Response(
                {"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND
            )
        employee = request.role_context.profile
        day = parse_date(request.query_params.get("date", "")) or timezone.localdate()
        roster = selectors.roster_for_batch(batch, employee=employee)
        attendance = selectors.attendance_map_for_batch(batch, day)

        rows = []
        for membership_student in roster:
            sid = str(membership_student.id)
            record = attendance.get(sid)
            rows.append(
                {
                    "student_id": sid,
                    "full_name": membership_student.full_name,
                    "admission_no": membership_student.admission_no,
                    "roll_number": membership_student.class_roll_no,
                    "status": selectors.status_from_record(record),
                    "reason": record.reason if record else None,
                }
            )
        return Response(
            {
                "batch": {"id": str(batch.id), "name": batch.name},
                "date": day.isoformat(),
                "entries": RegisterEntrySerializer(rows, many=True).data,
            }
        )

    def post(self, request, batch_id):
        batch = self._get_batch(request, batch_id)
        if batch is None:
            return Response(
                {"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND
            )
        employee = request.role_context.profile
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        day = serializer.validated_data["date"]
        entries = serializer.validated_data["entries"]

        valid_student_ids = {str(s.id) for s in selectors.roster_for_batch(batch, employee=employee)}
        tenant = getattr(request, "tenant", None)

        calendar = SchoolCalendarService(tenant)
        if not calendar.is_school_day(day):
            return Response(
                {"detail": NOT_SCHOOL_DAY_MESSAGE.format(date=day.isoformat())},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if calendar.is_locked(day, allow_admin=False):
            return Response(
                {"detail": LOCKED_MESSAGE.format(date=day.isoformat())},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not calendar.is_within_active_term(batch.academic_year, day):
            return Response(
                {"detail": NO_ACTIVE_TERM_MESSAGE.format(date=day.isoformat())},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prior_by_student = {
            str(a.student_id): a
            for a in Attendance.objects.filter(
                tenant=tenant, batch=batch, month_date=day,
                student_id__in=[str(e["student_id"]) for e in entries],
            )
        }

        saved = 0
        written = []
        with transaction.atomic():
            for entry in entries:
                sid = str(entry["student_id"])
                if sid not in valid_student_ids:
                    return Response(
                        {"detail": f"Student {sid} is not in this class."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                fields = selectors.fields_for_status(
                    entry["status"], entry.get("reason")
                )
                Attendance.objects.update_or_create(
                    student_id=sid,
                    batch=batch,
                    month_date=day,
                    defaults={**fields, "tenant": tenant},
                )
                written.append({
                    "student_id": sid,
                    "forenoon": fields.get("forenoon"),
                    "afternoon": fields.get("afternoon"),
                })
                saved += 1

        from core.services.attendance_notifications import notify_newly_absent
        notify_newly_absent(tenant, batch, day, prior_by_student, written)

        audit.info(
            "attendance.save user=%s tenant=%s batch=%s date=%s entries=%d",
            request.user.id,
            getattr(tenant, "schema_name", "?"),
            batch.id,
            day.isoformat(),
            saved,
        )
        return Response({"saved": saved, "date": day.isoformat()})


class TeacherExamsView(APIView):
    """Exams the teacher may enter marks for, optionally filtered by ?batch=."""

    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        employee = request.role_context.profile
        exams = selectors.markable_exams_for_teacher(employee)
        batch_id = request.query_params.get("batch")
        if batch_id:
            batch = Batch.objects.filter(id=batch_id).first()
            if not batch:
                return Response(
                    {"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND
                )
            # Filter to exams in this batch only; scope already enforced by markable_exams_for_teacher
            exams = [e for e in exams if str(e.exam_group.batch_id) == batch_id]
        return Response(MarkableExamSerializer(exams, many=True, context={"employee": employee}).data)


class TeacherMarkSheetView(GenericAPIView):
    """
    GET  /teacher/exams/{exam_id}/marksheet/ -> roster + existing marks
    POST /teacher/exams/{exam_id}/marksheet/ -> save marks (upsert per student)

    Save logic mirrors the admin gradebook (``save_marks_api``): numeric marks
    are validated against the exam maximum; grade-only exams take a GradeValue.
    """

    permission_classes = [IsAuthenticated, IsTeacher]
    serializer_class = SaveMarksSerializer

    def _get_exam(self, request, exam_id) -> Exam | None:
        exam = (
            Exam.objects.select_related(
                "subject", "exam_group", "exam_group__batch"
            )
            .filter(id=exam_id)
            .first()
        )
        if exam is None:
            return None
        employee = request.role_context.profile
        if not selectors.teacher_can_mark_exam(employee, exam):
            return None
        if not selectors.batch_in_active_academic_year(exam.exam_group.batch):
            return None
        return exam

    def _exam_meta(self, exam, employee) -> dict:
        return {
            "id": str(exam.id),
            "subject": exam.subject.name if exam.subject_id else "—",
            "exam_name": exam.exam_name or exam.display_name or "Exam",
            "exam_group": exam.exam_group.name,
            "exam_group_id": str(exam.exam_group.id),
            "batch": {
                "id": str(exam.exam_group.batch_id),
                "name": exam.exam_group.batch.name,
            },
            "maximum_marks": float(exam.maximum_marks)
            if exam.maximum_marks is not None
            else None,
            "minimum_marks": float(exam.minimum_marks)
            if exam.minimum_marks is not None
            else None,
            "assessment_slot": exam.assessment_slot,
            "assessment_slot_display": exam.get_assessment_slot_display(),
            "is_grade_only": selectors.exam_is_grade_only(exam),
            "available_grades": selectors.available_grades_for_exam(exam),
            "result_published": exam.exam_group.result_published,
            "status": self._status_for(exam),
            "is_class_teacher": selectors.is_class_teacher_for_batch(employee, exam.exam_group.batch),
        }

    def _status_for(self, exam) -> str:
        if exam.exam_group.result_published:
            return "published"
        sub = MarkSubmission.objects.filter(exam=exam).first()
        return sub.status if sub else "draft"

    def get(self, request, exam_id):
        exam = self._get_exam(request, exam_id)
        if exam is None:
            return Response(
                {"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND
            )
        employee = request.role_context.profile
        return Response(
            {
                "exam": self._exam_meta(exam, employee),
                "entries": MarkSheetEntrySerializer(
                    selectors.marksheet_entries_for_exam(exam, employee=employee), many=True
                ).data,
            }
        )

    def post(self, request, exam_id):
        exam = self._get_exam(request, exam_id)
        if exam is None:
            return Response(
                {"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if exam.exam_group.result_published:
            return Response(
                {"detail": "Results for this exam have been published and are locked."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        employee = request.role_context.profile
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entries = serializer.validated_data["entries"]
        submit = serializer.validated_data.get("submit", False)

        valid_student_ids = {str(s.id) for s in selectors.roster_for_batch(exam.exam_group.batch, employee=employee)}
        is_grade_only = selectors.exam_is_grade_only(exam)
        tenant = getattr(request, "tenant", None)
        maximum = exam.maximum_marks or Decimal("0")

        saved = 0
        with transaction.atomic():
            for entry in entries:
                sid = str(entry["student_id"])
                if sid not in valid_student_ids:
                    return Response(
                        {"detail": f"Student {sid} is not in this class."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                is_absent = entry.get("is_absent", False)
                marks = None
                grade_value = None

                if not is_absent:
                    if is_grade_only:
                        grade_id = entry.get("grade_value_id")
                        if grade_id:
                            grade_value = GradeValue.objects.filter(id=grade_id).first()
                            if grade_value is None:
                                return Response(
                                    {"detail": f"Invalid grade for student {sid}."},
                                    status=status.HTTP_400_BAD_REQUEST,
                                )
                    else:
                        raw = entry.get("marks")
                        if raw is not None:
                            try:
                                marks = Decimal(str(raw))
                            except (InvalidOperation, ValueError):
                                return Response(
                                    {"detail": f"Invalid marks for student {sid}."},
                                    status=status.HTTP_400_BAD_REQUEST,
                                )
                            if marks < 0 or marks > maximum:
                                return Response(
                                    {
                                        "detail": (
                                            f"Marks for student {sid} must be between "
                                            f"0 and {maximum}."
                                        )
                                    },
                                    status=status.HTTP_400_BAD_REQUEST,
                                )

                ExamScore.objects.update_or_create(
                    exam=exam,
                    student_id=sid,
                    defaults={
                        "tenant": tenant,
                        "marks": marks,
                        "grade_value": grade_value,
                        "is_absent": is_absent,
                        "remarks": (entry.get("remarks") or "") or None,
                    },
                )
                saved += 1

            # Record the draft/submitted lifecycle. Re-saving a submitted sheet as
            # a draft reopens it (clears the submission stamp).
            new_status = (
                MarkSubmission.STATUS_SUBMITTED if submit else MarkSubmission.STATUS_DRAFT
            )
            MarkSubmission.objects.update_or_create(
                exam=exam,
                defaults={
                    "tenant": tenant,
                    "status": new_status,
                    "submitted_by": request.user if submit else None,
                    "submitted_at": timezone.now() if submit else None,
                },
            )

        audit.info(
            "marks.%s user=%s tenant=%s exam=%s entries=%d",
            "submit" if submit else "draft",
            request.user.id,
            getattr(tenant, "schema_name", "?"),
            exam.id,
            saved,
        )
        return Response({"saved": saved, "status": new_status})


# ── Skills assessment (Beginners / Reception report layout) ──────────────────

class TeacherSkillsCatalogView(APIView):
    """The skill checklist catalogue + the teacher's roster for a class, used to
    render the skills entry grid. GET ?batch=<id>."""

    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        employee = request.role_context.profile
        batch_id = request.query_params.get("batch")
        batch = None
        if batch_id:
            batch = Batch.objects.filter(id=batch_id).first()
            if (
                batch is None
                or not selectors.is_class_teacher_for_batch(employee, batch)
                or not selectors.skills_assessment_enabled_for_batch(batch)
                or not selectors.batch_in_active_academic_year(batch)
            ):
                return Response(
                    {"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND
                )

        students = selectors.roster_for_batch(batch, employee=employee) if batch else []
        year = selectors.active_academic_year()
        active_term_name = selectors.skills_exam_group_term(batch) if batch else None
        submission = None
        if batch is not None:
            term_obj = selectors.resolve_term(active_term_name, batch=batch)
            submission = SkillsSubmission.objects.filter(
                batch=batch, term=term_obj
            ).first()
        return Response(
            {
                "categories": SkillCategorySerializer(
                    selectors.skill_catalog(batch), many=True
                ).data,
                "terms": selectors.term_names(batch),
                "active_term": active_term_name,
                "academic_year": year.name if year else None,
                "status": submission.status if submission else SkillsSubmission.STATUS_DRAFT,
                "submitted_at": submission.submitted_at if submission else None,
                "students": [
                    {
                        "id": str(s.id),
                        "full_name": s.full_name,
                        "admission_no": s.admission_no,
                    }
                    for s in students
                ],
            }
        )


class TeacherStudentSkillsView(GenericAPIView):
    """
    GET  /teacher/skills/students/{student_id}/?term= -> existing levels
    POST /teacher/skills/students/{student_id}/        -> save levels
    """

    permission_classes = [IsAuthenticated, IsTeacher]
    serializer_class = SaveSkillsSerializer

    def _get_student(self, request, student_id) -> Student | None:
        employee = request.role_context.profile
        if not selectors.teacher_owns_student(employee, student_id):
            return None
        student = Student.objects.filter(id=student_id).first()
        if student is None:
            return None
        batch = selectors.current_batch_for_student(student)
        if (
            batch is None
            or not selectors.skills_assessment_enabled_for_batch(batch)
            or not selectors.batch_in_active_academic_year(batch)
        ):
            return None
        return student

    def get(self, request, student_id):
        student = self._get_student(request, student_id)
        if student is None:
            return Response(
                {"detail": "Student not found."}, status=status.HTTP_404_NOT_FOUND
            )
        year = selectors.active_academic_year()
        batch = selectors.current_batch_for_student(student)
        term_obj = selectors.resolve_term(
            request.query_params.get("term"), batch=batch
        )
        levels = (
            selectors.skills_levels_for_student(student, year, term_obj)
            if year
            else {}
        )
        return Response({"levels": levels})

    def post(self, request, student_id):
        tenant = getattr(request, "tenant", None)
        student = self._get_student(request, student_id)
        if student is None:
            audit.warning(
                "skills.save.denied user=%s tenant=%s student=%s reason=student_not_found_or_not_owned",
                request.user.id,
                getattr(tenant, "schema_name", "?"),
                student_id,
            )
            return Response(
                {"detail": "Student not found."}, status=status.HTTP_404_NOT_FOUND
            )
        year = selectors.active_academic_year()
        if year is None:
            audit.warning(
                "skills.save.rejected user=%s tenant=%s student=%s reason=no_active_academic_year",
                request.user.id,
                getattr(tenant, "schema_name", "?"),
                student.id,
            )
            return Response(
                {"detail": "No active academic year is configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = selectors.current_batch_for_student(student)
        term_obj = selectors.resolve_term(
            serializer.validated_data.get("term"), batch=batch
        )
        if SkillsSubmission.objects.filter(
            batch=batch, term=term_obj, status=SkillsSubmission.STATUS_SUBMITTED
        ).exists():
            audit.warning(
                "skills.save.rejected user=%s tenant=%s student=%s batch=%s term=%s reason=results_locked",
                request.user.id,
                getattr(tenant, "schema_name", "?"),
                student.id,
                getattr(batch, "id", None),
                term_obj.name if term_obj else "-",
            )
            return Response(
                {"detail": "Skills results have been submitted and are locked."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        levels = serializer.validated_data["levels"]

        valid_item_ids = set(
            str(i)
            for i in SkillItem.objects.filter(is_active=True).values_list(
                "id", flat=True
            )
        )
        today = timezone.localdate()

        try:
            saved = 0
            with transaction.atomic():
                assessment, _ = SkillsAssessment.objects.update_or_create(
                    student=student,
                    academic_year=year,
                    term=term_obj,
                    defaults={
                        "tenant": tenant,
                        "assessment_date": today,
                        "assessor": request.user,
                    },
                )
                for item_id, level in levels.items():
                    if str(item_id) not in valid_item_ids:
                        audit.warning(
                            "skills.save.rejected user=%s tenant=%s student=%s reason=unknown_skill_item item=%s",
                            request.user.id,
                            getattr(tenant, "schema_name", "?"),
                            student.id,
                            item_id,
                        )
                        return Response(
                            {"detail": f"Unknown skill {item_id}."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    SkillAssessmentResult.objects.update_or_create(
                        assessment=assessment,
                        skill_item_id=item_id,
                        defaults={
                            "tenant": tenant,
                            "level": level,
                            "assessment_date": today,
                        },
                    )
                    saved += 1
        except Exception:
            audit.exception(
                "skills.save.failed user=%s tenant=%s student=%s batch=%s term=%s",
                request.user.id,
                getattr(tenant, "schema_name", "?"),
                student.id,
                getattr(batch, "id", None),
                term_obj.name if term_obj else "-",
            )
            raise

        audit.info(
            "skills.save user=%s tenant=%s student=%s term=%s skills=%d",
            request.user.id,
            getattr(tenant, "schema_name", "?"),
            student.id,
            term_obj.name if term_obj else "-",
            saved,
        )
        return Response({"saved": saved})


# ── Term activities (Homework / Project / Clubs / Sports / Other) ────────────

def _resolve_term_label(exam_group) -> str:
    """Canonical term label, identical to what the report generator uses, so
    portal entry and report lookups always agree."""
    from core.services.report_generation_service import ReportGenerationService

    return ReportGenerationService.resolve_exam_group_term(exam_group)


class TeacherActivitiesView(GenericAPIView):
    """
    GET  /teacher/classes/{batch_id}/activities/?exam_group=<id>
         -> activated exam groups for the class, and (if one is chosen) each
            pupil's homework/project ratings + clubs/sports/other.
    POST /teacher/classes/{batch_id}/activities/
         -> save those, keyed to the exam group's term (mirrors the admin).
    """

    permission_classes = [IsAuthenticated, IsTeacher]
    serializer_class = SaveActivitiesSerializer

    def _get_batch(self, request, batch_id) -> Batch | None:
        employee = request.role_context.profile
        if not selectors.teacher_teaches_batch(employee, batch_id):
            return None
        return Batch.objects.filter(id=batch_id).first()

    def _exam_group_options(self, batch, employee):
        """Only show exam groups where teacher has exams to mark."""
        exam_groups = ExamGroup.objects.filter(
            batch=batch, is_published=True
        ).order_by("-exam_date")

        # Filter to only groups where this teacher has exams
        accessible_groups = []
        for group in exam_groups:
            has_exams = Exam.objects.filter(
                exam_group=group,
                exam_group__is_published=True
            ).filter(
                Q(subject__employee=employee) | Q(exam_group__batch=batch)
            ).exists()

            if has_exams:
                # For subject teachers, check if they actually teach any subject in this group
                subject_ids = Exam.objects.filter(exam_group=group).values_list('subject_id', flat=True)
                is_class_teacher = selectors.is_class_teacher_for_batch(employee, batch)
                if is_class_teacher or Subject.objects.filter(id__in=subject_ids, employee=employee).exists():
                    accessible_groups.append(group)

        return [
            {"id": str(g.id), "name": g.name, "term": _resolve_term_label(g)}
            for g in accessible_groups
        ]

    def get(self, request, batch_id):
        employee = request.role_context.profile
        batch = self._get_batch(request, batch_id)
        if batch is None:
            return Response(
                {"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND
            )

        groups = self._exam_group_options(batch, employee)
        tenant = getattr(request, "tenant", None)
        payload = {
            "exam_groups": groups,
            "grades": [g[0] for g in HomeworkAssessment.ASSESSMENT_GRADES],
            "activity_options": ActivitiesService.activity_options(tenant),
            "homework_enabled": ActivitiesService.homework_enabled(batch),
            "activities_enabled": ActivitiesService.activities_enabled(batch),
        }

        eg_id = request.query_params.get("exam_group")
        if eg_id:
            exam_group = ExamGroup.objects.filter(
                id=eg_id, batch=batch, is_published=True
            ).first()
            if exam_group is None:
                return Response(
                    {"detail": "Exam group not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            term = _resolve_term_label(exam_group)
            ay = batch.academic_year
            students = selectors.roster_for_batch(batch, employee=employee)

            rows = ActivitiesService.roster_rows(batch, term, ay, students=students)
            payload.update(
                {"term": term, "academic_year": ay.name if ay else None, "students": rows}
            )

        return Response(payload)

    def post(self, request, batch_id):
        employee = request.role_context.profile
        batch = self._get_batch(request, batch_id)
        if batch is None:
            return Response(
                {"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        exam_group = ExamGroup.objects.filter(
            id=data["exam_group"], batch=batch, is_published=True
        ).first()
        if exam_group is None:
            return Response(
                {"detail": "Exam group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Verify teacher has access to this exam group
        accessible_groups = [g["id"] for g in self._exam_group_options(batch, employee)]
        if str(exam_group.id) not in accessible_groups:
            return Response(
                {"detail": "You do not have access to this exam group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        term = _resolve_term_label(exam_group)
        ay = batch.academic_year
        tenant = getattr(request, "tenant", None)
        valid_student_ids = {str(s.id) for s in selectors.roster_for_batch(batch, employee=employee)}

        rows_payload = [
            {**row, "id": row["student_id"]}
            for row in data["students"]
            if str(row["student_id"]) in valid_student_ids
        ]
        saved = ActivitiesService.save_roster_rows(batch, term, ay, rows_payload)

        has_ratings = any(('homework' in row) or ('project' in row) for row in rows_payload)
        has_activities = any(('clubs' in row) or ('sports' in row) or ('other' in row) for row in rows_payload)
        ActivitiesService.mark_saved(batch, exam_group, ratings=has_ratings, activities=has_activities)

        audit.info(
            "activities.save user=%s tenant=%s batch=%s term=%s students=%d",
            request.user.id,
            getattr(tenant, "schema_name", "?"),
            batch.id,
            term,
            saved,
        )
        return Response({"saved": saved, "term": term})


# ── Skills teacher comments (pre-grade report cards) ─────────────────────────

class SkillsTeacherCommentsView(APIView):
    """
    GET  /teacher/classes/{batch_id}/skills-comments/?term= -> saved comments + signature
    POST /teacher/classes/{batch_id}/skills-comments/?term= -> upsert comments + signature
    """

    permission_classes = [IsAuthenticated, IsTeacher]

    def _get_batch(self, request, batch_id):
        employee = request.role_context.profile
        batch = Batch.objects.filter(id=batch_id).first()
        if (
            batch is None
            or not selectors.is_class_teacher_for_batch(employee, batch)
            or not selectors.batch_in_active_academic_year(batch)
        ):
            return None
        return batch

    def get(self, request, batch_id):
        batch = self._get_batch(request, batch_id)
        if batch is None:
            return Response({"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND)

        employee = request.role_context.profile
        tenant = getattr(request, "tenant", None)
        svc = TeacherCommentService(tenant=tenant)
        # Always the skills route: the wizard has no exam group, so its data
        # must live on the batch+term key regardless of template state.
        route = svc.skills_route(batch, request.query_params.get("term"))

        # Get student IDs assigned to this teacher
        from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
        assignment_svc = ClassTeacherAssignmentService(tenant)
        assigned_ids = assignment_svc.assigned_student_ids(batch, employee)

        data = svc.get_comments(route, student_ids=list(assigned_ids))

        return Response({
            "batch_id": str(batch.id),
            "term": route.term.name if route.term else None,
            "signature_image": data["signature_image"],
            "comments": data["comments"],
        })

    def post(self, request, batch_id):
        batch = self._get_batch(request, batch_id)
        if batch is None:
            return Response({"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND)

        employee = request.role_context.profile
        tenant = getattr(request, "tenant", None)
        term_name = request.data.get("term") or request.query_params.get("term")
        comments = request.data.get("comments", [])
        signature = request.data.get("signature_image", "")

        # Get student IDs assigned to this teacher
        from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
        assignment_svc = ClassTeacherAssignmentService(tenant)
        valid_student_ids = assignment_svc.assigned_student_ids(batch, employee)

        svc = TeacherCommentService(tenant=tenant)
        route = svc.skills_route(batch, term_name)

        # Check if skills are locked for this teacher
        try:
            if svc.is_skills_locked(batch, route.term, employee=employee):
                return Response(
                    {"detail": "Skills results have been submitted and are locked."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            saved = svc.save_comments(
                route,
                comments,
                signature,
                enforce_skills_lock=False,  # We check above with employee scope
                valid_student_ids=valid_student_ids,
                acting_teacher=employee,
            )
        except SkillsLockedException as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"saved": saved})


class SkillsSubmissionView(APIView):
    """POST /teacher/classes/{batch_id}/skills-submission/ -> lock the class's
    skill ratings + comments for a term. Whole-class action: once submitted,
    both ``TeacherStudentSkillsView`` and ``SkillsTeacherCommentsView`` reject
    further writes for that batch/term."""

    permission_classes = [IsAuthenticated, IsTeacher]

    def _get_batch(self, request, batch_id):
        employee = request.role_context.profile
        batch = Batch.objects.filter(id=batch_id).first()
        if (
            batch is None
            or not selectors.is_class_teacher_for_batch(employee, batch)
            or not selectors.batch_in_active_academic_year(batch)
        ):
            return None
        return batch

    def post(self, request, batch_id):
        batch = self._get_batch(request, batch_id)
        if batch is None:
            return Response({"detail": "Class not found."}, status=status.HTTP_404_NOT_FOUND)

        employee = request.role_context.profile
        tenant = getattr(request, "tenant", None)
        term_obj = selectors.resolve_term(request.data.get("term"), batch=batch)

        existing = SkillsSubmission.objects.filter(batch=batch, term=term_obj, employee=employee).first()
        if existing and existing.status == SkillsSubmission.STATUS_SUBMITTED:
            return Response(
                {"detail": "Already submitted."}, status=status.HTTP_400_BAD_REQUEST
            )

        SkillsSubmission.objects.update_or_create(
            batch=batch,
            term=term_obj,
            employee=employee,
            defaults={
                "tenant": tenant,
                "status": SkillsSubmission.STATUS_SUBMITTED,
                "submitted_by": request.user,
                "submitted_at": timezone.now(),
            },
        )
        audit.info(
            "skills.submit user=%s tenant=%s batch=%s term=%s",
            request.user.id,
            getattr(tenant, "schema_name", "?"),
            batch.id,
            term_obj.name if term_obj else "-",
        )
        return Response({"status": SkillsSubmission.STATUS_SUBMITTED})


class TeacherSignatureView(APIView):
    """GET/POST /api/portal/teacher/profile/signature/ — read/write the teacher's signature.

    Signature is stored as base64 data-URI on the Employee model and printed on
    report cards for the teacher's assigned students."""

    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        employee = request.role_context.profile
        return Response({"signature_image": employee.signature_image or ""})

    def post(self, request):
        employee = request.role_context.profile
        signature_image = request.data.get("signature_image", "")
        employee.signature_image = signature_image
        employee.save(update_fields=["signature_image"])
        audit.info(
            "teacher.signature.updated user=%s tenant=%s",
            request.user.id,
            getattr(request, "tenant", {}).schema_name if hasattr(request, "tenant") else "?",
        )
        return Response({"signature_image": employee.signature_image})


# ── Public Admission (no auth) ────────────────────────────────────────────────

class AdmissionCoursesView(APIView):
    """GET /api/portal/admission/courses/?school_id=<uuid> — list courses open for admission.

    Resolves tenant via three fallback mechanisms (in order):
    1. Request domain (via TenantMainMiddleware)
    2. Optional ?school_id=<uuid> query parameter
    3. Public schema tenant
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django_tenants.utils import get_public_schema_name
        from core.models import School

        tenant = getattr(request, "tenant", None)

        # Try to resolve via school_id query parameter if no domain match
        if not tenant:
            school_id = request.query_params.get("school_id", "").strip()
            if school_id:
                tenant = School.objects.filter(id=school_id).first()

        # Fall back to the public schema tenant
        if not tenant:
            public_schema = get_public_schema_name()
            tenant = School.objects.filter(schema_name=public_schema).first()

        if not tenant:
            return Response({"error": "School not found."}, status=400)

        courses = (
            Course.objects.filter(tenant=tenant, is_deleted=False)
            .order_by("course_name")
            .values("id", "course_name")
        )
        return Response({"courses": list(courses)})


_REQUIRED_DOCS = [
    "immunization_record",
    "birth_certificate",
    "passport_photo_1",
    "passport_photo_2",
    "utility_bill",
    "parent1_id",
    "parent2_id",
]
_DOC_LABELS = {
    "immunization_record": "Under 5-card (Immunisation Record)",
    "birth_certificate": "Birth Certificate",
    "passport_photo_1": "Passport Photo 1",
    "passport_photo_2": "Passport Photo 2",
    "utility_bill": "Utility Bill",
    "parent1_id": "NRC – Parent 1",
    "parent2_id": "NRC – Parent 2",
}


class AdmissionApplyView(APIView):
    """POST /api/portal/admission/apply/?school_id=<uuid> — submit admission application.

    Accepts multipart/form-data (files + fields) or JSON (no files).
    Documents are MANDATORY for portal submissions.

    Resolves tenant via three fallback mechanisms (in order):
    1. Request domain (via TenantMainMiddleware)
    2. Optional ?school_id=<uuid> query parameter or school_id field in form data
    3. Public schema tenant
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import ValidationException
        from core.models import AcademicYear, AdmissionDocument, School
        from django_tenants.utils import get_public_schema_name

        tenant = getattr(request, "tenant", None)

        # Try to resolve via school_id query parameter or form data if no domain match
        if not tenant:
            school_id = (
                request.query_params.get("school_id", "").strip() or
                request.data.get("school_id", "").strip()
            )
            if school_id:
                tenant = School.objects.filter(id=school_id).first()

        # Fall back to the public schema tenant
        if not tenant:
            public_schema = get_public_schema_name()
            tenant = School.objects.filter(schema_name=public_schema).first()

        if not tenant:
            return Response({"error": "School not found."}, status=400)

        data = request.data
        required = ["first_name", "last_name", "date_of_birth", "gender",
                    "course_applied", "guardian1_first_name", "guardian1_mobile"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing)}"},
                status=400,
            )

        # Enforce mandatory documents for portal submissions
        missing_docs = [_DOC_LABELS[d] for d in _REQUIRED_DOCS if d not in request.FILES]
        if missing_docs:
            return Response(
                {"error": f"The following documents are required: {', '.join(missing_docs)}"},
                status=400,
            )

        try:
            svc = ExtendedAdmissionService(tenant)
            form_data = dict(data)
            form_data["terms_agreement"] = True
            if not form_data.get("academic_year"):
                active_year = AcademicYear.objects.filter(tenant=tenant, is_active=True).first()
                if active_year:
                    form_data["academic_year"] = str(active_year.id)

            with transaction.atomic():
                from core.view_modules.admission_views import AdmissionRegistrationSubmitView
                view_helper = AdmissionRegistrationSubmitView()
                existing = view_helper._find_existing_application(tenant, form_data)

                if existing and existing.status == 'submitted':
                    return Response({
                        "application_number": existing.application_number,
                        "status": existing.status,
                    }, status=200)
                elif existing and existing.status in ('approved', 'rejected'):
                    return Response({
                        "error": f"An application for this applicant already exists (application number {existing.application_number}). Please use the status check page instead of re-applying.",
                    }, status=400)
                elif existing:
                    application = svc.update_application(str(existing.id), form_data)
                else:
                    application = svc.create_application(form_data)

                # Save required documents
                for doc_type in _REQUIRED_DOCS:
                    f = request.FILES.get(doc_type)
                    if f:
                        AdmissionDocument.objects.create(
                            application=application,
                            tenant=tenant,
                            document_type=doc_type,
                            file=f,
                            original_filename=f.name,
                            file_size=f.size,
                            is_required=True,
                        )

                application = svc.submit_application(str(application.id))

            return Response({
                "application_number": application.application_number,
                "status": application.status,
            }, status=201)
        except ValidationException as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            audit.error("portal.admission.apply error tenant=%s err=%s", getattr(tenant, "schema_name", "?"), exc)
            return Response({"error": "An unexpected error occurred. Please try again."}, status=500)


class AdmissionStatusView(APIView):
    """GET /api/portal/admission/status/?app_number=XXX&school_id=<uuid>

    Resolves tenant via three fallback mechanisms (in order):
    1. Request domain (via TenantMainMiddleware)
    2. Optional ?school_id=<uuid> query parameter
    3. Public schema tenant
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from core.services.extended_admission_service import ExtendedAdmissionService
        from core.services.exceptions import NotFoundException
        from django_tenants.utils import get_public_schema_name
        from core.models import School

        tenant = getattr(request, "tenant", None)

        # Try to resolve via school_id query parameter if no domain match
        if not tenant:
            school_id = request.query_params.get("school_id", "").strip()
            if school_id:
                tenant = School.objects.filter(id=school_id).first()

        # Fall back to the public schema tenant
        if not tenant:
            public_schema = get_public_schema_name()
            tenant = School.objects.filter(schema_name=public_schema).first()

        if not tenant:
            return Response({"error": "School not found."}, status=400)

        app_number = request.query_params.get("app_number", "").strip()
        if not app_number:
            return Response({"error": "app_number is required."}, status=400)

        try:
            svc = ExtendedAdmissionService(tenant)
            app = svc.get_application_by_number(app_number)
            student_name = f"{app.first_name} {app.last_name}".strip()
            return Response({
                "application_number": app.application_number,
                "student_name": student_name,
                "course_applied": app.course_applied.course_name if app.course_applied else "",
                "status": app.status,
                "application_date": app.application_date.strftime("%d %b %Y") if app.application_date else "",
                "remarks": app.remarks or "",
            })
        except NotFoundException:
            return Response({"error": "Application not found. Please check your application number."}, status=404)
        except Exception as exc:
            audit.error("portal.admission.status error tenant=%s err=%s", getattr(tenant, "schema_name", "?"), exc)
            return Response({"error": "An error occurred."}, status=500)


class EnquirySubmitView(APIView):
    """POST /api/portal/enquiry/submit/?school_id=<uuid> — submit a public enquiry (lead capture).

    Accepts JSON only (no file uploads). Resolves tenant via the same three
    fallback mechanisms as the admission endpoints above:
    1. Request domain (via TenantMainMiddleware)
    2. Optional ?school_id=<uuid> query parameter or school_id field in the body
    3. Public schema tenant
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser]

    _PUBLIC_FIELDS = [
        "course", "first_name", "last_name", "date_of_birth", "email", "phone",
        "address_line1", "address_line2", "city", "state", "postal_code",
        "guardian_first_name", "guardian_last_name", "guardian_relation",
        "guardian_email", "guardian_phone", "source_of_info", "remarks",
    ]

    def post(self, request):
        from core.models import School
        from core.serializers.enquiry_serializers import ApplicantEnquiryCreateSerializer
        from django_tenants.utils import get_public_schema_name

        tenant = getattr(request, "tenant", None)

        if not tenant:
            school_id = (
                request.query_params.get("school_id", "").strip() or
                str(request.data.get("school_id", "")).strip()
            )
            if school_id:
                tenant = School.objects.filter(id=school_id).first()

        if not tenant:
            public_schema = get_public_schema_name()
            tenant = School.objects.filter(schema_name=public_schema).first()

        if not tenant:
            return Response({"error": "School not found."}, status=400)

        data = request.data
        if not data.get("first_name") or not data.get("last_name"):
            return Response({"error": "First name and last name are required."}, status=400)

        # Allow-list only public-safe fields — never trust client-supplied
        # counselor/stage/status flags for a public lead-capture submission.
        payload = {
            field: data[field]
            for field in self._PUBLIC_FIELDS
            if data.get(field) not in (None, "")
        }

        try:
            request.tenant = tenant
            serializer = ApplicantEnquiryCreateSerializer(data=payload, context={"request": request})
            if not serializer.is_valid():
                first_error = next(iter(serializer.errors.values()))[0]
                return Response({"error": str(first_error)}, status=400)

            enquiry = serializer.save()
            return Response({"enquiry_number": enquiry.enquiry_number}, status=201)
        except Exception as exc:
            audit.error("portal.enquiry.submit error tenant=%s err=%s", getattr(tenant, "schema_name", "?"), exc)
            return Response({"error": "An unexpected error occurred. Please try again."}, status=500)


# ── Librarian portal ────────────────────────────────────────────────────────────

class LibrarianDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request):
        employee = request.role_context.profile
        stats = selectors.librarian_dashboard_stats(employee)
        libraries = selectors.libraries_for_librarian(employee)
        return Response({
            'libraries': LibrarySerializer(libraries, many=True).data,
            'stats': stats
        })


class LibrarianLibrariesView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request):
        employee = request.role_context.profile
        libraries = selectors.libraries_for_librarian(employee)
        return Response(LibrarySerializer(libraries, many=True).data)


class LibrarianBooksView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request):
        employee = request.role_context.profile
        query = request.GET.get('q', '').strip()
        category_id = request.GET.get('category_id', '')
        library_id = request.GET.get('library_id', '')
        available_only = request.GET.get('available_only') == 'true'

        if library_id and not selectors.librarian_has_library(employee, library_id):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        filters = {
            'category_id': category_id or None,
            'available_only': available_only,
        }
        if query:
            filters['query'] = query

        books = selectors.books_for_librarian(employee, library_id=library_id or None, **filters)
        return Response(BookSerializer(books, many=True).data)

    def post(self, request):
        employee = request.role_context.profile
        library_id = request.data.get('library_id')

        if not library_id or not selectors.librarian_has_library(employee, library_id):
            return Response({'error': 'Invalid or unauthorized library'}, status=status.HTTP_400_BAD_REQUEST)

        title = (request.data.get('title') or '').strip()
        author = (request.data.get('author') or '').strip()
        category_id = request.data.get('category_id')
        missing = [
            label for value, label in (
                (title, 'title'), (author, 'author'), (category_id, 'category'),
            ) if not value
        ]
        if missing:
            return Response(
                {'error': f"Please provide: {', '.join(missing)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Book number is optional in the portal — generate a unique one when blank.
        book_number = (request.data.get('book_number') or '').strip()
        if not book_number:
            import uuid as _uuid
            book_number = f"BK-{_uuid.uuid4().hex[:10].upper()}"

        from core.services.library_service import LibraryService
        service = LibraryService(employee.tenant)

        try:
            book = service.create_book(
                title=title,
                author=author,
                book_number=book_number,
                category_id=category_id,
                isbn=request.data.get('isbn'),
                library_id=library_id,
                total_copies=int(request.data.get('total_copies', 1)),
                price=request.data.get('price') or None,
                book_type=request.data.get('book_type', 'OTHER'),
                school_level=request.data.get('school_level', 'ALL'),
            )
            return Response(BookSerializer(book).data, status=status.HTTP_201_CREATED)
        except ValidationException as e:
            return Response({'error': str(e.message)}, status=status.HTTP_400_BAD_REQUEST)
        except DuplicateException as e:
            return Response({'error': str(e.message)}, status=status.HTTP_409_CONFLICT)
        except NotFoundException as e:
            return Response({'error': str(e.message)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'error': f'Invalid input: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            audit.error(f"Book creation failed: {str(e)}")
            return Response({'error': 'An error occurred while creating the book'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LibrarianCategoriesView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request):
        employee = request.role_context.profile
        from core.services.library_service import LibraryService
        service = LibraryService(employee.tenant)
        categories = service.get_book_categories()
        return Response(BookCategorySerializer(categories, many=True).data)

    def post(self, request):
        employee = request.role_context.profile
        from core.services.library_service import LibraryService
        service = LibraryService(employee.tenant)

        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': 'A category name is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            category = service.create_book_category(name=name)
            return Response(BookCategorySerializer(category).data, status=status.HTTP_201_CREATED)
        except DuplicateException as e:
            return Response({'error': str(e.message)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            audit.error(f"Category creation failed: {str(e)}")
            return Response({'error': 'Could not create the category.'},
                            status=status.HTTP_400_BAD_REQUEST)


class LibrarianBookDetailView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request, book_id):
        employee = request.role_context.profile

        if not selectors.librarian_owns_book(employee, book_id):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            book = Book.objects.get(id=book_id, tenant=employee.tenant)
            return Response(BookSerializer(book).data)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, book_id):
        employee = request.role_context.profile

        if not selectors.librarian_owns_book(employee, book_id):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            from core.services.library_service import LibraryService
            service = LibraryService(employee.tenant)
            book = Book.objects.get(id=book_id, tenant=employee.tenant)

            if 'title' in request.data:
                book.title = request.data['title']
            if 'author' in request.data:
                book.author = request.data['author']
            if 'isbn' in request.data:
                book.isbn = request.data['isbn']
            if 'total_copies' in request.data:
                book.total_copies = int(request.data['total_copies'])
            if 'price' in request.data:
                book.price = request.data['price']
            if 'book_type' in request.data:
                book.book_type = request.data['book_type']
            if 'school_level' in request.data:
                book.school_level = request.data['school_level']

            book.save()
            return Response(BookSerializer(book).data)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, book_id):
        employee = request.role_context.profile

        if not selectors.librarian_owns_book(employee, book_id):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            book = Book.objects.get(id=book_id, tenant=employee.tenant)
            book.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)


class LibrarianBatchesView(APIView):
    """Active classes/batches, so the issue screen can pick a borrower by class."""
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request):
        employee = request.role_context.profile
        batches = selectors.all_active_batches(employee.tenant)
        return Response([
            {
                "id": str(b.id),
                "name": b.name,
                "course": b.course.course_name if b.course_id else None,
                "academic_year": b.academic_year.name if b.academic_year_id else None,
            }
            for b in batches
        ])


class LibrarianBatchStudentsView(APIView):
    """Active students in one batch (borrower picker for Issue Book)."""
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request, batch_id):
        employee = request.role_context.profile
        batch = selectors.batch_for_tenant(employee.tenant, batch_id)
        if batch is None:
            return Response({'error': 'Batch not found'}, status=status.HTTP_404_NOT_FOUND)
        students = selectors.roster_for_batch(batch)
        return Response([
            {
                "id": str(s.id),
                "full_name": s.full_name,
                "admission_no": s.admission_no,
            }
            for s in students
        ])


class LibrarianScanLookupView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def post(self, request):
        employee = request.role_context.profile
        barcode = request.data.get('barcode', '').strip()

        if not barcode:
            return Response({'error': 'Barcode required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from core.services.library_service import LibraryService
            service = LibraryService(employee.tenant)
            book = Book.objects.get(barcode=barcode, tenant=employee.tenant)

            if not selectors.librarian_owns_book(employee, str(book.id)):
                return Response({'error': 'Not authorized to access this book'}, status=status.HTTP_403_FORBIDDEN)

            return Response(BookSerializer(book).data)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)


class LibrarianScanIssueView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def post(self, request):
        employee = request.role_context.profile
        book_id = request.data.get('book_id')
        barcode = request.data.get('barcode')
        due_days = request.data.get('due_days', 14)

        # Borrower: a student picked from a class, a staff member, or a bare
        # ``borrower_id`` (legacy) that we resolve as student-then-employee.
        student_id = request.data.get('student_id')
        employee_id = request.data.get('employee_id')
        borrower_id = request.data.get('borrower_id')
        if not (student_id or employee_id) and borrower_id:
            from core.models import Student as _Student, Employee as _Employee
            if _Student.objects.filter(id=borrower_id, tenant=employee.tenant).exists():
                student_id = borrower_id
            elif _Employee.objects.filter(id=borrower_id, tenant=employee.tenant).exists():
                employee_id = borrower_id
            else:
                return Response({'error': 'That borrower could not be found.'},
                                status=status.HTTP_400_BAD_REQUEST)

        if not (book_id or barcode):
            return Response({'error': 'Book ID or barcode required'}, status=status.HTTP_400_BAD_REQUEST)

        if not (student_id or employee_id):
            return Response({'error': 'Select a borrower.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            due_days = int(due_days)
            if due_days <= 0:
                return Response({'error': 'Due days must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': 'Due days must be a valid number'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from core.services.library_service import LibraryService
            service = LibraryService(employee.tenant)

            if barcode:
                book = Book.objects.get(barcode=barcode, tenant=employee.tenant)
            else:
                book = Book.objects.get(id=book_id, tenant=employee.tenant)

            if not selectors.librarian_owns_book(employee, str(book.id)):
                return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

            due_date = timezone.now().date() + timezone.timedelta(days=due_days)
            movement = service.issue_book(
                book_id=str(book.id),
                student_id=student_id or None,
                employee_id=employee_id or None,
                due_date=due_date,
            )
            return Response(BookMovementSerializer(movement).data, status=status.HTTP_201_CREATED)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)
        except (NotFoundException, ValidationException, BusinessLogicException) as e:
            return Response({'error': str(e.message)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            audit.error(f"Book issue failed: {str(e)}")
            return Response({'error': 'An error occurred while issuing the book'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LibrarianScanReturnView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def post(self, request):
        employee = request.role_context.profile
        book_id = request.data.get('book_id')
        barcode = request.data.get('barcode')

        if not (book_id or barcode):
            return Response({'error': 'Book ID or barcode required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from core.services.library_service import LibraryService
            service = LibraryService(employee.tenant)

            if barcode:
                book = Book.objects.get(barcode=barcode, tenant=employee.tenant)
            else:
                book = Book.objects.get(id=book_id, tenant=employee.tenant)

            if not selectors.librarian_owns_book(employee, str(book.id)):
                return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

            movement = service.return_book(book_id=str(book.id))
            return Response(BookMovementSerializer(movement).data)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LibrarianIssuedBooksView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request):
        employee = request.role_context.profile
        overdue_only = request.GET.get('overdue_only') == 'true'
        library_id = request.GET.get('library_id', '')

        if library_id and not selectors.librarian_has_library(employee, library_id):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        from core.services.library_service import LibraryService
        service = LibraryService(employee.tenant)

        books = service.get_issued_books(library_id=library_id or None)
        if overdue_only:
            books = books.filter(return_date__isnull=True, due_date__lt=timezone.now().date())

        return Response(BookMovementSerializer(books, many=True).data)


class LibrarianOverdueBooksView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request):
        employee = request.role_context.profile
        library_id = request.GET.get('library_id', '')

        if library_id and not selectors.librarian_has_library(employee, library_id):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        from core.services.library_service import LibraryService
        service = LibraryService(employee.tenant)

        overdue = service.get_overdue_books(library_id=library_id or None)
        return Response(BookMovementSerializer(overdue, many=True).data)


class LibrarianBookHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsLibrarian]

    def get(self, request, book_id):
        employee = request.role_context.profile

        if not selectors.librarian_owns_book(employee, book_id):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            book = Book.objects.get(id=book_id, tenant=employee.tenant)
            movements = BookMovement.objects.filter(book=book, tenant=employee.tenant).order_by('-issue_date')
            return Response(BookMovementSerializer(movements, many=True).data)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)
