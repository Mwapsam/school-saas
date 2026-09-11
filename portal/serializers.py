"""Serializers for the portal API.

Most read serializers operate on plain dicts produced by ``selectors`` so they
stay thin. Model serializers are used only for the lightweight entity summaries
(student, batch) the portal surfaces.
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .roles import (
    hr_permissions_for,
    resolve_roles,
    ROLE_HR,
    ROLE_TEACHER,
    ROLE_LIBRARIAN,
    ROLE_PARENT,
)
from . import selectors


# ── Auth ─────────────────────────────────────────────────────────────────────

class PortalTokenObtainSerializer(TokenObtainPairSerializer):
    """JWT login that also rejects non-portal accounts early and embeds the
    user's role(s) in the access token claims."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        roleset = resolve_roles(user)
        token["roles"] = roleset.ordered()
        token["role"] = roleset.primary  # kept for backwards compatibility
        token["password_change_required"] = user.password_change_required
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        roleset = resolve_roles(self.user)
        if not roleset.is_portal_user:
            raise serializers.ValidationError(
                "This account does not have access to the parent/teacher portal."
            )
        data["roles"] = roleset.ordered()
        data["role"] = roleset.primary
        data["user"] = ProfileSerializer(self.user).data
        data["password_change_required"] = self.user.password_change_required
        return data


class ProfileSerializer(serializers.Serializer):
    """The authenticated user + their resolved role and profile snapshot."""

    id = serializers.UUIDField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    full_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    profiles = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    hr_permissions = serializers.SerializerMethodField()
    has_employee_profile = serializers.SerializerMethodField()

    def get_hr_permissions(self, obj):
        """HR codenames the user holds (``hr.*`` / ``reports.hr*``) so the
        frontend can show/hide HR sections. Empty list for non-HR users."""
        return sorted(hr_permissions_for(obj))

    def get_has_employee_profile(self, obj):
        """True when the account is linked to an active employee — gates the
        'My HR' self-service area for any staff member."""
        return self._roleset(obj).employee is not None

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_features(self, obj):
        """Parent-portal feature toggles for the user's school (Configuration →
        Feature Access). ``{}`` when there is no tenant-scoped profile."""
        roleset = self._roleset(obj)
        tenant = None
        for profile in (roleset.employee, roleset.guardian, roleset.student):
            tenant = getattr(profile, "tenant", None)
            if tenant is not None:
                break
        if tenant is None:
            return {}
        from core.services.configuration_service import portal_feature_map
        return portal_feature_map(tenant)

    def _roleset(self, obj):
        return resolve_roles(obj)

    def get_role(self, obj):
        return self._roleset(obj).primary

    def get_roles(self, obj):
        return self._roleset(obj).ordered()

    def _profile_snapshot(self, role, profile):
        if profile is None:
            return None
        data = {
            "id": str(profile.id),
            "first_name": getattr(profile, "first_name", ""),
            "last_name": getattr(profile, "last_name", ""),
        }
        if role in (ROLE_TEACHER, ROLE_LIBRARIAN, ROLE_HR):
            data["job_title"] = getattr(profile, "job_title", None)
            data["employee_number"] = getattr(profile, "employee_number", None)
        if role == ROLE_HR:
            dept = getattr(profile, "employee_department", None)
            data["department"] = getattr(dept, "name", None)
        if role == ROLE_LIBRARIAN:
            data["libraries"] = [
                {"id": str(lib.id), "name": lib.name}
                for lib in selectors.libraries_for_librarian(profile)
            ]
        if role == ROLE_PARENT:
            data["relation"] = getattr(profile, "relation", None)
            data["mobile_phone"] = getattr(profile, "mobile_phone", None)
        return data

    def get_profile(self, obj):
        roleset = self._roleset(obj)
        primary = roleset.primary
        return self._profile_snapshot(primary, roleset.profile_for(primary))

    def get_profiles(self, obj):
        roleset = self._roleset(obj)
        out = {}
        for role in roleset.ordered():
            snapshot = self._profile_snapshot(role, roleset.profile_for(role))
            if snapshot is not None:
                out[role] = snapshot
        return out


