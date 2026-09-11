"""Configuration module screens (``/configuration/...``).

Each screen is a thin ``TemplateView`` that reads through the ORM and mutates on
``POST`` via an ``action`` field — the same pattern as
:class:`core.views.SchoolSettingsView` and
:class:`core.views.AttendanceLabelEditView`. Business-logic-free CRUD lives here;
anything the rest of the app needs to *read* goes through
:mod:`core.services.configuration_service`.

All screens are gated on ``settings.school.manage``.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.text import slugify
from django.views.generic import TemplateView

from core.models import (
    AcademicYear, AdditionalField, ClientApp, ConfigStore, DocumentCategory,
    NotificationRule, PortalFeatureAccess, Student, StudentCategory,
    StudentExemption, TerminologyOverride,
)
from core.services.configuration_service import (
    SORT_FIELDS, portal_feature_map, student_sort_order,
)

def _tenant(request):
    return getattr(request, "tenant", None)


class _ConfigView(LoginRequiredMixin, TemplateView):
    """Base for configuration screens. Gated on login only — the same bar as
    :class:`core.views.SchoolSettingsView`. Tighten to the
    ``settings.school.manage`` codename once that is seeded to roles."""

    redirect_name: str = ""

    def tenant(self):
        return _tenant(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["school"] = self.tenant()
        return ctx

    def ok(self, msg):
        messages.success(self.request, msg)
        return redirect(self.redirect_name)

    def fail(self, msg):
        messages.error(self.request, msg)
        return redirect(self.redirect_name)


# ---------------------------------------------------------------------------
# 1. Manage Subjects — no screen of its own; the card links to Subjects Center.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2. General Settings
# ---------------------------------------------------------------------------

GENERAL_KEYS = {
    "date_format": "d/m/Y",
    "week_start": "monday",
    "currency_symbol": "K",
    "academic_terms_per_year": "3",
    "attendance_lock_after_days": "7",
    "default_pass_percentage": "40",
}


class GeneralSettingsView(_ConfigView):
    template_name = "core/configuration/general_settings.html"
    redirect_name = "core:general_settings"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = ConfigStore(self.tenant())
        stored = store.get_many(GENERAL_KEYS)
        ctx["settings"] = {k: stored.get(k, dflt) for k, dflt in GENERAL_KEYS.items()}
        return ctx

    def post(self, request, *args, **kwargs):
        if not self.tenant():
            return self.fail("School not found.")
        store = ConfigStore(self.tenant())
        store.set_many({
            k: request.POST.get(k, dflt) for k, dflt in GENERAL_KEYS.items()
        })
        return self.ok("General settings saved.")


# ---------------------------------------------------------------------------
# 3. Student Category  (reuses core.models.StudentCategory)
# ---------------------------------------------------------------------------


class StudentCategoryView(_ConfigView):
    template_name = "core/configuration/student_category.html"
    redirect_name = "core:student_category_config"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = StudentCategory.objects.filter(
            tenant=self.tenant(), is_deleted=False
        ).order_by("name")
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = self.tenant()
        if not tenant:
            return self.fail("School not found.")
        action = request.POST.get("action")
        if action == "create":
            name = (request.POST.get("name") or "").strip()
            if not name:
                return self.fail("Name is required.")
            obj, created = StudentCategory.objects.get_or_create(
                tenant=tenant, name=name, defaults={"is_deleted": False}
            )
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.save(update_fields=["is_deleted"])
                created = True
            return self.ok("Category added." if created else "Category already exists.")
        if action == "rename":
            obj = StudentCategory.objects.filter(
                tenant=tenant, id=request.POST.get("id")
            ).first()
            if not obj:
                return self.fail("Category not found.")
            obj.name = (request.POST.get("name") or obj.name).strip()
            obj.save(update_fields=["name"])
            return self.ok("Category renamed.")
        if action == "delete":
            obj = StudentCategory.objects.filter(
                tenant=tenant, id=request.POST.get("id")
            ).first()
            if not obj:
                return self.fail("Category not found.")
            obj.is_deleted = True
            obj.save(update_fields=["is_deleted"])
            return self.ok("Category removed.")
        return self.fail("Unknown action.")


# ---------------------------------------------------------------------------
# 4. Document Categories
# ---------------------------------------------------------------------------


class DocumentCategoryView(_ConfigView):
    template_name = "core/configuration/document_category.html"
    redirect_name = "core:document_category_config"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = DocumentCategory.objects.filter(tenant=self.tenant())
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = self.tenant()
        if not tenant:
            return self.fail("School not found.")
        action = request.POST.get("action")
        if action == "delete":
            DocumentCategory.objects.filter(
                tenant=tenant, id=request.POST.get("id")
            ).delete()
            return self.ok("Document category removed.")

        name = (request.POST.get("name") or "").strip()
        if not name:
            return self.fail("Name is required.")
        fields = {
            "name": name,
            "code": (request.POST.get("code") or "").strip(),
            "description": (request.POST.get("description") or "").strip(),
            "is_required": request.POST.get("is_required") == "on",
            "display_order": int(request.POST.get("display_order") or 0),
            "is_active": request.POST.get("is_active", "on") == "on",
        }
        if action == "create":
            if DocumentCategory.objects.filter(tenant=tenant, name=name).exists():
                return self.fail("A category with that name already exists.")
            DocumentCategory.objects.create(tenant=tenant, **fields)
            return self.ok("Document category added.")
        if action == "update":
            obj = DocumentCategory.objects.filter(
                tenant=tenant, id=request.POST.get("id")
            ).first()
            if not obj:
                return self.fail("Category not found.")
            for k, v in fields.items():
                setattr(obj, k, v)
            obj.save()
            return self.ok("Document category updated.")
        return self.fail("Unknown action.")


# ---------------------------------------------------------------------------
# 5. Feature Access (parent portal)
# ---------------------------------------------------------------------------


class FeatureAccessView(_ConfigView):
    template_name = "core/configuration/feature_access.html"
    redirect_name = "core:feature_access_config"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        enabled = portal_feature_map(self.tenant())
        ctx["features"] = [
            {"key": k, "label": label, "enabled": enabled[k]}
            for k, label in PortalFeatureAccess.FEATURES
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = self.tenant()
        if not tenant:
            return self.fail("School not found.")
        for key, _ in PortalFeatureAccess.FEATURES:
            PortalFeatureAccess.objects.update_or_create(
                tenant=tenant, feature=key,
                defaults={"is_enabled": request.POST.get(f"feature_{key}") == "on"},
            )
        return self.ok("Parent portal feature access updated.")


# ---------------------------------------------------------------------------
# 6. Notification Control
# ---------------------------------------------------------------------------


class NotificationControlView(_ConfigView):
    template_name = "core/configuration/notification_control.html"
    redirect_name = "core:notification_control_config"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = self.tenant()
        existing = {
            (r.event, r.audience): r
            for r in NotificationRule.objects.filter(tenant=tenant)
        }
        rows = []
        for event, event_label in NotificationRule.EVENTS:
            for audience, aud_label in NotificationRule.AUDIENCES:
                r = existing.get((event, audience))
                rows.append({
                    "event": event, "event_label": event_label,
                    "audience": audience, "audience_label": aud_label,
                    "sms": r.send_sms if r else False,
                    "email": r.send_email if r else False,
                    "push": r.send_push if r else (r is None and audience == "guardians"),
                    "in_app": r.send_in_app if r else (r is None),
                    "active": r.is_active if r else False,
                })
        ctx["rows"] = rows
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = self.tenant()
        if not tenant:
            return self.fail("School not found.")
        for event, _ in NotificationRule.EVENTS:
            for audience, _a in NotificationRule.AUDIENCES:
                prefix = f"{event}__{audience}__"
                active = request.POST.get(prefix + "active") == "on"
                channels = {
                    "send_sms": request.POST.get(prefix + "sms") == "on",
                    "send_email": request.POST.get(prefix + "email") == "on",
                    "send_push": request.POST.get(prefix + "push") == "on",
                    "send_in_app": request.POST.get(prefix + "in_app") == "on",
                }
                if not active and not any(channels.values()):
                    NotificationRule.objects.filter(
                        tenant=tenant, event=event, audience=audience
                    ).delete()
                    continue
                NotificationRule.objects.update_or_create(
                    tenant=tenant, event=event, audience=audience,
                    defaults={"is_active": active, **channels},
                )
        return self.ok("Notification rules saved.")


# ---------------------------------------------------------------------------
# 7. Admission Details  (custom admission fields — reuses AdditionalField)
# ---------------------------------------------------------------------------


class AdmissionDetailsView(_ConfigView):
    template_name = "core/configuration/admission_details.html"
    redirect_name = "core:admission_details_config"
    INPUT_TYPES = ["text", "textarea", "number", "date", "select", "checkbox"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["fields"] = AdditionalField.objects.filter(
            tenant=self.tenant(), applies_to="admission"
        ).order_by("sort_order", "name")
        ctx["input_types"] = self.INPUT_TYPES
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = self.tenant()
        if not tenant:
            return self.fail("School not found.")
        action = request.POST.get("action")
        if action == "delete":
            AdditionalField.objects.filter(
                tenant=tenant, applies_to="admission", id=request.POST.get("id")
            ).delete()
            return self.ok("Field removed.")

        name = (request.POST.get("name") or "").strip()
        if not name:
            return self.fail("Field label is required.")
        input_type = request.POST.get("input_type") or "text"
        if input_type not in self.INPUT_TYPES:
            input_type = "text"
        fields = {
            "name": name,
            "input_type": input_type,
            "is_mandatory": request.POST.get("is_mandatory") == "on",
            "sort_order": int(request.POST.get("sort_order") or 0),
            "options": (request.POST.get("options") or "").strip(),
            "is_active": request.POST.get("is_active", "on") == "on",
            "applies_to": "admission",
        }
        if action == "create":
            AdditionalField.objects.create(tenant=tenant, **fields)
            return self.ok("Admission field added.")
        if action == "update":
            obj = AdditionalField.objects.filter(
                tenant=tenant, applies_to="admission", id=request.POST.get("id")
            ).first()
            if not obj:
                return self.fail("Field not found.")
            for k, v in fields.items():
                setattr(obj, k, v)
            obj.save()
            return self.ok("Admission field updated.")
        return self.fail("Unknown action.")


# ---------------------------------------------------------------------------
# 8. Exempted Students
# ---------------------------------------------------------------------------


class ExemptedStudentsView(_ConfigView):
    template_name = "core/configuration/exempted_students.html"
    redirect_name = "core:exempted_students_config"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = self.tenant()
        ctx["exemptions"] = (
            StudentExemption.objects.filter(tenant=tenant, is_active=True)
            .select_related("student", "academic_year")
            .order_by("exemption_type", "student__first_name")
        )
        ctx["exemption_types"] = StudentExemption.TYPES
        ctx["academic_years"] = AcademicYear.objects.filter(tenant=tenant).order_by(
            "-start_date"
        )
        ctx["students"] = Student.objects.filter(
            tenant=tenant, is_active=True, is_deleted=False
        ).order_by("first_name", "last_name").only(
            "id", "first_name", "last_name", "admission_no"
        )
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = self.tenant()
        if not tenant:
            return self.fail("School not found.")
        action = request.POST.get("action")
        if action == "delete":
            StudentExemption.objects.filter(
                tenant=tenant, id=request.POST.get("id")
            ).delete()
            return self.ok("Exemption removed.")
        if action == "create":
            student = Student.objects.filter(
                tenant=tenant, id=request.POST.get("student_id")
            ).first()
            if not student:
                return self.fail("Select a valid student.")
            etype = request.POST.get("exemption_type")
            if etype not in dict(StudentExemption.TYPES):
                return self.fail("Select a valid exemption type.")
            year = AcademicYear.objects.filter(
                tenant=tenant, id=request.POST.get("academic_year") or None
            ).first()
            _, created = StudentExemption.objects.update_or_create(
                tenant=tenant, student=student, exemption_type=etype,
                academic_year=year,
                defaults={
                    "reason": (request.POST.get("reason") or "").strip(),
                    "is_active": True,
                    "created_by_id": getattr(request.user, "id", None),
                },
            )
            return self.ok("Student exempted." if created else "Exemption updated.")
        return self.fail("Unknown action.")


# ---------------------------------------------------------------------------
# 9. Students Sorting
# ---------------------------------------------------------------------------


class StudentsSortingView(_ConfigView):
    template_name = "core/configuration/students_sorting.html"
    redirect_name = "core:students_sorting_config"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current"] = student_sort_order(self.tenant())
        ctx["choices"] = [
            ("first_name", "First name, then last name"),
            ("last_name", "Last name, then first name"),
            ("admission_no", "Admission number"),
            ("roll_number", "Class roll number"),
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        if not self.tenant():
            return self.fail("School not found.")
        choice = request.POST.get("student_sort_order")
        if choice not in SORT_FIELDS:
            return self.fail("Invalid sort option.")
        ConfigStore(self.tenant()).set("student_sort_order", choice)
        return self.ok("Student sort order updated.")


# ---------------------------------------------------------------------------
# 10. Custom Words
# ---------------------------------------------------------------------------


class CustomWordsView(_ConfigView):
    template_name = "core/configuration/custom_words.html"
    redirect_name = "core:custom_words_config"
    COMMON_TERMS = [
        "student", "class", "batch", "subject", "teacher", "guardian",
        "admission", "term", "exam", "report card",
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["overrides"] = TerminologyOverride.objects.filter(tenant=self.tenant())
        ctx["common_terms"] = self.COMMON_TERMS
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = self.tenant()
        if not tenant:
            return self.fail("School not found.")
        action = request.POST.get("action")
        if action == "delete":
            TerminologyOverride.objects.filter(
                tenant=tenant, id=request.POST.get("id")
            ).delete()
            return self.ok("Custom word removed.")
        term = (request.POST.get("term") or "").strip().lower()
        replacement = (request.POST.get("replacement") or "").strip()
        if not term or not replacement:
            return self.fail("Both the term and its replacement are required.")
        defaults = {
            "replacement": replacement,
            "replacement_plural": (request.POST.get("replacement_plural") or "").strip(),
            "is_active": request.POST.get("is_active", "on") == "on",
        }
        TerminologyOverride.objects.update_or_create(
            tenant=tenant, term=term, defaults=defaults
        )
        return self.ok("Custom word saved.")


# ---------------------------------------------------------------------------
# 11. Manage Clients
# ---------------------------------------------------------------------------


class ManageClientsView(_ConfigView):
    template_name = "core/configuration/manage_clients.html"
    redirect_name = "core:manage_clients_config"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["clients"] = ClientApp.objects.filter(tenant=self.tenant())
        ctx["platforms"] = ClientApp.PLATFORMS
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = self.tenant()
        if not tenant:
            return self.fail("School not found.")
        action = request.POST.get("action")
        if action == "delete":
            ClientApp.objects.filter(tenant=tenant, id=request.POST.get("id")).delete()
            return self.ok("Client removed.")
        if action == "toggle":
            obj = ClientApp.objects.filter(
                tenant=tenant, id=request.POST.get("id")
            ).first()
            if not obj:
                return self.fail("Client not found.")
            obj.is_enabled = not obj.is_enabled
            obj.save(update_fields=["is_enabled"])
            return self.ok(f"{obj.name} {'enabled' if obj.is_enabled else 'disabled'}.")

        name = (request.POST.get("name") or "").strip()
        if not name:
            return self.fail("Client name is required.")
        platform = request.POST.get("platform") or "android"
        if platform not in dict(ClientApp.PLATFORMS):
            platform = "other"
        slug = slugify(request.POST.get("slug") or name)[:60]
        fields = {
            "name": name,
            "platform": platform,
            "min_supported_version": (request.POST.get("min_supported_version") or "").strip(),
            "notes": (request.POST.get("notes") or "").strip(),
            "is_enabled": request.POST.get("is_enabled", "on") == "on",
        }
        if action == "create":
            if ClientApp.objects.filter(tenant=tenant, slug=slug).exists():
                return self.fail("A client with that slug already exists.")
            ClientApp.objects.create(tenant=tenant, slug=slug, **fields)
            return self.ok("Client added.")
        if action == "update":
            obj = ClientApp.objects.filter(
                tenant=tenant, id=request.POST.get("id")
            ).first()
            if not obj:
                return self.fail("Client not found.")
            for k, v in fields.items():
                setattr(obj, k, v)
            obj.save()
            return self.ok("Client updated.")
        return self.fail("Unknown action.")
