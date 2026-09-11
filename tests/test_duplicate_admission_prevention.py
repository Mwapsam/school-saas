"""
Tests that applicant registration does not create duplicate applications
when the same final submission is posted more than once (double-click,
client retry after timeout, or retry after a failed submit).
"""
import pytest
import uuid
from datetime import date

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase, RequestFactory

from core.models import (
    School, ExtendedAdmissionApplication, AcademicYear, Course, Country
)
from core.view_modules.admission_views import AdmissionRegistrationSubmitView


@pytest.mark.django_db
class DuplicateAdmissionPreventionTestCase(TestCase):
    """Posting the same registration twice must yield exactly one application."""

    def setUp(self):
        self.factory = RequestFactory()

        # Unique codes: the test DB may be reused across runs and Course.code
        # and School.schema_name carry unique constraints.
        suffix = uuid.uuid4().hex[:8]
        self.school = School.objects.create(
            name="Test School",
            code=f"T{suffix[:4].upper()}",
            schema_name=f"test_school_dup_{suffix}"
        )
        self.academic_year = AcademicYear.objects.create(
            tenant=self.school,
            name="2026-2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
            admission_start_date=date(2026, 1, 1),
            admission_end_date=date(2026, 8, 31)
        )
        self.course = Course.objects.create(
            tenant=self.school,
            course_name="Grade 1",
            code=f"G1{suffix}",
            section_name="A"
        )
        self.country, _ = Country.objects.get_or_create(
            code="ZM", defaults={'name': 'Zambia'}
        )

        self.form_data = {
            'action': 'submit',
            'step': '7',
            'academic_year': str(self.academic_year.id),
            'course_applied': str(self.course.id),
            'first_name': 'Chanda',
            'last_name': 'Mwansa',
            'date_of_birth': '2018-05-10',
            'gender': 'male',
            'nationality': 'Zambian',
            'guardian1_first_name': 'Bwalya',
            'guardian1_last_name': 'Mwansa',
            'guardian1_relation': 'Father',
            'guardian1_mobile': '0977123456',
            'address_line1': '12 Independence Ave',
            'city': 'Lusaka',
            'country': str(self.country.id),
            'terms_agreement': 'on',
            'declaration_agreement': 'on',
            'declaration_date': '2026-07-03',
        }

    def _post_submission(self, data=None):
        request = self.factory.post('/register/submit/', data or self.form_data)
        request.tenant = self.school
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        request.user = None
        view = AdmissionRegistrationSubmitView()
        view.request = request
        return view.post(request)

    def test_single_submission_creates_one_application(self):
        response = self._post_submission()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ExtendedAdmissionApplication.objects.filter(tenant=self.school).count(),
            1
        )

    def test_duplicate_submission_does_not_create_second_application(self):
        first = self._post_submission()
        self.assertEqual(first.status_code, 200)

        second = self._post_submission()

        applications = ExtendedAdmissionApplication.objects.filter(
            tenant=self.school,
            first_name='Chanda',
            last_name='Mwansa'
        )
        self.assertEqual(
            applications.count(), 1,
            "Re-posting the same registration must not create a duplicate application"
        )

    def test_duplicate_submission_returns_existing_application_number(self):
        import json
        first = json.loads(self._post_submission().content)
        second = json.loads(self._post_submission().content)

        self.assertTrue(second.get('success'),
                        f"Duplicate resubmission should be treated as success, got: {second}")
        self.assertEqual(first['application_number'], second['application_number'])

    def test_retry_after_failed_submit_reuses_leftover_draft(self):
        """A draft left behind by a failed submission is reused, not duplicated."""
        ExtendedAdmissionApplication.objects.create(
            tenant=self.school,
            application_number='TEST-2026-0001',
            status='draft',
            current_step=7,
            first_name='Chanda',
            last_name='Mwansa',
            date_of_birth=date(2018, 5, 10),
            academic_year=self.academic_year,
        )

        response = self._post_submission()
        self.assertEqual(response.status_code, 200)

        applications = ExtendedAdmissionApplication.objects.filter(
            tenant=self.school,
            first_name='Chanda',
            last_name='Mwansa'
        )
        self.assertEqual(applications.count(), 1)
        self.assertEqual(applications.first().status, 'submitted')

    def test_different_applicant_same_name_different_dob_is_allowed(self):
        """Two genuinely different children sharing a name must both be accepted."""
        self._post_submission()

        other = dict(self.form_data)
        other['date_of_birth'] = '2019-11-22'
        self._post_submission(other)

        self.assertEqual(
            ExtendedAdmissionApplication.objects.filter(
                tenant=self.school,
                first_name='Chanda',
                last_name='Mwansa'
            ).count(),
            2
        )
