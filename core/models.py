from django.utils import timezone
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from tenant_users.tenants.models import UserProfile
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import (
    FileExtensionValidator,
    MinValueValidator,
    MaxValueValidator,
)
import uuid
import logging
from datetime import date, timedelta
from decimal import Decimal

from core.db_fields import EncryptedTextField
from core.modules import MODULES
from core.authz.registry import PERMISSIONS

logger = logging.getLogger(__name__)


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def school_logo_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"school_logos/{instance.schema_name}/logo.{ext}"


def school_logo_secondary_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"school_logos/{instance.schema_name}/crest.{ext}"


def school_signature_path(instance, filename):
    # No longer referenced by any field (School.signature was removed in favor of the
    # multi-signature SchoolSignature model) — kept only so historic migration
    # 0056_school_report_branding can still import this dotted path when migrations
    # are replayed from zero (fresh DB, CI). Do not delete.
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"school_logos/{instance.schema_name}/signature.{ext}"


def school_signature_image_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"school_logos/{instance.tenant.schema_name}/signatures/{instance.id}.{ext}"


def upload_to_news_documents(instance, filename):
    """Generate a safe, UUID-based filename for news document uploads.
    Prevents filename collisions and unsafe characters in storage paths.
    The original filename is not used as the storage key for security reasons."""
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"news/{instance.tenant.id}/{uuid.uuid4().hex}.{ext}"


def validate_news_document_size(file):
    """Validate that uploaded news document doesn't exceed 5MB."""
    max_size = 5 * 1024 * 1024  # 5MB
    if file.size > max_size:
        raise ValidationError(f"Document must not exceed 5MB. Current size: {file.size / (1024 * 1024):.2f}MB")


def default_zip_job_expiry():
    """Default expiry time for ZIP job files (24 hours from now).
    Defined as a named function (not lambda) so Django migrations can serialize it."""
    return timezone.now() + timedelta(hours=24)


def public_storage():
    """Storage for non-sensitive, openly-served files (logos, branding).

    Resolves to the 'public' entry in settings.STORAGES — the public S3 bucket
    in production, or the local filesystem in dev. Callable so it is evaluated
    at runtime per environment and never baked into migrations.
    """
    from django.core.files.storage import storages
    return storages["public"]


class School(TenantMixin):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    # Legacy Paperclip metadata kept for reference
    logo_file_name = models.CharField(max_length=255, blank=True, null=True)
    logo_content_type = models.CharField(max_length=255, blank=True, null=True)
    logo_file_size = models.IntegerField(blank=True, null=True)
    # Uploaded logo file — branding, served from the public bucket/CDN
    logo = models.ImageField(
        upload_to=school_logo_path,
        storage=public_storage,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'])],
    )
    # Optional second emblem (e.g. school crest/badge) shown on the right of reports
    logo_secondary = models.ImageField(
        upload_to=school_logo_secondary_path,
        storage=public_storage,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'])],
    )
    # Global report-card branding (used by every generated report)
    report_title = models.CharField(max_length=255, default="ASSESSMENT REPORT")
    footer_quote = models.TextField(
        default="",
        blank=True,
        help_text="Optional quote or motto to appear on report cards"
    )
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    pin_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.ForeignKey("Country", on_delete=models.SET_NULL, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    fax = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    operations_manager_name = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Operations Manager name for payment agreements"
    )
    fee_note_early_bird_discount_enabled = models.BooleanField(default=False)
    fee_note_early_bird_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="Shown only when the early-bird discount is enabled."
    )
    fee_note_terms = models.TextField(
        blank=True, default="",
        help_text="Free-form notice appended below every fee note (instalment terms, "
                  "bank account details, reminders). Rendered as plain text with line breaks preserved."
    )
    # Productization: Per-tenant timezone configuration (fallback to UTC if not set)
    timezone = models.CharField(
        max_length=63, default="UTC",
        help_text="IANA timezone identifier (e.g., 'Africa/Nairobi', 'UTC', 'America/New_York'). "
                  "Used to display times in the tenant's local timezone."
    )

    # Frontend branding and configuration
    description = models.TextField(
        blank=True,
        null=True,
        help_text="School's tagline or mission statement"
    )
    primary_color = models.CharField(
        blank=True,
        null=True,
        max_length=7,
        help_text="Primary brand color (hex, e.g., #1a7a3c)"
    )
    secondary_color = models.CharField(
        blank=True,
        null=True,
        max_length=7,
        help_text="Secondary brand color (hex)"
    )

    # Admission portal configuration
    admission_enabled = models.BooleanField(
        default=False,
        help_text="Whether the admission portal is enabled for this school"
    )
    admission_heading = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text="Custom heading for the admission portal"
    )
    admission_cta_text = models.CharField(
        blank=True,
        null=True,
        max_length=100,
        help_text="Call-to-action button text on admission portal"
    )
    admission_description = models.TextField(
        blank=True,
        null=True,
        help_text="Custom description of the admission process"
    )
    admission_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email address for admission inquiries (if different from main email)"
    )

    # Social media and external links
    social_links = models.JSONField(
        default=dict,
        blank=True,
        help_text="Social media links {twitter, facebook, instagram, linkedin}"
    )

    # Feature flags
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature flags {parent_portal, teacher_portal, librarian_portal, hr_portal, admission_portal}"
    )

    auto_create_schema = True

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name

    @property
    def logo_url(self):
        if self.logo and self.logo.name:
            return self.logo.url
        return None


class SchoolModule(BaseModel):
    """
    Runtime module enablement: schools can enable/disable product areas (HR, Finance, etc.)
    independently, turning whole feature sets on/off without code changes.

    This is the foundation of white-label SaaS — different schools have different needs
    (some run hostels, some don't; some use payroll, some use manual HR only, etc.).

    Each school gets SchoolModule rows (one per module) tracking enabled/disabled state
    plus module-specific configuration. The module registry (core.modules.MODULES)
    is the authoritative list of valid module keys.
    """
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="modules",
        help_text="School that owns this module configuration"
    )
    module = models.CharField(
        max_length=50,
        choices=[(key, meta["label"]) for key, meta in MODULES.items()],
        help_text="Module key (e.g. 'finance', 'hr', 'hostel') — must match core.modules.MODULES"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this module is currently active for the school"
    )
    configuration = models.JSONField(
        default=dict,
        blank=True,
        help_text="Module-specific configuration (e.g. {transport: {fleet_management: true}}). "
                  "Allows future extensibility without schema rewrites."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("school", "module")]
        indexes = [
            models.Index(fields=["school", "enabled"]),
            models.Index(fields=["module"]),
        ]

    def __str__(self):
        status = "✓ enabled" if self.enabled else "✗ disabled"
        return f"{self.school.name} - {self.module} [{status}]"

    def clean(self):
        from .modules import get_module_key
        try:
            get_module_key(self.module)
        except KeyError as e:
            raise ValidationError(f"Invalid module key: {e}")


class Domain(DomainMixin):
    pass


class User(UserProfile):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    # `is_admin` gates entry to the staff dashboard. `is_root` is the
    # break-glass owner flag: it bypasses all RBAC permission checks
    # (see core.authz.access). Normal staff — including HR — are `is_admin`
    # only, and their access is decided entirely by their assigned Roles.
    is_root = models.BooleanField(default=False)
    password_change_required = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    class Meta:
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["is_active", "created_at"]),
        ]

    def clean(self):
        super().clean()
        if not self.tenants.exists() and not self._state.adding:
            raise ValidationError("User must belong to at least one tenant")

    def __str__(self):
        return self.username

    @property
    def is_staff(self):
        return self.is_admin

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_active_tenant(self):
        return self.tenants.first()

    def has_tenant_access(self, tenant):
        return self.tenants.filter(id=tenant.id).exists()

    @property
    def is_superuser(self):
        return self.is_admin

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_perms(self, perm_list, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin


class TenantAwareManager(models.Manager):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def _apply_tenant_filter(self, qs):
        """Apply tenant filtering to a queryset using the current connection tenant.

        This is a shared helper used by both TenantAwareManager and its subclasses
        (e.g. BatchManager) to ensure consistent tenant-filtering logic across all
        manager implementations.

        Args:
            qs: A QuerySet to filter

        Returns:
            The filtered QuerySet if a current tenant is detected, otherwise the
            original QuerySet unmodified.
        """
        from django_tenants.utils import get_tenant_model
        from django.db import connection

        if (
            hasattr(connection, "tenant")
            and connection.tenant
            and hasattr(connection.tenant, "pk")
            and connection.tenant.pk
            and not str(type(connection.tenant)).endswith("FakeTenant")
        ):
            qs = qs.filter(tenant=connection.tenant)

        return qs

    def get_queryset(self):
        return self._apply_tenant_filter(super().get_queryset())


class TenantAwareModel(BaseModel):
    tenant = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="%(class)s_set"
    )

    objects = TenantAwareManager()

    class Meta:
        abstract = True


class Student(TenantAwareModel):
    admission_no = models.CharField(max_length=50, unique=True)
    class_roll_no = models.CharField(max_length=50, blank=True, null=True)
    admission_date = models.DateField()
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
    )
    blood_group = models.CharField(max_length=10, blank=True, null=True)
    birth_place = models.CharField(max_length=255, blank=True, null=True)
    nationality = models.ForeignKey("Country", on_delete=models.SET_NULL, null=True, blank=True)
    language = models.CharField(max_length=100, blank=True, null=True)
    religion = models.CharField(max_length=100, blank=True, null=True)
    student_category = models.ForeignKey(
        "StudentCategory", on_delete=models.SET_NULL, null=True, blank=True
    )
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    pin_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.ForeignKey(
        "Country", on_delete=models.SET_NULL, null=True, blank=True, related_name="students_country"
    )
    phone1 = models.CharField(max_length=20, blank=True, null=True)
    phone2 = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_sms_enabled = models.BooleanField(default=True)
    photo_file_name = models.CharField(max_length=255, blank=True, null=True)
    photo_content_type = models.CharField(max_length=255, blank=True, null=True)
    photo_file_size = models.IntegerField(blank=True, null=True)
    status_description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False
    )
    immediate_contact = models.ForeignKey(
        "Guardian", on_delete=models.SET_NULL, null=True, blank=True
    )
    has_paid_fees = models.BooleanField(default=False)

    class Meta:
        ordering = ["first_name", "last_name"]
        indexes = [
            models.Index(fields=["admission_no", "tenant"]),
            models.Index(fields=["first_name", "middle_name", "last_name", "tenant"]),
            models.Index(fields=["tenant"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "is_active"]),
        ]
        unique_together = ["admission_no", "tenant"]

    @property
    def full_name(self):
        """Return the full name of the student"""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.admission_no})"


class Guardian(TenantAwareModel):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    relation = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    mobile_phone = models.CharField(max_length=20, blank=True, null=True)
    office_phone = models.CharField(max_length=20, blank=True, null=True)
    office_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    office_address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    country = models.ForeignKey("Country", on_delete=models.SET_NULL, null=True)
    dob = models.DateField(blank=True, null=True)
    occupation = models.CharField(max_length=255, blank=True, null=True)
    income = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    education = models.CharField(max_length=255, blank=True, null=True)
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class StudentGuardianRelation(TenantAwareModel):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="guardian_relations"
    )
    guardian = models.ForeignKey(
        Guardian, on_delete=models.CASCADE, related_name="student_relations"
    )
    relation = models.CharField(max_length=100)
    is_immediate_contact = models.BooleanField(default=False)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="student_guardian_relations"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["guardian"]),
        ]


class StudentAdditionalDetail(TenantAwareModel):
    student = models.OneToOneField(
        Student, on_delete=models.CASCADE, related_name="additional_details"
    )
    additional_info = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]


class StudentPreviousData(TenantAwareModel):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="previous_data"
    )
    institution = models.CharField(max_length=255)
    year = models.CharField(max_length=10)
    course = models.CharField(max_length=255)
    total_mark = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
        ]


class Employee(TenantAwareModel):
    employee_number = models.CharField(max_length=50, unique=True)
    joining_date = models.DateField()
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    gender = models.BooleanField(choices=[(True, "Male"), (False, "Female")])
    job_title = models.CharField(max_length=255, blank=True, null=True)
    is_teaching_staff = models.BooleanField(default=False, db_index=True)
    employee_category = models.ForeignKey(
        "EmployeeCategory", on_delete=models.SET_NULL, null=True, blank=True
    )
    employee_position = models.ForeignKey(
        "EmployeePosition", on_delete=models.SET_NULL, null=True, blank=True
    )
    employee_department = models.ForeignKey(
        "EmployeeDepartment", on_delete=models.SET_NULL, null=True, blank=True
    )
    reporting_manager = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True
    )
    employee_grade = models.ForeignKey(
        "EmployeeGrade", on_delete=models.SET_NULL, null=True, blank=True
    )
    qualification = models.CharField(max_length=255, blank=True, null=True)
    experience_detail = models.TextField(blank=True, null=True)
    experience_year = models.IntegerField(blank=True, null=True)
    experience_month = models.IntegerField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    marital_status = models.CharField(max_length=50, blank=True, null=True)
    children_count = models.IntegerField(blank=True, null=True)
    blood_group = models.CharField(max_length=10, blank=True, null=True)
    nationality = models.ForeignKey("Country", on_delete=models.SET_NULL, null=True, blank=True)
    home_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    home_address_line2 = models.CharField(max_length=255, blank=True, null=True)
    home_city = models.CharField(max_length=255, blank=True, null=True)
    home_state = models.CharField(max_length=255, blank=True, null=True)
    home_country = models.ForeignKey(
        "Country",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_home_country",
    )
    home_pin_code = models.CharField(max_length=20, blank=True, null=True)
    office_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    office_address_line2 = models.CharField(max_length=255, blank=True, null=True)
    office_city = models.CharField(max_length=255, blank=True, null=True)
    office_state = models.CharField(max_length=255, blank=True, null=True)
    office_country = models.ForeignKey(
        "Country",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_office_country",
    )
    office_pin_code = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    mobile_phone = models.CharField(max_length=20, blank=True, null=True)
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False
    )
    status = models.BooleanField(default=True)

    # --- HR lifecycle -------------------------------------------------------
    EMPLOYMENT_STATUS_CHOICES = [
        ("active", "Active"),
        ("probation", "Probation"),
        ("on_leave", "On Leave"),
        ("suspended", "Suspended"),
        ("notice_period", "Notice Period"),
        ("exited", "Exited"),
    ]
    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default="active",
        db_index=True,
        help_text="HR-managed lifecycle status. Independent of the boolean "
        "`status` flag, which stays the login/soft-delete gate.",
    )
    national_id = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="NRC / passport number",
    )
    emergency_contact_name = models.CharField(max_length=255, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True, null=True)
    emergency_contact_relation = models.CharField(max_length=80, blank=True, null=True)
    next_of_kin_name = models.CharField(max_length=255, blank=True, null=True)
    next_of_kin_phone = models.CharField(max_length=30, blank=True, null=True)
    next_of_kin_relation = models.CharField(max_length=80, blank=True, null=True)
    photo = models.ImageField(
        upload_to="employee_photos/", blank=True, null=True,
        help_text="Profile photo shown in the HR portal.",
    )

    photo_file_name = models.CharField(max_length=255, blank=True, null=True)
    photo_content_type = models.CharField(max_length=255, blank=True, null=True)
    photo_file_size = models.IntegerField(blank=True, null=True)
    signature_image = models.TextField(
        blank=True, default="",
        help_text="Base64 data-URI of the teacher's signature, printed on report cards for their assigned students. Set via the Teacher Portal signature endpoint.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["employee_number"]),
            models.Index(fields=["tenant"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "is_teaching_staff"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_number})"

    @property
    def full_name(self):
        """Full display name, e.g. 'Jane Doe' (used by reports, assignments, etc.)."""
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p).strip()

    @property
    def roles(self):
        """Active RBAC roles held by this employee's linked login, if any.

        Read-only convenience for the employee detail page — real access
        decisions go through :mod:`core.authz.access`.
        """
        if not self.user_id:
            return Role.objects.none()
        return Role.objects.filter(
            tenant_id=self.tenant_id,
            is_active=True,
            assignments__user_id=self.user_id,
            assignments__is_active=True,
        ).distinct()

    @property
    def current_contract(self):
        """Most recent contract by start date, or ``None``. Superseded contracts
        are kept as history — never mutated."""
        return self.contracts.order_by("-start_date", "-created_at").first()


class Course(TenantAwareModel):
    course_name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    section_name = models.CharField(max_length=255, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    grading_type = models.CharField(max_length=50, blank=True, null=True)
    max_hours_day = models.IntegerField(blank=True, null=True)
    max_hours_week = models.IntegerField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"{self.course_name} ({self.code})"


class BatchQuerySet(models.QuerySet):
    """Custom QuerySet for Batch with natural sorting support."""

    def order_by_name_natural(self):
        """
        Order batches by name using natural sort (1, 2, 10 instead of 1, 10, 2).

        This method fetches all batches and sorts them in Python using
        natural sort logic. Use sparingly on large datasets.

        Returns:
            list: Batches sorted by natural order of batch names.
        """
        from core.utils.natural_sort import natural_sort
        batches = list(self)
        return natural_sort(batches, key=lambda b: b.name)


class BatchManager(TenantAwareManager):
    """Custom manager for Batch with natural sorting support."""

    def get_queryset(self):
        # Create BatchQuerySet and apply tenant filtering via shared helper
        qs = BatchQuerySet(self.model, using=self._db)
        return self._apply_tenant_filter(qs)

    def order_by_name_natural(self):
        """Order batches by name using natural sort."""
        return self.get_queryset().order_by_name_natural()


class Batch(TenantAwareModel):
    name = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="batches")
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="batches"
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, related_name="batches",
        help_text="Primary class teacher (kept in sync with the first class teacher)",
    )
    class_teachers = models.ManyToManyField(
        Employee, related_name="class_teacher_batches", blank=True,
        help_text="All class teachers responsible for this batch",
    )
    grading_type = models.CharField(max_length=50, blank=True, null=True)

    objects = BatchManager()

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["is_deleted", "is_active", "course", "name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.course.course_name})"

    def class_teacher_names(self):
        """Display string for all class teachers, falling back to the legacy single teacher."""
        names = [f"{e.first_name} {e.last_name}".strip() for e in self.class_teachers.all()]
        if not names and self.employee:
            names = [f"{self.employee.first_name} {self.employee.last_name}".strip()]
        return ", ".join(names)


class BatchStudent(TenantAwareModel):
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="batch_students"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="student_batches"
    )
    roll_number = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["batch", "student"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["student"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.batch}"


class ClassTeacherAssignment(TenantAwareModel):
    """Per-student assignment of a class teacher within a batch. Supports
    batches with multiple class teachers each responsible for a subset of
    students. Exactly one row is active per (student, batch, academic_year).
    Reassignment deactivates the old row and creates a new one (mirrors
    StudentService.transfer_batch's soft-deactivate pattern) so historical
    rows — and therefore comments/reports stamped from them — never get
    silently repointed to a new teacher."""

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="class_teacher_assignments"
    )
    batch = models.ForeignKey(
        "Batch", on_delete=models.CASCADE, related_name="class_teacher_assignments"
    )
    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="class_teacher_assignments"
    )
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="class_teacher_assignments"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "batch", "is_active"]),
            models.Index(fields=["tenant", "student", "is_active"]),
            models.Index(fields=["tenant", "employee", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "batch", "academic_year"],
                condition=models.Q(is_active=True),
                name="uniq_active_class_teacher_assignment",
            ),
        ]

    def __str__(self):
        return f"{self.student} → {self.employee} ({self.batch}, active={self.is_active})"


class ActiveSubjectManager(TenantAwareManager):
    """Default manager: excludes soft-deleted subjects from all queries."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Subject(TenantAwareModel):
    """
    Core primitive for academic subjects.

    Subjects can have:
    - Traditional exams (via Exam model)
    - Skills assessments (via SubjectSkillSet)
    - Both exams AND skills (hybrid assessment)
    - Neither (informational subjects)

    The assessment type is determined by the presence of related records,
    not by a boolean flag, allowing maximum flexibility.
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="subjects")
    no_exams = models.BooleanField(
        default=False,
        help_text='DEPRECATED: Use skill_sets relationship instead. Kept for backward compatibility.'
    )
    max_weekly_classes = models.IntegerField(blank=True, null=True)
    elective_group = models.ForeignKey(
        "ElectiveGroup", on_delete=models.SET_NULL, null=True
    )
    is_deleted = models.BooleanField(default=False)
    language = models.BooleanField(default=False)
    credit_hours = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )
    prefer_consecutive = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    grading_scale = models.ForeignKey(
        "GradingScale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects',
        help_text='Grading scale for this subject (overrides batch default)'
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subjects_taught",
        help_text="Teacher assigned to this subject within its batch",
    )

    # Default manager excludes soft-deleted rows; use all_objects in admin/migrations.
    objects = ActiveSubjectManager()
    all_objects = TenantAwareManager()

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch", "elective_group", "is_deleted"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def has_exams(self):
        """Returns True if subject has traditional exams configured"""
        return self.exams.exists()

    def has_skills(self):
        """Returns True if subject has skill sets configured"""
        return self.skill_sets.filter(is_active=True).exists()

    def get_assessment_type(self):
        """Returns the assessment type for this subject"""
        has_exams = self.has_exams()
        has_skills = self.has_skills()

        if has_exams and has_skills:
            return 'HYBRID'
        elif has_exams:
            return 'EXAMS'
        elif has_skills:
            return 'SKILLS'
        else:
            return 'NONE'

    def get_grading_scale(self):
        """
        Get the effective grading scale for this subject.

        Hierarchy: Subject grading_scale > Batch default_grading_scale >
        course-name-inferred default (e.g. Reception/Nursery -> SKILL_LEVELS,
        see infer_report_layout) > Tenant default
        """
        # Subject-specific grading scale
        if self.grading_scale:
            return self.grading_scale

        # Batch default grading scale (field removed in migration 0040; this
        # branch is kept for forward compat but never matches today)
        if hasattr(self.batch, 'default_grading_scale') and self.batch.default_grading_scale:
            return self.batch.default_grading_scale

        # Course-name-inferred default — same keyword-based fallback the
        # report-generation code already relies on for pre-grade batches
        # that never got an explicit scale set on the subject/exam.
        from core.grading_utils import infer_report_layout, _SKILLS_COURSE_KEYWORDS
        _, inferred_scale = infer_report_layout(self.batch)
        if inferred_scale:
            return inferred_scale

        # infer_report_layout() only resolves a scale under the exact seeded
        # code for its layout (e.g. SKILL_LEVELS) — a school whose LEVEL
        # scale was created under a different code still has a course name
        # that says "this is a skills batch", so match on scale_type
        # directly instead of requiring that exact code.
        text = ''
        try:
            text = (self.batch.course.course_name or '').upper()
        except Exception:
            pass
        text = f"{text} {(getattr(self.batch, 'name', '') or '').upper()}"
        if any(kw in text for kw in _SKILLS_COURSE_KEYWORDS):
            from core.models import GradingScale
            level_scale = GradingScale.objects.filter(
                tenant=self.tenant, scale_type='LEVEL', is_active=True
            ).first()
            if level_scale:
                return level_scale

        # Tenant default grading scale
        from core.models import GradingScale
        return GradingScale.objects.filter(
            tenant=self.tenant,
            is_default=True,
            is_active=True
        ).first()

    def get_available_grades(self):
        """
        Get list of available grade values for this subject.

        Returns GradeValue queryset ordered by display_order.
        """
        grading_scale = self.get_grading_scale()
        if grading_scale:
            return grading_scale.grade_values.filter(
                tenant=self.tenant
            ).order_by('display_order')
        return []


class Weekday(TenantAwareModel):
    weekday = models.CharField(max_length=20)
    day_of_week = models.IntegerField()

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.weekday


class Timetable(TenantAwareModel):
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="timetables"
    )
    weekday = models.ForeignKey(
        Weekday, on_delete=models.CASCADE, related_name="timetables"
    )
    class_timing = models.ForeignKey(
        "ClassTiming", on_delete=models.CASCADE, related_name="timetables"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.SET_NULL, null=True, blank=True
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True
    )
    classroom = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch", "weekday"]),
        ]
        unique_together = ["batch", "weekday", "class_timing"]

    def __str__(self):
        return f"{self.batch} - {self.weekday} - {self.class_timing}"


class FinanceTransactionCategory(TenantAwareModel):
    name = models.CharField(max_length=255)
    prefix = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_income = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class FinanceTransaction(TenantAwareModel):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    category = models.ForeignKey(FinanceTransactionCategory, on_delete=models.CASCADE)
    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True
    )
    transaction_date = models.DateField()
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.PROTECT, null=True, blank=True,
        related_name="finance_transactions",
        help_text="Academic year this transaction belongs to",
    )
    description = models.TextField(blank=True, null=True)
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES,
        default='cash', blank=True,
        help_text='Method used for this transaction',
    )
    reference_number = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["transaction_date"]),
            models.Index(fields=["tenant", "transaction_date"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "academic_year", "transaction_date"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.amount}"


class FeeCategory(TenantAwareModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, null=True, blank=True
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["academic_year"]),
        ]

    def __str__(self):
        return f"{self.name}" + (
            f" ({self.academic_year})" if self.academic_year else ""
        )


class BatchFeeCategory(TenantAwareModel):
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["fee_category", "batch"]
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"{self.fee_category} - {self.batch}"


