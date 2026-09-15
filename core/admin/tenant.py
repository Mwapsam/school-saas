from django import forms
from django.contrib import admin, messages
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from core.models import (
    School, User, Domain, SchoolSignature, SchoolModule,
    Role, RolePermission, UserRoleAssignment, DemoRequest,
)
from core.modules import MODULES
from core.authz.registry import PERMISSIONS

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
    fields = ("module", "module_description", "enabled", "configuration")
    readonly_fields = ("module_description",)

    def module_description(self, obj):
        """Display the module's description from the registry."""
        if obj.pk and obj.module:
            meta = MODULES.get(obj.module, {})
            description = meta.get("description", "")
            is_required = meta.get("required", False)
            required_badge = " [REQUIRED]" if is_required else ""
            return f"{description}{required_badge}"
        return "—"
    module_description.short_description = "Description"


def _provision_all_modules(schools):
    """Ensure every school has a SchoolModule row for every registered module key.
    Missing rows are created disabled by default — superuser must explicitly enable
    only the modules covered by that school's agreement. Existing rows are left untouched.
    Mirrors `manage.py provision_school_modules`.
    """
    created = 0
    for school in schools:
        for module_key in MODULES.keys():
            _, was_created = SchoolModule.objects.get_or_create(
                school=school, module=module_key, defaults={"enabled": False}
            )
            if was_created:
                created += 1
    return created


