from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from core.models import School, User, Domain, SchoolSignature

class DomainInline(TabularInline):
    model = Domain
    extra = 1

@admin.register(School)
class SchoolAdmin(ModelAdmin):
    list_display = ("name", "code", "email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "email")
    search_help_text = "Search by school name, code, or email"

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
    inlines = [DomainInline]


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