class BatchFeeCategoryStudent(TenantAwareModel):
    """Optional scoping of a BatchFeeCategory to a hand-picked subset of
    students in that batch. Empty (no rows for a given BatchFeeCategory) =
    applies to the whole batch, preserving current/pre-existing behavior.
    Populated = FinanceFee generation is limited to these students only."""

    batch_fee_category = models.ForeignKey(
        BatchFeeCategory, on_delete=models.CASCADE, related_name="scoped_students"
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["batch_fee_category", "student"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch_fee_category"]),
        ]

    def __str__(self):
        return f"{self.batch_fee_category} - {self.student}"


class FeeApplicabilityRule(TenantAwareModel):
    """Rule determining which students a fee particular or discount applies to"""

    RULE_TYPE_CHOICES = [
        ("all", "All Students"),
        ("admission_number", "By Admission Number"),
        ("student_category", "By Student Category"),
        ("batch", "By Batch"),
        ("individual_student", "Individual Student"),
    ]

    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    admission_number = models.CharField(max_length=50, null=True, blank=True)
    student_category = models.ForeignKey(
        "StudentCategory", on_delete=models.SET_NULL, null=True, blank=True
    )
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    student = models.ForeignKey(
        "Student", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["rule_type"]),
        ]

    def __str__(self):
        if self.rule_type == "all":
            return "All Students"
        elif self.rule_type == "admission_number":
            return f"Admission #{self.admission_number}"
        elif self.rule_type == "student_category":
            return f"Category: {self.student_category}"
        elif self.rule_type == "batch":
            return f"Batch: {self.batch}"
        elif self.rule_type == "individual_student":
            return f"Student: {self.student}"
        return f"Rule {self.id}"

    def matches(self, student):
        """
        Return True if this rule applies to the given student.

        - rule_type='all': always matches
        - rule_type='admission_number': matches only if student.admission_no == self.admission_number
        - rule_type='student_category': matches if student.student_category == self.student_category
        - rule_type='batch': matches if student is in the batch (via BatchStudent)
        - rule_type='individual_student': matches only if student == self.student
        """
        if not self.is_active:
            return False

        if self.rule_type == "all":
            return True
        elif self.rule_type == "admission_number":
            return student.admission_no == self.admission_number
        elif self.rule_type == "student_category":
            return student.student_category_id == self.student_category_id
        elif self.rule_type == "batch":
            return BatchStudent.objects.filter(
                student=student, batch=self.batch, tenant=self.tenant
            ).exists()
        elif self.rule_type == "individual_student":
            return student.id == self.student_id
        return False


class FeeMasterParticular(TenantAwareModel):
    """Master template for fee particulars — reusable across categories"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        unique_together = ["tenant", "name"]

    def __str__(self):
        return self.name


class FeeMasterDiscount(TenantAwareModel):
    """Master template for fee discounts — reusable across categories"""

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    ]

    name = models.CharField(max_length=255)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        unique_together = ["tenant", "name"]

    def __str__(self):
        return f"{self.name} ({self.discount_type})"


class FinanceFee(TenantAwareModel):
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.PROTECT, null=True, blank=True,
        related_name="finance_fees",
        help_text="Academic year this fee charge belongs to",
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_date = models.DateField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    fee_collection = models.ForeignKey('FeeCollection', on_delete=models.CASCADE, null=True, blank=True)
    particular_total = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    invoice_number = models.CharField(
        max_length=100, unique=True, null=True, blank=True,
        help_text="Unique invoice identifier (generated when collection is published)"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["tenant", "student", "academic_year"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.fee_category}"


class FinanceFeeItem(TenantAwareModel):
    """Itemized line item snapshot on a finance fee invoice"""

    finance_fee = models.ForeignKey(
        FinanceFee, on_delete=models.CASCADE, related_name="items"
    )
    fee_particular = models.ForeignKey(
        "FeeParticular", on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Original fee particular (for provenance; may be deleted later)"
    )
    particular_name = models.CharField(
        max_length=255,
        help_text="Snapshot of FeeParticular.name at generation time"
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="Snapshot of FeeParticular.amount at generation time"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["finance_fee"]),
        ]

    def __str__(self):
        return f"{self.finance_fee} - {self.particular_name}: {self.amount}"


class FeeParticular(TenantAwareModel):
    """Individual fee items that belong to a master fee category"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    applicability_rule = models.ForeignKey(
        "FeeApplicabilityRule", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fee_particulars",
        help_text="Rule determining which students this particular applies to",
    )
    master_particular = models.ForeignKey(
        "FeeMasterParticular", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="particulars",
        help_text="Link to master template if instantiated from one",
    )
    is_active = models.BooleanField(default=True)
    due_date = models.DateField(null=True, blank=True)
    effective_date = models.DateField(
        null=True, blank=True,
        help_text="Particular is only applied on/after this date"
    )
    expiry_date = models.DateField(
        null=True, blank=True,
        help_text="Particular is no longer applied after this date"
    )
    fine_slab = models.ForeignKey(
        "FineSlab", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fee_particulars",
        help_text="Any one row of the fine slab ladder (grouped by fine_name) to apply after due_date",
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["fee_category"]),
        ]
        unique_together = ["tenant", "name", "fee_category"]

    def __str__(self):
        return f"{self.name} - {self.fee_category}"


class FeeDiscount(TenantAwareModel):
    """Fee discount system for batch or individual students"""

    DISCOUNT_TYPE_CHOICES = [
        ("batch", "Batch Discount"),
        ("individual", "Individual Discount"),
    ]

    DISCOUNT_MODE_CHOICES = [
        ("percentage", "Percentage"),
        ("amount", "Fixed Amount"),
    ]

    name = models.CharField(max_length=255)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    discount_mode = models.CharField(max_length=20, choices=DISCOUNT_MODE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    applicability_rule = models.ForeignKey(
        "FeeApplicabilityRule", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fee_discounts",
        help_text="Rule determining which students this discount applies to",
    )
    master_discount = models.ForeignKey(
        "FeeMasterDiscount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="discounts",
        help_text="Link to master template if instantiated from one",
    )
    effective_date = models.DateField(
        null=True, blank=True,
        help_text="Discount is only applied on/after this date"
    )
    expiry_date = models.DateField(
        null=True, blank=True,
        help_text="Discount is no longer applied after this date"
    )

    # For batch discounts
    batches = models.ManyToManyField(Batch, blank=True)

    # For individual discounts
    students = models.ManyToManyField(Student, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["fee_category"]),
        ]
        unique_together = ["tenant", "name", "fee_category"]

    def __str__(self):
        return f"{self.name} ({self.discount_type})"

    def calculate_discount(self, amount):
        """Calculate discount amount based on mode"""
        if self.discount_mode == "percentage":
            return (amount * self.discount_value) / 100
        else:
            return self.discount_value


class FeeAmountChangeLog(TenantAwareModel):
    """Audit trail for fee particular and discount amount changes"""

    fee_particular = models.ForeignKey(
        FeeParticular, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="amount_changes"
    )
    fee_discount = models.ForeignKey(
        FeeDiscount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="amount_changes"
    )
    old_amount = models.DecimalField(max_digits=15, decimal_places=2)
    new_amount = models.DecimalField(max_digits=15, decimal_places=2)
    changed_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fee_amount_changes"
    )
    changed_at = models.DateTimeField(default=timezone.now)
    reason = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["fee_particular"]),
            models.Index(fields=["fee_discount"]),
            models.Index(fields=["changed_at"]),
        ]

    def __str__(self):
        if self.fee_particular:
            return f"{self.fee_particular.name}: {self.old_amount} → {self.new_amount}"
        elif self.fee_discount:
            return f"{self.fee_discount.name}: {self.old_amount} → {self.new_amount}"
        return f"Change: {self.old_amount} → {self.new_amount}"


class FineSlab(TenantAwareModel):
    """Fine slab structure for late fee payments"""

    fine_name = models.CharField(max_length=255)
    days_after_due = models.IntegerField()
    fine_mode = models.CharField(
        max_length=20,
        choices=[("percentage", "Percentage"), ("amount", "Fixed Amount")],
        default="percentage",
    )
    fine_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["fine_name"]),
        ]
        ordering = ["days_after_due"]

    def __str__(self):
        return f"{self.fine_name} - {self.days_after_due} days"

    def calculate_fine(self, amount):
        """Calculate fine amount based on mode"""
        if self.fine_mode == "percentage":
            return (amount * self.fine_value) / 100
        else:
            return self.fine_value


class FeeTransaction(TenantAwareModel):
    """Track all fee-related transactions"""

    TRANSACTION_TYPES = [
        ("payment", "Fee Payment"),
        ("discount", "Discount Applied"),
        ("fine", "Fine Applied"),
        ("refund", "Fee Refund"),
        ("adjustment", "Fee Adjustment"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    fee_category = models.ForeignKey(
        FeeCategory, on_delete=models.CASCADE, null=True, blank=True
    )
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.PROTECT, null=True, blank=True,
        related_name="fee_transactions",
        help_text="Academic year this fee ledger row belongs to",
    )
    fee_particular = models.ForeignKey(
        FeeParticular, on_delete=models.CASCADE, null=True, blank=True
    )
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ]

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    transaction_date = models.DateTimeField(auto_now_add=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES,
        default='cash', blank=True,
        help_text='Payment method used',
    )

    # For tracking discounts and fines
    discount = models.ForeignKey(
        FeeDiscount, on_delete=models.SET_NULL, null=True, blank=True
    )
    fine_slab = models.ForeignKey(
        FineSlab, on_delete=models.SET_NULL, null=True, blank=True
    )
    collected_by = models.ForeignKey(
        "Employee", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fee_payments_collected",
        help_text="Staff member who processed this payment",
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["transaction_type"]),
            models.Index(fields=["transaction_date"]),
            models.Index(fields=["tenant", "student", "academic_year"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.transaction_type} - {self.amount}"


class FeeReconciliation(TenantAwareModel):
    """Track fee reconciliation between academic years"""

    from_academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="reconciliation_from"
    )
    to_academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="reconciliation_to"
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    outstanding_amount = models.DecimalField(max_digits=15, decimal_places=2)
    reconciliation_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    is_processed = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["from_academic_year"]),
            models.Index(fields=["to_academic_year"]),
            models.Index(fields=["student"]),
        ]
        unique_together = [
            "tenant",
            "from_academic_year",
            "to_academic_year",
            "student",
        ]

    def __str__(self):
        return f"{self.student} - {self.from_academic_year} to {self.to_academic_year}"


class News(TenantAwareModel):
    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    document = models.FileField(
        upload_to=upload_to_news_documents,
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf"]),
            validate_news_document_size,
        ],
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Sms(TenantAwareModel):
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    body = models.TextField()
    recipient = models.CharField(max_length=20)
    is_sent = models.BooleanField(default=False)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    sent_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_sent'
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    batch = models.ForeignKey(
        'Batch', on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_messages'
    )
    guardian = models.ForeignKey(
        'Guardian', on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_messages'
    )
    student = models.ForeignKey(
        'Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_messages'
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["tenant", "batch"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "created_at"]),
        ]

    def __str__(self):
        return f"SMS to {self.recipient}"


class Library(TenantAwareModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"], name="unique_library_name_per_tenant"
            ),
        ]

    def __str__(self):
        return self.name


class LibraryStaff(TenantAwareModel):
    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="library_assignments"
    )
    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, related_name="staff_assignments"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["employee"]),
            models.Index(fields=["library"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "library"], name="unique_employee_library_assignment"
            ),
        ]

    def __str__(self):
        return f"{self.employee} @ {self.library}"


class BookCategory(TenantAwareModel):
    name = models.CharField(max_length=255)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class Book(TenantAwareModel):
    BOOK_TYPE_CHOICES = [
        ("TEXTBOOK", "Textbook"),
        ("STORYBOOK", "Storybook"),
        ("TEACHER_RESOURCE", "Teacher's Resource Book"),
        ("REFERENCE", "Reference"),
        ("OTHER", "Other"),
    ]

    SCHOOL_LEVEL_CHOICES = [
        ("LOWER_SCHOOL", "Lower School"),
        ("UPPER_SCHOOL", "Upper School"),
        ("ALL", "All Levels"),
    ]

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    isbn = models.CharField(max_length=50, blank=True, null=True)
    book_number = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(BookCategory, on_delete=models.CASCADE)
    location = models.CharField(max_length=255, blank=True, null=True)
    total_copies = models.IntegerField(default=1)
    available_copies = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    book_type = models.CharField(
        max_length=50, choices=BOOK_TYPE_CHOICES, default="OTHER"
    )
    school_level = models.CharField(
        max_length=50, choices=SCHOOL_LEVEL_CHOICES, default="ALL"
    )
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True, db_index=True)
    library = models.ForeignKey(
        "Library", on_delete=models.PROTECT, null=True, blank=True, related_name="books"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["book_number"]),
            models.Index(fields=["book_type"]),
            models.Index(fields=["school_level"]),
            models.Index(fields=["library"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.author}"


class BookMovement(TenantAwareModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="movements")
    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True
    )
    issue_date = models.DateField()
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    is_returned = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["book"]),
        ]

    def __str__(self):
        borrower = self.student or self.employee
        return f"{self.book} - {borrower}"


class Exam(TenantAwareModel):
    exam_group = models.ForeignKey(
        "ExamGroup", on_delete=models.CASCADE, related_name="exams"
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="exams")
    term = models.ForeignKey(
        "Term", on_delete=models.SET_NULL, null=True, blank=True, related_name="exams"
    )
    exam_name = models.CharField(max_length=255, blank=True, null=True, help_text='Exam name like "EXAMINATION/TEST MARK"')
    exam_code = models.CharField(max_length=50, blank=True, null=True, help_text='Exam code like "EM2"')
    display_name = models.CharField(max_length=255, blank=True, null=True, help_text='Optional display name for the exam')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    maximum_marks = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_marks = models.DecimalField(max_digits=10, decimal_places=2)
    grading_level = models.ForeignKey(
        "GradingLevel", on_delete=models.SET_NULL, null=True
    )
    grading_scale = models.ForeignKey(
        "GradingScale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams',
        help_text='Grading scale for this exam (overrides subject default)'
    )
    weightage = models.IntegerField(default=0)
    event = models.ForeignKey("Event", on_delete=models.SET_NULL, null=True)

    SLOT_EXAM       = 'EXAM'
    SLOT_ATTAINMENT = 'ATTAINMENT'
    SLOT_EFFORT     = 'EFFORT'
    SLOT_CLASSWORK  = 'CLASSWORK'
    SLOT_TEST       = 'TEST'
    SLOT_CHOICES = [
        ('EXAM',        'Examination / Test'),
        ('ATTAINMENT',  'Attainment (Term grade)'),
        ('EFFORT',      'Effort (Term grade)'),
        ('CLASSWORK',   'Classwork'),
        ('TEST',        'Test'),
    ]
    assessment_slot = models.CharField(
        max_length=20, choices=SLOT_CHOICES, default='EXAM',
        help_text='Report column this exam feeds into (ATTAINMENT/EFFORT for grades 3-7, CLASSWORK for grades 1-2)',
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["exam_group", "subject"]),
        ]

    def __str__(self):
        return f"{self.subject.name} - {self.exam_group.name}"

    def get_grading_scale(self):
        """Get effective grading scale with fallback hierarchy"""
        # 1. Use exam's grading scale if set
        if self.grading_scale:
            return self.grading_scale
        # 2. Use subject's grading scale
        if self.subject:
            return self.subject.get_grading_scale()
        return None

    def get_available_grades(self):
        """Returns GradeValue queryset ordered by display_order"""
        grading_scale = self.get_grading_scale()
        if grading_scale:
            return grading_scale.grade_values.filter(tenant=self.tenant).order_by('display_order')
        return []


class ExamGroup(TenantAwareModel):
    name = models.CharField(max_length=255)
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="exam_groups"
    )
    exam_type = models.CharField(max_length=255)
    is_published = models.BooleanField(default=False)
    result_published = models.BooleanField(default=False)
    exam_date = models.DateField()
    is_final_exam = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class Term(TenantAwareModel):
    """
    Year-scoped academic term, configurable per tenant.
    PRODUCTIZATION: No longer assumes 3 terms per AcademicYear. Tenants configure
    their own academic structure (3 terms, 2 semesters, quarters, etc.) via admin.
    """

    academic_year = models.ForeignKey(
        "AcademicYear",
        on_delete=models.CASCADE,
        related_name="terms_by_year",
    )
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["academic_year", "order"]
        unique_together = [["tenant", "academic_year", "name"]]
        indexes = [
            models.Index(fields=["tenant", "academic_year"]),
        ]

    def __str__(self):
        return f"{self.academic_year.name} - {self.name}"


class ExamScore(TenantAwareModel):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="exam_scores"
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="scores")
    marks = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    grading_level = models.ForeignKey(
        "GradingLevel", on_delete=models.SET_NULL, null=True
    )
    grade_value = models.ForeignKey(
        "GradeValue",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_scores',
        help_text='Selected grade for grade-only exams (maximum_marks=0)',
    )
    remarks = models.TextField(blank=True, null=True)
    is_absent = models.BooleanField(default=False)

    class Meta:
        unique_together = ["student", "exam"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["exam"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.exam} - {self.marks}"


class SchoolSignature(TenantAwareModel):
    """A named, titled signature (e.g. Lower Primary Head, Secondary Head) that can be
    assigned to individual ReportTemplates, or act as the tenant-wide default when a
    template doesn't specify one. Distinct from Employee.signature_image /
    TeacherComment.signature_image, which are per-teacher comment signatures."""
    name = models.CharField(max_length=150, help_text="Signatory's name, e.g. 'Mrs. Jane Mwansa'")
    title = models.CharField(
        max_length=100, default='Head of School',
        help_text="Title printed under the signature image on report cards",
    )
    section_label = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Optional descriptive grouping, e.g. 'Lower Primary' — informational only "
                   "(mirrors Course.section_name), not linked to any batch/course",
    )
    image = models.ImageField(
        upload_to=school_signature_image_path,
        storage=public_storage,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'webp'])],
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Used by report templates that don't specify a signature of their own",
    )

    class Meta:
        indexes = [models.Index(fields=["tenant"])]
        ordering = ['-is_default', 'title', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant'], condition=models.Q(is_default=True),
                name='unique_default_school_signature_per_tenant',
            ),
        ]

    def __str__(self):
        return f"{self.name} — {self.title}" if self.name else self.title


class ReportTemplate(TenantAwareModel):
    """Template configuration for student reports"""

    LAYOUT_SKILLS = 'SKILLS'
    LAYOUT_SIMPLE = 'SIMPLE_ACADEMIC'
    LAYOUT_FULL   = 'FULL_ACADEMIC'
    LAYOUT_CHOICES = [
        (LAYOUT_SKILLS, 'Skills Checklist (Beginners / Reception)'),
        (LAYOUT_SIMPLE, 'Simple Academic (Grade 1–2)'),
        (LAYOUT_FULL,   'Full Academic (Grade 3–7)'),
    ]

    name = models.CharField(max_length=255)
    batch = models.ForeignKey(
        "Batch", on_delete=models.CASCADE, related_name="report_templates"
    )
    term = models.CharField(max_length=100)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="report_templates"
    )

    # School branding — source from tenant (School model); no hardcoded defaults
    school_name = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Sourced from tenant at creation; left blank to use tenant values at display time"
    )
    school_address = models.TextField(blank=True, null=True)
    school_contact = models.CharField(max_length=255, blank=True, null=True)
    school_email = models.EmailField(blank=True, null=True)
    school_website = models.URLField(blank=True, null=True)
    school_logo_url = models.URLField(blank=True, null=True)

    # Report configuration — tenant-configurable, no Pinewood defaults
    include_exam_scores = models.BooleanField(
        default=False, help_text="Include exam scores in report"
    )
    include_homework_assessment = models.BooleanField(
        default=False, help_text="Include homework assessment in report"
    )
    include_project_work = models.BooleanField(
        default=False, help_text="Include project work in report"
    )
    include_clubs = models.BooleanField(
        default=False, help_text="Include club participation in report"
    )
    include_sports = models.BooleanField(
        default=False, help_text="Include sports participation in report"
    )
    include_other_activities = models.BooleanField(
        default=False, help_text="Include other activities in report"
    )
    include_attendance = models.BooleanField(
        default=False, help_text="Include attendance data in report"
    )
    include_grading_scale = models.BooleanField(
        default=False, help_text="Include grading scale reference in report"
    )
    include_skills = models.BooleanField(
        default=False,
        help_text='Show the skills checklist (Skills layout only)',
    )

    # Customizable text
    report_title = models.CharField(max_length=255, default="ASSESSMENT REPORT")
    footer_quote = models.TextField(
        default="",
        blank=True,
        help_text="Optional quote or motto to appear on report cards"
    )

    # Branding — primary color (sourced from tenant or report template config)
    primary_color = models.CharField(
        max_length=7, blank=True, null=True,
        help_text='Hex color for report card headers and accents; sourced from tenant if not set',
    )

    # Section ordering — list of group keys in the order they should appear in the PDF.
    # Default (empty list) falls back to DEFAULT_SECTION_ORDER in the service.
    section_order = models.JSONField(
        default=list,
        help_text='Ordered section-group keys for PDF rendering',
    )

    # Subject ordering — list of Subject UUIDs (as strings) in the order they should
    # appear in the exam-scores table. Empty list means alphabetical (default behaviour).
    subject_order = models.JSONField(
        default=list,
        help_text='Ordered Subject IDs for the exam-scores table in the PDF',
    )
    skill_category_order = models.JSONField(
        default=list,
        help_text='Ordered SkillCategory IDs for the skills checklist in the PDF',
    )

    # Grading scale — when set, overrides batch GradingLevel lookup and the
    # hardcoded default; drives both the grade letters on exam rows and the
    # scale table at the bottom of the PDF.
    grading_scale = models.ForeignKey(
        'GradingScale', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='report_templates',
        help_text='Leave blank to use per-batch GradingLevel or the layout default scale',
    )

    # Layout — controls which PDF template structure is rendered
    layout_type = models.CharField(
        max_length=20, choices=LAYOUT_CHOICES, default=LAYOUT_FULL,
        help_text='Controls which PDF template structure is used for this report',
    )

    # Signature — which named SchoolSignature prints on report cards using this
    # template. Leave blank to use the tenant's default SchoolSignature.
    report_signature = models.ForeignKey(
        'SchoolSignature', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='report_templates',
        help_text='Leave blank to use the tenant default signature',
    )

    # "Next term commences" date printed on the report. When blank, the report
    # auto-detects it from the next Term in the exam plan.
    next_term_start = models.DateField(
        null=True, blank=True,
        help_text='Overrides the auto-detected "Next term commences" date on the report',
    )

    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["academic_year"]),
        ]
        unique_together = [["tenant", "batch", "term", "academic_year"]]

    def __str__(self):
        return f"{self.name} - {self.batch.name} - {self.term}"


class StudentReport(TenantAwareModel):
    """Generated report for a student"""

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="reports"
    )
    template = models.ForeignKey(
        "ReportTemplate", on_delete=models.CASCADE, related_name="generated_reports"
    )
    exam_group = models.ForeignKey(
        "ExamGroup", on_delete=models.CASCADE, related_name="student_reports"
    )

    # Report data cache (JSON)
    report_data = models.JSONField(default=dict)

    # File paths
    pdf_file_path = models.CharField(max_length=500, blank=True, null=True)
    html_file_path = models.CharField(max_length=500, blank=True, null=True)

    # Generation status
    GENERATION_STATUS = [
        ("pending", "Pending"),
        ("generating", "Generating"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    generation_status = models.CharField(
        max_length=20, choices=GENERATION_STATUS, default="pending"
    )
    generation_error = models.TextField(blank=True, null=True)
    generation_started_at = models.DateTimeField(blank=True, null=True)
    generation_completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["template"]),
            models.Index(fields=["generation_status"]),
        ]
        unique_together = [["tenant", "student", "template", "exam_group"]]

    def __str__(self):
        return f"Report - {self.student.full_name} - {self.template.name}"

    @property
    def pdf_url(self):
        if not self.pdf_file_path:
            return None
        return self._stored_file_url(self.pdf_file_path)

    @property
    def html_url(self):
        """Servable URL for the HTML version, if one was generated."""
        if not self.html_file_path:
            return None
        return self._stored_file_url(self.html_file_path)

    @staticmethod
    def _stored_file_url(path):
        """Public URL for a stored report file.

        Uses the S3/CloudFront public backend in deployments and the local
        media storage in development. We gate on ``USE_S3`` because importing
        ``storage_backends`` evaluates S3-only settings at class-definition
        time, which raises when those settings are absent locally.
        """
        from django.conf import settings
        if getattr(settings, "USE_S3", False):
            from core.storage_backends import PublicMediaStorage
            return PublicMediaStorage().url(path)
        from django.core.files.storage import default_storage
        return default_storage.url(path)