@admin.register(School)
class SchoolAdmin(ModelAdmin):
    """Payment collection is manual (invoiced outside the app) — `billing_status`,
    `plan_tier`, and `trial_ends_at` here are the record the operator maintains by
    hand, and the only thing `core.middleware.BillingAccessMiddleware` reads to
    decide whether the school's dashboard is reachable. Always update this when a
    payment lands or a trial is extended.
    """
    list_display = ("name", "code", "email", "billing_status", "plan_tier", "trial_ends_at", "is_active")
    list_filter = ("is_active", "billing_status", "plan_tier")
    search_fields = ("name", "code", "email")
    search_help_text = "Search by school name, code, or email"
    actions = [
        "provision_missing_modules",
        "mark_billing_active",
        "mark_billing_suspended",
    ]

    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "code", "is_active"),
        }),
        ("Billing & Subscription", {
            "fields": ("billing_status", "plan_tier", "trial_ends_at", "billing_notes"),
            "description": "Payment is collected manually. Set billing_status to 'suspended' or "
                           "'past_due' to block this school's dashboard immediately.",
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

    @admin.action(description="Provision missing modules (create rows, disabled by default, for all module keys)")
    def provision_missing_modules(self, request, queryset):
        created = _provision_all_modules(queryset)
        if created:
            self.message_user(
                request,
                f"Created {created} missing module row(s), disabled by default. "
                f"Open each school to manually enable only the modules in their agreement.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "Every selected school already has a row for every module.",
                level=messages.INFO,
            )

    @admin.action(description="Mark billing as active (payment received)")
    def mark_billing_active(self, request, queryset):
        updated = queryset.update(billing_status=School.BILLING_STATUS_ACTIVE)
        self.message_user(
            request,
            f"Marked {updated} school(s) as billing-active.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Suspend billing (payment overdue/cancelled)")
    def mark_billing_suspended(self, request, queryset):
        updated = queryset.update(billing_status=School.BILLING_STATUS_SUSPENDED)
        self.message_user(
            request,
            f"Suspended {updated} school(s) — their dashboard is now blocked.",
            level=messages.WARNING,
        )


@admin.register(SchoolModule)
class SchoolModuleAdmin(ModelAdmin):
    """Module enablement administration.

    Platform operators can enable/disable product features (HR, Finance,
    Hostel, etc.) for each school, and configure module-specific settings
    without code changes. Module access is tied to what each school has paid for
    in their agreement — always manually enable only the modules they're contracted to use.
    """
    list_display = ("school", "module_label", "module_category", "is_required_badge", "enabled", "updated_at")
    list_filter = ("enabled", "module")
    search_fields = ("school__name", "school__code", "module")
    autocomplete_fields = ("school",)
    ordering = ("school", "module")
    fieldsets = (
        ("Module Assignment", {
            "fields": ("school", "module", "module_description", "enabled"),
        }),
        ("Configuration", {
            "fields": ("configuration",),
            "description": "Module-specific settings (JSON). Leave empty for defaults.",
        }),
    )
    readonly_fields = ("created_at", "updated_at", "module_description")

    def module_label(self, obj):
        """Display the module's human-readable label."""
        meta = MODULES.get(obj.module, {})
        return meta.get("label", obj.module)
    module_label.short_description = "Module"

    def module_category(self, obj):
        """Display the module's category (core, enrollment, operations, engagement)."""
        meta = MODULES.get(obj.module, {})
        return meta.get("category", "—")
    module_category.short_description = "Category"

    def is_required_badge(self, obj):
        """Display a badge if this module is required."""
        if MODULES.get(obj.module, {}).get("required", False):
            return "[REQUIRED]"
        return "—"
    is_required_badge.short_description = "Required"

    def module_description(self, obj):
        """Display the module's description from the registry."""
        meta = MODULES.get(obj.module, {})
        return meta.get("description", "No description available")
    module_description.short_description = "Description"


@admin.register(DemoRequest)
class DemoRequestAdmin(ModelAdmin):
    """Read/triage view of prospective-customer demo requests. Conversion into
    a provisioned tenant is a self-contained flow (provision_school +
    create_tenant_superuser + default modules + trial billing status) driven
    from the admin frontend's Convert action, not from here — this page is
    for visibility and manual status/notes triage only.
    """
    list_display = ("full_name", "email", "school_name", "status", "converted_school", "created_at")
    list_filter = ("status",)
    search_fields = ("full_name", "email", "school_name")
    readonly_fields = ("converted_school", "created_at", "updated_at")
    fieldsets = (
        ("Request", {
            "fields": ("full_name", "email", "phone", "school_name", "message"),
        }),
        ("Triage", {
            "fields": ("status", "notes"),
        }),
        ("Conversion", {
            "fields": ("converted_school",),
        }),
    )


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
        ("Permissions", {"classes": ["tab"], "fields": ("is_active", "is_admin", "is_root", "password_change_required")}),
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


class RolePermissionForm(forms.ModelForm):
    """Permission codename form with dropdown choices from canonical registry.

    Displays canonical codenames (from core.authz.registry.PERMISSIONS) as a
    dropdown with human-readable descriptions. Excludes legacy codenames to
    encourage migration to canonical names.
    """
    # Build choices from canonical permissions only (no legacy names)
    CODENAME_CHOICES = [
        (codename, f"{codename} — {description}")
        for codename, description in PERMISSIONS.items()
        # Filter to DRF API layer (lines 93-167 in registry.py)
        if "API" in description or codename.startswith(("students.", "academics.", "finance.", "hr.", "admissions.", "hostel.", "transport.", "library."))
    ]

    codename = forms.ChoiceField(
        choices=CODENAME_CHOICES,
        label="Permission (Canonical)",
        help_text="Select from canonical permission codenames. Legacy codenames (singular) are deprecated.",
    )

    class Meta:
        model = RolePermission
        fields = ("codename",)


class RolePermissionInline(TabularInline):
    """Inline editor for the permission codenames granted to a Role.

    `codename` is a dropdown sourced from core.authz.registry.PERMISSIONS —
    the same registry that actually enforces access (core.authz.access), so
    an operator can't grant a typo'd or non-existent codename.

    Only shows canonical (DRF API) codenames to encourage migration away
    from legacy singular codenames.
    """
    model = RolePermission
    extra = 0
    fields = ("codename",)
    form = RolePermissionForm


@admin.register(Role)
class RoleAdmin(ModelAdmin):
    """Permission role administration.

    A Role is a named bag of permission codenames (see RolePermissionInline);
    assigning a Role to a user (via UserRoleAssignment) is what actually
    grants that user access to gated API endpoints — module enablement
    (SchoolModule) only controls whether a feature area exists for the
    school at all, it does not grant any user access to it.

    CODENAME NAMING CONVENTION (Phase 2.1+):
    - Canonical (NEW): plural domain.resource.action format
      Examples: hr.employees.view, finance.fees.manage, students.manage
    - Legacy (DEPRECATED): singular format, kept for backward compatibility
      Examples: hr.employee.view, finance.fees.view (old)

    New roles MUST use canonical codenames. Existing roles using legacy
    codenames should be migrated gradually via the inline editor below.
    """
    list_display = ("name", "slug", "is_system", "is_active", "permission_count")
    list_filter = ("is_system", "is_active")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RolePermissionInline]
    fieldsets = (
        ("Role", {
            "fields": ("name", "slug", "description", "is_active"),
        }),
        ("System", {
            "fields": ("is_system",),
            "description": "System roles are seeded per tenant and cannot be deleted, "
                           "but their permissions can still be edited.",
        }),
    )

    def permission_count(self, obj):
        """Display count of permissions assigned to this role."""
        return obj.rolepermission_set.count()
    permission_count.short_description = "Permissions"


class UserRoleAssignmentForm(forms.ModelForm):
    """UserRoleAssignment.user_id is a bare UUID (no DB FK - User lives in the
    shared/public schema, this row lives in a tenant schema). This form swaps
    it for a proper user-picker in the admin UI, storing the picked user's id
    back into user_id on save.
    """
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label="User",
        help_text="The staff login to grant this role to.",
    )

    class Meta:
        model = UserRoleAssignment
        fields = ("user", "role", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user_id:
            try:
                self.fields["user"].initial = User.objects.get(pk=self.instance.user_id)
            except User.DoesNotExist:
                pass

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user_id = self.cleaned_data["user"].id
        if commit:
            instance.save()
        return instance


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(ModelAdmin):
    """Grants a Role to a user within this tenant — this is what actually
    gives a logged-in user access to permission-gated API endpoints.
    """
    form = UserRoleAssignmentForm
    list_display = ("get_username", "role", "is_active", "created_at")
    list_filter = ("is_active", "role")
    autocomplete_fields = ("role",)

    @admin.display(description="User")
    def get_username(self, obj):
        try:
            return User.objects.get(pk=obj.user_id).username
        except User.DoesNotExist:
            return str(obj.user_id)
