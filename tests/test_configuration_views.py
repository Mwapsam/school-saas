"""Configuration module staff screens (core/view_modules/configuration_views.py)."""
import pytest
from django.test import Client
from django.urls import reverse

from core.models import (
    ClientApp, ConfigStore, DocumentCategory, PortalFeatureAccess,
    StudentCategory, TerminologyOverride,
)


@pytest.fixture
def staff_client(db, user, school, domain):
    user.is_admin = True
    user.save(update_fields=["is_admin"])
    c = Client()
    c.force_login(user)
    return c


@pytest.mark.django_db
class TestStudentCategoryScreen:
    url = "/configuration/student-categories/"

    def test_get_renders(self, staff_client):
        assert staff_client.get(self.url).status_code == 200

    def test_create_rename_delete(self, staff_client, school):
        r = staff_client.post(self.url, {"action": "create", "name": "Scholarship"})
        assert r.status_code == 302
        cat = StudentCategory.objects.get(tenant=school, name="Scholarship")

        staff_client.post(self.url, {"action": "rename", "id": str(cat.id), "name": "Bursary"})
        cat.refresh_from_db()
        assert cat.name == "Bursary"

        staff_client.post(self.url, {"action": "delete", "id": str(cat.id)})
        cat.refresh_from_db()
        assert cat.is_deleted is True


@pytest.mark.django_db
class TestFeatureAccessScreen:
    url = "/configuration/feature-access/"

    def test_toggle_writes_rows(self, staff_client, school):
        # Post with only "attendance" on -> every other feature recorded as off.
        r = staff_client.post(self.url, {"feature_attendance": "on"})
        assert r.status_code == 302
        assert PortalFeatureAccess.objects.get(tenant=school, feature="attendance").is_enabled
        assert not PortalFeatureAccess.objects.get(tenant=school, feature="results").is_enabled


@pytest.mark.django_db
class TestStudentsSortingScreen:
    url = "/configuration/students-sorting/"

    def test_saves_valid_choice(self, staff_client, school):
        r = staff_client.post(self.url, {"student_sort_order": "admission_no"})
        assert r.status_code == 302
        assert ConfigStore(school).get("student_sort_order") == "admission_no"

    def test_rejects_invalid_choice(self, staff_client, school):
        staff_client.post(self.url, {"student_sort_order": "bogus"})
        assert ConfigStore(school).get("student_sort_order") in (None, "")


@pytest.mark.django_db
class TestCustomWordsScreen:
    url = "/configuration/custom-words/"

    def test_upsert(self, staff_client, school):
        staff_client.post(self.url, {
            "term": "Student", "replacement": "Pupil", "replacement_plural": "Pupils",
        })
        row = TerminologyOverride.objects.get(tenant=school, term="student")
        assert row.replacement == "Pupil"


@pytest.mark.django_db
class TestManageClientsScreen:
    url = "/configuration/manage-clients/"

    def test_create_and_toggle(self, staff_client, school):
        staff_client.post(self.url, {
            "action": "create", "name": "Parent App", "platform": "android",
        })
        app = ClientApp.objects.get(tenant=school, name="Parent App")
        assert app.is_enabled and app.slug == "parent-app"

        staff_client.post(self.url, {"action": "toggle", "id": str(app.id)})
        app.refresh_from_db()
        assert app.is_enabled is False


@pytest.mark.django_db
class TestDocumentCategoryScreen:
    url = "/configuration/document-categories/"

    def test_create(self, staff_client, school):
        staff_client.post(self.url, {
            "action": "create", "name": "Birth Certificate", "display_order": "1",
        })
        assert DocumentCategory.objects.filter(
            tenant=school, name="Birth Certificate"
        ).exists()


@pytest.mark.django_db
def test_configuration_urls_resolve():
    for name in [
        "general_settings", "student_category_config", "document_category_config",
        "feature_access_config", "notification_control_config",
        "admission_details_config", "exempted_students_config",
        "students_sorting_config", "custom_words_config", "manage_clients_config",
    ]:
        assert reverse(f"core:{name}").startswith("/configuration/")