class TeacherComment(TenantAwareModel):
    """Per-student teacher comment entered during marks submission, included in the PDF report."""

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="teacher_comments"
    )
    exam_group = models.ForeignKey(
        "ExamGroup", on_delete=models.CASCADE, related_name="teacher_comments"
    )
    comment = models.TextField(blank=True, default="")
    # Base64 data URI of the teacher's signature image (shared across all student
    # records in the same exam_group — stored per row for simple retrieval).
    signature_image = models.TextField(blank=True, default="")
    class_teacher = models.ForeignKey(
        "Employee", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
        help_text="Teacher resolved as responsible for this student when the row was last saved — stamped by TeacherCommentService, never edited directly. A display/grouping stamp only: it is NOT part of the row's identity, so a reassignment restamps this row rather than starting a new one.",
    )

    class Meta:
        unique_together = [["tenant", "student", "exam_group"]]
        indexes = [
            models.Index(fields=["tenant", "exam_group"]),
        ]

    def __str__(self):
        return f"Comment — {self.student} / {self.exam_group}"


class SkillsTeacherComment(TenantAwareModel):
    """Per-student teacher comment for skills (pre-grade) report cards, keyed by batch + term."""

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="skills_teacher_comments"
    )
    batch = models.ForeignKey(
        "Batch", on_delete=models.CASCADE, related_name="skills_teacher_comments"
    )
    term = models.ForeignKey(
        "Term",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="skills_teacher_comments",
    )
    comment = models.TextField(blank=True, default="")
    # Base64 data URI shared across the whole batch+term — stored per row for
    # simple retrieval without a separate join.
    signature_image = models.TextField(blank=True, default="")
    class_teacher = models.ForeignKey(
        "Employee", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
        help_text="Teacher resolved as responsible for this student when the row was last saved — stamped by TeacherCommentService, never edited directly. A display/grouping stamp only: it is NOT part of the row's identity, so a reassignment restamps this row rather than starting a new one.",
    )

    class Meta:
        unique_together = [["tenant", "student", "batch", "term"]]
        constraints = [
            # unique_together cannot reach rows with no term: Postgres treats
            # NULLs as distinct, so it would happily hold several. This partial
            # index closes exactly that gap, giving TeacherCommentService the
            # one-row-per-student guarantee its reads assume.
            models.UniqueConstraint(
                fields=["tenant", "student", "batch"],
                condition=models.Q(term__isnull=True),
                name="uniq_skills_comment_null_term",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "batch", "term"]),
        ]

    def __str__(self):
        return f"SkillsComment — {self.student} / {self.batch} / {self.term or 'full year'}"


class ReportSection(TenantAwareModel):
    """Configurable sections within a report template"""

    template = models.ForeignKey(
        "ReportTemplate", on_delete=models.CASCADE, related_name="sections"
    )

    SECTION_TYPES = [
        ("header", "Header"),
        ("student_info", "Student Information"),
        ("exam_results", "Exam Results"),
        ("homework", "Homework Assessment"),
        ("project_work", "Project Work"),
        ("clubs", "Clubs"),
        ("sports", "Sports"),
        ("other_activities", "Other Activities"),
        ("attendance", "Attendance"),
        ("grading_scale", "Grading Scale"),
        ("footer", "Footer"),
    ]
    section_type = models.CharField(max_length=50, choices=SECTION_TYPES)
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)

    # Section-specific configuration (JSON)
    configuration = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["template"]),
            models.Index(fields=["order"]),
        ]
        ordering = ["order", "title"]

    def __str__(self):
        return f"{self.template.name} - {self.title}"


class HomeworkAssessment(TenantAwareModel):
    """Homework assessment for students"""

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="homework_assessments"
    )
    term = models.CharField(max_length=100)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="homework_assessments"
    )

    ASSESSMENT_GRADES = [
        ("Very Good", "Very Good"),
        ("Good", "Good"),
        ("Satisfactory", "Satisfactory"),
        ("Weak", "Weak"),
        ("Very Weak", "Very Weak"),
    ]

    submission = models.CharField(
        max_length=20, choices=ASSESSMENT_GRADES, default="Good"
    )
    presentation = models.CharField(
        max_length=20, choices=ASSESSMENT_GRADES, default="Good"
    )
    effort = models.CharField(max_length=20, choices=ASSESSMENT_GRADES, default="Good")

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["academic_year"]),
        ]
        unique_together = [["student", "term", "academic_year"]]

    def __str__(self):
        return f"{self.student.full_name} - Homework - {self.term}"


class ProjectWorkAssessment(TenantAwareModel):
    """Project work assessment for students"""

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="project_assessments"
    )
    term = models.CharField(max_length=100)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="project_assessments"
    )

    ASSESSMENT_GRADES = [
        ("Very Good", "Very Good"),
        ("Good", "Good"),
        ("Satisfactory", "Satisfactory"),
        ("Weak", "Weak"),
        ("Very Weak", "Very Weak"),
    ]

    submission = models.CharField(
        max_length=20, choices=ASSESSMENT_GRADES, default="Good"
    )
    presentation = models.CharField(
        max_length=20, choices=ASSESSMENT_GRADES, default="Good"
    )
    effort = models.CharField(max_length=20, choices=ASSESSMENT_GRADES, default="Good")

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["academic_year"]),
        ]
        unique_together = [["student", "term", "academic_year"]]

    def __str__(self):
        return f"{self.student.full_name} - Project Work - {self.term}"


class StudentActivity(TenantAwareModel):
    """Student participation in clubs, sports, and other activities"""

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="activities"
    )
    term = models.CharField(max_length=100)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="student_activities"
    )

    ACTIVITY_TYPES = [
        ("club", "Club"),
        ("sport", "Sport"),
        ("other", "Other Activity"),
    ]
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    activity_name = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["activity_type"]),
        ]

    def __str__(self):
        return f"{self.student.full_name} - {self.activity_name}"


class ActivitiesSaveCheckpoint(TenantAwareModel):
    """Marks that the class teacher has saved the Homework & Project modal
    and/or the Clubs/Sports/Other modal at least once for a batch's exam
    group. Needed because activity data is legitimately sparse (a student can
    have zero clubs), so row existence alone can't prove the section was
    reviewed — Submit Results gates on this explicit checkpoint instead."""

    batch = models.ForeignKey(
        "Batch", on_delete=models.CASCADE, related_name="activities_checkpoints"
    )
    exam_group = models.ForeignKey(
        "ExamGroup", on_delete=models.CASCADE, related_name="activities_checkpoints"
    )
    ratings_saved_at = models.DateTimeField(null=True, blank=True)
    activities_saved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [["tenant", "batch", "exam_group"]]

    def __str__(self):
        return f"ActivitiesSaveCheckpoint — {self.batch} / {self.exam_group}"


class Attendance(TenantAwareModel):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendances"
    )
    period_table_entry = models.ForeignKey(
        "PeriodEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendances"
    )
    forenoon = models.BooleanField(default=False)
    afternoon = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True, null=True)
    month_date = models.DateField()
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="attendances"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["month_date", "batch"]),
            models.Index(fields=["student", "batch"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.month_date}"

    @property
    def is_present(self):
        """Check if student is present (either forenoon or afternoon)"""
        return self.forenoon or self.afternoon

    @property
    def is_full_day_present(self):
        """Check if student is present for full day"""
        return self.forenoon and self.afternoon

    @property
    def is_half_day_present(self):
        """Check if student is present for half day only"""
        return (self.forenoon or self.afternoon) and not (
            self.forenoon and self.afternoon
        )

    @property
    def attendance_status(self):
        """Get attendance status as string"""
        if self.forenoon and self.afternoon:
            return "Full Day"
        elif self.forenoon:
            return "Forenoon Only"
        elif self.afternoon:
            return "Afternoon Only"
        else:
            return "Absent"

    @property
    def attendance_percentage(self):
        """Get attendance percentage for the day (0, 50, or 100)"""
        if self.forenoon and self.afternoon:
            return 100
        elif self.forenoon or self.afternoon:
            return 50
        else:
            return 0


class StudentLeave(TenantAwareModel):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="leaves"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True
    )
    employee_remark = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.start_date} to {self.end_date}"


class EmployeeLeave(TenantAwareModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="leaves"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_leaves",
    )
    manager_remark = models.TextField(blank=True, null=True)
    # Legacy free-text leave type, kept for audit only — superseded by leave_type below.
    leave_type_legacy = models.CharField(max_length=100, blank=True, null=True)
    leave_type = models.ForeignKey(
        "LeaveType", on_delete=models.SET_NULL, null=True, blank=True, related_name="leaves"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # --- Two-step workflow: employee -> supervisor -> HR ------------------
    STEP_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    supervisor_status = models.CharField(
        max_length=20, choices=STEP_CHOICES, default="pending"
    )
    supervisor_by = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="supervised_leaves",
    )
    supervisor_remark = models.TextField(blank=True, null=True)
    supervisor_acted_at = models.DateTimeField(null=True, blank=True)
    hr_status = models.CharField(
        max_length=20, choices=STEP_CHOICES, default="pending"
    )
    hr_by = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hr_reviewed_leaves",
    )
    hr_remark = models.TextField(blank=True, null=True)
    hr_acted_at = models.DateTimeField(null=True, blank=True)
    document = models.FileField(
        upload_to="employee_leave_documents/", blank=True, null=True,
        help_text="Supporting document (e.g. medical certificate).",
    )
    document_name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["employee"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return f"{self.employee} - {self.start_date} to {self.end_date}"


class EmployeeAttendance(TenantAwareModel):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('on_leave', 'On Leave'),
        ('half_day', 'Half Day'),
        ('official_duty', 'Official Duty'),
        ('training', 'Training'),
        ('holiday', 'Holiday'),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    marked_by = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="marked_attendance_records"
    )
    remarks = models.TextField(blank=True, null=True)
    clock_in = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    hours_worked = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    late_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["tenant", "date"]),
            models.Index(fields=["employee", "date"]),
        ]
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.get_status_display()})"


class EmployeeContract(TenantAwareModel):
    """One contract period for an employee. Renewals create a NEW row so the
    full history is preserved — an existing row is never rewritten."""

    CONTRACT_TYPE_CHOICES = [
        ("permanent", "Permanent"),
        ("fixed_term", "Fixed Term"),
        ("probation", "Probation"),
        ("temporary", "Temporary"),
        ("casual", "Casual"),
        ("consultant", "Consultant / Contract"),
        ("intern", "Internship"),
    ]
    RENEWAL_STATUS_CHOICES = [
        ("active", "Active"),
        ("expiring_soon", "Expiring Soon"),
        ("renewal_pending", "Renewal Pending"),
        ("renewed", "Renewed"),
        ("not_renewed", "Not Renewed"),
        ("expired", "Expired"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="contracts"
    )
    contract_type = models.CharField(max_length=30, choices=CONTRACT_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Blank = open-ended")
    probation_end_date = models.DateField(null=True, blank=True)
    salary_review_date = models.DateField(null=True, blank=True)
    renewal_status = models.CharField(
        max_length=20, choices=RENEWAL_STATUS_CHOICES, default="active", db_index=True
    )
    notes = models.TextField(blank=True, null=True)
    document = models.FileField(
        upload_to="employee_contracts/", blank=True, null=True
    )
    supersedes = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="renewed_by",
    )
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "employee"]),
            models.Index(fields=["tenant", "renewal_status"]),
            models.Index(fields=["tenant", "end_date"]),
        ]

    def __str__(self):
        return f"{self.employee} · {self.get_contract_type_display()} from {self.start_date}"

    @property
    def days_remaining(self):
        if not self.end_date:
            return None
        from datetime import date
        return (self.end_date - date.today()).days


class EmployeeDocument(TenantAwareModel):
    """A file held against an employee (NRC, CV, certificates, contract, ...),
    with an optional expiry so the dashboard can flag renewals.

    ``document_type`` is a free CharField (not a lookup) so schools are not
    forced to pre-configure a category list; a curated choice list is offered
    in the UI but any value is accepted.
    """

    STATUS_VALID = "valid"
    STATUS_EXPIRING = "expiring"
    STATUS_EXPIRED = "expired"

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="hr_documents"
    )
    document_type = models.CharField(max_length=100)
    file = models.FileField(upload_to="employee_documents/")
    original_filename = models.CharField(max_length=255, blank=True)
    note = models.CharField(max_length=255, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    uploaded_by_id = models.UUIDField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["tenant", "employee"]),
            models.Index(fields=["tenant", "expiry_date"]),
        ]

    def __str__(self):
        return f"{self.employee_id} · {self.document_type}"

    def status(self, *, soon_days=30):
        from datetime import date, timedelta
        if not self.expiry_date:
            return self.STATUS_VALID
        today = date.today()
        if self.expiry_date < today:
            return self.STATUS_EXPIRED
        if self.expiry_date <= today + timedelta(days=soon_days):
            return self.STATUS_EXPIRING
        return self.STATUS_VALID


class EmployeeQualification(TenantAwareModel):
    """A structured qualification record. Supplements the single free-text
    ``Employee.qualification`` field (kept for backwards compatibility)."""

    QUALIFICATION_TYPE_CHOICES = [
        ("academic", "Academic"),
        ("teaching", "Teaching"),
        ("professional", "Professional"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="qualifications_detail"
    )
    qualification_type = models.CharField(
        max_length=20, choices=QUALIFICATION_TYPE_CHOICES, default="academic"
    )
    name = models.CharField(max_length=255)
    institution = models.CharField(max_length=255, blank=True)
    year_obtained = models.PositiveIntegerField(null=True, blank=True)
    is_highest = models.BooleanField(default=False)
    document = models.ForeignKey(
        EmployeeDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="qualifications",
    )

    class Meta:
        ordering = ["-is_highest", "-year_obtained"]
        indexes = [models.Index(fields=["tenant", "employee"])]

    def __str__(self):
        return f"{self.employee_id} · {self.name}"


class EmploymentHistoryEvent(TenantAwareModel):
    """An append-only record of a material change to an employment record —
    the data behind the employee profile's 'Employment History' tab."""

    EVENT_TYPE_CHOICES = [
        ("employed", "Employed"),
        ("promotion", "Promotion"),
        ("department_change", "Department Change"),
        ("position_change", "Position Change"),
        ("grade_change", "Grade Change"),
        ("manager_change", "Reporting Manager Change"),
        ("salary_change", "Salary Change"),
        ("contract_renewal", "Contract Renewal"),
        ("status_change", "Status Change"),
        ("exit", "Exit"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="history_events"
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    effective_date = models.DateField()
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-effective_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "employee"]),
            models.Index(fields=["tenant", "event_type"]),
        ]

    def __str__(self):
        return f"{self.employee_id} · {self.get_event_type_display()} · {self.effective_date}"


class HRAuditLog(TenantAwareModel):
    """Generic who-changed-what trail for HR-sensitive mutations. Written via
    ``core.services.hr_audit.record_hr_audit`` from HR service methods."""

    actor_id = models.UUIDField(null=True, blank=True)
    actor_label = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=64, blank=True)
    field = models.CharField(max_length=100, blank=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    detail = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.action} {self.target_type}:{self.target_id}"


class HRTask(TenantAwareModel):
    """A reminder / to-do on the HR desk. Either created by hand or generated
    from expiry rules by the nightly ``hr_generate_tasks`` job."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    CATEGORY_CHOICES = [
        ("contract", "Contract"),
        ("probation", "Probation"),
        ("document", "Document"),
        ("training", "Training"),
        ("appraisal", "Appraisal"),
        ("onboarding", "Onboarding"),
        ("exit", "Exit"),
        ("general", "General"),
    ]
    SOURCE_MANUAL = "manual"
    SOURCE_AUTO = "auto"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="general")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, null=True, blank=True,
        related_name="hr_tasks",
    )
    assigned_to_id = models.UUIDField(null=True, blank=True)
    source = models.CharField(max_length=10, default=SOURCE_MANUAL)
    dedupe_key = models.CharField(
        max_length=200, blank=True,
        help_text="Set on auto-generated tasks to prevent duplicates.",
    )
    created_by_id = models.UUIDField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "dedupe_key"],
                condition=models.Q(dedupe_key__gt=""),
                name="uniq_hrtask_tenant_dedupe",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "due_date"]),
        ]

    def __str__(self):
        return self.title


class Vacancy(TenantAwareModel):
    """An open position HR is recruiting for. Applicants attach to it."""

    EMPLOYMENT_TYPE_CHOICES = [
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contract", "Contract"),
        ("temporary", "Temporary"),
        ("intern", "Internship"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("closed", "Closed"),
        ("filled", "Filled"),
        ("cancelled", "Cancelled"),
    ]

    title = models.CharField(max_length=255)
    department = models.ForeignKey(
        "EmployeeDepartment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="vacancies",
    )
    number_of_positions = models.PositiveIntegerField(default=1)
    job_description = models.TextField(blank=True)
    employment_type = models.CharField(
        max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default="full_time"
    )
    is_teaching_role = models.BooleanField(default=False)
    date_advertised = models.DateField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class Applicant(TenantAwareModel):
    """A candidate moving through the pipeline for one :class:`Vacancy`."""

    STAGE_CHOICES = [
        ("applied", "Applied"),
        ("shortlisted", "Shortlisted"),
        ("interview", "Interview"),
        ("reference_check", "Reference Check"),
        ("offered", "Offered"),
        ("hired", "Hired"),
        ("unsuccessful", "Unsuccessful"),
    ]
    ACTIVE_STAGES = ["applied", "shortlisted", "interview", "reference_check", "offered"]

    vacancy = models.ForeignKey(
        Vacancy, on_delete=models.CASCADE, related_name="applicants"
    )
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    cv = models.FileField(upload_to="applicant_cvs/", blank=True, null=True)
    qualifications_summary = models.TextField(blank=True)
    stage = models.CharField(
        max_length=20, choices=STAGE_CHOICES, default="applied", db_index=True
    )
    stage_changed_at = models.DateTimeField(null=True, blank=True)
    interview_date = models.DateField(null=True, blank=True)
    interview_panel = models.CharField(max_length=500, blank=True)
    interview_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    interview_comments = models.TextField(blank=True)
    reference_check_notes = models.TextField(blank=True)
    decision_notes = models.TextField(blank=True)
    converted_employee = models.OneToOneField(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="from_applicant",
    )
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "vacancy"]),
            models.Index(fields=["tenant", "stage"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} · {self.get_stage_display()}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class OnboardingChecklist(TenantAwareModel):
    """One onboarding checklist per employee, auto-created when the employee
    record is created. Progress is derived from its items."""

    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE, related_name="onboarding"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Default items generated for every new hire (label, order).
    DEFAULT_ITEMS = [
        "Employment contract signed",
        "Job description signed",
        "NRC / passport received",
        "Qualifications verified",
        "References checked",
        "Payroll details submitted",
        "School policies acknowledged",
        "Safeguarding requirements completed",
        "Staff ID issued",
        "System account created",
        "Email account created",
        "Department assigned",
        "Reporting manager assigned",
        "Orientation completed",
        "Probation review scheduled",
    ]

    class Meta:
        indexes = [models.Index(fields=["tenant", "completed_at"])]

    def __str__(self):
        return f"Onboarding · {self.employee_id}"

    def progress(self):
        items = list(self.items.all())
        total = len(items)
        done = sum(1 for i in items if i.is_done)
        return {
            "total": total,
            "done": done,
            "percent": round(done / total * 100) if total else 0,
        }


class OnboardingItem(TenantAwareModel):
    checklist = models.ForeignKey(
        OnboardingChecklist, on_delete=models.CASCADE, related_name="items"
    )
    label = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by_id = models.UUIDField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["tenant", "checklist"])]

    def __str__(self):
        return f"{'✓' if self.is_done else '○'} {self.label}"


class PerformanceReview(TenantAwareModel):
    """A performance / appraisal cycle for one employee. Suitable for both
    teaching and non-teaching staff — ``is_teacher_review`` selects the
    criteria template and enables the classroom-observation attachment."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_review", "In Review"),
        ("employee_ack", "Awaiting Employee"),
        ("completed", "Completed"),
    ]

    GENERIC_CRITERIA = [
        "Quality of work", "Productivity", "Job knowledge", "Reliability",
        "Communication", "Teamwork", "Initiative", "Professional conduct",
    ]
    TEACHER_CRITERIA = [
        "Lesson preparation", "Classroom management", "Teaching quality",
        "Learner engagement", "Curriculum delivery", "Assessment & marking",
        "Record keeping", "Parent communication", "Professional conduct",
        "Extracurricular participation",
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="performance_reviews"
    )
    reviewer = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviews_conducted",
    )
    review_period = models.CharField(max_length=100)
    review_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    is_teacher_review = models.BooleanField(default=False)
    overall_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    objectives = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    improvement_areas = models.TextField(blank=True)
    development_actions = models.TextField(blank=True)
    reviewer_comments = models.TextField(blank=True)
    employee_comments = models.TextField(blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    observation_document = models.FileField(
        upload_to="performance_observations/", blank=True, null=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-review_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "employee"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return f"{self.employee_id} · {self.review_period}"


class PerformanceCriterion(TenantAwareModel):
    review = models.ForeignKey(
        PerformanceReview, on_delete=models.CASCADE, related_name="criteria"
    )
    name = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["tenant", "review"])]

    def __str__(self):
        return f"{self.name}: {self.rating if self.rating is not None else '—'}"


class TrainingRecord(TenantAwareModel):
    """A training / CPD activity for one employee, with optional certificate
    and renewal date. Mandatory records feed the dashboard compliance panel."""

    CATEGORY_CHOICES = [
        ("child_safeguarding", "Child Safeguarding"),
        ("first_aid", "First Aid"),
        ("fire_safety", "Fire / Safety"),
        ("curriculum", "Curriculum Training"),
        ("classroom_management", "Classroom Management"),
        ("ict", "ICT"),
        ("leadership", "Leadership"),
        ("professional_development", "Professional Development"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    # Categories every school treats as mandatory — used for gap detection when
    # no per-tenant policy list is configured.
    MANDATORY_CATEGORIES = ["child_safeguarding", "first_aid", "fire_safety"]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="training_records"
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="other")
    provider = models.CharField(max_length=255, blank=True)
    training_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    certificate = models.FileField(upload_to="training_certificates/", blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")
    is_mandatory = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-training_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "employee"]),
            models.Index(fields=["tenant", "category"]),
            models.Index(fields=["tenant", "expiry_date"]),
        ]

    def __str__(self):
        return f"{self.employee_id} · {self.name}"

    def compliance_status(self, *, soon_days=60):
        from datetime import date, timedelta
        if self.status != "completed":
            return self.status
        if not self.expiry_date:
            return "valid"
        today = date.today()
        if self.expiry_date < today:
            return "expired"
        if self.expiry_date <= today + timedelta(days=soon_days):
            return "expiring"
        return "valid"


class EmployeeExit(TenantAwareModel):
    """The offboarding record for one employee. Completing it (all clearance
    items done) flips the employee to ``exited`` and writes an
    :class:`ArchivedEmployee` snapshot — the employee row itself is never
    deleted, so historical HR data survives."""

    EXIT_TYPE_CHOICES = [
        ("resignation", "Resignation"),
        ("termination", "Termination"),
        ("retirement", "Retirement"),
        ("end_of_contract", "End of Contract"),
        ("redundancy", "Redundancy"),
        ("death", "Death in Service"),
        ("other", "Other"),
    ]
    FINAL_PAY_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("paid", "Paid"),
    ]
    HANDOVER_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("complete", "Complete"),
    ]
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    DEFAULT_CLEARANCE_ITEMS = [
        "School property returned",
        "Laptop / device returned",
        "Books / materials returned",
        "Keys returned",
        "Finance clearance",
        "Classroom / department handover",
        "System access disabled",
        "Email disabled",
        "Final payment processed",
        "Service / reference letter prepared",
    ]

    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE, related_name="exit_record"
    )
    exit_type = models.CharField(max_length=20, choices=EXIT_TYPE_CHOICES)
    notice_date = models.DateField(null=True, blank=True)
    last_working_date = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)
    exit_interview_notes = models.TextField(blank=True)
    final_payment_status = models.CharField(
        max_length=20, choices=FINAL_PAY_CHOICES, default="pending"
    )
    outstanding_leave_days = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    handover_status = models.CharField(
        max_length=20, choices=HANDOVER_CHOICES, default="not_started"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="in_progress", db_index=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "status"])]

    def __str__(self):
        return f"Exit · {self.employee_id} ({self.get_exit_type_display()})"

    def clearance_progress(self):
        items = list(self.clearance_items.all())
        total = len(items)
        done = sum(1 for i in items if i.is_done)
        return {"total": total, "done": done, "percent": round(done / total * 100) if total else 0}


class ExitClearanceItem(TenantAwareModel):
    exit = models.ForeignKey(
        EmployeeExit, on_delete=models.CASCADE, related_name="clearance_items"
    )
    label = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by_id = models.UUIDField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["tenant", "exit"])]

    def __str__(self):
        return f"{'✓' if self.is_done else '○'} {self.label}"