# ── Parent: fees & invoices ───────────────────────────────────────────────────

class FamilyInvoiceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    invoice_number = serializers.CharField()
    status = serializers.CharField()
    academic_year = serializers.SerializerMethodField()
    subtotal = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance_due = serializers.DecimalField(max_digits=15, decimal_places=2)
    due_date = serializers.DateField(allow_null=True)
    generated_at = serializers.DateTimeField()

    def get_academic_year(self, obj):
        return obj.academic_year.name if obj.academic_year_id else None


class ReceiptSummarySerializer(serializers.Serializer):
    reference_number = serializers.CharField()
    student_id = serializers.UUIDField()
    student_name = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    paid_on = serializers.DateTimeField()


# ── Parent: children & academics ─────────────────────────────────────────────

class ChildSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    admission_no = serializers.CharField()
    gender = serializers.CharField()
    photo_url = serializers.SerializerMethodField()
    current_batch = serializers.SerializerMethodField()
    guardians = serializers.SerializerMethodField()

    def get_photo_url(self, obj):
        return None  # Photos are served via signed storage elsewhere.

    def get_current_batch(self, obj):
        batch = selectors.current_batch_for_student(obj)
        if not batch:
            return None
        return {
            "id": str(batch.id),
            "name": batch.name,
            "course": batch.course.course_name if batch.course_id else None,
            "academic_year": batch.academic_year.name if batch.academic_year_id else None,
        }

    def get_guardians(self, obj):
        """Return list of other guardians (co-parents) linked to this student."""
        guardian = self.context.get("guardian")
        if not guardian:
            return []
        return selectors.co_guardians_for_student(obj, guardian.id)


class SubjectResultSerializer(serializers.Serializer):
    subject = serializers.CharField()
    exam_name = serializers.CharField()
    marks = serializers.FloatField(allow_null=True)
    maximum_marks = serializers.FloatField(allow_null=True)
    percentage = serializers.FloatField(allow_null=True)
    grade = serializers.CharField(allow_null=True)
    is_absent = serializers.BooleanField()
    remarks = serializers.CharField(allow_null=True)


class ResultGroupSerializer(serializers.Serializer):
    exam_group_id = serializers.CharField()
    name = serializers.CharField()
    exam_type = serializers.CharField()
    exam_date = serializers.DateField()
    batch_name = serializers.CharField(allow_null=True)
    subjects = SubjectResultSerializer(many=True)


class StudentReportSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    exam_group_id = serializers.CharField()
    name = serializers.CharField()
    term = serializers.CharField(allow_null=True)
    generated_at = serializers.DateTimeField(allow_null=True)


class AttendanceSummarySerializer(serializers.Serializer):
    total_days = serializers.IntegerField()
    present_days = serializers.IntegerField()
    half_days = serializers.IntegerField()
    absent_days = serializers.IntegerField()
    attendance_rate = serializers.FloatField(allow_null=True)


# ── Teacher: classes & register ──────────────────────────────────────────────

class TeacherBatchSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    course = serializers.SerializerMethodField()
    academic_year = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    has_markable_exams = serializers.SerializerMethodField()
    has_skills_assessment = serializers.SerializerMethodField()
    is_class_teacher = serializers.SerializerMethodField()

    def get_course(self, obj):
        return obj.course.course_name if obj.course_id else None

    def get_academic_year(self, obj):
        return obj.academic_year.name if obj.academic_year_id else None

    def get_student_count(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "role_context"):
            employee = request.role_context.profile
            return len(selectors.roster_for_batch(obj, employee=employee))
        return obj.batch_students.filter(is_active=True).count()

    def get_has_markable_exams(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "role_context"):
            employee = request.role_context.profile
            return selectors.has_markable_exams_for_batch(employee, obj)
        return False

    def get_has_skills_assessment(self, obj):
        return selectors.has_active_skills_for_batch(obj)

    def get_is_class_teacher(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "role_context"):
            employee = request.role_context.profile
            return selectors.is_class_teacher_for_batch(employee, obj)
        return False


