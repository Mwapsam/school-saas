"""
Module-level access control tests.

Tests for the module access control system that ensures:
1. Enabled modules are accessible and appear in navigation
2. Disabled modules are hidden and return 403
3. Server-side enforcement is non-bypassable
4. Tenant isolation is maintained
5. Root users have break-glass access
6. Cache isolation prevents cross-tenant leakage
7. Bootstrap and dashboard agree on enabled modules
"""
from __future__ import annotations

from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.models import School, SchoolModule
from core.modules import MODULES, enabled_modules_for

User = get_user_model()


class EnabledModulesForTests(TestCase):
    """Test the enabled_modules_for() helper function."""

    def setUp(self):
        self.school = School.objects.create(
            name="Test School",
            domain="test.local",
            schema_name="test",
        )

    def test_no_tenant_returns_required_only(self):
        result = enabled_modules_for(None)
        self.assertEqual(result, {"academics"})

    def test_required_modules_always_included(self):
        result = enabled_modules_for(self.school)
        self.assertIn("academics", result)

    def test_enabled_optional_modules_included(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=True,
        )
        result = enabled_modules_for(self.school)
        self.assertIn("finance", result)

    def test_disabled_optional_modules_excluded(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=False,
        )
        result = enabled_modules_for(self.school)
        self.assertNotIn("finance", result)

    def test_missing_optional_module_row_is_disabled(self):
        result = enabled_modules_for(self.school)
        self.assertNotIn("finance", result)
        self.assertNotIn("hr", result)

    def test_request_scoped_caching(self):
        factory = RequestFactory()
        request1 = factory.get("/")
        request1.tenant = self.school

        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=True,
        )
        result1 = enabled_modules_for(self.school, request=request1)
        self.assertIn("finance", result1)
        self.assertIsNotNone(getattr(request1, "_module_access_cache", None))

        request2 = factory.get("/")
        request2.tenant = self.school

        result2 = enabled_modules_for(self.school, request=request2)
        self.assertIn("finance", result2)
        self.assertIsNotNone(getattr(request2, "_module_access_cache", None))

        self.assertTrue(request1._module_access_cache["tenant_id"], self.school.id)

    def test_cache_isolation_between_tenants(self):
        school_a = School.objects.create(
            name="School A",
            domain="a.local",
            schema_name="a",
        )
        school_b = School.objects.create(
            name="School B",
            domain="b.local",
            schema_name="b",
        )

        SchoolModule.objects.create(
            school=school_a,
            module="finance",
            enabled=True,
        )

        factory = RequestFactory()
        request_a = factory.get("/")
        request_a.tenant = school_a
        request_b = factory.get("/")
        request_b.tenant = school_b

        enabled_a = enabled_modules_for(school_a, request=request_a)
        enabled_b = enabled_modules_for(school_b, request=request_b)

        self.assertIn("finance", enabled_a)
        self.assertNotIn("finance", enabled_b)

        self.assertNotEqual(request_a._module_access_cache, request_b._module_access_cache)