class DisciplinaryCase(TenantAwareModel):
    """A disciplinary matter raised against one employee. Restricted view —
    gated by ``hr.disciplinary.view`` / ``hr.disciplinary.manage``. Every
    mutation is written to :class:`HRAuditLog`."""

    CASE_TYPE_CHOICES = [
        ("misconduct", "Misconduct"),
        ("poor_performance", "Poor Performance"),
        ("attendance", "Attendance / Punctuality"),
        ("policy_breach", "Policy Breach"),
        ("insubordination", "Insubordination"),
        ("safeguarding", "Safeguarding Concern"),
        ("other", "Other"),
    ]
    SEVERITY_CHOICES = [
        ("minor", "Minor"),
        ("major", "Major"),
        ("gross", "Gross Misconduct"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("under_investigation", "Under Investigation"),
        ("hearing", "Hearing Scheduled"),
        ("action_taken", "Action Taken"),
        ("appealed", "Appealed"),
        ("closed", "Closed"),
    ]
    OUTCOME_CHOICES = [
        ("none", "No Outcome Yet"),
        ("no_action", "No Action / Cleared"),
        ("verbal_warning", "Verbal Warning"),
        ("written_warning", "Written Warning"),
        ("final_warning", "Final Written Warning"),
        ("suspension", "Suspension"),
        ("demotion", "Demotion"),
        ("dismissal", "Dismissal"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="disciplinary_cases"
    )
    case_type = models.CharField(max_length=30, choices=CASE_TYPE_CHOICES)
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default="minor"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    incident_date = models.DateField(null=True, blank=True)
    reported_by_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="open", db_index=True
    )
    investigation_notes = models.TextField(blank=True)
    hearing_date = models.DateField(null=True, blank=True)
    outcome = models.CharField(
        max_length=20, choices=OUTCOME_CHOICES, default="none"
    )
    outcome_notes = models.TextField(blank=True)
    action_date = models.DateField(null=True, blank=True)
    warning_expiry_date = models.DateField(null=True, blank=True)
    appeal_notes = models.TextField(blank=True)
    document = models.FileField(
        upload_to="hr_disciplinary/", null=True, blank=True
    )
    created_by_id = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "employee"]),
        ]

    def __str__(self):
        return f"Disciplinary · {self.title} ({self.get_status_display()})"


class Grievance(TenantAwareModel):
    """A grievance raised by an employee. Restricted — same codenames as
    :class:`DisciplinaryCase`."""

    CATEGORY_CHOICES = [
        ("harassment", "Harassment / Bullying"),
        ("discrimination", "Discrimination"),
        ("workload", "Workload / Working Hours"),
        ("pay", "Pay / Benefits"),
        ("management", "Management / Supervision"),
        ("working_conditions", "Working Conditions"),
        ("safeguarding", "Safeguarding Concern"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("mediation", "Mediation"),
        ("resolved", "Resolved"),
        ("dismissed", "Dismissed"),
        ("escalated", "Escalated"),
    ]

    raised_by = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="grievances_raised"
    )
    against = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="grievances_against",
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    date_raised = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="submitted", db_index=True
    )
    handled_by_id = models.UUIDField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    document = models.FileField(
        upload_to="hr_grievance/", null=True, blank=True
    )
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "raised_by"]),
        ]

    def __str__(self):
        return f"Grievance · {self.title} ({self.get_status_display()})"


class PolicyDocument(TenantAwareModel):
    """An HR / school policy that staff may be required to read and acknowledge.
    Employees see outstanding acknowledgements in the "My HR" self-service area."""

    CATEGORY_CHOICES = [
        ("safeguarding", "Safeguarding / Child Protection"),
        ("code_of_conduct", "Code of Conduct"),
        ("hr", "HR / Employment"),
        ("health_safety", "Health & Safety"),
        ("it", "IT / Acceptable Use"),
        ("finance", "Finance / Procurement"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=255)
    category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, default="hr"
    )
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="hr_policies/", null=True, blank=True)
    version = models.CharField(max_length=40, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    requires_acknowledgement = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-effective_date", "title"]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["tenant", "category"]),
        ]

    def __str__(self):
        return f"{self.title}{f' v{self.version}' if self.version else ''}"


class PolicyAcknowledgement(TenantAwareModel):
    policy = models.ForeignKey(
        PolicyDocument, on_delete=models.CASCADE, related_name="acknowledgements"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="policy_acknowledgements"
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-acknowledged_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "policy", "employee"],
                name="uniq_policyack_tenant_policy_employee",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "employee"])]

    def __str__(self):
        return f"{self.employee_id} ack {self.policy_id}"


class AttendanceSummary(TenantAwareModel):
    """Model to store pre-calculated attendance summaries for efficient reporting"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance_summaries"
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="attendance_summaries"
    )
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="attendance_summaries"
    )
    term = models.ForeignKey(
        "Term",
        on_delete=models.CASCADE,
        related_name="attendance_summaries",
        null=True,
        blank=True,
    )

    # Summary period
    PERIOD_CHOICES = [
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
        ("TERM", "Term"),
        ("ANNUAL", "Annual"),
    ]
    period_type = models.CharField(
        max_length=20, choices=PERIOD_CHOICES, default="MONTHLY"
    )
    period_start = models.DateField()
    period_end = models.DateField()

    # Attendance statistics
    total_days = models.IntegerField(default=0)
    present_days = models.IntegerField(default=0)
    absent_days = models.IntegerField(default=0)
    half_day_count = models.IntegerField(default=0)
    late_count = models.IntegerField(default=0)

    # Calculated fields
    attendance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )

    # Remarks and notes
    remarks = models.TextField(blank=True, null=True)
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student", "period_type"]),
            models.Index(fields=["batch", "academic_year"]),
            models.Index(fields=["period_start", "period_end"]),
        ]
        unique_together = ["student", "period_type", "period_start", "period_end"]

    def __str__(self):
        return f"{self.student} - {self.period_type} ({self.period_start} to {self.period_end})"

    def calculate_percentage(self):
        """Calculate attendance percentage considering half-days"""
        if self.total_days > 0:
            # Half days count as 0.5 present days
            effective_present_days = self.present_days + (self.half_day_count * 0.5)
            self.attendance_percentage = (
                effective_present_days / self.total_days
            ) * 100
        else:
            self.attendance_percentage = 0
        return self.attendance_percentage

    @property
    def status_color(self):
        """Get color code based on attendance percentage"""
        if self.attendance_percentage >= 90:
            return "success"  # Green
        elif self.attendance_percentage >= 75:
            return "warning"  # Yellow
        else:
            return "danger"  # Red

    @property
    def status_text(self):
        """Get status text based on attendance percentage"""
        if self.attendance_percentage >= 90:
            return "Excellent"
        elif self.attendance_percentage >= 75:
            return "Satisfactory"
        else:
            return "Needs Improvement"


class Assignment(TenantAwareModel):
    title = models.CharField(max_length=255)
    content = models.TextField()
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="assignments"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="assignments"
    )
    due_date = models.DateField()
    attachment_file_name = models.CharField(max_length=255, blank=True, null=True)
    attachment_content_type = models.CharField(max_length=255, blank=True, null=True)
    attachment_file_size = models.IntegerField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["subject"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.subject}"


class AssignmentAnswer(TenantAwareModel):
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="answers"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="assignment_answers"
    )
    answer = models.TextField()
    attachment_file_name = models.CharField(max_length=255, blank=True, null=True)
    attachment_content_type = models.CharField(max_length=255, blank=True, null=True)
    attachment_file_size = models.IntegerField(blank=True, null=True)
    marks = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ["assignment", "student"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
        ]

    def __str__(self):
        return f"{self.assignment} - {self.student}"


class Reminder(TenantAwareModel):
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    delivery_date = models.DateTimeField()
    is_delivered = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["delivery_date"]),
        ]

    def __str__(self):
        return f"{self.subject} - {self.recipient}"


class Vehicle(TenantAwareModel):
    VEHICLE_STATUS_CHOICES = [
        ("active", "Active"),
        ("maintenance", "In Maintenance"),
        ("inactive", "Inactive"),
    ]

    vehicle_number = models.CharField(max_length=50)
    vehicle_type = models.CharField(max_length=100)
    seating_capacity = models.IntegerField()
    # Legacy direct route link. Route -> Vehicle is now the authoritative
    # direction (TransportRoute.vehicle); kept nullable for old rows.
    route = models.ForeignKey(
        "TransportRoute", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="legacy_vehicles",
    )
    make_model = models.CharField(max_length=255, blank=True, default="")
    manufacture_year = models.PositiveIntegerField(null=True, blank=True)
    insurance_provider = models.CharField(max_length=255, blank=True, default="")
    insurance_expiry = models.DateField(null=True, blank=True)
    roadworthiness_expiry = models.DateField(null=True, blank=True)
    registration_expiry = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=VEHICLE_STATUS_CHOICES, default="active"
    )
    odometer_km = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"{self.vehicle_number} - {self.vehicle_type}"

    COMPLIANCE_WARNING_DAYS = 30

    @property
    def compliance_flags(self):
        """{'Insurance': 'expired'|'expiring', ...} for docs needing attention."""
        from datetime import date as _date
        today = _date.today()
        out = {}
        labels = {
            "insurance_expiry": "Insurance",
            "roadworthiness_expiry": "Roadworthiness",
            "registration_expiry": "Registration",
        }
        for field, label in labels.items():
            value = getattr(self, field)
            if not value:
                continue
            delta = (value - today).days
            if delta < 0:
                out[label] = "expired"
            elif delta <= self.COMPLIANCE_WARNING_DAYS:
                out[label] = "expiring"
        return out


class TransportStaff(TenantAwareModel):
    """A driver or attendant operating school transport.

    Optionally linked to an Employee when the person is on regular staff;
    standalone otherwise (contracted drivers).
    """

    STAFF_TYPE_CHOICES = [
        ("driver", "Driver"),
        ("attendant", "Attendant"),
    ]

    staff_type = models.CharField(max_length=20, choices=STAFF_TYPE_CHOICES)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    alt_phone = models.CharField(max_length=30, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    national_id = models.CharField(max_length=50, blank=True, default="")
    license_number = models.CharField(max_length=50, blank=True, default="")
    license_expiry = models.DateField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=255, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=30, blank=True, default="")
    employee = models.ForeignKey(
        "Employee", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transport_staff_roles",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["staff_type"]),
        ]

    def __str__(self):
        return f"{self.get_staff_type_display()}: {self.full_name}"


class TransportRoute(TenantAwareModel):
    route_name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    fare = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=500, blank=True, default="")
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_routes",
    )
    driver = models.ForeignKey(
        TransportStaff, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="driver_routes",
    )
    attendant = models.ForeignKey(
        TransportStaff, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendant_routes",
    )
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.route_name


class TransportStop(TenantAwareModel):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, default="")
    landmark = models.CharField(max_length=255, blank=True, default="")
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class TransportRouteStop(TenantAwareModel):
    """One stop's position and timing on a route."""

    route = models.ForeignKey(
        TransportRoute, on_delete=models.CASCADE, related_name="route_stops"
    )
    stop = models.ForeignKey(
        TransportStop, on_delete=models.PROTECT, related_name="route_stops"
    )
    order = models.PositiveIntegerField(default=1)
    pickup_time = models.TimeField(null=True, blank=True)
    dropoff_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = ("route", "stop")
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["route", "order"]),
        ]

    def __str__(self):
        return f"{self.route.route_name} #{self.order}: {self.stop.name}"


class TransportSettings(TenantAwareModel):
    """Per-academic-year transport configuration (one row per year)."""

    BILLING_FREQUENCY_CHOICES = [
        ("one_time", "One Time"),
        ("monthly", "Monthly"),
        ("termly", "Termly"),
        ("yearly", "Yearly"),
    ]

    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, related_name="transport_settings"
    )
    default_pickup_time = models.TimeField(null=True, blank=True)
    default_dropoff_time = models.TimeField(null=True, blank=True)
    fee_category = models.ForeignKey(
        "FeeCategory", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transport_settings",
    )
    billing_frequency = models.CharField(
        max_length=20, choices=BILLING_FREQUENCY_CHOICES, null=True, blank=True,
        help_text="How often transport fees are billed (tenant-configurable; no Pinewood default)"
    )
    attendance_tracking_enabled = models.BooleanField(default=False)
    notify_on_changes = models.BooleanField(default=False)

    class Meta:
        unique_together = ("tenant", "academic_year")
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"Transport settings ({self.academic_year})"


class StudentTransportAssignment(TenantAwareModel):
    """A student bound to a route for a date range; the billable unit."""

    DIRECTION_CHOICES = [
        ("both", "Pickup & Drop-off"),
        ("pickup", "Pickup only"),
        ("dropoff", "Drop-off only"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="transport_assignments"
    )
    route = models.ForeignKey(
        TransportRoute, on_delete=models.PROTECT, related_name="student_assignments"
    )
    boarding_stop = models.ForeignKey(
        TransportRouteStop, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="student_assignments",
    )
    direction = models.CharField(
        max_length=10, choices=DIRECTION_CHOICES, default="both"
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    finance_fee = models.ForeignKey(
        "FinanceFee", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transport_assignments",
    )
    notes = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
            models.Index(fields=["route"]),
        ]

    def __str__(self):
        return f"{self.student} -> {self.route}"


class EmployeeTransportAssignment(TenantAwareModel):
    """An employee bound to a route for a date range. Not billed."""

    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="transport_assignments"
    )
    route = models.ForeignKey(
        TransportRoute, on_delete=models.PROTECT,
        related_name="employee_assignments",
    )
    boarding_stop = models.ForeignKey(
        TransportRouteStop, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employee_assignments",
    )
    direction = models.CharField(
        max_length=10, choices=StudentTransportAssignment.DIRECTION_CHOICES,
        default="both",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["employee"]),
        ]

    def __str__(self):
        return f"{self.employee} -> {self.route}"


class TransportFee(TenantAwareModel):
    """DEPRECATED. Retained for historical rows only.

    New transport billing flows through StudentTransportAssignment.finance_fee
    and the finance subsystem (FeeCategory / FinanceFee / FamilyInvoice).
    Do not write to this model.
    """

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="transport_fees"
    )
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.route}"


class HostelRoom(TenantAwareModel):
    room_number = models.CharField(max_length=50)
    room_type = models.CharField(max_length=100)
    capacity = models.IntegerField()
    rent = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"Room {self.room_number} - {self.room_type}"


class HostelFee(TenantAwareModel):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="hostel_fees"
    )
    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.room}"


class ArchivedStudent(TenantAwareModel):
    former_id = models.CharField(max_length=50)
    admission_no = models.CharField(max_length=50)
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    batch_name = models.CharField(max_length=255)
    course_name = models.CharField(max_length=255)
    status_description = models.TextField(blank=True, null=True)
    date_of_leaving = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["former_id"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (Archived)"


class ArchivedEmployee(TenantAwareModel):
    former_id = models.CharField(max_length=50)
    employee_number = models.CharField(max_length=50)
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    employee_department_name = models.CharField(max_length=255, blank=True, null=True)
    employee_category_name = models.CharField(max_length=255, blank=True, null=True)
    status_description = models.TextField(blank=True, null=True)
    date_of_leaving = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["former_id"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (Archived)"


class Country(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=10, blank=True, null=True)
    currency_code = models.CharField(max_length=10, blank=True, null=True)
    regional_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class StudentCategory(TenantAwareModel):
    name = models.CharField(max_length=255)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class EmployeeCategory(TenantAwareModel):
    name = models.CharField(max_length=255)
    prefix = models.CharField(max_length=50)
    status = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class EmployeePosition(TenantAwareModel):
    name = models.CharField(max_length=255)
    employee_category = models.ForeignKey(
        EmployeeCategory, on_delete=models.SET_NULL, null=True
    )
    status = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class EmployeeDepartment(TenantAwareModel):
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    status = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class EmployeeGrade(TenantAwareModel):
    name = models.CharField(max_length=255)
    priority = models.IntegerField()
    status = models.BooleanField(default=True)
    max_hours_day = models.IntegerField(blank=True, null=True)
    max_hours_week = models.IntegerField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class LeaveType(TenantAwareModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, null=True)
    default_annual_days = models.IntegerField(default=0)
    is_paid = models.BooleanField(default=True)
    status = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class EmployeeWorkingDaySettings(TenantAwareModel):
    """Tenant-wide employee working day / hours configuration (one row per tenant)."""
    working_days = models.JSONField(
        default=list, help_text="Weekday integers (0=Mon, 6=Sun) employees are expected to work"
    )
    default_daily_hours = models.DecimalField(
        max_digits=4, decimal_places=2, blank=True, null=True
    )
    half_day_hours_threshold = models.DecimalField(
        max_digits=4, decimal_places=2, blank=True, null=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        verbose_name = "Employee Working Day Settings"
        verbose_name_plural = "Employee Working Day Settings"

    def __str__(self):
        return f"Employee Working Day Settings - {self.tenant}"

    def save(self, *args, **kwargs):
        if not self.working_days:
            self.working_days = [0, 1, 2, 3, 4]
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls, tenant):
        settings, created = cls.objects.get_or_create(
            tenant=tenant,
            defaults={'working_days': [0, 1, 2, 3, 4]},
        )
        return settings


class PayrollCategory(TenantAwareModel):
    """A named pay component (earning or deduction) admins can attach to a
    payroll group — e.g. Basic Salary, Housing Allowance, PAYE. No built-in
    tax logic; admins configure their own fixed amounts/percentages.
    """
    CATEGORY_TYPE_CHOICES = [
        ('earning', 'Earning'),
        ('deduction', 'Deduction'),
    ]
    CALCULATION_TYPE_CHOICES = [
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage of Basic Pay'),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, null=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPE_CHOICES)
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPE_CHOICES, default='fixed')
    default_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    default_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    is_basic_pay = models.BooleanField(
        default=False, help_text="The one earning category used as the percentage base for this tenant"
    )
    taxable = models.BooleanField(default=False, help_text="Display-only flag; no tax calculation is applied")
    status = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class PayrollGroup(TenantAwareModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class PayrollGroupComponent(TenantAwareModel):
    """Through model: which PayrollCategory line items belong to a
    PayrollGroup, with optional per-group overrides of the category's
    default amount/percentage.
    """
    payroll_group = models.ForeignKey(PayrollGroup, on_delete=models.CASCADE, related_name="components")
    payroll_category = models.ForeignKey(PayrollCategory, on_delete=models.CASCADE)
    override_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    override_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        unique_together = ('payroll_group', 'payroll_category')
        ordering = ['order']

    def __str__(self):
        return f"{self.payroll_group.name} - {self.payroll_category.name}"


class EmployeePayrollProfile(TenantAwareModel):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="payroll_profile")
    payroll_group = models.ForeignKey(PayrollGroup, on_delete=models.SET_NULL, null=True, blank=True)
    basic_pay_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    bank_account_number = models.CharField(max_length=100, blank=True, null=True)
    bank_branch = models.CharField(max_length=255, blank=True, null=True)
    effective_date = models.DateField(blank=True, null=True)
    status = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"Payroll profile - {self.employee}"


class Payslip(TenantAwareModel):
    STATUS_CHOICES = [
        ('generated', 'Generated'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payslips")
    payroll_group = models.ForeignKey(PayrollGroup, on_delete=models.SET_NULL, null=True, blank=True)
    payroll_group_name_snapshot = models.CharField(max_length=255, blank=True, null=True)
    period_start = models.DateField()
    period_end = models.DateField()
    basic_pay_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generated')
    rejection_reason = models.TextField(blank=True, null=True)
    version = models.IntegerField(default=1)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_payslips", db_constraint=False
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_payslips", db_constraint=False
    )
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["employee", "period_start"]),
        ]
        unique_together = ('employee', 'period_start', 'period_end')

    def __str__(self):
        return f"{self.employee} - {self.period_start} to {self.period_end}"


class PayslipLineItem(TenantAwareModel):
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="line_items")
    payroll_category = models.ForeignKey(PayrollCategory, on_delete=models.SET_NULL, null=True, blank=True)
    category_name_snapshot = models.CharField(max_length=255)
    category_type_snapshot = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        ordering = ['order']

    def __str__(self):
        return f"{self.payslip} - {self.category_name_snapshot}"


class PayslipSettings(TenantAwareModel):
    """Tenant-wide config for what appears on a generated payslip PDF."""
    show_company_logo = models.BooleanField(default=True)
    show_bank_details = models.BooleanField(default=True)
    show_leave_balance = models.BooleanField(default=False)
    show_ytd_earnings = models.BooleanField(default=False)
    show_employee_photo = models.BooleanField(default=False)
    footer_text = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        verbose_name = "Payslip Settings"
        verbose_name_plural = "Payslip Settings"

    def __str__(self):
        return f"Payslip Settings - {self.tenant}"

    @classmethod
    def get_settings(cls, tenant):
        settings, created = cls.objects.get_or_create(tenant=tenant)
        return settings


class FeeReceiptSettings(TenantAwareModel):
    """Tenant-wide config for what appears on a generated fee receipt."""
    cashier = models.ForeignKey(
        'Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text="Employee whose name prints as Cashier on fee receipts",
    )
    receipt_prefix = models.CharField(
        max_length=10, default='PW',
        help_text="Prefix for auto-generated sequential receipt numbers, e.g. PW7022",
    )
    next_receipt_number = models.PositiveIntegerField(
        default=1,
        help_text="Next sequential number to allocate for a receipt (auto-increments)",
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        verbose_name = "Fee Receipt Settings"
        verbose_name_plural = "Fee Receipt Settings"

    def __str__(self):
        return f"Fee Receipt Settings - {self.tenant}"

    @classmethod
    def get_settings(cls, tenant):
        settings, created = cls.objects.get_or_create(tenant=tenant)
        return settings

    @classmethod
    def allocate_receipt_number(cls, tenant) -> str:
        """Atomically claim the next sequential receipt number for this
        tenant. Must be called inside an existing transaction.atomic() block
        so select_for_update() actually serializes concurrent cashiers."""
        settings, _ = cls.objects.select_for_update().get_or_create(tenant=tenant)
        number = settings.next_receipt_number
        settings.next_receipt_number = number + 1
        settings.save(update_fields=['next_receipt_number'])
        return f"{settings.receipt_prefix}{number}"


class PayslipReportTemplate(TenantAwareModel):
    """A saved payslip report configuration (filters + columns), re-runnable
    later — not a generic query builder, just a named preset.
    """
    name = models.CharField(max_length=255)
    filters = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False
    )
    is_default = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class ElectiveGroup(TenantAwareModel):
    name = models.CharField(max_length=255)
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="elective_groups"
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return self.name


class SkillSet(TenantAwareModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name


class SubjectSkillSet(TenantAwareModel):
    """
    Bridge model linking subjects to skill frameworks with assessment configuration.

    This model enables:
    - Multiple skill frameworks per subject
    - Flexible assessment modes (descriptive, numeric, hybrid, activity-based)
    - Weighted contribution to final grades
    - Activity exam grading profiles
    """
    ASSESSMENT_MODES = [
        ('DESCRIPTIVE', 'Descriptive Levels Only'),  # Not Yet, Beginning, Satisfactory, Good
        ('NUMERIC', 'Convert to Numeric Marks'),     # Skills contribute numeric marks
        ('HYBRID', 'Both Levels and Marks'),         # Show both descriptive and numeric
        ('ACTIVITY', 'Activity-Based Assessment'),   # Sports, Clubs, Projects with grading
    ]

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="skill_sets"
    )
    skill_set = models.ForeignKey(
        SkillSet, on_delete=models.CASCADE, related_name="subjects"
    )

    # Assessment Configuration
    assessment_mode = models.CharField(
        max_length=20,
        choices=ASSESSMENT_MODES,
        default='DESCRIPTIVE',
        help_text='How skills are assessed and reported'
    )
    weight_in_final_grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Percentage weight if contributing to final grade (0-100)'
    )
    grading_profile = models.ForeignKey(
        'GradingLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subject_skill_sets',
        help_text='LEGACY: Old grading profile. Use grading_scale instead.'
    )
    grading_scale = models.ForeignKey(
        'GradingScale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subject_skill_sets_custom',
        help_text='Custom grading scale for this skill set (overrides subject default)'
    )

    # Display Configuration
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this skill set is currently used for assessments'
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text='Order in which skill sets appear in reports'
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["subject", "skill_set"]),
            models.Index(fields=["subject", "is_active", "display_order"]),
        ]
        unique_together = [["subject", "skill_set", "tenant"]]
        ordering = ["display_order", "skill_set__name"]

    def __str__(self):
        return f"{self.subject.name} - {self.skill_set.name} ({self.get_assessment_mode_display()})"

    def supports_numeric_marks(self):
        """Returns True if this skill set contributes numeric marks"""
        return self.assessment_mode in ['NUMERIC', 'HYBRID', 'ACTIVITY']

    def supports_descriptive_levels(self):
        """Returns True if this skill set uses descriptive levels"""
        return self.assessment_mode in ['DESCRIPTIVE', 'HYBRID']


class Skill(TenantAwareModel):
    skill_set = models.ForeignKey(
        SkillSet, on_delete=models.CASCADE, related_name="skills"
    )
    name = models.CharField(max_length=255)
    formula = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["skill_set"]),
            models.Index(fields=["order"]),
        ]
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class SubSkill(TenantAwareModel):
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="sub_skills"
    )
    name = models.CharField(max_length=255)
    formula = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["skill"]),
            models.Index(fields=["order"]),
        ]
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.skill.name} - {self.name}"


