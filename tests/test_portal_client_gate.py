"""portal.client_gate.check_client_app — X-Client-App header enforcement."""
import pytest
from rest_framework.test import APIRequestFactory

from core.models import ClientApp
from portal.client_gate import _parse_version, check_client_app

rf = APIRequestFactory()


def _req(school, **headers):
    r = rf.get("/api/portal/auth/login/", **headers)
    r.tenant = school
    return r


def test_parse_version_orders_numerically():
    assert _parse_version("1.4.0") < _parse_version("1.10.0")
    assert _parse_version("2.0") > _parse_version("1.99.99")
    assert _parse_version("1.2.3") == _parse_version("1.2.3")
    assert _parse_version("") == (0,)


@pytest.mark.django_db
class TestCheckClientApp:
    def test_no_header_passes(self, school):
        assert check_client_app(_req(school)) is None

    def test_unknown_slug_passes(self, school):
        r = _req(school, HTTP_X_CLIENT_APP="never-registered")
        assert check_client_app(r) is None

    def test_disabled_client_is_403(self, school):
        ClientApp.objects.create(
            tenant=school, name="Parent App", slug="parent-app",
            platform="android", is_enabled=False,
        )
        resp = check_client_app(_req(school, HTTP_X_CLIENT_APP="parent-app"))
        assert resp is not None and resp.status_code == 403
        assert resp.data["code"] == "client_disabled"

    def test_below_min_version_is_426(self, school):
        ClientApp.objects.create(
            tenant=school, name="Parent App", slug="parent-app",
            platform="android", is_enabled=True, min_supported_version="1.5.0",
        )
        resp = check_client_app(_req(
            school, HTTP_X_CLIENT_APP="parent-app", HTTP_X_CLIENT_APP_VERSION="1.4.9",
        ))
        assert resp is not None and resp.status_code == 426
        assert resp.data["code"] == "upgrade_required"

    def test_ok_version_passes_and_stamps_last_seen(self, school):
        app = ClientApp.objects.create(
            tenant=school, name="Parent App", slug="parent-app",
            platform="android", is_enabled=True, min_supported_version="1.5.0",
        )
        resp = check_client_app(_req(
            school, HTTP_X_CLIENT_APP="parent-app", HTTP_X_CLIENT_APP_VERSION="1.5.0",
        ))
        assert resp is None
        app.refresh_from_db()
        assert app.last_seen_at is not None

    def test_no_tenant_passes(self):
        r = rf.get("/")
        r.tenant = None
        assert check_client_app(r) is None