class ModuleAccessMiddlewareTests(TestCase):
    """Test the ModuleAccessMiddleware enforcement."""

    def setUp(self):
        self.school = School.objects.create(
            name="Test School",
            domain="test.local",
            schema_name="test",
        )
        self.root_user = User.objects.create_user(
            username="root",
            password="testpass",
            is_root=True,
            is_admin=True,
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            password="testpass",
            is_admin=True,
            is_root=False,
        )
        self.client = Client()

    def test_enabled_module_url_allowed(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=True,
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="test.local",
        )
        self.assertNotEqual(response.status_code, 403)

    def test_disabled_module_url_returns_403(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=False,
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="test.local",
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_module_row_is_disabled(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="test.local",
        )
        self.assertEqual(response.status_code, 403)

    def test_root_user_bypasses_module_gate(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=False,
        )

        self.client.force_login(self.root_user)
        response = self.client.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="test.local",
        )
        self.assertNotEqual(response.status_code, 403)

    def test_admin_user_does_not_bypass_module_gate(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=False,
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="test.local",
        )
        self.assertEqual(response.status_code, 403)

    def test_unmapped_url_not_affected(self):
        self.client.force_login(self.admin_user)

        SchoolModule.objects.create(
            school=self.school,
            module="academics",
            enabled=True,
        )

        response = self.client.get(
            reverse("core:dashboard"),
            HTTP_HOST="test.local",
        )
        self.assertNotEqual(response.status_code, 403)

    def test_module_reenabledment_restores_access(self):
        school_module = SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=False,
        )

        self.client.force_login(self.admin_user)

        response1 = self.client.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="test.local",
        )
        self.assertEqual(response1.status_code, 403)

        school_module.enabled = True
        school_module.save()

        response2 = self.client.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="test.local",
        )
        self.assertNotEqual(response2.status_code, 403)

    def test_tenant_isolation_different_module_states(self):
        school_a = School.objects.create(
            name="School A",
            domain="a.local",
            schema_name="a",
        )
        school_b = School.objects.create(
            name="School B",
            domain="b.local",
            schema_name="b",
        )

        SchoolModule.objects.create(
            school=school_a,
            module="finance",
            enabled=True,
        )
        SchoolModule.objects.create(
            school=school_b,
            module="finance",
            enabled=False,
        )

        admin_a = User.objects.create_user(
            username="admin_a",
            password="testpass",
            is_admin=True,
        )
        admin_b = User.objects.create_user(
            username="admin_b",
            password="testpass",
            is_admin=True,
        )

        client_a = Client()
        client_a.force_login(admin_a)
        response_a = client_a.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="a.local",
        )

        client_b = Client()
        client_b.force_login(admin_b)
        response_b = client_b.get(
            reverse("core:finance_dashboard"),
            HTTP_HOST="b.local",
        )

        self.assertNotEqual(response_a.status_code, 403)
        self.assertEqual(response_b.status_code, 403)


class TemplateNavigationTests(TestCase):
    """Test that enabled_modules context is available in templates."""

    def setUp(self):
        self.school = School.objects.create(
            name="Test School",
            domain="test.local",
            schema_name="test",
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            password="testpass",
            is_admin=True,
        )
        self.client = Client()

    def test_enabled_modules_in_context(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=True,
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse("core:dashboard"),
            HTTP_HOST="test.local",
        )

        self.assertIn("enabled_modules", response.context)
        enabled = response.context["enabled_modules"]
        self.assertIn("finance", enabled)

    def test_disabled_modules_not_in_context(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=False,
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse("core:dashboard"),
            HTTP_HOST="test.local",
        )

        self.assertIn("enabled_modules", response.context)
        enabled = response.context["enabled_modules"]
        self.assertNotIn("finance", enabled)


class BootstrapConsistencyTests(TestCase):
    """Test that bootstrap and dashboard agree on enabled modules."""

    def setUp(self):
        self.school = School.objects.create(
            name="Test School",
            domain="test.local",
            schema_name="test",
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            password="testpass",
            is_admin=True,
        )
        self.client = Client()

    def test_bootstrap_and_dashboard_agree(self):
        SchoolModule.objects.create(
            school=self.school,
            module="finance",
            enabled=True,
        )
        SchoolModule.objects.create(
            school=self.school,
            module="hr",
            enabled=False,
        )

        self.client.force_login(self.admin_user)

        from core.modules import enabled_modules_for
        dashboard_enabled = enabled_modules_for(self.school)

        response = self.client.get(
            "/api/v1/bootstrap/",
            HTTP_HOST="test.local",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        bootstrap_modules = data.get("modules", {})

        for module_key in MODULES:
            dashboard_enabled_bool = module_key in dashboard_enabled
            bootstrap_enabled_bool = bootstrap_modules.get(module_key, False)
            self.assertEqual(
                dashboard_enabled_bool,
                bootstrap_enabled_bool,
                f"Module {module_key} mismatch: dashboard={dashboard_enabled_bool}, bootstrap={bootstrap_enabled_bool}"
            )