class GradingScale(TenantAwareModel):
    """
    Dynamic grading scale system supporting multiple grading types.

    This model enables flexible grading configurations per subject/assessment.
    Different subjects can use different grading scales:
    - Letter grades (A/B/C)
    - Descriptive (Very Good, Good, Satisfactory)
    - Skill levels (Not Yet, Beginning, Satisfactory, Good)
    - Binary (Pass/Fail, Y/N)
    - Numeric marks
    """
    SCALE_TYPES = [
        ('LETTER', 'Letter Grades (A, B, C, D, E)'),
        ('DESCRIPTIVE', 'Descriptive (Very Good, Good, Satisfactory, Weak)'),
        ('NUMERIC', 'Numeric Marks'),
        ('LEVEL', 'Skill Levels (Not Yet, Beginning, Satisfactory, Good)'),
        ('BINARY', 'Pass/Fail or Y/N'),
        ('CUSTOM', 'Custom Grade Set'),
    ]

    name = models.CharField(
        max_length=255,
        help_text='e.g., Letter Grades, Descriptive Grades, Numeric Percentage'
    )
    code = models.CharField(
        max_length=50,
        help_text='Unique code for programmatic access'
    )
    scale_type = models.CharField(
        max_length=20,
        choices=SCALE_TYPES,
        help_text='Type of grading scale'
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text='Default scale for new subjects'
    )
    report_layout = models.CharField(
        max_length=20,
        choices=ReportTemplate.LAYOUT_CHOICES,
        blank=True,
        help_text='Report card format produced by this scheme (drives the report template layout)',
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["code"]),
        ]
        unique_together = [["tenant", "code"]]

    def __str__(self):
        return f"{self.name} ({self.get_scale_type_display()})"

    def get_grade_for_percentage(self, percentage):
        """Get the appropriate grade value for a given percentage"""
        grade_values = self.grade_values.filter(
            min_percentage__lte=percentage,
            max_percentage__gte=percentage
        ).order_by('-min_percentage').first()
        return grade_values


class GradeValue(TenantAwareModel):
    """
    Individual grade values within a grading scale.

    Examples:
    - Letter Scale: A (90-100), B (80-89), C (70-79)
    - Descriptive: Very Good, Good, Satisfactory, Weak
    - Skills: Not Yet, Beginning, Satisfactory, Good
    - Binary: Y, N or Pass, Fail
    """
    grading_scale = models.ForeignKey(
        GradingScale,
        on_delete=models.CASCADE,
        related_name='grade_values'
    )
    name = models.CharField(
        max_length=100,
        help_text='Display name: A, Very Good, 90-100, etc.'
    )
    code = models.CharField(
        max_length=50,
        help_text='Internal code for programmatic access'
    )
    min_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Minimum percentage for this grade (0-100)'
    )
    max_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Maximum percentage for this grade (0-100)'
    )
    gpa_value = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='GPA equivalent (e.g., 4.0 for A)'
    )
    display_order = models.IntegerField(
        default=0,
        help_text='Order in dropdowns and reports'
    )
    is_passing = models.BooleanField(
        default=True,
        help_text='Whether this grade is considered passing'
    )
    color_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        help_text='Hex color for UI display (#FF0000)'
    )

    class Meta:
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=["tenant", "grading_scale"]),
            models.Index(fields=["grading_scale", "display_order"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.grading_scale.name})"


class GradingLevel(TenantAwareModel):
    """LEGACY: Old grading level model - kept for backward compatibility"""
    name = models.CharField(max_length=255)
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="grading_levels"
    )
    grading_type = models.ForeignKey(
        "GradingType", on_delete=models.SET_NULL, null=True, blank=True
    )
    min_score = models.IntegerField()
    max_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    order = models.IntegerField()
    is_deleted = models.BooleanField(default=False)
    credit_points = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )
    description = models.TextField(blank=True, null=True)

    # Extended grading support
    gpa_points = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    cce_grade_point = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    icse_grade = models.CharField(max_length=2, blank=True, null=True)
    is_fail = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch", "is_deleted"]),
            models.Index(fields=["grading_type", "min_score"]),
        ]

    def __str__(self):
        return self.name


class Event(TenantAwareModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_common = models.BooleanField(default=False)
    is_holiday = models.BooleanField(default=False)
    is_exam = models.BooleanField(default=False)
    is_due = models.BooleanField(default=False)
    origin_id = models.IntegerField(blank=True, null=True)
    origin_type = models.CharField(max_length=255, blank=True, null=True)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, null=True, blank=True, related_name="events"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["is_common", "is_holiday", "is_exam"]),
            models.Index(fields=["academic_year", "is_holiday"]),
        ]

    def __str__(self):
        return self.title


class PeriodEntry(TenantAwareModel):
    month_date = models.DateField()
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="period_entries"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="period_entries"
    )
    class_timing = models.ForeignKey(
        "ClassTiming", on_delete=models.CASCADE, related_name="period_entries"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="period_entries"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["month_date", "batch"]),
        ]

    def __str__(self):
        return f"{self.subject.name} - {self.month_date}"


class ClassTiming(TenantAwareModel):
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="class_timings"
    )
    name = models.CharField(max_length=255)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch", "start_time", "end_time"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"


class Configuration(TenantAwareModel):
    config_key = models.CharField(max_length=255)
    config_value = models.TextField()

    class Meta:
        unique_together = ["config_key", "tenant"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["config_key"]),
        ]

    def __str__(self):
        return f"{self.config_key}: {self.config_value[:50]}"


class AdmissionApplication(TenantAwareModel):
    application_number = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
    )
    course_applied = models.ForeignKey(Course, on_delete=models.CASCADE)
    guardian_name = models.CharField(max_length=255)
    guardian_phone = models.CharField(max_length=20)
    guardian_email = models.EmailField(blank=True, null=True)
    address = models.TextField()
    status = models.CharField(max_length=50, default="pending")
    application_date = models.DateField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["application_number"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.application_number}"


def upload_to_documents(instance, filename):
    return f"admissions/{instance.tenant.id}/documents/{filename}"


def upload_to_photos(instance, filename):
    return f"admissions/{instance.tenant.id}/photos/{filename}"


class AcademicYear(TenantAwareModel):
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    admission_start_date = models.DateField(null=True, blank=True)
    admission_end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
        ]

    def clean(self):
        """Ensure only one academic year is active per tenant"""
        super().clean()
        if self.is_active and self.tenant_id:
            # Check if there's already an active academic year for this tenant
            existing_active = AcademicYear.objects.filter(
                tenant=self.tenant, is_active=True
            ).exclude(pk=self.pk)

            if existing_active.exists():
                from django.core.exceptions import ValidationError

                raise ValidationError("Only one academic year can be active at a time.")

    def save(self, *args, **kwargs):
        """Auto-deactivate other academic years when this one is set to active,
        and cascade the active/inactive state to all related batches."""
        if self.is_active and self.tenant_id:
            # Deactivate sibling years and cascade to their batches
            other_years = AcademicYear.objects.filter(
                tenant=self.tenant, is_active=True
            ).exclude(pk=self.pk)
            Batch.objects.filter(
                tenant=self.tenant, academic_year__in=other_years
            ).update(is_active=False)
            other_years.update(is_active=False)
            # Restore non-deleted batches for the year now being activated
            Batch.objects.filter(
                tenant=self.tenant, academic_year=self, is_deleted=False
            ).update(is_active=True)

        elif not self.is_active and self.pk and self.tenant_id:
            # Year explicitly deactivated — cascade to its batches
            Batch.objects.filter(
                tenant=self.tenant, academic_year=self
            ).update(is_active=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ExtendedAdmissionApplication(TenantAwareModel):
    application_number = models.CharField(max_length=50, unique=True)
    # academic_year and course_applied are chosen in step 1, so a freshly
    # started draft has neither yet — they must be nullable.
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="applications",
        null=True, blank=True,
    )
    course_applied = models.ForeignKey(
        Course, on_delete=models.CASCADE, null=True, blank=True,
    )
    terms_agreement = models.BooleanField(default=False)
    preferred_start_date = models.DateField(null=True, blank=True)
    application_date = models.DateTimeField(auto_now_add=True)
    current_step = models.IntegerField(default=1)
    status = models.CharField(
        max_length=50,
        choices=[
            ("draft", "Draft"),
            ("step1_completed", "Step 1 Completed"),
            ("step2_completed", "Step 2 Completed"),
            ("step3_completed", "Step 3 Completed"),
            ("step4_completed", "Step 4 Completed"),
            ("step5_completed", "Step 5 Completed"),
            ("step6_completed", "Step 6 Completed"),
            ("step7_completed", "Step 7 Completed"),
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("waitlisted", "Waitlisted"),
            ("admitted", "Admitted"),
        ],
        default="draft",
    )

    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
        blank=True,
    )
    nationality = models.CharField(max_length=100, blank=True)
    student_photo = models.FileField(
        upload_to=upload_to_photos,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png"])],
    )
    student_category = models.ForeignKey(
        StudentCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    religion = models.CharField(max_length=100, blank=True)
    birth_place = models.CharField(max_length=255, blank=True)
    mother_tongue = models.CharField(max_length=100, blank=True)
    preferred_name = models.CharField(
        max_length=100, blank=True,
        help_text="Name by which the child should be addressed in school",
    )
    home_language = models.CharField(
        max_length=100, blank=True,
        help_text="Language most commonly spoken in the child's home",
    )
    authorized_pickup_persons = models.TextField(
        blank=True, help_text="Person(s) authorised to collect the child from school"
    )

    address = models.TextField(blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.ForeignKey(
        "Country", on_delete=models.SET_NULL, null=True, blank=True
    )
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    guardian1_first_name = models.CharField(max_length=100, blank=True)
    guardian1_last_name = models.CharField(max_length=100, blank=True)
    guardian1_relation = models.CharField(max_length=50, blank=True)
    guardian1_occupation = models.CharField(max_length=200, blank=True)
    guardian1_office_address_line1 = models.CharField(max_length=255, blank=True)
    guardian1_office_city = models.CharField(max_length=100, blank=True)
    guardian1_office_phone1 = models.CharField(max_length=20, blank=True)
    guardian1_mobile = models.CharField(max_length=20, blank=True)
    guardian1_email = models.EmailField(blank=True)
    guardian1_house_plot_no = models.CharField(max_length=100, blank=True)
    guardian1_road_name = models.CharField(max_length=200, blank=True)
    guardian1_area_location = models.CharField(max_length=200, blank=True)
    guardian1_flat_block_name = models.CharField(max_length=200, blank=True)

    guardian2_first_name = models.CharField(max_length=100, blank=True)
    guardian2_last_name = models.CharField(max_length=100, blank=True)
    guardian2_relation = models.CharField(max_length=50, blank=True)
    guardian2_occupation = models.CharField(max_length=200, blank=True)
    guardian2_office_address_line1 = models.CharField(max_length=255, blank=True)
    guardian2_office_city = models.CharField(max_length=100, blank=True)
    guardian2_office_phone1 = models.CharField(max_length=20, blank=True)
    guardian2_mobile = models.CharField(max_length=20, blank=True)
    guardian2_email = models.EmailField(blank=True)
    guardian2_house_plot_no = models.CharField(max_length=100, blank=True)
    guardian2_road_name = models.CharField(max_length=200, blank=True)
    guardian2_area_location = models.CharField(max_length=200, blank=True)
    guardian2_flat_block_name = models.CharField(max_length=200, blank=True)

    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    emergency_contact_mobile = models.CharField(max_length=20, blank=True)
    emergency_contact_address = models.TextField(blank=True)

    previous_school_name = models.CharField(max_length=300, blank=True)
    previous_school_address = models.TextField(blank=True)
    previous_school_phone = models.CharField(max_length=20, blank=True)
    previous_school_email = models.EmailField(blank=True)
    expected_start_date = models.DateField(null=True, blank=True)

    has_medical_problems = models.BooleanField(null=True, blank=True)
    recent_hospitalization = models.BooleanField(null=True, blank=True)
    has_allergies = models.BooleanField(null=True, blank=True)
    medical_details = models.TextField(
        blank=True, help_text="Details if any medical questions answered YES"
    )

    religious_observances = models.TextField(
        blank=True, help_text="Special requests for religious observances"
    )
    background_information = models.TextField(
        blank=True,
        help_text="Background information to help understand the child better",
    )

    declaration_agreement = models.BooleanField(default=False)
    declaration_date = models.DateField(null=True, blank=True)
    declaration_signature_name = models.CharField(
        max_length=200, blank=True,
        help_text="Typed full name of parent/guardian as a digital signature",
    )
    fee_acknowledgment = models.BooleanField(
        default=False, help_text="Acknowledgment of admission fee payment requirement"
    )

    remarks = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admitted_student = models.ForeignKey(
        "Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_applications",
    )

    class Meta:
        ordering = ["-application_date"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["application_number"]),
            models.Index(fields=["academic_year", "status"]),
            models.Index(fields=["course_applied", "status"]),
        ]

    def __str__(self):
        return f"{self.application_number} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)

    @property
    def is_step1_complete(self):
        # Step 1: Terms and Conditions
        return bool(self.terms_agreement)

    @property
    def is_step2_complete(self):
        # Step 2: Academic Year & Course
        return bool(self.academic_year and self.course_applied)

    @property
    def is_step3_complete(self):
        # Step 3: Student Personal Details & Health
        required_fields = [
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "nationality",
        ]
        return all(getattr(self, field, None) for field in required_fields)

    @property
    def is_step4_complete(self):
        # Step 4: Guardian 1 Personal Information
        guardian1_required = [
            "guardian1_first_name",
            "guardian1_last_name",
            "guardian1_relation",
            "guardian1_mobile",
        ]
        return all(getattr(self, field, None) for field in guardian1_required)

    @property
    def is_step5_complete(self):
        # Step 5: Guardian 2 & Emergency Contact (all optional but health questions required)
        health_questions_answered = [
            self.has_medical_problems is not None,
            self.recent_hospitalization is not None,
            self.has_allergies is not None,
        ]
        return all(health_questions_answered)

    @property
    def is_step6_complete(self):
        # Step 6: Student Address & Previous School & Additional Information
        address_fields = ["address_line1", "city", "country"]
        return all(getattr(self, field, None) for field in address_fields)

    @property
    def is_step7_complete(self):
        # Step 7: Document Upload (optional, no validation required)
        return True

    @property
    def is_step8_complete(self):
        # Step 8: Declaration & Submission
        return (
            bool(self.declaration_agreement)
            and bool(self.fee_acknowledgment)
            and bool(self.declaration_date)
            and bool(self.declaration_signature_name)
        )

    @property
    def is_complete(self):
        return (
            self.is_step1_complete
            and self.is_step2_complete
            and self.is_step3_complete
            and self.is_step4_complete
            and self.is_step5_complete
            and self.is_step6_complete
            and self.is_step7_complete
        )

    def can_submit(self):
        return self.is_complete

    def get_next_step(self):
        if not self.is_step1_complete:
            return 1
        elif not self.is_step2_complete:
            return 2
        elif not self.is_step3_complete:
            return 3
        elif not self.is_step4_complete:
            return 4
        elif not self.is_step5_complete:
            return 5
        elif not self.is_step6_complete:
            return 6
        elif not self.is_step7_complete:
            return 7
        else:
            return None

    def advance_to_next_step(self):
        next_step = self.get_next_step()
        if next_step:
            self.current_step = next_step
            if next_step == 1 and self.is_step1_complete:
                self.status = "step1_completed"
            elif next_step == 2 and self.is_step2_complete:
                self.status = "step2_completed"
            elif next_step == 3 and self.is_step3_complete:
                self.status = "step3_completed"
            elif next_step == 4 and self.is_step4_complete:
                self.status = "step4_completed"
            elif next_step == 5 and self.is_step5_complete:
                self.status = "step5_completed"
            elif next_step == 6 and self.is_step6_complete:
                self.status = "step6_completed"
            elif next_step == 7 and self.is_step7_complete:
                self.status = "step7_completed"
        elif self.is_complete:
            self.current_step = 7
            self.status = "submitted"


class AdmissionDocument(TenantAwareModel):
    DOCUMENT_TYPES = [
        ("immunization_record", "Under 5 Card (Immunization Record)"),
        ("birth_certificate", "Birth Certificate"),
        ("utility_bill", "Utility Bill (Proof of Residence)"),
        ("parent1_id", "National Registration Card - Parent 1"),
        ("parent2_id", "National Registration Card - Parent 2"),
        ("student_photo", "Student Passport Photo"),
        ("passport_photo_1", "Passport Photo 1"),
        ("passport_photo_2", "Passport Photo 2"),
        ("academic_transcript", "Academic Transcript"),
        ("other", "Other Document"),
    ]

    application = models.ForeignKey(
        ExtendedAdmissionApplication, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(
        upload_to=upload_to_documents,
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf", "jpg", "jpeg", "png"])
        ],
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    is_required = models.BooleanField(default=True)
    verification_notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["application", "document_type"]
        indexes = [
            models.Index(fields=["tenant", "application"]),
            models.Index(fields=["document_type"]),
        ]

    def __str__(self):
        return f"{self.application.application_number} - {self.get_document_type_display()}"

    @property
    def file_size_mb(self):
        """Return file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)


class AdmissionApplicationNote(TenantAwareModel):
    application = models.ForeignKey(
        ExtendedAdmissionApplication, on_delete=models.CASCADE, related_name="notes"
    )
    note = models.TextField()
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="admission_notes"
    )
    is_internal = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "application"]),
        ]

    def __str__(self):
        return f"Note for {self.application.application_number} by {self.created_by.get_full_name()}"


class AdmissionApplicationStatus(TenantAwareModel):
    application = models.ForeignKey(
        ExtendedAdmissionApplication,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    previous_status = models.CharField(max_length=50, blank=True)
    new_status = models.CharField(max_length=50)
    changed_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="status_changes"
    )
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "application"]),
        ]

    def __str__(self):
        return f"{self.application.application_number}: {self.previous_status} → {self.new_status}"


class AdmissionTerms(TenantAwareModel):
    title = models.CharField(
        max_length=255, default="Terms and Conditions for Admission"
    )
    terms_content = models.TextField(
        help_text="HTML content for admission terms and conditions"
    )
    admission_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Admission fee amount (leave blank to use default)",
    )
    fee_currency = models.CharField(
        max_length=3, default="ZMW", help_text="Currency code (e.g., USD, GBP, ZMW)"
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(
        default=1, help_text="Order in which terms appear"
    )

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["tenant", "is_active", "order"]),
        ]
        verbose_name = "Admission Terms and Conditions"
        verbose_name_plural = "Admission Terms and Conditions"

    def __str__(self):
        return f"{self.title} (Order: {self.order})"


class QuickBooksRealmMapping(BaseModel):
    """Public-schema lookup of QuickBooks realm_id -> tenant.

    Webhooks arrive at one fixed URL for the whole (shared) Intuit app, with
    no tenant subdomain to route on, and QuickBooksIntegration.realm_id lives
    inside each tenant's own schema (invisible from the public schema). This
    table is the only public, schema-agnostic way to resolve "which school
    does this realmId belong to". Written by QuickBooksService.connect()/
    disconnect() (explicitly switching to the public schema to do so).
    """

    realm_id = models.CharField(max_length=255, unique=True)
    tenant = models.ForeignKey(School, on_delete=models.CASCADE, related_name="quickbooks_realm_mappings")

    def __str__(self):
        return f"realm {self.realm_id} -> {self.tenant.schema_name}"


class QuickBooksIntegration(TenantAwareModel):
    """Model to store QuickBooks integration credentials and tokens"""

    client_id = models.CharField(max_length=255, help_text="QuickBooks App Client ID")
    client_secret = EncryptedTextField(
        help_text="QuickBooks App Client Secret (encrypted at rest)"
    )
    redirect_uri = models.URLField(help_text="OAuth redirect URI")
    environment = models.CharField(
        max_length=20,
        choices=[("sandbox", "Sandbox"), ("production", "Production")],
        default="sandbox",
        help_text="QuickBooks environment",
    )

    # OAuth tokens
    access_token = EncryptedTextField(
        null=True, blank=True, help_text="Current access token (encrypted at rest)"
    )
    refresh_token = EncryptedTextField(
        null=True, blank=True, help_text="Refresh token (encrypted at rest)"
    )
    realm_id = models.CharField(
        max_length=255, null=True, blank=True, help_text="Company ID (realm_id)"
    )
    token_expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Token expiration time"
    )

    # Connection status
    is_connected = models.BooleanField(
        default=False, help_text="Whether QuickBooks is currently connected"
    )
    last_sync = models.DateTimeField(
        null=True, blank=True, help_text="Last successful sync time"
    )
    sync_enabled = models.BooleanField(
        default=True, help_text="Whether automatic sync is enabled"
    )

    # Company info from QuickBooks
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_country = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "is_connected"]),
        ]
        verbose_name = "QuickBooks Integration"
        verbose_name_plural = "QuickBooks Integrations"

    def __str__(self):
        status = "Connected" if self.is_connected else "Not Connected"
        return f"QuickBooks Integration - {status} ({self.environment})"

    def is_token_expired(self, buffer_minutes: int = 5):
        """
        Check if the access token is expired or will expire soon.

        Args:
            buffer_minutes: Minutes before actual expiration to consider token as expired
        """
        if not self.token_expires_at:
            return True
        from django.utils import timezone
        from datetime import date, timedelta

        # Add buffer time to avoid using tokens that are about to expire
        buffer_time = timedelta(minutes=buffer_minutes)
        return timezone.now() >= (self.token_expires_at - buffer_time)

    def time_until_expiry(self):
        """Get time remaining until token expires"""
        if not self.token_expires_at:
            return None

        return self.token_expires_at - timezone.now()

    def needs_refresh(self):
        """Check if token should be refreshed proactively"""
        return self.is_token_expired(buffer_minutes=10)  # Refresh 10 minutes early


class CurrencyConfiguration(TenantAwareModel):
    """Model to store currency configuration for the school"""

    # Currency details
    currency_code = models.CharField(
        max_length=3, help_text="ISO currency code (e.g., USD, EUR, KES)"
    )
    currency_symbol = models.CharField(
        max_length=10, help_text="Currency symbol (e.g., $, €, KSh)"
    )
    currency_name = models.CharField(
        max_length=100,
        help_text="Full currency name (e.g., US Dollar, Euro, Kenyan Shilling)",
    )

    # Display preferences
    symbol_position = models.CharField(
        max_length=15,
        choices=[
            ("before", "Before amount ($100)"),
            ("after", "After amount (100$)"),
            ("before_space", "Before with space ($ 100)"),
            ("after_space", "After with space (100 $)"),
        ],
        default="before",
        help_text="Position of currency symbol relative to amount",
    )

    # Formatting options
    decimal_places = models.PositiveIntegerField(
        default=2, help_text="Number of decimal places to display"
    )
    thousands_separator = models.CharField(
        max_length=1,
        choices=[
            (",", "Comma (1,000)"),
            (".", "Period (1.000)"),
            (" ", "Space (1 000)"),
        ],
        default=",",
        help_text="Separator for thousands",
    )
    decimal_separator = models.CharField(
        max_length=1,
        choices=[(".", "Period (100.50)"), (",", "Comma (100,50)")],
        default=".",
        help_text="Decimal separator",
    )

    # Settings
    is_active = models.BooleanField(
        default=True, help_text="Whether this currency is currently active"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
        ]
        verbose_name = "Currency Configuration"
        verbose_name_plural = "Currency Configurations"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_currency_per_tenant",
            )
        ]

    def __str__(self):
        return f"{self.currency_name} ({self.currency_code}) - {self.currency_symbol}"

    def format_amount(self, amount):
        """Format an amount according to the currency configuration"""
        try:
            # Convert to float if it's a Decimal
            amount_float = float(amount)

            # Format with decimal places
            formatted = f"{amount_float:.{self.decimal_places}f}"

            # Split into integer and decimal parts
            if "." in formatted:
                integer_part, decimal_part = formatted.split(".")
            else:
                integer_part, decimal_part = formatted, ""

            # Add thousands separator
            if len(integer_part) > 3:
                # Reverse, add separators every 3 digits, then reverse back
                reversed_int = integer_part[::-1]
                separated = self.thousands_separator.join(
                    [reversed_int[i : i + 3] for i in range(0, len(reversed_int), 3)]
                )
                integer_part = separated[::-1]

            # Combine with decimal separator
            if self.decimal_places > 0 and decimal_part:
                formatted_amount = (
                    f"{integer_part}{self.decimal_separator}{decimal_part}"
                )
            else:
                formatted_amount = integer_part

            # Add currency symbol based on position
            if self.symbol_position == "before":
                return f"{self.currency_symbol}{formatted_amount}"
            elif self.symbol_position == "after":
                return f"{formatted_amount}{self.currency_symbol}"
            elif self.symbol_position == "before_space":
                return f"{self.currency_symbol} {formatted_amount}"
            elif self.symbol_position == "after_space":
                return f"{formatted_amount} {self.currency_symbol}"
            else:
                return f"{self.currency_symbol}{formatted_amount}"

        except (ValueError, TypeError):
            return f"{self.currency_symbol}0.00"

    @classmethod
    def get_active_currency(cls, tenant):
        """Get the active currency for a tenant"""
        try:
            return cls.objects.get(tenant=tenant, is_active=True)
        except cls.DoesNotExist:
            # Return default Zambian Kwacha configuration if none exists
            return cls(
                tenant=tenant,
                currency_code="ZMW",
                currency_symbol="K",
                currency_name="Zambian Kwacha",
                symbol_position="before",
                decimal_places=2,
                thousands_separator=",",
                decimal_separator=".",
                is_active=True,
            )


# Family (Guardian) Invoicing Models
#
# Local source of truth for consolidated, per-guardian invoicing. Exists
# independently of QuickBooks so balances and PDF downloads never depend on
# QB reachability; the QuickBooksFeeInvoiceSync models below mirror this.


class FamilyInvoice(TenantAwareModel):
    """One consolidated invoice per guardian per academic year.

    Aggregates every FinanceFee charge raised for any of the guardian's
    children (via Student.immediate_contact) into a single billing document.
    """

    guardian = models.ForeignKey(
        "Guardian", on_delete=models.PROTECT, related_name="family_invoices"
    )
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.PROTECT, related_name="family_invoices"
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("open", "Open"),
            ("paid", "Paid"),
            ("void", "Void"),
        ],
        default="open",
    )
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["tenant", "guardian", "academic_year"]
        indexes = [
            models.Index(fields=["tenant", "guardian", "academic_year"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.guardian} ({self.total_amount})"


class FamilyInvoiceLine(TenantAwareModel):
    """One line on a FamilyInvoice, representing a single student's charge.

    finance_fee is the idempotency key: at most one line per charge, so
    re-running the upsert for one student's new fee never touches siblings.
    """

    invoice = models.ForeignKey(
        FamilyInvoice, on_delete=models.CASCADE, related_name="lines"
    )
    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="family_invoice_lines"
    )
    finance_fee = models.OneToOneField(
        "FinanceFee", on_delete=models.CASCADE, related_name="family_invoice_line",
    )
    academic_year = models.ForeignKey("AcademicYear", on_delete=models.PROTECT)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["invoice", "student"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.description} ({self.amount})"


# QuickBooks Fee Sync Models


class QuickBooksCustomerSync(TenantAwareModel):
    """Track guardian-to-QuickBooks customer synchronization.

    Keyed on Guardian (not Student) so that all of a guardian's children
    share a single QuickBooks customer record.
    """

    guardian = models.OneToOneField(
        "Guardian", on_delete=models.CASCADE, null=True, blank=True
    )
    quickbooks_customer_id = models.CharField(
        max_length=255, null=True, blank=True, help_text="QuickBooks Customer ID"
    )
    customer_display_name = models.CharField(
        max_length=255, help_text="Display name in QuickBooks"
    )
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ("synced", "Synced"),
            ("pending", "Pending Sync"),
            ("failed", "Sync Failed"),
            ("outdated", "Needs Update"),
        ],
        default="pending",
    )
    last_synced = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(
        null=True, blank=True, help_text="Last sync error message"
    )
    # Set by the QuickBooks webhook handler when a change made directly in
    # QuickBooks (edit/merge/delete) doesn't match local state - staff must
    # review and clear it manually; never auto-applied to the ledger.
    needs_review = models.BooleanField(default=False)
    review_note = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "sync_status"]),
            models.Index(fields=["quickbooks_customer_id"]),
        ]
        unique_together = ["tenant", "quickbooks_customer_id"]

    def __str__(self):
        return f"{self.guardian} -> QB Customer {self.quickbooks_customer_id}"


class QuickBooksFeeInvoiceSync(TenantAwareModel):
    """Header row for a consolidated guardian invoice synced to QuickBooks.

    One row per (guardian, academic_year) mirroring a FamilyInvoice; the
    per-student breakdown lives on QuickBooksFeeInvoiceLineSync below.
    """

    guardian = models.ForeignKey(
        "Guardian", on_delete=models.CASCADE, null=True, blank=True
    )
    academic_year = models.ForeignKey("AcademicYear", on_delete=models.CASCADE)
    # Back-reference to the local invoice this mirrors (idempotency anchor).
    family_invoice = models.OneToOneField(
        FamilyInvoice, on_delete=models.CASCADE, related_name="qb_invoice_sync",
        null=True, blank=True,
    )

    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    due_date = models.DateField()

    # QuickBooks information
    quickbooks_customer_sync = models.ForeignKey(
        QuickBooksCustomerSync, on_delete=models.CASCADE
    )
    quickbooks_invoice_id = models.CharField(max_length=255, null=True, blank=True)
    quickbooks_doc_number = models.CharField(max_length=100, null=True, blank=True)

    # Sync tracking
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("synced", "Synced to QuickBooks"),
            ("failed", "Sync Failed"),
            ("cancelled", "Cancelled"),
            ("outdated", "Legacy - superseded by guardian invoicing"),
        ],
        default="draft",
    )
    synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(null=True, blank=True)
    needs_review = models.BooleanField(default=False)
    review_note = models.TextField(null=True, blank=True)

    # Financial tracking
    balance_remaining = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "sync_status"]),
            models.Index(fields=["guardian", "academic_year"]),
            models.Index(fields=["quickbooks_invoice_id"]),
        ]
        unique_together = [
            ["tenant", "guardian", "academic_year"],
            ["tenant", "quickbooks_invoice_id"],
        ]

    def __str__(self):
        return f"Invoice {self.quickbooks_doc_number or 'Draft'} - {self.guardian} ({self.total_amount})"


class QuickBooksFeeInvoiceLineSync(TenantAwareModel):
    """One line within a consolidated QuickBooksFeeInvoiceSync header.

    finance_fee is the idempotency key: a re-run for one student's new
    charge only touches/creates this row, never re-touches sibling lines.
    """

    invoice_sync = models.ForeignKey(
        QuickBooksFeeInvoiceSync, on_delete=models.CASCADE, related_name="lines"
    )
    student = models.ForeignKey("Student", on_delete=models.CASCADE)
    finance_fee = models.OneToOneField(
        "FinanceFee", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="qb_invoice_line_syncs",
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    # QuickBooks' Line.Id for this specific line, so it can be sparse-updated
    # without resending the whole invoice.
    qb_line_id = models.CharField(max_length=100, null=True, blank=True)

    sync_status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("synced", "Synced to QuickBooks"),
            ("failed", "Sync Failed"),
        ],
        default="draft",
    )
    synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(null=True, blank=True)
    needs_review = models.BooleanField(default=False)
    review_note = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["invoice_sync", "student"]),
        ]
        unique_together = ["tenant", "finance_fee"]

    def __str__(self):
        return f"{self.student} - {self.description} ({self.amount})"


class QuickBooksFeePaymentSync(TenantAwareModel):
    """Track fee payments synchronized with QuickBooks"""

    # Local payment information
    student = models.ForeignKey("Student", on_delete=models.CASCADE)
    related_invoice = models.ForeignKey(
        QuickBooksFeeInvoiceSync, on_delete=models.CASCADE, null=True, blank=True
    )
    # Back-reference to the local payment ledger row this mirrors. Unique so a
    # given FeeTransaction syncs to QuickBooks at most once (idempotency key).
    fee_transaction = models.ForeignKey(
        "FeeTransaction", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="qb_payment_syncs",
    )

    # Payment details
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    # QuickBooks information
    quickbooks_customer_sync = models.ForeignKey(
        QuickBooksCustomerSync, on_delete=models.CASCADE
    )
    quickbooks_payment_id = models.CharField(max_length=255, null=True, blank=True)

    # Sync tracking
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending Sync"),
            ("synced", "Synced to QuickBooks"),
            ("failed", "Sync Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
    )
    synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(null=True, blank=True)
    needs_review = models.BooleanField(default=False)
    review_note = models.TextField(null=True, blank=True)

    # Receipt information
    receipt_number = models.CharField(max_length=100, null=True, blank=True)
    receipt_generated = models.BooleanField(default=False)
    receipt_sent = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "sync_status"]),
            models.Index(fields=["student", "payment_date"]),
            models.Index(fields=["quickbooks_payment_id"]),
            models.Index(fields=["receipt_number"]),
        ]
        unique_together = [
            ["tenant", "quickbooks_payment_id"],
            ["tenant", "fee_transaction"],
        ]

    def __str__(self):
        return f"Payment {self.receipt_number or 'Pending'} - {self.student} ({self.amount})"

    def generate_receipt_number(self):
        """Generate a unique receipt number"""
        if not self.receipt_number:
            from django.utils import timezone

            year = timezone.now().year
            # Get count of payments for this year
            count = (
                QuickBooksFeePaymentSync.objects.filter(
                    tenant=self.tenant,
                    payment_date__year=year,
                    receipt_number__isnull=False,
                ).count()
                + 1
            )

            self.receipt_number = f"RCP{year}{count:06d}"
            self.save(update_fields=["receipt_number"])


class QuickBooksSyncLog(TenantAwareModel):
    """Log all QuickBooks synchronization activities"""

    SYNC_TYPES = [
        ("customer", "Customer Sync"),
        ("invoice", "Invoice Sync"),
        ("payment", "Payment Sync"),
        ("bulk_sync", "Bulk Sync Operation"),
    ]

    ACTION_TYPES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("sync", "Sync"),
    ]

    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("partial", "Partial Success"),
    ]

    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    action_type = models.CharField(max_length=10, choices=ACTION_TYPES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    # Reference to the object being synced
    object_type = models.CharField(max_length=50)  # Model name
    object_id = models.UUIDField(null=True, blank=True)  # Object ID
    quickbooks_id = models.CharField(max_length=255, null=True, blank=True)

    # Sync details
    details = models.JSONField(default=dict, help_text="Additional sync details")
    error_message = models.TextField(null=True, blank=True)

    # Performance tracking
    duration_seconds = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "sync_type", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.sync_type} {self.action_type} - {self.status} ({self.created_at})"
        )


class QuickBooksConfiguration(TenantAwareModel):
    """QuickBooks-specific configuration for fee sync"""

    # Default accounts and items
    default_income_account = models.CharField(max_length=255, null=True, blank=True)
    default_service_item = models.CharField(max_length=255, null=True, blank=True)
    default_payment_method = models.CharField(max_length=255, null=True, blank=True)

    # Sync preferences
    auto_sync_customers = models.BooleanField(default=True)
    auto_sync_invoices = models.BooleanField(default=True)
    auto_sync_payments = models.BooleanField(default=True)

    # Invoice settings
    invoice_prefix = models.CharField(
        max_length=10, default="FEE", help_text="Prefix for fee invoices"
    )
    payment_terms_days = models.IntegerField(
        null=True, blank=True, help_text="Default payment terms in days (tenant-configurable; no Pinewood default)"
    )

    # Email settings
    send_invoices_by_email = models.BooleanField(default=False)
    send_receipts_by_email = models.BooleanField(default=True)

    # Reconciliation
    last_reconciliation_date = models.DateTimeField(null=True, blank=True)
    reconciliation_enabled = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"QB Config - {self.tenant.name}"


# Grading System Models
class GradingType(TenantAwareModel):
    """Different grading systems supported: Normal, GPA, CCE, ICSE, CWA"""

    GRADING_TYPES = [
        ("NORMAL", "Normal"),
        ("GPA", "GPA"),
        ("CCE", "CCE (Continuous Comprehensive Evaluation)"),
        ("ICSE", "ICSE"),
        ("CWA", "CWA (Course Weighted Average)"),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, choices=GRADING_TYPES)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # GPA specific settings
    gpa_scale = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Maximum GPA (e.g., 4.0)",
    )

    # CCE specific settings
    cce_scholastic_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=70.00,
        help_text="Scholastic assessment weight %",
    )
    cce_coscholastic_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=30.00,
        help_text="Co-scholastic assessment weight %",
    )

    class Meta:
        unique_together = ["tenant", "code"]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["code"]),
        ]

    def clean(self):
        if self.cce_scholastic_weight + self.cce_coscholastic_weight != 100:
            raise ValidationError(
                "CCE scholastic and co-scholastic weights must sum to 100%"
            )

    def __str__(self):
        return f"{self.name} ({self.get_code_display()})"


class CoScholasticAssessment(TenantAwareModel):
    """Co-scholastic assessments for CCE system"""

    ASSESSMENT_TYPES = [
        ("LIFE_SKILLS", "Life Skills"),
        ("WORK_EDUCATION", "Work Education"),
        ("VISUAL_ARTS", "Visual Arts"),
        ("PERFORMING_ARTS", "Performing Arts"),
        ("HEALTH_PHYSICAL", "Health & Physical Education"),
        ("DISCIPLINE", "Discipline"),
        ("GAMES_SPORTS", "Games & Sports"),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, choices=ASSESSMENT_TYPES)
    description = models.TextField(blank=True, null=True)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["tenant", "code"]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.name}"


class SubjectGradingSettings(TenantAwareModel):
    """Subject-specific grading configuration"""

    subject = models.OneToOneField(
        Subject, on_delete=models.CASCADE, related_name="grading_settings"
    )
    grading_type = models.ForeignKey(GradingType, on_delete=models.CASCADE)

    # Credit settings
    credit_hours = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)
    is_elective = models.BooleanField(default=False)

    # Assessment weightings
    internal_assessment_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=30.00,
        help_text="Internal assessment weight %",
    )
    external_assessment_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=70.00,
        help_text="External assessment weight %",
    )

    # CCE specific
    formative_assessment_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Formative assessment weight %",
    )
    summative_assessment_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Summative assessment weight %",
    )

    class Meta:
        indexes = [
            models.Index(fields=["subject", "grading_type"]),
        ]

    def clean(self):
        if self.internal_assessment_weight + self.external_assessment_weight != 100:
            raise ValidationError(
                "Internal and external assessment weights must sum to 100%"
            )

    def __str__(self):
        return f"{self.subject.name} - {self.grading_type.name}"


class StudentGradingProfile(TenantAwareModel):
    """Student's grading profile for tracking cumulative performance"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="grading_profiles"
    )
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    grading_type = models.ForeignKey(GradingType, on_delete=models.CASCADE)

    # Cumulative metrics
    cumulative_gpa = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    total_credits_attempted = models.DecimalField(
        max_digits=6, decimal_places=2, default=0
    )
    total_credits_earned = models.DecimalField(
        max_digits=6, decimal_places=2, default=0
    )

    # CCE specific
    cce_scholastic_grade = models.CharField(max_length=2, blank=True, null=True)
    cce_coscholastic_grade = models.CharField(max_length=2, blank=True, null=True)
    overall_cce_grade = models.CharField(max_length=2, blank=True, null=True)

    # Status tracking
    is_promoted = models.BooleanField(default=False)
    promotion_status = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ["student", "academic_year", "grading_type"]
        indexes = [
            models.Index(fields=["student", "academic_year"]),
            models.Index(fields=["cumulative_gpa"]),
        ]

    def __str__(self):
        return f"{self.student.full_name} - {self.academic_year.name} - {self.grading_type.name}"


class EnhancedExamScore(TenantAwareModel):
    """Enhanced exam score with comprehensive grading support"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="enhanced_exam_scores"
    )
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name="enhanced_scores"
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    # Raw scores
    obtained_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100.00)

    # Internal/External breakdown
    internal_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    external_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    internal_total = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    external_total = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    # CCE breakdown
    formative_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    summative_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    formative_total = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    summative_total = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    # Calculated results
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    grade = models.CharField(max_length=10, blank=True, null=True)
    grade_points = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    credit_points = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    # Status
    is_pass = models.BooleanField(null=True, blank=True)
    is_absent = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ["student", "exam", "subject"]
        indexes = [
            models.Index(fields=["exam", "subject"]),
            models.Index(fields=["student", "exam"]),
            models.Index(fields=["grade", "is_pass"]),
        ]

    def calculate_percentage(self):
        if self.obtained_marks is not None and self.total_marks > 0:
            return (self.obtained_marks / self.total_marks) * 100
        return None

    def save(self, *args, **kwargs):
        if self.obtained_marks is not None:
            self.percentage = self.calculate_percentage()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.full_name} - {self.exam.name} - {self.subject.name}: {self.obtained_marks}/{self.total_marks}"


class CoScholasticScore(TenantAwareModel):
    """Co-scholastic assessment scores for CCE"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="coscholastic_scores"
    )
    assessment = models.ForeignKey(CoScholasticAssessment, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, null=True, blank=True)

    # Scores
    obtained_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)

    # Grade
    grade = models.CharField(max_length=2, blank=True, null=True)  # A+, A, B+, etc.

    # Qualitative assessment
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ["student", "assessment", "academic_year", "term"]
        indexes = [
            models.Index(fields=["student", "academic_year"]),
            models.Index(fields=["assessment", "term"]),
        ]

    def __str__(self):
        return f"{self.student.full_name} - {self.assessment.name}: {self.grade}"


