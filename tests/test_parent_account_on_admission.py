"""
Tests for automatic parent portal account creation when a student is admitted
from an approved admission application (admission_admit_api).
"""
import json
import uuid
import pytest
from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase, RequestFactory

from core.models import (
    School, ExtendedAdmissionApplication, AcademicYear, Course, Batch,
    Guardian, Student, StudentGuardianRelation, User,
)
from core.views import admission_admit_api


@pytest.mark.django_db
class ParentAccountOnAdmissionTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        # Unique codes/emails: the test DB is reused across runs and several
        # of these columns carry unique constraints.
        self.sfx = uuid.uuid4().hex[:8]

        self.school = School.objects.create(
            name="Test School",
            code=f"P{self.sfx[:4].upper()}",
            schema_name=f"test_school_parent_{self.sfx}"
        )
        self.academic_year = AcademicYear.objects.create(
            tenant=self.school,
            name=f"2026-2027-{self.sfx}",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )
        self.course = Course.objects.create(
            tenant=self.school,
            course_name="Grade 1",
            code=f"PG{self.sfx}",
            section_name="A"
        )
        self.batch = Batch.objects.create(
            tenant=self.school,
            name="Grade 1 A",
            course=self.course,
            academic_year=self.academic_year,
            start_date=datetime(2026, 9, 1, tzinfo=dt_timezone.utc),
            end_date=datetime(2027, 6, 30, tzinfo=dt_timezone.utc),
            is_active=True,
        )

    def _make_application(self, **overrides):
        defaults = dict(
            tenant=self.school,
            application_number=f"APP-{uuid.uuid4().hex[:10]}",
            status='approved',
            first_name='Chanda',
            last_name=f'Mwansa{self.sfx}',
            date_of_birth=date(2018, 5, 10),
            gender='male',
            academic_year=self.academic_year,
            course_applied=self.course,
            guardian1_first_name='Bwalya',
            guardian1_last_name='Mwansa',
            guardian1_relation='Father',
            guardian1_mobile='0977123456',
            guardian1_email=f'bwalya.{self.sfx}@example.com',
            guardian1_occupation='Engineer',
        )
        defaults.update(overrides)
        return ExtendedAdmissionApplication.objects.create(**defaults)

    def _admit(self, application):
        request = self.factory.post(
            f'/management/{application.id}/admit/',
            data=json.dumps({'batch_id': str(self.batch.id)}),
            content_type='application/json',
        )
        request.tenant = self.school
        response = admission_admit_api(request, application.id)
        return json.loads(response.content)

    def test_parent_account_created_on_admission(self):
        application = self._make_application()
        result = self._admit(application)

        self.assertTrue(result['success'], result)
        account = result['parent_account']
        self.assertEqual(account['status'], 'created')
        self.assertTrue(account['username'])
        self.assertGreaterEqual(len(account['password']), 8)
        self.assertEqual(account['guardian_name'], 'Bwalya Mwansa')

        guardian = Guardian.objects.get(
            tenant=self.school, email__iexact=application.guardian1_email
        )
        self.assertIsNotNone(guardian.user)
        self.assertEqual(guardian.user.username, account['username'])
        self.assertTrue(guardian.user.check_password(account['password']))
        self.assertTrue(guardian.user.tenants.filter(id=self.school.id).exists())
        self.assertEqual(guardian.occupation, 'Engineer')

        student = Student.objects.get(id=result['student_id'])
        self.assertTrue(StudentGuardianRelation.objects.filter(
            student=student, guardian=guardian
        ).exists())
        self.assertEqual(student.immediate_contact_id, guardian.id)

        from portal.roles import resolve_role, ROLE_PARENT
        self.assertEqual(resolve_role(guardian.user).role, ROLE_PARENT)

    def test_existing_guardian_with_user_is_reused_case_insensitive(self):
        email = f'bwalya.{self.sfx}@example.com'
        user = User(
            username=f'bwalya{self.sfx}', email=email,
            first_name='Bwalya', last_name='Mwansa', is_active=True,
        )
        user.set_password('existingpass123')
        user.save()
        user.tenants.add(self.school)
        guardian = Guardian.objects.create(
            tenant=self.school, first_name='Bwalya', last_name='Mwansa',
            relation='Father', email=email, user=user, is_active=True,
        )

        application = self._make_application(guardian1_email=email.upper())
        result = self._admit(application)

        account = result['parent_account']
        self.assertEqual(account['status'], 'reused')
        self.assertEqual(account['username'], user.username)
        self.assertNotIn('password', account)
        self.assertEqual(
            Guardian.objects.filter(tenant=self.school, email__iexact=email).count(), 1
        )

        student = Student.objects.get(id=result['student_id'])
        self.assertTrue(StudentGuardianRelation.objects.filter(
            student=student, guardian=guardian
        ).exists())

    def test_existing_guardian_matched_by_mobile_when_no_email(self):
        mobile = f'09{self.sfx[:8]}'
        user = User(
            username=f'mobileparent{self.sfx}',
            email=f'mp.{self.sfx}@example.com',
            first_name='Bwalya', last_name='Mwansa', is_active=True,
        )
        user.set_password('existingpass123')
        user.save()
        user.tenants.add(self.school)
        guardian = Guardian.objects.create(
            tenant=self.school, first_name='Bwalya', last_name='Mwansa',
            relation='Father', mobile_phone=mobile, user=user, is_active=True,
        )

        application = self._make_application(
            guardian1_email='', guardian1_mobile=mobile
        )
        result = self._admit(application)

        self.assertEqual(result['parent_account']['status'], 'reused')
        student = Student.objects.get(id=result['student_id'])
        self.assertTrue(StudentGuardianRelation.objects.filter(
            student=student, guardian=guardian
        ).exists())

    def test_existing_guardian_without_user_gets_login_granted(self):
        email = f'nologin.{self.sfx}@example.com'
        guardian = Guardian.objects.create(
            tenant=self.school, first_name='Bwalya', last_name='Mwansa',
            relation='Father', email=email, is_active=True,
        )

        application = self._make_application(guardian1_email=email)
        result = self._admit(application)

        account = result['parent_account']
        self.assertEqual(account['status'], 'created')
        guardian.refresh_from_db()
        self.assertIsNotNone(guardian.user)
        self.assertEqual(guardian.user.username, account['username'])
        self.assertTrue(guardian.user.check_password(account['password']))

    def test_missing_guardian_name_skips_account_but_admits_student(self):
        application = self._make_application(
            guardian1_first_name='', guardian1_last_name=''
        )
        result = self._admit(application)

        self.assertTrue(result['success'])
        self.assertEqual(result['parent_account']['status'], 'skipped')
        self.assertTrue(Student.objects.filter(id=result['student_id']).exists())
        application.refresh_from_db()
        self.assertEqual(application.status, 'admitted')

    def test_provisioning_failure_does_not_block_admission(self):
        application = self._make_application()
        with patch(
            'core.services.portal_account_service.PortalAccountService'
            '.provision_parent_account_from_application',
            side_effect=RuntimeError('boom')
        ):
            result = self._admit(application)

        self.assertTrue(result['success'])
        self.assertEqual(result['parent_account']['status'], 'skipped')
        self.assertTrue(Student.objects.filter(id=result['student_id']).exists())
        application.refresh_from_db()
        self.assertEqual(application.status, 'admitted')

    def test_username_collision_gets_numeric_suffix(self):
        taken = f'collide{self.sfx}'
        user = User(
            username=taken, email=f'{taken}@other.com',
            first_name='Other', last_name='Person', is_active=True,
        )
        user.set_password('somepassword1')
        user.save()
        user.tenants.add(self.school)

        application = self._make_application(
            guardian1_email=f'{taken}@example.com'
        )
        result = self._admit(application)

        account = result['parent_account']
        self.assertEqual(account['status'], 'created')
        self.assertEqual(account['username'], f'{taken}2')

    def test_second_sibling_links_same_guardian_single_user(self):
        email = f'sibling.{self.sfx}@example.com'
        first = self._make_application(guardian1_email=email)
        result1 = self._admit(first)
        self.assertEqual(result1['parent_account']['status'], 'created')

        second = self._make_application(
            first_name='Mutale', guardian1_email=email
        )
        result2 = self._admit(second)
        self.assertEqual(result2['parent_account']['status'], 'reused')

        guardians = Guardian.objects.filter(tenant=self.school, email__iexact=email)
        self.assertEqual(guardians.count(), 1)
        guardian = guardians.first()
        self.assertEqual(StudentGuardianRelation.objects.filter(
            guardian=guardian,
            student_id__in=[result1['student_id'], result2['student_id']],
        ).count(), 2)
        self.assertIsNotNone(guardian.user)
