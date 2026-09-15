"""
Billing access control tests.

Tests for the manual billing-status gate that ensures:
1. active/trial schools (with a future or unset trial end) can reach the dashboard
2. suspended/past_due schools are blocked with a 402
3. an expired trial blocks access even though billing_status is still 'trial'
4. root users have break-glass access regardless of billing status
5. tenant isolation is maintained

BillingAccessMiddleware is exercised directly via RequestFactory (request.tenant
set manually), the same style EnabledModulesForTests uses in
test_module_access.py, rather than through a full Client HTTP round trip:
core:dashboard's view has its own data requirements (academic year, etc.)
unrelated to billing, and asserting through it would couple these tests to
that view's internals instead of to the middleware being tested here.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.middleware import BillingAccessMiddleware
from core.models import School

User = get_user_model()

# The `core` app lives in SHARED_APPS (its tables live in the public schema —
# see tests/conftest.py), so tests never need a real per-tenant Postgres
# schema. Disabling auto_create_schema turns School.objects.create() into a
# plain row insert instead of a slow (and here, unnecessary) schema migration.
School.auto_create_schema = False


def _ok_response(request):
    return HttpResponse("OK")


class SchoolIsBillingActiveTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Test School",
            code="BILL_UNIT",
            schema_name="test_billing_unit",
        )

    def test_active_status_is_active(self):
        self.school.billing_status = School.BILLING_STATUS_ACTIVE
        self.assertTrue(self.school.is_billing_active)

    def test_trial_without_end_date_is_active(self):
        self.school.billing_status = School.BILLING_STATUS_TRIAL
        self.school.trial_ends_at = None
        self.assertTrue(self.school.is_billing_active)

    def test_trial_with_future_end_date_is_active(self):
        self.school.billing_status = School.BILLING_STATUS_TRIAL
        self.school.trial_ends_at = timezone.now() + timedelta(days=1)
        self.assertTrue(self.school.is_billing_active)

    def test_trial_with_past_end_date_is_inactive(self):
        self.school.billing_status = School.BILLING_STATUS_TRIAL
        self.school.trial_ends_at = timezone.now() - timedelta(days=1)
        self.assertFalse(self.school.is_billing_active)

    def test_past_due_is_inactive(self):
        self.school.billing_status = School.BILLING_STATUS_PAST_DUE
        self.assertFalse(self.school.is_billing_active)

    def test_suspended_is_inactive(self):
        self.school.billing_status = School.BILLING_STATUS_SUSPENDED
        self.assertFalse(self.school.is_billing_active)


class BillingAccessMiddlewareTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Test School",
            code="BILL_MW_A",
            schema_name="test_billing_mw_a",
            billing_status=School.BILLING_STATUS_ACTIVE,
        )
        self.root_user = self._make_user("root", is_admin=True, is_root=True)
        self.admin_user = self._make_user("admin", is_admin=True, is_root=False)
        self.factory = RequestFactory()
        self.middleware = BillingAccessMiddleware(_ok_response)

    def _make_user(self, username, **extra_fields):
        # tenant_users' create_user() requires a public-schema tenant + add_user,
        # which this project's School model does not provide in tests (see
        # tests/conftest.py's `user` fixture) — build users directly instead.
        user = User(username=username, email=f"{username}@test.local", **extra_fields)
        user.set_password("testpass")
        user.save()
        user.tenants.add(self.school)
        return user

    def _request_for(self, user, school=None):
        request = self.factory.get(reverse("core:dashboard"))
        request.user = user
        request.tenant = school or self.school
        return request

    def test_active_school_dashboard_allowed(self):
        response = self.middleware(self._request_for(self.admin_user))
        self.assertEqual(response.status_code, 200)

    def test_trial_school_dashboard_allowed(self):
        self.school.billing_status = School.BILLING_STATUS_TRIAL
        self.school.trial_ends_at = timezone.now() + timedelta(days=7)
        self.school.save()

        response = self.middleware(self._request_for(self.admin_user))
        self.assertEqual(response.status_code, 200)

    def test_suspended_school_dashboard_blocked(self):
        self.school.billing_status = School.BILLING_STATUS_SUSPENDED
        self.school.save()

        response = self.middleware(self._request_for(self.admin_user))
        self.assertEqual(response.status_code, 402)

    def test_past_due_school_dashboard_blocked(self):
        self.school.billing_status = School.BILLING_STATUS_PAST_DUE
        self.school.save()

        response = self.middleware(self._request_for(self.admin_user))
        self.assertEqual(response.status_code, 402)

    def test_expired_trial_dashboard_blocked(self):
        self.school.billing_status = School.BILLING_STATUS_TRIAL
        self.school.trial_ends_at = timezone.now() - timedelta(days=1)
        self.school.save()

        response = self.middleware(self._request_for(self.admin_user))
        self.assertEqual(response.status_code, 402)

    def test_root_user_bypasses_billing_gate(self):
        self.school.billing_status = School.BILLING_STATUS_SUSPENDED
        self.school.save()

        response = self.middleware(self._request_for(self.root_user))
        self.assertEqual(response.status_code, 200)

    def test_tenant_isolation_different_billing_states(self):
        school_b = School.objects.create(
            name="School B",
            code="BILL_MW_B",
            schema_name="test_billing_mw_b",
            billing_status=School.BILLING_STATUS_SUSPENDED,
        )

        response_a = self.middleware(self._request_for(self.admin_user, school=self.school))
        response_b = self.middleware(self._request_for(self.admin_user, school=school_b))

        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 402)
