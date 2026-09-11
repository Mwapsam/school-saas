"""Admin registrations for the Configuration module models
(see ``core/view_modules/configuration_views.py`` for the staff-facing screens).
"""
from django.contrib import admin
from unfold.admin import ModelAdmin

from core.models import (
    ClientApp,
    DocumentCategory,
    NotificationRule,
    PortalFeatureAccess,
    StudentDocument,
    StudentExemption,
    TerminologyOverride,
)


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(ModelAdmin):
    list_display = ("name", "code", "is_required", "is_active", "display_order", "tenant")
    list_filter = ("is_active", "is_required", "tenant")
    search_fields = ("name", "code")
    ordering = ("display_order", "name")


@admin.register(StudentDocument)
class StudentDocumentAdmin(ModelAdmin):
    list_display = ("student", "category", "original_filename", "uploaded_at", "tenant")
    list_filter = ("category", "tenant")
    search_fields = ("student__first_name", "student__last_name", "original_filename", "note")
    autocomplete_fields = ("student", "category")
    readonly_fields = ("uploaded_at",)


@admin.register(PortalFeatureAccess)
class PortalFeatureAccessAdmin(ModelAdmin):
    list_display = ("feature", "is_enabled", "tenant")
    list_filter = ("is_enabled", "feature", "tenant")


@admin.register(NotificationRule)
class NotificationRuleAdmin(ModelAdmin):
    list_display = (
        "event", "audience", "is_active",
        "send_sms", "send_email", "send_push", "send_in_app", "tenant",
    )
    list_filter = ("event", "audience", "is_active", "tenant")


@admin.register(StudentExemption)
class StudentExemptionAdmin(ModelAdmin):
    list_display = ("student", "exemption_type", "academic_year", "is_active", "tenant")
    list_filter = ("exemption_type", "is_active", "academic_year", "tenant")
    search_fields = ("student__first_name", "student__last_name", "reason")
    autocomplete_fields = ("student", "academic_year")


@admin.register(TerminologyOverride)
class TerminologyOverrideAdmin(ModelAdmin):
    list_display = ("term", "replacement", "replacement_plural", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("term", "replacement")


@admin.register(ClientApp)
class ClientAppAdmin(ModelAdmin):
    list_display = (
        "name", "slug", "platform", "is_enabled",
        "min_supported_version", "last_seen_at", "tenant",
    )
    list_filter = ("platform", "is_enabled", "tenant")
    search_fields = ("name", "slug")
    readonly_fields = ("last_seen_at",)