class RegisterEntrySerializer(serializers.Serializer):
    """One row of the attendance register (read)."""

    student_id = serializers.CharField()
    full_name = serializers.CharField()
    admission_no = serializers.CharField()
    roll_number = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    reason = serializers.CharField(allow_null=True)


class MarkableExamSerializer(serializers.Serializer):
    """One exam a teacher can enter marks for."""

    id = serializers.UUIDField()
    subject = serializers.SerializerMethodField()
    exam_name = serializers.SerializerMethodField()
    exam_group = serializers.SerializerMethodField()
    batch = serializers.SerializerMethodField()
    exam_date = serializers.SerializerMethodField()
    maximum_marks = serializers.SerializerMethodField()
    is_grade_only = serializers.SerializerMethodField()
    assessment_slot = serializers.CharField()
    assessment_slot_display = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    scored_count = serializers.SerializerMethodField()
    result_published = serializers.SerializerMethodField()
    is_class_teacher = serializers.SerializerMethodField()

    def get_assessment_slot_display(self, obj):
        return obj.get_assessment_slot_display()

    def get_subject(self, obj):
        return obj.subject.name if obj.subject_id else "—"

    def get_exam_name(self, obj):
        return obj.exam_name or obj.display_name or "Exam"

    def get_exam_group(self, obj):
        return obj.exam_group.name

    def get_batch(self, obj):
        b = obj.exam_group.batch
        return {"id": str(b.id), "name": b.name}

    def get_exam_date(self, obj):
        return obj.exam_group.exam_date

    def get_maximum_marks(self, obj):
        return float(obj.maximum_marks) if obj.maximum_marks is not None else None

    def get_is_grade_only(self, obj):
        from . import selectors
        return selectors.exam_is_grade_only(obj)

    def get_student_count(self, obj):
        from . import selectors
        employee = self.context.get("employee")
        if employee:
            return len(selectors.roster_for_batch(obj.exam_group.batch, employee=employee))
        return obj.exam_group.batch.batch_students.filter(is_active=True).count()

    def get_scored_count(self, obj):
        return obj.scores.count()

    def get_result_published(self, obj):
        return obj.exam_group.result_published

    def get_is_class_teacher(self, obj):
        from . import selectors
        employee = self.context.get("employee")
        if employee:
            return selectors.is_class_teacher_for_batch(employee, obj.exam_group.batch)
        return False


class MarkSheetEntrySerializer(serializers.Serializer):
    student_id = serializers.CharField()
    full_name = serializers.CharField()
    admission_no = serializers.CharField()
    roll_number = serializers.CharField(allow_null=True)
    marks = serializers.FloatField(allow_null=True)
    grade_value_id = serializers.CharField(allow_null=True)
    is_absent = serializers.BooleanField()
    remarks = serializers.CharField(allow_null=True)


class SaveMarkEntrySerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    marks = serializers.FloatField(required=False, allow_null=True)
    grade_value_id = serializers.UUIDField(required=False, allow_null=True)
    is_absent = serializers.BooleanField(required=False, default=False)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SaveMarksSerializer(serializers.Serializer):
    entries = SaveMarkEntrySerializer(many=True)
    # False = save as draft; True = submit for review.
    submit = serializers.BooleanField(required=False, default=False)

    def validate_entries(self, value):
        if not value:
            raise serializers.ValidationError("At least one entry is required.")
        return value


class SkillItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    description = serializers.CharField()


class SkillCategorySerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    items = SkillItemSerializer(many=True)


class SaveSkillsSerializer(serializers.Serializer):
    term = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    levels = serializers.DictField(
        child=serializers.ChoiceField(choices=selectors.SKILL_LEVELS),
    )

    def validate_levels(self, value):
        if not value:
            raise serializers.ValidationError("At least one skill must be rated.")
        return value