# Early Childhood Skills Assessment Models
class SkillCategory(TenantAwareModel):
    """Categories for early childhood skills assessment"""

    SKILL_CATEGORIES = [
        ("MOTOR_SKILLS", "Motor Skills"),
        ("CONCEPTUAL_SKILLS", "Conceptual Skills"),
        ("COMMUNICATION_SKILLS", "Communication Skills"),
        ("CREATIVE_SKILLS", "Creative Skills"),
        ("SOCIAL_SKILLS", "Social Skills"),
        ("CONCENTRATION_SKILLS", "Concentration Skills"),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, choices=SKILL_CATEGORIES)
    description = models.TextField(blank=True, null=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["tenant", "code"]
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["code", "display_order"]),
        ]

    def __str__(self):
        return self.name


class SkillItem(TenantAwareModel):
    """Individual skills to be assessed"""

    category = models.ForeignKey(
        SkillCategory, on_delete=models.CASCADE, related_name="skill_items"
    )
    description = models.TextField(help_text="Description of the skill to be assessed")
    # Batches (classes) this activity applies to. Empty = shared across all
    # pre-grade classes. Lets Beginners / Middle Class / Reception batches have
    # their own activity content under the same category structure, and lets one
    # activity be attached to several batches at once.
    batches = models.ManyToManyField(
        Batch, blank=True, related_name="skill_items",
        help_text="Classes/batches this activity applies to; leave empty to share across all pre-grade classes",
    )
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # Age-related settings
    min_age_months = models.IntegerField(
        null=True, blank=True, help_text="Minimum age in months for this skill"
    )
    max_age_months = models.IntegerField(
        null=True, blank=True, help_text="Maximum age in months for this skill"
    )

    class Meta:
        ordering = ["category", "display_order", "description"]
        indexes = [
            models.Index(fields=["category", "display_order"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return f"{self.category.name}: {self.description[:50]}"


class SkillsAssessment(TenantAwareModel):
    """Main assessment record for a student's skills"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="skills_assessments"
    )
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, null=True, blank=True)
    assessment_date = models.DateField()

    # Assessment metadata
    assessor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="skills_assessments",
    )
    notes = models.TextField(blank=True, null=True)

    # Status
    is_completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["student", "academic_year", "term"]
        indexes = [
            models.Index(fields=["student", "academic_year"]),
            models.Index(fields=["assessment_date"]),
            models.Index(fields=["is_completed"]),
        ]

    def __str__(self):
        return f"{self.student.full_name} - {self.academic_year.name} - {self.term.name if self.term else 'Full Year'}"


class SkillAssessmentResult(TenantAwareModel):
    """Individual skill assessment results"""

    SKILL_LEVELS = [
        ("NOT_YET", "Not Yet"),
        ("BEGINNING", "Beginning"),
        ("SATISFACTORY", "Satisfactory"),
        ("GOOD", "Good"),
    ]

    assessment = models.ForeignKey(
        SkillsAssessment, on_delete=models.CASCADE, related_name="results"
    )
    skill_item = models.ForeignKey(
        SkillItem, on_delete=models.CASCADE, related_name="assessment_results"
    )
    level = models.CharField(max_length=20, choices=SKILL_LEVELS)

    # Additional tracking
    assessment_date = models.DateField()
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ["assessment", "skill_item"]
        indexes = [
            models.Index(fields=["assessment", "skill_item"]),
            models.Index(fields=["skill_item", "level"]),
        ]

    def __str__(self):
        return f"{self.assessment.student.full_name} - {self.skill_item.description[:30]}: {self.get_level_display()}"


class ActivityProfile(TenantAwareModel):
    """
    Activity categories for activity-based assessments.

    Examples from Fedena:
    - CLUBS (Chess, Drama, Debate, Art and Craft)
    - SPORTS (Football, Basketball, Swimming)
    - PROJECT WORK
    - HOMEWORK (Submission, Presentation, Effort)
    - OTHER
    """
    name = models.CharField(
        max_length=255,
        help_text='e.g., CLUBS, SPORTS, PROJECT WORK, HOMEWORK'
    )
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return self.display_name


class Activity(TenantAwareModel):
    """
    Individual activities within an activity profile.

    Examples:
    - Chess (under CLUBS)
    - Drama (under CLUBS)
    - Submission (under HOMEWORK)
    - Art and Craft (under CLUBS)
    """
    name = models.CharField(
        max_length=255,
        help_text='e.g., Chess, Art and Craft, Drama'
    )
    activity_profile = models.ForeignKey(
        ActivityProfile,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Activities'
        indexes = [
            models.Index(fields=["tenant", "activity_profile"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.activity_profile.name})"


class ActivityAssessment(TenantAwareModel):
    """
    Activity-based assessment session.

    Links activities to subjects via SubjectSkillSet with assessment_mode='ACTIVITY'.
    Allows grading students on activities like sports, clubs, projects.
    """
    subject_skill_set = models.ForeignKey(
        SubjectSkillSet,
        on_delete=models.CASCADE,
        related_name='activity_assessments',
        help_text='Links to subject configured for activity assessment'
    )
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='assessments'
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='activity_assessments',
        null=True,
        blank=True
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='activity_assessments'
    )
    assessment_date = models.DateField()
    is_published = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "subject_skill_set", "term"]),
        ]

    def __str__(self):
        return f"{self.activity.name} - {self.subject_skill_set.subject.name} ({self.assessment_date})"


class ActivityGrade(TenantAwareModel):
    """
    Student grade for an activity assessment.

    Uses GradingLevel (A/B/C/D/E/F) for grading activities.
    """
    activity_assessment = models.ForeignKey(
        ActivityAssessment,
        on_delete=models.CASCADE,
        related_name='grades'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='activity_grades'
    )
    grading_level = models.ForeignKey(
        GradingLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_grades',
        help_text='Grade: A/B/C/D/E/F'
    )
    remarks = models.TextField(blank=True, null=True)
    is_absent = models.BooleanField(default=False)

    class Meta:
        unique_together = ['activity_assessment', 'student', 'tenant']
        indexes = [
            models.Index(fields=["tenant", "student"]),
            models.Index(fields=["activity_assessment", "student"]),
        ]

    def __str__(self):
        grade_display = self.grading_level.name if self.grading_level else 'No Grade'
        return f"{self.student.full_name} - {self.activity_assessment.activity.name}: {grade_display}"


class SkillsBasedGradingProfile(TenantAwareModel):
    """Overall skills-based grading profile for early childhood students"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="skills_grading_profiles"
    )
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

    # Summary statistics
    total_skills_assessed = models.IntegerField(default=0)
    not_yet_count = models.IntegerField(default=0)
    beginning_count = models.IntegerField(default=0)
    satisfactory_count = models.IntegerField(default=0)
    good_count = models.IntegerField(default=0)

    # Calculated percentages
    not_yet_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00
    )
    beginning_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00
    )
    satisfactory_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00
    )
    good_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # Overall assessment
    overall_development_level = models.CharField(
        max_length=20, choices=SkillAssessmentResult.SKILL_LEVELS, null=True, blank=True
    )

    # Progress tracking
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["student", "academic_year"]
        indexes = [
            models.Index(fields=["student", "academic_year"]),
            models.Index(fields=["overall_development_level"]),
        ]

    def calculate_statistics(self):
        """Calculate and update statistics from assessment results"""
        assessments = SkillsAssessment.objects.filter(
            student=self.student, academic_year=self.academic_year, is_completed=True
        )

        total_results = SkillAssessmentResult.objects.filter(assessment__in=assessments)

        self.total_skills_assessed = total_results.count()
        self.not_yet_count = total_results.filter(level="NOT_YET").count()
        self.beginning_count = total_results.filter(level="BEGINNING").count()
        self.satisfactory_count = total_results.filter(level="SATISFACTORY").count()
        self.good_count = total_results.filter(level="GOOD").count()

        if self.total_skills_assessed > 0:
            self.not_yet_percentage = (
                self.not_yet_count / self.total_skills_assessed
            ) * 100
            self.beginning_percentage = (
                self.beginning_count / self.total_skills_assessed
            ) * 100
            self.satisfactory_percentage = (
                self.satisfactory_count / self.total_skills_assessed
            ) * 100
            self.good_percentage = (self.good_count / self.total_skills_assessed) * 100

            # Determine overall development level based on majority
            if self.good_percentage >= 60:
                self.overall_development_level = "GOOD"
            elif self.satisfactory_percentage + self.good_percentage >= 60:
                self.overall_development_level = "SATISFACTORY"
            elif (
                self.beginning_percentage
                + self.satisfactory_percentage
                + self.good_percentage
                >= 60
            ):
                self.overall_development_level = "BEGINNING"
            else:
                self.overall_development_level = "NOT_YET"

        self.save()

    def __str__(self):
        return f"{self.student.full_name} - {self.academic_year.name} Skills Profile"


# Priority Phase 1 Models - Enhanced Academic and Assessment Features
# These models enhance existing functionality without replacing any data

