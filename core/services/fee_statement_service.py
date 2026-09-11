"""Fee statement PDF generation and distribution service.

Handles PDF generation from student fee statements and distribution via:
- SMS (via SMSClient)
- Email (via Django mail)
- Parent portal sync (via API)
"""
import logging
import io
import threading
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple

from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from core.models import Student, AcademicYear, Guardian, StudentGuardianRelation
from core.services.base import TenantAwareService
from core.services.exceptions import ServiceException, NotFoundException, ValidationException
from core.services.fee_reporting_service import FeeReportingService
from core.services.currency_service import CurrencyService
from utils.sms_client import SMSClient

logger = logging.getLogger(__name__)

# Thread-local storage for WeasyPrint FontConfiguration (same pattern as ReportGenerationService)
_thread_local = threading.local()


def _get_font_config():
    """Get or create a thread-local FontConfiguration instance."""
    if not hasattr(_thread_local, 'font_config'):
        _thread_local.font_config = FontConfiguration()
    return _thread_local.font_config


class FeeStatementService(TenantAwareService):
    """Service for generating and distributing student fee statements."""

    def __init__(self, tenant):
        super().__init__(model_class=Student, tenant=tenant)

    def generate_pdf(self, student: Student, academic_year: AcademicYear) -> bytes:
        """Generate a PDF fee statement for a student in an academic year.

        Args:
            student: The Student object
            academic_year: The AcademicYear object

        Returns:
            bytes: PDF content

        Raises:
            ServiceException: If PDF generation fails
            NotFoundException: If statement data cannot be retrieved
        """
        try:
            reporting = FeeReportingService(self.tenant)
            statement = reporting.student_statement(student, academic_year)

            if not statement:
                raise NotFoundException(f"No fee statement found for student {student.id}")

            currency_symbol = CurrencyService(self.tenant).get_currency_symbol()

            context = {
                'school': self.tenant,
                'student': student,
                'statement': statement,
                'currency_symbol': currency_symbol,
                'academic_year': academic_year,
                'generated_at': timezone.now(),
            }

            html_content = render_to_string(
                'core/fees/statement_pdf.html',
                context
            )

            # Use thread-local FontConfiguration to avoid expensive filesystem scans
            font_config = _get_font_config()
            pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

            return pdf_bytes

        except Exception as e:
            logger.error(f"Error generating PDF for student {student.id}: {e}", exc_info=True)
            raise ServiceException(f"PDF generation failed: {e}")

    def send_via_sms(
        self,
        guardian: Guardian,
        student: Student,
        academic_year: AcademicYear,
        message: str = None
    ) -> Dict[str, Any]:
        """Send fee statement notification via SMS.

        Args:
            guardian: Guardian to send SMS to
            student: Student whose statement is being sent
            academic_year: Academic year of the statement
            message: Optional custom message (else a default is used)

        Returns:
            dict: {success: bool, message: str, error: str|None}
        """
        if not guardian.mobile_phone:
            return {
                'success': False,
                'message': 'SMS sending failed',
                'error': f'Guardian {guardian.id} has no phone number',
            }

        if not message:
            message = (
                f"Hello {guardian.first_name}, "
                f"the fee statement for {student.first_name} {student.last_name} "
                f"in {academic_year.name} is ready. "
                f"Log in to the parent portal to view details."
            )

        try:
            result = SMSClient.send_sms(
                recipients=guardian.mobile_phone,
                message=message,
                sender_id=self.tenant.name,
                enqueue=False,
            )
            if result:
                return {
                    'success': True,
                    'message': f'SMS sent to {guardian.mobile_phone}',
                    'error': None,
                }
            else:
                return {
                    'success': False,
                    'message': 'SMS sending failed',
                    'error': 'SMS provider returned no response',
                }
        except Exception as e:
            logger.error(f"Error sending SMS to guardian {guardian.id}: {e}")
            return {
                'success': False,
                'message': 'SMS sending failed',
                'error': str(e),
            }

    def send_via_email(
        self,
        guardian: Guardian,
        student: Student,
        academic_year: AcademicYear,
        pdf_bytes: bytes,
        subject: str = None,
        message: str = None,
    ) -> Dict[str, Any]:
        """Send fee statement PDF via email.

        Args:
            guardian: Guardian to send email to
            student: Student whose statement is being sent
            academic_year: Academic year of the statement
            pdf_bytes: PDF content bytes
            subject: Email subject (else a default is used)
            message: Email body message (else a default is used)

        Returns:
            dict: {success: bool, message: str, error: str|None}
        """
        if not guardian.email:
            return {
                'success': False,
                'message': 'Email sending failed',
                'error': f'Guardian {guardian.id} has no email address',
            }

        if not subject:
            subject = (
                f"Fee Statement for {student.first_name} {student.last_name} "
                f"- {academic_year.name}"
            )

        if not message:
            message = (
                f"<p>Dear {guardian.first_name},</p>\n"
                f"<p>Please find attached the fee statement for {student.first_name} {student.last_name} "
                f"for the academic year {academic_year.name}.</p>\n"
                f"<p>If you have any questions, please contact the school finance office.</p>\n"
                f"<p>Regards,<br>{self.tenant.name} Finance Team</p>"
            )

        try:
            filename = (
                f"statement_{student.admission_no}_{academic_year.name.replace(' ', '_')}.pdf"
            )
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=None,  # Uses DEFAULT_FROM_EMAIL from settings
                to=[guardian.email],
            )
            email.content_subtype = 'html'
            email.attach(filename, pdf_bytes, 'application/pdf')
            email.send()

            return {
                'success': True,
                'message': f'Email sent to {guardian.email}',
                'error': None,
            }
        except Exception as e:
            logger.error(f"Error sending email to guardian {guardian.id}: {e}")
            return {
                'success': False,
                'message': 'Email sending failed',
                'error': str(e),
            }

    def sync_to_parent_portal(
        self,
        guardian: Guardian,
        student: Student,
        academic_year: AcademicYear,
        pdf_bytes: bytes,
        portal_api_url: str = None,
    ) -> Dict[str, Any]:
        """Sync fee statement to parent portal dashboard.

        Args:
            guardian: Guardian who should see the statement
            student: Student whose statement is being synced
            academic_year: Academic year of the statement
            pdf_bytes: PDF content bytes
            portal_api_url: Override portal API URL (else from tenant settings)

        Returns:
            dict: {success: bool, message: str, error: str|None}
        """
        # This would be implemented by calling the Next.js frontend API
        # For now, we'll save it to storage and return metadata that the
        # portal can use to fetch it.
        try:
            timestamp = timezone.now().isoformat()
            filename = (
                f"statements/{self.tenant.id}/{academic_year.id}/"
                f"{guardian.id}/{student.id}/{timestamp}.pdf"
            )

            # Save to storage
            path = default_storage.save(filename, ContentFile(pdf_bytes))

            # In a real implementation, you'd POST to the portal API:
            # response = requests.post(
            #     f"{portal_api_url}/api/statements/sync",
            #     json={
            #         "guardian_id": str(guardian.id),
            #         "student_id": str(student.id),
            #         "academic_year_id": str(academic_year.id),
            #         "pdf_path": path,
            #         "synced_at": timestamp,
            #     },
            #     headers={"Authorization": f"Bearer {api_token}"}
            # )

            logger.info(f"Statement synced to portal storage: {path}")
            return {
                'success': True,
                'message': f'Statement synced to parent portal',
                'error': None,
                'pdf_path': path,  # Path in storage for portal to fetch
            }
        except Exception as e:
            logger.error(f"Error syncing to portal for guardian {guardian.id}: {e}")
            return {
                'success': False,
                'message': 'Portal sync failed',
                'error': str(e),
            }

    def get_student_guardians(self, student: Student) -> List[Guardian]:
        """Get all active guardians linked to a student.

        Returns:
            List of Guardian objects
        """
        return list(
            Guardian.objects.filter(
                student_relations__student=student,
                student_relations__tenant=self.tenant,
                is_active=True,
            ).distinct()
        )

    def distribute_statement(
        self,
        student: Student,
        academic_year: AcademicYear,
        guardian_ids: List[str],
        channels: List[str],  # ['sms', 'email', 'portal']
        custom_message: str = None,
    ) -> Dict[str, Any]:
        """Distribute a statement to one or more guardians via selected channels.

        Args:
            student: Student whose statement to distribute
            academic_year: Academic year of the statement
            guardian_ids: List of guardian UUIDs to send to
            channels: List of distribution channels ('sms', 'email', 'portal')
            custom_message: Optional custom message for SMS

        Returns:
            dict: {
                success: bool,
                total: int,
                results: [
                    {
                        guardian_id: str,
                        guardian_name: str,
                        sms: {success, message, error} | None,
                        email: {success, message, error} | None,
                        portal: {success, message, error} | None,
                    }
                ],
                errors: [str]
            }
        """
        if not guardian_ids:
            raise ValidationException("At least one guardian must be selected")

        if not channels:
            raise ValidationException("At least one distribution channel must be selected")

        # Validate channels
        valid_channels = {'sms', 'email', 'portal'}
        invalid = set(channels) - valid_channels
        if invalid:
            raise ValidationException(f"Invalid channels: {', '.join(invalid)}")

        # Fetch guardians
        guardians = Guardian.objects.filter(
            id__in=guardian_ids,
            tenant=self.tenant,
            is_active=True,
        )

        if not guardians.exists():
            raise NotFoundException("No guardians found for the specified IDs")

        # Generate PDF once (reuse for all recipients)
        try:
            pdf_bytes = self.generate_pdf(student, academic_year)
        except Exception as e:
            logger.error(f"Failed to generate statement PDF: {e}")
            return {
                'success': False,
                'total': len(guardian_ids),
                'results': [],
                'errors': [f"PDF generation failed: {e}"],
            }

        results = []
        errors = []

        for guardian in guardians:
            result_entry = {
                'guardian_id': str(guardian.id),
                'guardian_name': f"{guardian.first_name} {guardian.last_name}",
                'sms': None,
                'email': None,
                'portal': None,
            }

            if 'sms' in channels:
                result_entry['sms'] = self.send_via_sms(
                    guardian, student, academic_year, custom_message
                )
                if not result_entry['sms']['success']:
                    errors.append(
                        f"SMS to {guardian.mobile_phone}: {result_entry['sms']['error']}"
                    )

            if 'email' in channels:
                result_entry['email'] = self.send_via_email(
                    guardian, student, academic_year, pdf_bytes
                )
                if not result_entry['email']['success']:
                    errors.append(
                        f"Email to {guardian.email}: {result_entry['email']['error']}"
                    )

            if 'portal' in channels:
                result_entry['portal'] = self.sync_to_parent_portal(
                    guardian, student, academic_year, pdf_bytes
                )
                if not result_entry['portal']['success']:
                    errors.append(
                        f"Portal sync for guardian {guardian.id}: {result_entry['portal']['error']}"
                    )

            results.append(result_entry)

        all_successful = all(
            (r.get('sms', {}).get('success', True) if 'sms' in channels else True) and
            (r.get('email', {}).get('success', True) if 'email' in channels else True) and
            (r.get('portal', {}).get('success', True) if 'portal' in channels else True)
            for r in results
        )

        return {
            'success': all_successful,
            'total': len(results),
            'results': results,
            'errors': errors,
        }
