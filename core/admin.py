"""
Django Unfold admin configuration for core models.

Registers models with Unfold (the modern admin interface used by platform operators
for multi-tenant management). School, User, Domain, and SchoolModule are managed here.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import School, SchoolModule, User, Domain


class SchoolModuleInline(TabularInline):
    """Inline editor for SchoolModule records within a School admin page.

    Platform operators can quickly enable/disable modules for a school and configure
    module-specific settings (e.g., transport fleet management options) without
    leaving the School detail page.
    """
    model = SchoolModule
    extra = 0
    fields = ("module", "enabled", "configuration")
    readonly_fields = ("module",)  # Module key shouldn't be changed after creation


@admin.register(School)
class SchoolAdmin(ModelAdmin):
    """Multi-tenant School model administration.

    Platform operators manage tenant setup here: branding (logo, name, address),
    module enablement (what features are available), and basic configuration.
    """
    list_display = (
        "name",
        "code",
        "is_active",
        "phone",
        "email",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "code", "email")
    fieldsets = (
        ("Identity", {
            "fields": ("name", "code", "is_active"),
        }),
        ("Branding", {
            "fields": ("logo", "logo_secondary", "report_title", "footer_quote"),
            "description": "Per-school branding shown in reports and admin UI",
        }),
        ("Contact Information", {
            "fields": ("phone", "email", "website", "fax"),
        }),
        ("Address", {
            "fields": ("address_line1", "address_line2", "city", "state", "pin_code", "country"),
        }),
        ("Finance Configuration", {
            "fields": (
                "operations_manager_name",
                "fee_note_early_bird_discount_enabled",
                "fee_note_early_bird_discount_percent",
                "fee_note_terms",
            ),
            "description": "Default fee note settings applied to invoices",
        }),
    )
    inlines = [SchoolModuleInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(SchoolModule)
class SchoolModuleAdmin(ModelAdmin):
    """Module enablement administration.

    Platform operators can enable/disable product features (HR, Finance, Hostel, etc.)
    for each school, and configure module-specific settings without code changes.
    """
    list_display = (
        "school",
        "module",
        "enabled",
        "updated_at",
    )
    list_filter = ("enabled", "module", "updated_at")
    search_fields = ("school__name", "school__code", "module")
    fieldsets = (
        ("Module Assignment", {
            "fields": ("school", "module", "enabled"),
        }),
        ("Configuration", {
            "fields": ("configuration",),
            "description": "Module-specific settings (JSON). Leave empty for defaults.",
        }),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class UserAdmin(ModelAdmin):
    """User management for platform and tenant staff.

    Platform operators manage global staff accounts and tenant users here.
    """
    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "is_admin",
    )
    list_filter = ("is_active", "is_admin", "created_at")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = (
        ("Account", {
            "fields": ("username", "email", "password_change_required"),
        }),
        ("Personal Info", {
            "fields": ("first_name", "last_name"),
        }),
        ("Permissions", {
            "fields": ("is_active", "is_admin", "is_root"),
            "description": "is_admin: staff dashboard access. is_root: bypass all RBAC (break-glass only).",
        }),
    )
    readonly_fields = ("created_at", "updated_at", "last_login")


@admin.register(Domain)
class DomainAdmin(ModelAdmin):
    """Domain registration for multi-tenant routing.

    Maps subdomains/domains to School tenants so users can access their school
    via tenant-specific URLs (e.g., pinewood.platform.com → Pinewood school).
    """
    list_display = (
        "domain",
        "tenant",
        "is_primary",
    )
    list_filter = ("is_primary", "created_at")
    search_fields = ("domain", "tenant__name")
    readonly_fields = ("created_at", "updated_at")
