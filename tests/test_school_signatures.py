"""Regression tests for the multi-signature feature: SchoolSignature model,
SchoolSignatureService, and ReportGenerationService's fallback resolution
(template's own signature -> tenant default -> "Head of School" text only).
"""
import uuid

import pytest
from django.db import IntegrityError
from django.test import Client

from core.models import ReportTemplate, SchoolSignature, User
from core.services.exceptions import NotFoundException, ValidationException
from core.services.report_generation_service import ReportGenerationService
from core.services.school_signature_service import SchoolSignatureService


def _signature(school, **kwargs):
    defaults = dict(tenant=school, name=f"Sig-{uuid.uuid4().hex[:6]}", title="Head of School")
    defaults.update(kwargs)
    return SchoolSignature.objects.create(**defaults)


def _report_template(school, batch, academic_year, **kwargs):
    defaults = dict(
        tenant=school, name=f"Template-{uuid.uuid4().hex[:6]}", batch=batch,
        term="TERM 1", academic_year=academic_year,
    )
    defaults.update(kwargs)
    return ReportTemplate.objects.create(**defaults)


@pytest.mark.django_db
@pytest.mark.unit
class TestSchoolSignatureModel:
    def test_unique_default_constraint_per_tenant(self, school):
        _signature(school, is_default=True)
        with pytest.raises(IntegrityError):
            _signature(school, is_default=True)


@pytest.mark.django_db
@pytest.mark.unit
class TestSchoolSignatureService:
    def test_first_signature_becomes_default_automatically(self, school):
        svc = SchoolSignatureService(school)
        sig = svc.create(name="Mrs. A", title="Head of School")
        assert sig.is_default is True

    def test_second_signature_is_not_default(self, school):
        svc = SchoolSignatureService(school)
        svc.create(name="Mrs. A")
        second = svc.create(name="Mr. B")
        assert second.is_default is False

    def test_create_requires_name(self, school):
        svc = SchoolSignatureService(school)
        with pytest.raises(ValidationException):
            svc.create(name="")

    def test_set_default_switches_atomically(self, school):
        svc = SchoolSignatureService(school)
        first = svc.create(name="Mrs. A")
        second = svc.create(name="Mr. B")

        svc.set_default(second.id)

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.is_default is False
        assert second.is_default is True

    def test_delete_default_promotes_another(self, school):
        svc = SchoolSignatureService(school)
        first = svc.create(name="Mrs. A")
        second = svc.create(name="Mr. B")
        assert first.is_default is True

        svc.delete(first.id)

        second.refresh_from_db()
        assert second.is_default is True

    def test_delete_only_signature_leaves_no_default(self, school):
        svc = SchoolSignatureService(school)
        only = svc.create(name="Mrs. A")
        assert only.is_default is True

        svc.delete(only.id)

        assert SchoolSignature.objects.filter(tenant=school).count() == 0

    def test_delete_missing_signature_raises_not_found(self, school):
        svc = SchoolSignatureService(school)
        with pytest.raises(NotFoundException):
            svc.delete(uuid.uuid4())


@pytest.mark.django_db
@pytest.mark.unit
class TestReportGenerationSignatureResolution:
    def test_template_without_signature_falls_back_to_tenant_default(self, school, batch, academic_year):
        default_sig = _signature(school, name="Mrs. A", title="Head of Lower Primary", is_default=True)
        template = _report_template(school, batch, academic_year)

        data = ReportGenerationService(tenant=school)._get_school_data(template)

        assert data['signature_title'] == default_sig.title

    def test_template_with_explicit_signature_overrides_default(self, school, batch, academic_year):
        _signature(school, name="Mrs. A", title="Head of Lower Primary", is_default=True)
        secondary_head = _signature(school, name="Mr. B", title="Head of Secondary")
        template = _report_template(school, batch, academic_year, report_signature=secondary_head)

        data = ReportGenerationService(tenant=school)._get_school_data(template)

        assert data['signature_title'] == secondary_head.title

    def test_no_signatures_at_all_falls_back_to_generic_title(self, school, batch, academic_year):
        template = _report_template(school, batch, academic_year)

        data = ReportGenerationService(tenant=school)._get_school_data(template)

        assert data['signature_url'] is None
        assert data['signature_title'] == 'Head of School'


@pytest.mark.django_db
@pytest.mark.integration
class TestSchoolSignaturePages:
    """Requests go through TenantMainMiddleware, which resolves the `testserver`
    host to the session-shared school (see tests/conftest.py), so request.tenant
    is set for real rather than mocked — same pattern as test_attendance_api.py.
    """

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def tenant(self, school, domain):
        return school

    @pytest.fixture
    def user(self, tenant):
        suffix = uuid.uuid4().hex[:6]
        u = User(
            username=f"sigtest_{suffix}",
            email=f"sigtest_{suffix}@example.com",
            first_name="Sig", last_name="Test",
            is_admin=True,
        )
        u.set_password("testpass123")
        u.save()
        u.tenants.add(tenant)
        return u

    def test_school_settings_page_renders(self, client, tenant, user):
        client.force_login(user)
        response = client.get('/configuration/school_settings/')
        assert response.status_code == 200

    def test_report_template_list_page_renders(self, client, tenant, user):
        client.force_login(user)
        response = client.get('/reports/templates/')
        assert response.status_code == 200

    def test_add_signature_via_settings_page(self, client, tenant, user):
        client.force_login(user)
        response = client.post('/configuration/school_settings/', {
            'action': 'add_signature',
            'name': 'Mrs. Test Head',
            'title': 'Head of Lower Primary',
            'section_label': 'Lower Primary',
        })
        assert response.status_code == 302
        assert SchoolSignature.objects.filter(tenant=tenant, name='Mrs. Test Head').exists()

    def test_report_template_create_api_accepts_signature_id(self, client, tenant, user, batch, academic_year):
        client.force_login(user)
        sig = _signature(tenant, name="Mrs. Test Head")
        response = client.post('/api/reports/create-template/', {
            'name': 'Sig Test Template',
            'batch_id': str(batch.id),
            'course_id': str(batch.course_id),
            'term': 'TERM 1',
            'academic_year_id': str(academic_year.id),
            'report_signature_id': str(sig.id),
        })
        assert response.status_code == 200
        assert response.json().get('success') is True
        template = ReportTemplate.objects.get(id=response.json()['template_id'])
        assert template.report_signature_id == sig.id