class AttendanceLabel(TenantAwareModel):
    """Attendance status types (Present, Absent, Late, etc.)"""
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10, unique=True)
    color_code = models.CharField(max_length=7, default="#000000")  # Hex color
    is_considered_present = models.BooleanField(default=True)
    affects_attendance_percentage = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = ["code", "tenant"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class AttendanceSettings(TenantAwareModel):
    """Global attendance configuration settings"""
    # Attendance calculation method
    CALCULATION_CHOICES = [
        ('student_admission', 'Student admission date'),
        ('batch_start', 'Batch start date'),
    ]
    calculation_method = models.CharField(
        max_length=20,
        choices=CALCULATION_CHOICES,
        default='batch_start'
    )

    # Attendance marking frequency
    FREQUENCY_CHOICES = [
        ('open', 'Open'),
        ('lock', 'Lock'),
    ]
    mark_frequency = models.CharField(
        max_length=10,
        choices=FREQUENCY_CHOICES,
        default='open'
    )

    # Custom attendance settings
    enable_custom_attendance = models.BooleanField(default=True)

    # Lock settings
    lock_after_days = models.IntegerField(default=7, help_text="Days after which attendance gets locked")
    allow_admin_unlock = models.BooleanField(default=True)

    # Notification settings
    send_absence_notifications = models.BooleanField(default=True)
    notification_threshold = models.IntegerField(default=3, help_text="Send notification after X consecutive absences")

    # School calendar settings
    working_days = models.JSONField(default=list, help_text="Weekday integers (0=Mon, 6=Sun) when school operates")

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
        ]
        verbose_name = "Attendance Settings"
        verbose_name_plural = "Attendance Settings"

    def __str__(self):
        return f"Attendance Settings - {self.get_calculation_method_display()}"

    def save(self, *args, **kwargs):
        if not self.working_days:
            self.working_days = [0, 1, 2, 3, 4]
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls, tenant):
        """Get or create attendance settings for tenant"""
        settings, created = cls.objects.get_or_create(
            tenant=tenant,
            defaults={
                'calculation_method': 'batch_start',
                'mark_frequency': 'open',
                'enable_custom_attendance': True,
                'working_days': [0, 1, 2, 3, 4],
            }
        )
        return settings


class AssessmentMark(TenantAwareModel):
    """Individual student assessment scores - enhances existing exam system"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="assessment_marks")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assessment_marks")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="assessment_marks", null=True, blank=True)

    # Assessment details
    assessment_name = models.CharField(max_length=255)
    assessment_type = models.CharField(max_length=50, choices=[
        ('CONTINUOUS', 'Continuous Assessment'),
        ('FORMATIVE', 'Formative Assessment'),
        ('SUMMATIVE', 'Summative Assessment'),
        ('QUIZ', 'Quiz'),
        ('TEST', 'Test'),
        ('ASSIGNMENT', 'Assignment'),
        ('PROJECT', 'Project'),
        ('PRACTICAL', 'Practical'),
    ])

    # Marks
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    maximum_marks = models.DecimalField(max_digits=6, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=5, blank=True, null=True)

    # Assessment metadata
    assessment_date = models.DateField()
    term = models.ForeignKey("Term", on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

    # Teacher and verification
    assessed_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    is_published = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student", "subject", "assessment_date"]),
            models.Index(fields=["academic_year", "term"]),
            models.Index(fields=["assessment_type", "is_published"]),
        ]

    def save(self, *args, **kwargs):
        # Auto-calculate percentage
        if self.marks_obtained and self.maximum_marks and self.maximum_marks > 0:
            self.percentage = (self.marks_obtained / self.maximum_marks) * 100
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.first_name} {self.student.last_name} - {self.subject.name} - {self.assessment_name}"


class TimetableEntry(TenantAwareModel):
    """Detailed class scheduling - enhances existing timetable system"""
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name="detailed_entries")

    # Core scheduling
    weekday = models.ForeignKey(Weekday, on_delete=models.CASCADE)
    class_timing = models.ForeignKey(ClassTiming, on_delete=models.CASCADE)
    period_number = models.IntegerField(help_text="Period sequence number (1, 2, 3, etc.)")

    # Academic details
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="timetable_entries")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="timetable_entries")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="timetable_entries")

    # Optional details
    classroom = models.CharField(max_length=100, blank=True, null=True)
    is_substitution = models.BooleanField(default=False)
    original_employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="original_timetable_entries",
        help_text="Original teacher if this is a substitution"
    )

    # Status and notes
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch", "weekday", "period_number"]),
            models.Index(fields=["employee", "weekday"]),
            models.Index(fields=["subject", "batch"]),
            models.Index(fields=["is_active", "is_substitution"]),
        ]
        unique_together = ["timetable", "weekday", "class_timing", "batch"]

    def __str__(self):
        return f"{self.batch.name} - {self.subject.name} - {self.weekday.order} P{self.period_number}"


class ClassTimingSet(TenantAwareModel):
    """School timing configurations for different schedules"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["academic_year", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.academic_year.name}"


class ClassPeriod(TenantAwareModel):
    """Individual class periods within timing sets"""
    timing_set = models.ForeignKey(ClassTimingSet, on_delete=models.CASCADE, related_name="periods")
    period_number = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    period_type = models.CharField(max_length=50, choices=[
        ('REGULAR', 'Regular Class'),
        ('BREAK', 'Break'),
        ('LUNCH', 'Lunch Break'),
        ('ASSEMBLY', 'Assembly'),
        ('ACTIVITY', 'Activity Period'),
    ], default='REGULAR')
    duration_minutes = models.IntegerField(help_text="Duration in minutes")

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["timing_set", "period_number"]),
        ]
        unique_together = ["timing_set", "period_number"]

    def save(self, *args, **kwargs):
        # Auto-calculate duration
        if self.start_time and self.end_time:
            start = self.start_time.hour * 60 + self.start_time.minute
            end = self.end_time.hour * 60 + self.end_time.minute
            self.duration_minutes = end - start
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Period {self.period_number}: {self.start_time} - {self.end_time}"


class EnhancedAttendance(TenantAwareModel):
    """Enhanced attendance with detailed labels - complements existing attendance"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enhanced_attendance")
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="enhanced_attendance")
    attendance_date = models.DateField()

    # Enhanced attendance details
    attendance_label = models.ForeignKey(AttendanceLabel, on_delete=models.CASCADE)
    period_number = models.IntegerField(null=True, blank=True, help_text="For period-wise attendance")
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)

    # Timing details
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    late_minutes = models.IntegerField(default=0)

    # Metadata
    marked_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student", "attendance_date"]),
            models.Index(fields=["batch", "attendance_date"]),
            models.Index(fields=["academic_year", "attendance_date"]),
            models.Index(fields=["attendance_label"]),
        ]
        unique_together = ["student", "attendance_date", "period_number"]

    def __str__(self):
        return f"{self.student.first_name} {self.student.last_name} - {self.attendance_date} - {self.attendance_label.name}"


class SubjectAssessment(TenantAwareModel):
    """Subject-specific assessment methods and configurations"""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assessment_methods")
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="subject_assessments")

    # Assessment configuration
    assessment_name = models.CharField(max_length=255)
    assessment_type = models.CharField(max_length=50, choices=[
        ('CONTINUOUS', 'Continuous Assessment'),
        ('FORMATIVE', 'Formative Assessment'),
        ('SUMMATIVE', 'Summative Assessment'),
        ('PRACTICAL', 'Practical Assessment'),
    ])

    # Weightage and scoring
    weightage_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight in final grade")
    maximum_marks = models.DecimalField(max_digits=6, decimal_places=2)
    minimum_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Configuration
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    assessment_frequency = models.CharField(max_length=50, choices=[
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('TERM', 'Per Term'),
        ('ANNUAL', 'Annual'),
    ], default='MONTHLY')

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["subject", "batch"]),
            models.Index(fields=["academic_year", "is_active"]),
        ]

    def __str__(self):
        return f"{self.subject.name} - {self.assessment_name} ({self.batch.name})"


# ===== EXTENDED PAYMENT MODELS =====
#
# NOTE: PaymentMethod, FeeInvoice, and PaymentTransaction were removed here
# (2026-07) — they were a parallel, never-integrated payment subsystem
# (only referenced from admin registrations), fully superseded by
# FinanceFee/FeeTransaction and FamilyInvoice above.


class FeeWaiver(TenantAwareModel):
    """Fee waivers and scholarships"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    waiver_type = models.CharField(max_length=20, choices=[
        ('SCHOLARSHIP', 'Scholarship'),
        ('DISCOUNT', 'Discount'),
        ('WAIVER', 'Fee Waiver'),
        ('STAFF_CHILD', 'Staff Child Discount'),
        ('SIBLING', 'Sibling Discount'),
    ])
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reason = models.TextField()
    approved_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    approval_date = models.DateField()
    is_active = models.BooleanField(default=True)
    revoked_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, blank=True, related_name="revoked_waivers",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["student", "academic_year"]),
            models.Index(fields=["waiver_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.waiver_type} - {self.student.first_name} {self.student.last_name}"


# Missing Django Models for Fedena to Pinewood Migration
class AdditionalField(TenantAwareModel):
    APPLIES_TO = [
        ("employee", "Employee record"),
        ("student", "Student record"),
        ("admission", "Admission application"),
    ]

    name = models.CharField(max_length=255)
    input_type = models.CharField(max_length=50, blank=True, null=True)
    is_mandatory = models.BooleanField(default=False)
    sort_order = models.IntegerField(blank=True, null=True)
    applies_to = models.CharField(max_length=20, choices=APPLIES_TO, default="employee")
    options = models.TextField(
        blank=True, help_text="Newline-separated choices for select/radio inputs"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_additionalfield'

    @property
    def option_list(self):
        return [o.strip() for o in (self.options or "").splitlines() if o.strip()]

    def __str__(self):
        return str(self.name or '')


class AssessmentGroup(TenantAwareModel):
    name = models.CharField(max_length=255)
    batch = models.ForeignKey("Batch", on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'core_assessmentgroup'

    def __str__(self):
        return str(self.name or '')


class BatchEvent(TenantAwareModel):
    batch = models.ForeignKey("Batch", on_delete=models.CASCADE)
    event = models.ForeignKey("Event", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_batchevent'

    def __str__(self):
        return f'{self.batch} - {self.event}'


class BatchExamTypeConfiguration(TenantAwareModel):
    """Configuration to control which exam types are enabled for each batch/class.

    This allows schools to enable/disable specific assessment types (exams, skills assessments,
    activities, etc.) at the batch level. Teachers will only see exams for enabled types.
    """
    batch = models.OneToOneField(
        "Batch", on_delete=models.CASCADE, related_name="exam_type_config"
    )
    enable_traditional_exams = models.BooleanField(default=True, help_text="Enable traditional written exams")
    enable_skills_assessment = models.BooleanField(default=True, help_text="Enable skills assessment tests")
    enable_activities = models.BooleanField(default=False, help_text="Enable activities (clubs, sports, projects)")
    enable_classwork = models.BooleanField(default=True, help_text="Enable classwork assessment")
    enable_tests = models.BooleanField(default=True, help_text="Enable short tests")
    enable_homework = models.BooleanField(default=True, help_text="Enable homework assessment")
    enabled_custom_exam_types = models.JSONField(
        default=list, blank=True,
        help_text="List of additional custom exam type names that are enabled for this batch"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch"]),
        ]

    def __str__(self):
        return f"{self.batch.name} - Exam Configuration"

    def is_exam_type_enabled(self, exam_type_code):
        """Check if a specific exam type is enabled for this batch.

        Args:
            exam_type_code: One of 'EXAM', 'SKILLS', 'ACTIVITY', 'CLASSWORK', 'TEST',
                           'HOMEWORK', or an Exam.assessment_slot value
                           ('ATTAINMENT'/'EFFORT' follow traditional exams),
                           or a custom string listed in enabled_custom_exam_types.

        Returns:
            bool: True if the exam type is enabled, False otherwise
        """
        type_mapping = {
            'EXAM': self.enable_traditional_exams,
            'SKILLS': self.enable_skills_assessment,
            'ACTIVITY': self.enable_activities,
            'CLASSWORK': self.enable_classwork,
            'TEST': self.enable_tests,
            'HOMEWORK': self.enable_homework,
            # Report-column slots that ride on traditional exams
            'ATTAINMENT': self.enable_traditional_exams,
            'EFFORT': self.enable_traditional_exams,
        }

        if exam_type_code in type_mapping:
            return type_mapping[exam_type_code]

        return exam_type_code in self.enabled_custom_exam_types

    @classmethod
    def for_batch(cls, batch, tenant):
        """Return the configuration for a batch, or None if the school has not
        configured one (which means every exam type is visible)."""
        return cls.objects.filter(batch=batch, tenant=tenant).first()

    @classmethod
    def filter_enabled_exams(cls, exams, batch, tenant):
        """Keep only exams whose assessment type is enabled for the batch.

        Accepts an Exam queryset (returns a filtered queryset, preserving
        .count()/.exists()) or any iterable (returns a list). When the batch
        has no configuration, all exams pass through unchanged.
        """
        config = cls.for_batch(batch, tenant)
        if config is None:
            return exams
        enabled = [
            exam for exam in exams
            if config.is_exam_type_enabled(exam.assessment_slot or 'EXAM')
        ]
        if hasattr(exams, 'filter'):
            return exams.filter(id__in=[e.id for e in enabled])
        return enabled

    @classmethod
    def skills_assessment_enabled(cls, batch, tenant):
        """Whether skills assessment is enabled for the batch (default True)."""
        config = cls.for_batch(batch, tenant)
        return True if config is None else config.enable_skills_assessment

    @classmethod
    def activities_enabled(cls, batch, tenant):
        """Whether activities (clubs, sports, projects) are enabled for the batch."""
        config = cls.for_batch(batch, tenant)
        return True if config is None else config.enable_activities


class ConvertedAssessmentMark(TenantAwareModel):
    student = models.ForeignKey("Student", on_delete=models.CASCADE)
    assessment_group = models.ForeignKey("AssessmentGroup", on_delete=models.CASCADE)
    markable_id = models.UUIDField(blank=True, null=True)
    markable_type = models.CharField(max_length=100, blank=True, null=True)
    mark = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    grade = models.CharField(max_length=10, blank=True, null=True)
    grade_points = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    passed = models.BooleanField(default=True)
    is_absent = models.BooleanField(default=False)
    actual_mark = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'core_convertedassessmentmark'

    def __str__(self):
        return f'{self.student} - {self.mark}'


class CourseSubject(TenantAwareModel):
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    subject = models.ForeignKey("Subject", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_coursesubject'

    def __str__(self):
        return f'{self.course} - {self.subject}'


class EmployeeAdditionalDetail(TenantAwareModel):
    employee = models.ForeignKey("Employee", on_delete=models.CASCADE)
    additional_field = models.ForeignKey("AdditionalField", on_delete=models.CASCADE)
    additional_info = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'core_employeeadditionaldetail'

    def __str__(self):
        return f'{self.employee} - {self.additional_field}'


class EmployeeSubject(TenantAwareModel):
    employee = models.ForeignKey("Employee", on_delete=models.CASCADE)
    subject = models.ForeignKey("Subject", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_employeesubject'

    def __str__(self):
        return f'{self.employee} - {self.subject}'


class FeeCollection(TenantAwareModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    due_date = models.DateField()
    fee_category = models.ForeignKey("FeeCategory", on_delete=models.CASCADE)
    batch = models.ForeignKey("Batch", on_delete=models.CASCADE)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.PROTECT, null=True, blank=True,
        related_name="fee_collections",
        help_text="Academic year this fee collection belongs to",
    )
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft",
        help_text="Collection workflow status: draft → published → closed/archived"
    )
    frequency = models.CharField(
        max_length=20,
        choices=[
            ("one_time", "One Time"),
            ("monthly", "Monthly"),
            ("termly", "Termly"),
            ("yearly", "Yearly"),
        ],
        default="one_time",
        help_text="Collection recurrence pattern"
    )
    late_fee_rule = models.ForeignKey(
        "FineSlab", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fee_collections",
        help_text="Late fee rule for this collection (overrides particular-level rules)"
    )
    parent_collection = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="recurrences",
        help_text="Parent collection if this is a recurring instance"
    )
    next_generation_date = models.DateField(
        null=True, blank=True,
        help_text="When the next recurrence should be generated (for recurring collections)"
    )

    term = models.ForeignKey(
        'core.Term',
        on_delete=models.PROTECT,
        related_name='fee_collections',
        null=True, blank=True,
        help_text='Academic term this billing run belongs to.',
    )

    class Meta:
        db_table = 'core_feecollection'
        indexes = [
            models.Index(fields=["tenant", "academic_year"]),
        ]

    def __str__(self):
        return str(self.name or '')


class FeeCollectionParticular(TenantAwareModel):
    """A one-off fee particular attached to a single FeeCollection (e.g. PTA for
    Term 2), instantiated from a tenant-wide FeeMasterParticular template.

    Unlike FeeParticular (which lives on a FeeCategory and is therefore shared by
    every collection of that category, across terms), this belongs to exactly one
    collection. Collection pricing unions these on top of the category's
    particulars, and adding one tops up the collection's existing FinanceFee rows.
    """

    fee_collection = models.ForeignKey(
        FeeCollection, on_delete=models.CASCADE, related_name="extra_particulars"
    )
    master_particular = models.ForeignKey(
        "FeeMasterParticular", on_delete=models.PROTECT,
        related_name="collection_particulars",
    )
    name = models.CharField(
        max_length=255,
        help_text="Snapshot of the master particular's name at add time",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    fine_slab = models.ForeignKey(
        "FineSlab", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="collection_particulars",
    )
    applicability_rule = models.ForeignKey(
        "FeeApplicabilityRule", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="collection_particulars",
        help_text="Optional student scoping; empty = every student in the collection",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["fee_collection", "master_particular"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["fee_collection"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.fee_collection}"


class FinanceTransactionLedger(TenantAwareModel):
    finance_transaction = models.ForeignKey("FinanceTransaction", on_delete=models.CASCADE)
    fee_account_id = models.UUIDField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'core_financetransactionledger'

    def __str__(self):
        return f'{self.finance_transaction} - {self.amount}'


class FinanceTransactionReceiptRecord(TenantAwareModel):
    finance_transaction = models.ForeignKey("FinanceTransaction", on_delete=models.CASCADE)
    transaction_receipt_id = models.UUIDField(blank=True, null=True)
    fee_account_id = models.UUIDField(blank=True, null=True)
    fee_receipt_template_id = models.UUIDField(blank=True, null=True)
    precision_count = models.IntegerField(blank=True, null=True)
    receipt_data = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'core_financetransactionreceiptrecord'

    def __str__(self):
        return f'{self.finance_transaction} Receipt'


class FinancialYear(TenantAwareModel):
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_financialyear'

    def __str__(self):
        return str(self.name or '')


class Fine(TenantAwareModel):
    student = models.ForeignKey("Student", on_delete=models.CASCADE)
    fine_rule = models.ForeignKey("FineRule", on_delete=models.CASCADE)
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2)
    fine_date = models.DateField()
    is_paid = models.BooleanField(default=False)

    class Meta:
        db_table = 'core_fine'

    def __str__(self):
        return f'{self.student} - {self.fine_amount}'


class FineRule(TenantAwareModel):
    name = models.CharField(max_length=255, blank=True, null=True)
    fine_days = models.IntegerField()
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_amount = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_finerule'

    def __str__(self):
        return str(self.name or '')


class PaymentAgreement(TenantAwareModel):
    """
    A payment agreement for a student's outstanding fees.
    Stores debtor info, debt breakdown, installment schedule, and signature details.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
        ('cancelled', 'Cancelled'),
    ]

    student = models.ForeignKey("Student", on_delete=models.CASCADE, related_name="payment_agreements")
    guardian = models.ForeignKey("Guardian", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="payment_agreements")

    # Debtor snapshot fields (captured at creation, independent of live Guardian record)
    debtor_name = models.CharField(max_length=255)
    nrc_number = models.CharField(max_length=50, blank=True, null=True)
    debtor_address = models.TextField(blank=True, null=True)

    # Debt breakdown
    unpaid_fees_amount = models.DecimalField(max_digits=15, decimal_places=2)
    other_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_description = models.TextField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Agreement terms
    start_date = models.DateField()
    end_date = models.DateField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5)  # 5% per month

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Signature fields
    debtor_signed_date = models.DateField(blank=True, null=True)
    witness_name = models.CharField(max_length=255, blank=True, null=True)
    witness_signed_date = models.DateField(blank=True, null=True)
    director_name = models.CharField(max_length=255, blank=True, default="")
    director_signed_date = models.DateField(blank=True, null=True)
    director_witness_name = models.CharField(max_length=255, blank=True, default="")
    director_witness_signed_date = models.DateField(blank=True, null=True)

    # Metadata
    created_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True, related_name="payment_agreements_created")
    # Note: created_at and updated_at are inherited from BaseModel via TenantAwareModel

    class Meta:
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['student']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        db_table = 'core_paymentagreement'

    def __str__(self):
        return f"Agreement for {self.student} (K{self.total_amount})"


class PaymentAgreementInstallment(TenantAwareModel):
    """
    An installment in a payment agreement.
    Represents a scheduled payment: sequence number, due date, and amount.
    """
    agreement = models.ForeignKey(PaymentAgreement, on_delete=models.CASCADE, related_name="installments")
    sequence = models.PositiveIntegerField()  # 1, 2, 3, ...
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Note: created_at and updated_at are inherited from BaseModel via TenantAwareModel

    class Meta:
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['agreement']),
            models.Index(fields=['due_date']),
        ]
        db_table = 'core_paymentagreementinstallment'
        ordering = ['sequence']

    def __str__(self):
        return f"Installment {self.sequence} for {self.agreement} - K{self.amount}"


class PaymentAgreementPaymentRecord(TenantAwareModel):
    """
    A payment record against a payment agreement.
    Tracks when and how much was paid, updates running balance.
    Can link to a FeeTransaction if payment was also recorded in Collect Fees.

    Note: balance_after is computed at write-time from the prior payment record's
    balance, not derived live. This is a denormalized field for convenience. If a
    future edit/delete endpoint is added for payment records, all subsequent
    balance_after values must be recomputed in sequence to stay consistent.
    """
    agreement = models.ForeignKey(PaymentAgreement, on_delete=models.CASCADE, related_name="payment_records")
    payment_date = models.DateField()
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)  # Running balance (denormalized, see docstring)

    recorded_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True, related_name="payment_agreement_records")
    fee_transaction = models.ForeignKey("FeeTransaction", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="payment_agreement_record")

    # Note: created_at and updated_at are inherited from BaseModel via TenantAwareModel

    class Meta:
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['agreement']),
            models.Index(fields=['payment_date']),
        ]
        db_table = 'core_paymentagreementpaymentrecord'
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment of K{self.amount_paid} on {self.payment_date}"


class GeneratedReport(TenantAwareModel):
    report = models.ForeignKey("Report", on_delete=models.CASCADE)
    student = models.ForeignKey("Student", on_delete=models.SET_NULL, null=True)
    generated_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True)
    file_path = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        db_table = 'core_generatedreport'

    def __str__(self):
        return f'{self.report} for {self.student}'


class IndividualReport(TenantAwareModel):
    student = models.ForeignKey("Student", on_delete=models.CASCADE)
    generated_report_batch_id = models.UUIDField(blank=True, null=True)
    reportable_id = models.UUIDField(blank=True, null=True)
    reportable_type = models.CharField(max_length=100, blank=True, null=True)
    report = models.TextField(blank=True, null=True)
    report_component = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'core_individualreport'

    def __str__(self):
        return f'Report for {self.student}'


class Message(TenantAwareModel):
    sender = models.ForeignKey("User", on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey("User", on_delete=models.CASCADE, related_name="received_messages")
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    sent_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_message'

    def __str__(self):
        return str(self.subject or '')


class Notification(TenantAwareModel):
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_notification'

    def __str__(self):
        return str(self.title or '')


class NotificationRecipient(TenantAwareModel):
    notification = models.ForeignKey("Notification", on_delete=models.CASCADE)
    recipient_id = models.UUIDField()
    recipient_type = models.CharField(max_length=100)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = 'core_notificationrecipient'

    def __str__(self):
        return f'{self.notification} - {self.recipient_type}'


class Privilege(TenantAwareModel):
    name = models.CharField(max_length=255)
    privilege_id = models.UUIDField(unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_privilege'

    def __str__(self):
        return str(self.name or '')


class Report(TenantAwareModel):
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_report'

    def __str__(self):
        return str(self.name or '')


class SmsLog(TenantAwareModel):
    mobile_number = models.CharField(max_length=20)
    message = models.TextField()
    status = models.CharField(max_length=50)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'core_smslog'

    def __str__(self):
        return f'{self.mobile_number} - {self.status}'


class TimeZone(TenantAwareModel):
    name = models.CharField(max_length=255)
    zone = models.CharField(max_length=255)

    class Meta:
        db_table = 'core_timezone'

    def __str__(self):
        return str(self.name or '')


class UserPrivilege(TenantAwareModel):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    privilege = models.ForeignKey("Privilege", on_delete=models.CASCADE)

    class Meta:
        db_table = 'core_userprivilege'

    def __str__(self):
        return f'{self.user} - {self.privilege}'


class WeekdaySetWeekday(TenantAwareModel):
    weekday_set = models.ForeignKey("Weekday", on_delete=models.CASCADE, related_name="weekday_set_items")
    weekday_id = models.UUIDField()

    class Meta:
        db_table = 'core_weekdaysetweekday'

    def __str__(self):
        return f'{self.weekday_set} - {self.weekday_id}'

# ===== GRADEBOOK ADVANCED FEATURES =====
class OnlineExamGroup(TenantAwareModel):
    """Online exam groups for digital assessment"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="online_exam_groups"
    )

    # Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(480)]  # 1 min to 8 hours
    )

    # Configuration
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100.00)
    passing_marks = models.DecimalField(max_digits=6, decimal_places=2, default=40.00)
    max_attempts = models.IntegerField(default=1)
    shuffle_questions = models.BooleanField(default=True)
    show_results_immediately = models.BooleanField(default=False)

    # Status
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "batch", "start_time"]),
            models.Index(fields=["tenant", "is_active", "is_published"]),
        ]
        unique_together = [("tenant", "name", "batch")]

    def __str__(self):
        return f"{self.name} - {self.batch}"


class OnlineExamQuestion(TenantAwareModel):
    """Questions for online exams"""

    QUESTION_TYPES = [
        ("MCQ", "Multiple Choice"),
        ("MSQ", "Multiple Select"),
        ("SHORT", "Short Answer"),
        ("LONG", "Long Answer"),
        ("TRUE_FALSE", "True/False"),
        ("FILL_BLANK", "Fill in the Blanks"),
        ("MATCH", "Matching"),
    ]

    exam_group = models.ForeignKey(
        OnlineExamGroup, on_delete=models.CASCADE, related_name="questions"
    )
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)

    # Question order and timing
    order = models.PositiveIntegerField(default=0)
    time_limit_seconds = models.IntegerField(null=True, blank=True)

    # Advanced options
    is_required = models.BooleanField(default=True)
    explanation = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "exam_group", "order"]),
        ]
        unique_together = [("tenant", "exam_group", "order")]

    def __str__(self):
        return f"{self.exam_group.name} - Q{self.order}"


