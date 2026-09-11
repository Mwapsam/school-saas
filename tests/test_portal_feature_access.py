"""PortalFeatureRequired — parent endpoints gated by Configuration -> Feature Access."""
import uuid

import pytest
from django.test import Client

from core.models import Guardian, PortalFeatureAccess, StudentGuardianRelation, User


@pytest.fixture
def parent(db, school):
    u = User(username=f"parent_{uuid.uuid4().hex[:6]}", email=f"p_{uuid.uuid4().hex[:6]}@example.com")
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    g = Guardian.objects.create(
        tenant=school, first_name="Pat", last_name="Parent", relation="Mother",
        is_active=True, user=u, mobile_phone="0970000000",
    )
    return u, g


@pytest.fixture
def parent_client(parent, domain):
    c = Client()
    c.force_login(parent[0])
    return c


@pytest.fixture
def child_of_parent(db, school, batch, student, parent):
    StudentGuardianRelation.objects.create(
        tenant=school, school=school, student=student, guardian=parent[1],
        relation="Mother", is_immediate_contact=True,
    )
    return student


@pytest.mark.django_db
class TestFeatureAccessGate:
    def _attendance_url(self, child):
        return f"/api/portal/parent/children/{child.id}/attendance/"

    def test_enabled_by_default(self, parent_client, child_of_parent):
        # No PortalFeatureAccess row -> feature is on.
        resp = parent_client.get(self._attendance_url(child_of_parent))
        assert resp.status_code == 200

    def test_disabled_returns_403_with_code(self, parent_client, child_of_parent, school):
        PortalFeatureAccess.objects.create(
            tenant=school, feature="attendance", is_enabled=False,
        )
        resp = parent_client.get(self._attendance_url(child_of_parent))
        assert resp.status_code == 403
        # DRF renders PermissionDenied as {"detail": ...}; the machine-readable
        # code lives on the exception (exc.get_codes()), not the response body.
        assert "not available" in resp.json()["detail"].lower()

    def test_me_endpoint_exposes_features_map(self, parent_client, school):
        PortalFeatureAccess.objects.create(
            tenant=school, feature="invoices", is_enabled=False,
        )
        data = parent_client.get("/api/portal/auth/me/").json()
        assert data["features"]["invoices"] is False
        assert data["features"]["attendance"] is True  # default
