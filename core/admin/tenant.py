from django.contrib import admin, messages
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from core.models import School, User, Domain, SchoolSignature, SchoolModule
from core.modules import MODULES

class DomainInline(TabularInline):
    model = Domain
    extra = 1


class SchoolModuleInline(TabularInline):
    """Inline editor for SchoolModule records within a School admin page.

    Platform operators can enable/disable modules for a school and configure
    module-specific settings without leaving the School detail page. The
    module field is a dropdown constrained to core.modules.MODULES (see
    SchoolModule.module choices), so operators can add rows for modules that
    don't exist yet for a school without needing to know exact key spelling.
    """
    model = SchoolModule
    extra = 0
    fields = ("module", "enabled", "configuration")


def _provision_all_modules(schools):
    """Ensure every school has a SchoolModule row for every registered module key.
    Missing rows are created enabled by default; existing rows are left untouched.
    Mirrors `manage.py provision_school_modules`.
    """
    created = 0
    for school in schools:
        for module_key in MODULES.keys():
            _, was_created = SchoolModule.objects.get_or_create(
                school=school, module=module_key, defaults={"enabled": True}
            )
            if was_created:
                created += 1
    return created


@admin.register(School)
class SchoolAdmin(ModelAdmin):
    list_display = ("name", "code", "email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "email")
    search_help_text = "Search by school name, code, or email"
    actions = ["provision_missing_modules"]

    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "code", "is_active"),
        }),
        ("Contact Details", {
            "fields": ("email", "phone", "address_line1", "city", "country"),
        }),
        ("Branding & Assets", {
            "fields": ("logo", "logo_secondary", "report_title", "footer_quote"),
            "classes": ("collapse",),
        }),
    )
    inlines = [DomainInline, SchoolModuleInline]

    @admin.action(description="Provision missing modules (create rows, enabled by default, for all module keys)")
    def provision_missing_modules(self, request, queryset):
        created = _provision_all_modules(queryset)
        if created:
            self.message_user(
                request,
                f"Created {created} missing module row(s), enabled by default. "
                f"Open each school to toggle modules on/off.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "Every selected school already has a row for every module.",
                level=messages.INFO,
            )


@admin.register(SchoolModule)
class SchoolModuleAdmin(ModelAdmin):
    """Module enablement administration.

    Platform operators can enable/disable product features (HR, Finance,
    Hostel, etc.) for each school, and configure module-specific settings
    without code changes.
    """
    list_display = ("school", "module", "enabled", "updated_at")
    list_filter = ("enabled", "module")
    search_fields = ("school__name", "school__code", "module")
    autocomplete_fields = ("school",)
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


@admin.register(SchoolSignature)
class SchoolSignatureAdmin(ModelAdmin):
    list_display = ("name", "title", "tenant", "is_default")
    list_filter = ("is_default",)
    search_fields = ("name", "title", "tenant__name")
    autocomplete_fields = ("tenant",)


@admin.register(Domain)
class DomainAdmin(ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain",)
    autocomplete_fields = ("tenant",)


@admin.register(User)
class UserAdmin(ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ("username", "full_name", "email", "is_active", "is_admin", "last_login")
    list_filter = ("is_active", "is_admin")
    search_fields = ("username", "email", "first_name", "last_name")
    readonly_fields = ("last_login", "created_at", "updated_at")
    filter_horizontal = ("tenants",)

    fieldsets = (
        ("Account", {"classes": ["tab"], "fields": ("username", "password")}),
        ("Personal info", {"classes": ["tab"], "fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"classes": ["tab"], "fields": ("is_active", "is_admin", "password_change_required")}),
        ("Tenants", {"classes": ["tab"], "fields": ("tenants",)}),
        ("Important dates", {"classes": ["tab"], "fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "email", "first_name", "last_name",
                "password1", "password2", "is_admin", "is_active", "tenants",
            ),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        # unfold's ModelAdmin (like Django's base ModelAdmin) has no concept of
        # a separate add_form - it always builds from `self.form`. Only
        # django.contrib.auth.admin.UserAdmin special-cases this, and we don't
        # subclass that, so we replicate it here.
        if obj is None:
            kwargs.setdefault("form", self.add_form)
        return super().get_form(request, obj, **kwargs)