class _RatingSerializer(serializers.Serializer):
    submission = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    presentation = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    effort = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ActivityRowSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    homework = _RatingSerializer(required=False)
    project = _RatingSerializer(required=False)
    clubs = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sports = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    other = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SaveActivitiesSerializer(serializers.Serializer):
    exam_group = serializers.UUIDField()
    students = ActivityRowSerializer(many=True)

    def validate_students(self, value):
        if not value:
            raise serializers.ValidationError("At least one pupil is required.")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
    new_password = serializers.CharField(min_length=6, max_length=128, write_only=True)
    confirm_password = serializers.CharField(min_length=6, max_length=128, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return data


class FirstTimePasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(min_length=6, max_length=128, write_only=True)
    new_password = serializers.CharField(min_length=6, max_length=128, write_only=True)
    confirm_password = serializers.CharField(min_length=6, max_length=128, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from current password."}
            )
        return data


class ChangePasswordSerializer(serializers.Serializer):
    """Authenticated user changing their password."""

    current_password = serializers.CharField(min_length=6, max_length=128, write_only=True)
    new_password = serializers.CharField(min_length=6, max_length=128, write_only=True)
    confirm_password = serializers.CharField(min_length=6, max_length=128, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from current password."}
            )
        return data


class AttendanceMarkSerializer(serializers.Serializer):
    """One row of an attendance save request (write)."""

    student_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=selectors.ATTENDANCE_STATUSES)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SaveAttendanceSerializer(serializers.Serializer):
    date = serializers.DateField()
    entries = AttendanceMarkSerializer(many=True)

    def validate_entries(self, value):
        if not value:
            raise serializers.ValidationError("At least one entry is required.")
        seen = set()
        for entry in value:
            sid = str(entry["student_id"])
            if sid in seen:
                raise serializers.ValidationError(
                    f"Duplicate entry for student {sid}."
                )
            seen.add(sid)
        return value


# ── Librarian ────────────────────────────────────────────────────────────────

class LibrarySerializer(serializers.Serializer):
    """Library summary."""
    id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField(allow_blank=True, allow_null=True)
    is_active = serializers.BooleanField()


class BookSerializer(serializers.Serializer):
    """Book details."""
    id = serializers.UUIDField()
    title = serializers.CharField()
    author = serializers.CharField()
    isbn = serializers.CharField(allow_blank=True, allow_null=True)
    book_number = serializers.CharField()
    category_name = serializers.SerializerMethodField()
    library_name = serializers.SerializerMethodField()
    total_copies = serializers.IntegerField()
    available_copies = serializers.IntegerField()
    book_type = serializers.CharField()
    school_level = serializers.CharField()
    barcode = serializers.CharField(allow_blank=True, allow_null=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)

    def get_category_name(self, obj):
        return getattr(obj.category, 'name', None) if hasattr(obj, 'category') else None

    def get_library_name(self, obj):
        return getattr(obj.library, 'name', None) if hasattr(obj, 'library') else None


class BookCategorySerializer(serializers.Serializer):
    """Book category."""
    id = serializers.UUIDField()
    name = serializers.CharField()


class BookMovementSerializer(serializers.Serializer):
    """Book issue/return movement."""
    id = serializers.UUIDField()
    book_title = serializers.SerializerMethodField()
    book_number = serializers.SerializerMethodField()
    borrower_name = serializers.SerializerMethodField()
    borrower_type = serializers.SerializerMethodField()
    issue_date = serializers.DateField()
    due_date = serializers.DateField()
    return_date = serializers.DateField(allow_null=True)
    is_returned = serializers.BooleanField()
    is_overdue = serializers.SerializerMethodField()

    def get_book_title(self, obj):
        return obj.book.title if hasattr(obj, 'book') else None

    def get_book_number(self, obj):
        return obj.book.book_number if hasattr(obj, 'book') else None

    def get_borrower_name(self, obj):
        if hasattr(obj, 'student') and obj.student:
            return f"{obj.student.first_name} {obj.student.last_name}".strip()
        if hasattr(obj, 'employee') and obj.employee:
            return f"{obj.employee.first_name} {obj.employee.last_name}".strip()
        return None

    def get_borrower_type(self, obj):
        return "student" if (hasattr(obj, 'student') and obj.student) else "employee"

    def get_is_overdue(self, obj):
        from datetime import date
        return not obj.is_returned and obj.due_date < date.today()


class LibrarianDashboardSerializer(serializers.Serializer):
    """Librarian dashboard stats and libraries."""
    libraries = LibrarySerializer(many=True)
    stats = serializers.DictField()
