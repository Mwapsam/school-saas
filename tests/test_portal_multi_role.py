"""
Multi-role portal access: one account may be teacher + parent (+ librarian) at
once. Covers portal.roles.resolve_roles and the portal permission classes.
"""
import uuid
import pytest
from datetime import date

from django.test import TestCase, RequestFactory

from core.models import (
    School, Employee, Guardian, Student, StudentGuardianRelation, User,
    Library, LibraryStaff,
)
from portal.roles import resolve_roles, resolve_role
from portal.permissions import IsParent, IsTeacher, IsLibrarian, IsPortalUser


@pytest.mark.django_db
class MultiRolePortalTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.sfx = uuid.uuid4().hex[:8]
        self.school = School.objects.create(
            name="MR School",
            code=f"MR{self.sfx[:4].upper()}",
            schema_name=f"test_school_mr_{self.sfx}",
        )
        # One login, two profiles: an active Employee and an active Guardian.
        self.user = User.objects.create(
            username=f"jbanda_{self.sfx}",
            email=f"jbanda_{self.sfx}@example.com",
            first_name="Joyce",
            last_name="Banda",
            is_admin=False,
        )
        self.user.set_password("pw12345")
        self.user.save()
        self.school.add_user(self.user) if hasattr(self.school, "add_user") else None

        self.employee = Employee.objects.create(
            tenant=self.school,
            first_name="Joyce",
            last_name="Banda",
            employee_number=f"EMP-{self.sfx}",
            joining_date=date(2024, 1, 1),
            gender=True,
            status=True,
            user=self.user,
        )
        self.guardian = Guardian.objects.create(
            tenant=self.school,
            first_name="Joyce",
            last_name="Banda",
            relation="Mother",
            is_active=True,
            user=self.user,
        )

    def _request(self):
        req = self.factory.get("/api/portal/anything/")
        req.user = self.user
        return req

    def test_resolve_roles_returns_both(self):
        rs = resolve_roles(self.user)
        assert rs.roles == frozenset({"teacher", "parent"})
        assert rs.primary == "teacher"
        assert rs.is_portal_user is True
        assert rs.profile_for("teacher").id == self.employee.id
        assert rs.profile_for("parent").id == self.guardian.id

    def test_adding_library_assignment_adds_librarian(self):
        lib = Library.objects.create(tenant=self.school, name="Main", is_active=True)
        LibraryStaff.objects.create(
            tenant=self.school, employee=self.employee, library=lib, is_active=True
        )
        rs = resolve_roles(self.user)
        assert rs.roles == frozenset({"teacher", "parent", "librarian"})
        assert rs.primary == "librarian"

    def test_parent_permission_scopes_context_to_guardian(self):
        req = self._request()
        assert IsParent().has_permission(req, None) is True
        assert req.role_context.role == "parent"
        assert req.role_context.profile.id == self.guardian.id

    def test_teacher_permission_scopes_context_to_employee(self):
        req = self._request()
        assert IsTeacher().has_permission(req, None) is True
        assert req.role_context.role == "teacher"
        assert req.role_context.profile.id == self.employee.id

    def test_librarian_permission_denied_without_assignment(self):
        req = self._request()
        assert IsLibrarian().has_permission(req, None) is False

    def test_is_portal_user_true(self):
        req = self._request()
        assert IsPortalUser().has_permission(req, None) is True

    def test_single_role_teacher_unchanged(self):
        self.guardian.delete()
        # Re-fetch so stale reverse-OneToOne caches don't mask the delete
        # (a real request always resolves against a fresh User instance).
        user = User.objects.get(pk=self.user.pk)
        rs = resolve_roles(user)
        assert rs.roles == frozenset({"teacher"})
        assert resolve_role(user).role == "teacher"

    def test_admin_only_account_not_portal_user(self):
        self.employee.delete()
        self.guardian.delete()
        self.user.is_admin = True
        self.user.save()
        user = User.objects.get(pk=self.user.pk)
        rs = resolve_roles(user)
        assert rs.roles == frozenset({"admin"})
        assert rs.is_portal_user is False