class OnlineExamOption(TenantAwareModel):
    """Answer options for multiple choice questions"""

    question = models.ForeignKey(
        OnlineExamQuestion, on_delete=models.CASCADE, related_name="options"
    )
    option_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "question", "order"]),
        ]
        unique_together = [("tenant", "question", "order")]

    def __str__(self):
        return f"{self.question} - Option {self.order}"


class OnlineExamAttempt(TenantAwareModel):
    """Student attempts at online exams"""

    STATUS_CHOICES = [
        ("STARTED", "Started"),
        ("IN_PROGRESS", "In Progress"),
        ("SUBMITTED", "Submitted"),
        ("TIMEOUT", "Timed Out"),
        ("CANCELLED", "Cancelled"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="online_exam_attempts"
    )
    exam_group = models.ForeignKey(
        OnlineExamGroup, on_delete=models.CASCADE, related_name="attempts"
    )

    # Attempt details
    attempt_number = models.PositiveIntegerField(default=1)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="STARTED")

    # Results
    total_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    obtained_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # System tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "student", "exam_group"]),
            models.Index(fields=["tenant", "exam_group", "status"]),
        ]
        unique_together = [("tenant", "student", "exam_group", "attempt_number")]

    def __str__(self):
        return f"{self.student} - {self.exam_group} (Attempt {self.attempt_number})"


class OnlineExamAnswer(TenantAwareModel):
    """Student answers to online exam questions"""

    attempt = models.ForeignKey(
        OnlineExamAttempt, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        OnlineExamQuestion, on_delete=models.CASCADE, related_name="student_answers"
    )

    # Answer content
    answer_text = models.TextField(blank=True, null=True)
    selected_options = models.ManyToManyField(
        OnlineExamOption, blank=True, related_name="selected_by"
    )

    # Evaluation
    marks_awarded = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    is_correct = models.BooleanField(null=True, blank=True)

    # Timing
    time_taken_seconds = models.IntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "attempt", "question"]),
        ]
        unique_together = [("tenant", "attempt", "question")]

    def __str__(self):
        return f"{self.attempt.student} - {self.question}"


class CCEGradeSet(TenantAwareModel):
    """CCE Grade sets for different batches/courses"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="cce_grade_sets"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="cce_grade_sets"
    )

    # CCE Configuration
    scholastic_weightage = models.DecimalField(
        max_digits=5, decimal_places=2, default=70.00
    )
    co_scholastic_weightage = models.DecimalField(
        max_digits=5, decimal_places=2, default=30.00
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "batch", "academic_year"]),
        ]
        unique_together = [("tenant", "name", "batch", "academic_year")]

    def __str__(self):
        return f"{self.name} - {self.batch} ({self.academic_year})"


class CCEGrade(TenantAwareModel):
    """Individual CCE grades (A1, A2, B1, etc.)"""

    grade_set = models.ForeignKey(
        CCEGradeSet, on_delete=models.CASCADE, related_name="grades"
    )

    # Grade details
    name = models.CharField(max_length=10)  # A1, A2, B1, B2, C1, C2, D, E
    description = models.CharField(max_length=255, blank=True, null=True)

    # Percentage ranges
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    # Grade points
    grade_points = models.DecimalField(max_digits=4, decimal_places=2)

    # Display
    order = models.PositiveIntegerField(default=0)
    color_code = models.CharField(max_length=7, default="#808080")  # Hex color

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "grade_set", "order"]),
            models.Index(
                fields=["tenant", "grade_set", "min_percentage", "max_percentage"]
            ),
        ]
        unique_together = [("tenant", "grade_set", "name")]
        ordering = ["order", "min_percentage"]

    def __str__(self):
        return f"{self.name} ({self.min_percentage}%-{self.max_percentage}%)"


class GradebookTemplate(TenantAwareModel):
    """Predefined gradebook templates for different assessment styles"""

    TEMPLATE_TYPES = [
        ("CCE", "Continuous Comprehensive Evaluation"),
        ("TRADITIONAL", "Traditional Grading"),
        ("CBSE", "CBSE Pattern"),
        ("IB", "International Baccalaureate"),
        ("CAMBRIDGE", "Cambridge International"),
        ("CUSTOM", "Custom Template"),
    ]

    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    description = models.TextField(blank=True, null=True)

    # Template configuration (JSON field for flexibility)
    configuration = models.JSONField(default=dict)

    # Applicable to
    courses = models.ManyToManyField(
        "Course", blank=True, related_name="gradebook_templates"
    )

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "template_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.template_type})"


class RemarkBank(TenantAwareModel):
    """Predefined remarks for quick entry in gradebooks"""

    REMARK_CATEGORIES = [
        ("ACADEMIC", "Academic Performance"),
        ("BEHAVIOR", "Behavior"),
        ("ATTENDANCE", "Attendance"),
        ("PARTICIPATION", "Class Participation"),
        ("IMPROVEMENT", "Areas for Improvement"),
        ("STRENGTH", "Strengths"),
        ("GENERAL", "General Comments"),
    ]

    category = models.CharField(max_length=20, choices=REMARK_CATEGORIES)
    remark_text = models.TextField()

    # Usage context
    subjects = models.ManyToManyField(Subject, blank=True, related_name="remark_banks")

    # Sentiment/Type
    is_positive = models.BooleanField(default=True)
    frequency_used = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "category", "is_active"]),
            models.Index(fields=["tenant", "frequency_used"]),
        ]

    def __str__(self):
        return f"{self.category}: {self.remark_text[:50]}..."


class StudentPreviousMarks(TenantAwareModel):
    """Historical marks from previous schools/systems"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="previous_marks"
    )

    # Previous school details
    previous_school_name = models.CharField(max_length=255)
    board_name = models.CharField(max_length=255, blank=True, null=True)
    academic_year = models.CharField(max_length=50)
    class_or_grade = models.CharField(max_length=50)

    # Subject and marks
    subject_name = models.CharField(max_length=255)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2)
    grade = models.CharField(max_length=10, blank=True, null=True)

    # Additional info
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "student", "academic_year"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.subject_name} ({self.academic_year})"


class AdvancedAssessmentRubric(TenantAwareModel):
    """Advanced rubrics for detailed assessment"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="assessment_rubrics"
    )

    # Rubric configuration
    total_points = models.PositiveIntegerField(default=100)
    criteria = models.JSONField(default=list)  # List of criteria with point values

    # Usage
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_rubrics",
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "subject", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.subject}"


class AssessmentAnalytics(TenantAwareModel):
    """Analytics and insights for assessments"""

    assessment_name = models.CharField(max_length=255)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

    # Analytics data
    total_students = models.PositiveIntegerField()
    students_appeared = models.PositiveIntegerField()
    students_passed = models.PositiveIntegerField()

    # Statistical measures
    average_marks = models.DecimalField(max_digits=6, decimal_places=2)
    highest_marks = models.DecimalField(max_digits=6, decimal_places=2)
    lowest_marks = models.DecimalField(max_digits=6, decimal_places=2)
    median_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    standard_deviation = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    # Grade distribution (JSON field for flexibility)
    grade_distribution = models.JSONField(default=dict)

    # Analysis timestamp
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "subject", "batch", "academic_year"]),
            models.Index(fields=["tenant", "generated_at"]),
        ]

    def __str__(self):
        return f"{self.assessment_name} - {self.subject} ({self.batch})"


# ============================================================================
# ENQUIRY MANAGEMENT MODELS
# ============================================================================

class ApplicantEnquiryStage(TenantAwareModel):
    """Stages for tracking enquiry progress"""

    name = models.CharField(max_length=255)
    is_default = models.BooleanField(default=False)
    priority = models.PositiveIntegerField(default=1)
    color = models.CharField(max_length=7, default="#007bff")  # Hex color for UI

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "is_default"]),
            models.Index(fields=["tenant", "priority"]),
        ]
        unique_together = [("tenant", "name")]
        ordering = ["priority"]

    def __str__(self):
        return self.name


class ApplicantEnquiryFormField(TenantAwareModel):
    """Configuration for dynamic enquiry form fields"""

    FIELD_TYPES = [
        (0, 'Text'),
        (1, 'Select'),
        (2, 'Textarea'),
        (3, 'Date'),
        (4, 'Email'),
        (5, 'Number'),
        (6, 'Phone'),
    ]

    FIELD_CATEGORIES = [
        ('enquiry', 'Enquiry Form Field'),
        ('guardian', 'Guardian Form Field'),
        ('office', 'Office Form Field'),
    ]

    category = models.CharField(max_length=20, choices=FIELD_CATEGORIES)
    field_name = models.CharField(max_length=100)  # Technical name (e.g., 'first_name')
    display_text = models.CharField(max_length=255)  # Human-readable label
    field_type = models.IntegerField(choices=FIELD_TYPES, default=0)
    is_active = models.BooleanField(default=True)
    is_mandatory = models.BooleanField(default=False)
    is_additional = models.BooleanField(default=False)  # Custom field flag
    priority = models.PositiveIntegerField(default=1)
    placeholder_text = models.CharField(max_length=255, blank=True, null=True)
    help_text = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "category", "is_active"]),
            models.Index(fields=["tenant", "category", "priority"]),
        ]
        unique_together = [("tenant", "category", "field_name")]
        ordering = ["category", "priority"]

    def __str__(self):
        return f"{self.display_text} ({self.get_category_display()})"


class ApplicantEnquiryFormFieldOption(TenantAwareModel):
    """Options for select-type form fields"""

    form_field = models.ForeignKey(
        ApplicantEnquiryFormField,
        on_delete=models.CASCADE,
        related_name="options"
    )
    option_value = models.CharField(max_length=255)
    option_text = models.CharField(max_length=255)
    priority = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "form_field"]),
        ]
        ordering = ["priority"]

    def __str__(self):
        return f"{self.option_text} ({self.form_field.display_text})"


class ApplicantEnquiry(TenantAwareModel):
    """Main enquiry record"""

    # Reference fields
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="enquiries"
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="enquiries"
    )
    stage = models.ForeignKey(
        ApplicantEnquiryStage,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="enquiries"
    )

    # Basic info
    enquiry_number = models.CharField(max_length=50, unique=True, blank=True)
    enquired_date = models.DateField(default=date.today)

    # Student Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    # Guardian Information
    guardian_first_name = models.CharField(max_length=100, blank=True, null=True)
    guardian_last_name = models.CharField(max_length=100, blank=True, null=True)
    guardian_relation = models.CharField(max_length=50, blank=True, null=True)
    guardian_email = models.EmailField(blank=True, null=True)
    guardian_phone = models.CharField(max_length=20, blank=True, null=True)
    guardian_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    guardian_address_line2 = models.CharField(max_length=255, blank=True, null=True)
    guardian_occupation = models.CharField(max_length=100, blank=True, null=True)
    guardian_income = models.CharField(max_length=50, blank=True, null=True)
    guardian_education = models.CharField(max_length=100, blank=True, null=True)

    # Office Information
    counselor = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assigned_enquiries"
    )
    source_of_info = models.CharField(max_length=100, blank=True, null=True)

    # Status tracking
    is_processed = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    is_viewed = models.BooleanField(default=False)
    is_email_enabled = models.BooleanField(default=True)

    # Additional data (JSON field for dynamic form data)
    additional_data = models.JSONField(default=dict, blank=True)

    # Notes and remarks
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "course", "is_processed"]),
            models.Index(fields=["tenant", "stage", "enquired_date"]),
            models.Index(fields=["tenant", "counselor"]),
            models.Index(fields=["tenant", "is_processed", "is_rejected"]),
            models.Index(fields=["enquiry_number"]),
        ]
        ordering = ["-enquired_date", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.enquiry_number:
            self.enquiry_number = self.generate_enquiry_number()
        super().save(*args, **kwargs)

    def generate_enquiry_number(self):
        """Generate unique enquiry number"""
        current_year = timezone.now().year
        prefix = f"ENQ{current_year}"

        # Get the last enquiry number for this year
        last_enquiry = ApplicantEnquiry.objects.filter(
            tenant=self.tenant,
            enquiry_number__startswith=prefix
        ).order_by("-enquiry_number").first()

        if last_enquiry:
            try:
                last_number = int(last_enquiry.enquiry_number.replace(prefix, ""))
                new_number = last_number + 1
            except ValueError:
                new_number = 1
        else:
            new_number = 1

        return f"{prefix}{new_number:05d}"

    def __str__(self):
        return f"{self.enquiry_number} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def guardian_full_name(self):
        if self.guardian_first_name:
            return f"{self.guardian_first_name} {self.guardian_last_name or ''}".strip()
        return None


class EnquiryStageLog(TenantAwareModel):
    """Track stage changes for enquiries"""

    enquiry = models.ForeignKey(
        ApplicantEnquiry,
        on_delete=models.CASCADE,
        related_name="stage_logs"
    )
    stage = models.ForeignKey(
        ApplicantEnquiryStage,
        on_delete=models.CASCADE,
        related_name="stage_logs"
    )
    changed_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="stage_changes"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "enquiry"]),
            models.Index(fields=["tenant", "stage"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.enquiry.enquiry_number} -> {self.stage.name}"


class EnquiryStageLogNote(TenantAwareModel):
    """Notes and follow-ups for enquiry stage logs"""

    stage_log = models.ForeignKey(
        EnquiryStageLog,
        on_delete=models.CASCADE,
        related_name="notes"
    )
    notes = models.TextField()
    follow_up_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="enquiry_notes"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "stage_log"]),
            models.Index(fields=["tenant", "follow_up_date"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note for {self.stage_log.enquiry.enquiry_number}"


class EnquiryFollowUp(TenantAwareModel):
    """Follow-up activities for enquiries"""

    FOLLOW_UP_TYPES = [
        ('call', 'Phone Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('visit', 'Campus Visit'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    ]

    enquiry = models.ForeignKey(
        ApplicantEnquiry,
        on_delete=models.CASCADE,
        related_name="follow_ups"
    )
    follow_up_type = models.CharField(max_length=20, choices=FOLLOW_UP_TYPES)
    scheduled_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assigned_follow_ups"
    )
    notes = models.TextField(blank=True, null=True)
    completion_notes = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "enquiry"]),
            models.Index(fields=["tenant", "scheduled_date", "status"]),
            models.Index(fields=["tenant", "assigned_to", "status"]),
        ]
        ordering = ["scheduled_date"]

    def __str__(self):
        return f"{self.get_follow_up_type_display()} for {self.enquiry.enquiry_number}"


class PasswordResetToken(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_reset_token')
    token = models.CharField(max_length=255, unique=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_used"]),
            models.Index(fields=["token"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"Reset token for {self.user.username}"

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at


class ReportZipJob(TenantAwareModel):
    """Tracks asynchronous ZIP file generation jobs for bulk report downloads."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    requested_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="zip_jobs"
    )
    file_path = models.CharField(max_length=500, blank=True, help_text="Storage path to the ZIP file once completed")
    total_reports = models.IntegerField(default=0, help_text="Total reports to include in the ZIP")
    processed_reports = models.IntegerField(default=0, help_text="Reports added to ZIP so far")
    error_message = models.TextField(blank=True, help_text="Error details if the job failed")
    expires_at = models.DateTimeField(
        default=default_zip_job_expiry,
        help_text="When this job and its ZIP file should be cleaned up"
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "requested_by"]),
            models.Index(fields=["tenant", "expires_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"ZipJob {self.id} ({self.get_status_display()})"

    @property
    def pct_complete(self):
        """Return progress as a percentage."""
        if self.total_reports == 0:
            return 0
        return int((self.processed_reports / self.total_reports) * 100)


class Role(TenantAwareModel):
    """A named bag of permission codenames, assignable to staff logins.

    Authorization is resolved exclusively through :mod:`core.authz.access`;
    nothing reads this model directly to make an access decision. System roles
    (``is_system=True``) are seeded per tenant and cannot be deleted — their
    permission sets may still be edited.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.CharField(max_length=255, blank=True, default="")
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"], name="uniq_role_tenant_slug"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "slug"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return self.name

    @property
    def codenames(self):
        return list(self.permissions.values_list("codename", flat=True))


class RolePermission(TenantAwareModel):
    """One permission codename granted to a :class:`Role`."""

    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="permissions"
    )
    codename = models.CharField(
        max_length=100,
        choices=[(code, f"{code} — {label}") for code, label in PERMISSIONS.items()],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "codename"], name="uniq_rolepermission_role_codename"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "codename"]),
        ]

    def __str__(self):
        return f"{self.role.name} · {self.codename}"


class UserRoleAssignment(TenantAwareModel):
    """Grants a :class:`Role` to a user login within this tenant.

    ``user_id`` / ``assigned_by_id`` are stored without a DB foreign key because
    ``User`` lives in the shared/public schema while this row lives in the
    tenant schema (same pattern as ``Employee.user`` ``db_constraint=False``).
    """

    user_id = models.UUIDField(db_index=True)
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_by_id = models.UUIDField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "role"], name="uniq_userroleassignment_user_role"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "user_id", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user_id} · {self.role.name}"


# ============================================================================
# CONFIGURATION MODULE  (/configuration/)
# ----------------------------------------------------------------------------
# Backs the configuration landing page. Where an existing model already fits
# (Configuration key/value, StudentCategory, AdditionalField) it is reused
# rather than duplicated. Everything here is per-tenant (TenantAwareModel).
# ============================================================================


class ConfigStore:
    """Thin typed accessor over the generic :class:`Configuration` key/value
    table. Keeps callers from re-implementing get-or-default everywhere.

    Usage::

        ConfigStore(tenant).get('student_sort_order', 'first_name')
        ConfigStore(tenant).set('student_sort_order', 'admission_number')
    """

    def __init__(self, tenant):
        self.tenant = tenant

    def get(self, key, default=None):
        row = Configuration.objects.filter(tenant=self.tenant, config_key=key).first()
        return row.config_value if row else default

    def get_many(self, keys):
        rows = Configuration.objects.filter(tenant=self.tenant, config_key__in=list(keys))
        return {r.config_key: r.config_value for r in rows}

    def set(self, key, value):
        Configuration.objects.update_or_create(
            tenant=self.tenant, config_key=key,
            defaults={'config_value': '' if value is None else str(value)},
        )

    def set_many(self, mapping):
        for k, v in mapping.items():
            self.set(k, v)


class DocumentCategory(TenantAwareModel):
    """Category for documents attached to a student (birth certificate,
    medical record, transfer letter, ...)."""

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    is_required = models.BooleanField(
        default=False, help_text="Flagged as expected for every student"
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"], name="uniq_documentcategory_tenant_name"
            ),
        ]
        indexes = [models.Index(fields=["tenant", "is_active"])]

    def __str__(self):
        return self.name


class StudentDocument(TenantAwareModel):
    """A file held against a student, classified by :class:`DocumentCategory`."""

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="documents"
    )
    category = models.ForeignKey(
        DocumentCategory, on_delete=models.PROTECT, related_name="documents"
    )
    file = models.FileField(upload_to="student_documents/")
    original_filename = models.CharField(max_length=255, blank=True)
    note = models.CharField(max_length=255, blank=True)
    uploaded_by_id = models.UUIDField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [models.Index(fields=["tenant", "student"])]

    def __str__(self):
        return f"{self.student_id} · {self.category.name}"


class PortalFeatureAccess(TenantAwareModel):
    """Per-tenant on/off switches for what the parent/guardian portal exposes.
    One row per tenant; read by the portal API to gate each section."""

    FEATURES = [
        ("attendance", "Attendance"),
        ("results", "Results / report cards"),
        ("invoices", "Invoices"),
        ("fees", "Fee payments"),
        ("assignments", "Assignments"),
        ("transport", "Transport"),
        ("announcements", "Announcements"),
        ("documents", "Student documents"),
        ("timetable", "Timetable"),
    ]

    feature = models.CharField(max_length=40, choices=FEATURES)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "feature"], name="uniq_portalfeature_tenant_feature"
            ),
        ]
        indexes = [models.Index(fields=["tenant"])]

    def __str__(self):
        return f"{self.feature}: {'on' if self.is_enabled else 'off'}"


class NotificationRule(TenantAwareModel):
    """Which channels fire for a given system event, and who receives it."""

    EVENTS = [
        ("fee_due", "Fee due / reminder"),
        ("fee_payment_received", "Fee payment received"),
        ("attendance_absent", "Student marked absent"),
        ("exam_results_published", "Exam results published"),
        ("report_card_published", "Report card published"),
        ("announcement", "General announcement"),
        ("admission_status_change", "Admission status change"),
        ("assignment_posted", "Assignment posted"),
    ]
    AUDIENCES = [
        ("guardians", "Guardians"),
        ("students", "Students"),
        ("staff", "Staff"),
        ("admins", "Administrators"),
    ]

    event = models.CharField(max_length=50, choices=EVENTS)
    audience = models.CharField(max_length=20, choices=AUDIENCES, default="guardians")
    send_sms = models.BooleanField(default=False)
    send_email = models.BooleanField(default=False)
    send_push = models.BooleanField(default=True)
    send_in_app = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["event", "audience"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "event", "audience"],
                name="uniq_notificationrule_tenant_event_audience",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "event", "is_active"])]

    def __str__(self):
        return f"{self.event} → {self.audience}"


class StudentExemption(TenantAwareModel):
    """Marks a student as excluded from a specific academic/reporting process."""

    TYPES = [
        ("report_block", "Report-card blocking (fees etc.)"),
        ("ranking", "Class ranking / position"),
        ("grading", "Grading & report-card calculations"),
        ("promotion", "Automatic promotion"),
    ]

    student = models.ForeignKey(
        "Student", on_delete=models.CASCADE, related_name="exemptions"
    )
    exemption_type = models.CharField(max_length=30, choices=TYPES)
    academic_year = models.ForeignKey(
        "AcademicYear", on_delete=models.CASCADE, null=True, blank=True,
        related_name="student_exemptions",
        help_text="Leave blank for an open-ended exemption",
    )
    reason = models.CharField(max_length=255, blank=True)
    created_by_id = models.UUIDField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "student", "exemption_type", "academic_year"],
                name="uniq_studentexemption_scope",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "exemption_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.student_id} · {self.exemption_type}"


class TerminologyOverride(TenantAwareModel):
    """Institution-specific wording. ``term`` is a stable key ("student"),
    ``replacement`` is what the school calls it ("Pupil")."""

    term = models.CharField(max_length=60)
    replacement = models.CharField(max_length=60)
    replacement_plural = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["term"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "term"], name="uniq_terminology_tenant_term"
            ),
        ]
        indexes = [models.Index(fields=["tenant", "is_active"])]

    def __str__(self):
        return f"{self.term} → {self.replacement}"


class ClientApp(TenantAwareModel):
    """A known first-party client application (parent app, staff mobile app).
    Not OAuth — just an enable/disable registry the portal API consults."""

    PLATFORMS = [
        ("android", "Android"),
        ("ios", "iOS"),
        ("web", "Web"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=60)
    platform = models.CharField(max_length=20, choices=PLATFORMS, default="android")
    min_supported_version = models.CharField(max_length=20, blank=True)
    is_enabled = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"], name="uniq_clientapp_tenant_slug"
            ),
        ]
        indexes = [models.Index(fields=["tenant", "is_enabled"])]

    def __str__(self):
        return self.name


class AdmissionAdditionalDetail(TenantAwareModel):
    """Value captured for an :class:`AdditionalField` (``applies_to='admission'``)
    against one admission application."""

    application = models.ForeignKey(
        "ExtendedAdmissionApplication", on_delete=models.CASCADE,
        related_name="additional_details",
    )
    field = models.ForeignKey(
        AdditionalField, on_delete=models.CASCADE, related_name="admission_values"
    )
    value = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["application", "field"],
                name="uniq_admissionadditionaldetail_app_field",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "application"])]

    def __str__(self):
        return f"{self.application_id} · {self.field_id}"


class DemoRequest(BaseModel):
    """Public schema model for prospective customers to request a demo.

    NOT tenant-scoped (no tenant FK). Lives in the shared schema.
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("contacted", "Contacted"),
        ("demo_scheduled", "Demo Scheduled"),
        ("converted", "Converted"),
        ("rejected", "Rejected"),
    ]

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    school_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the prospective school/organization"
    )
    message = models.TextField(
        blank=True,
        help_text="Additional message or inquiry"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )
    notes = models.TextField(
        blank=True,
        help_text="Internal notes from admin"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email}) - {self.status}"
