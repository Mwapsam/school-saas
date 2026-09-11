from django.contrib import admin, messages
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from core.models import (
    Batch, BatchStudent, Subject, Exam, ExamScore, Student,
    AcademicYear, Course, Employee, ExamGroup, GradingScale,
    ExtendedAdmissionApplication, StudentCategory, Attendance, ReportTemplate,
    ReportSection, Weekday, EmployeeCategory, EmployeePosition, EmployeeDepartment,
    EmployeeGrade, EmployeeLeave, EmployeeAdditionalDetail, EmployeeSubject,
    AdditionalField, Country, Term, HomeworkAssessment, ProjectWorkAssessment,
    StudentActivity, ClassTeacherAssignment, TeacherComment, SkillsTeacherComment, ActivityProfile, Activity
)
from core.services.report_generation_service import ReportGenerationService

class BatchStudentInline(TabularInline):
    model = BatchStudent
    extra = 0
    autocomplete_fields = ("student",)
    fields = ("student", "roll_number", "is_active")


class ClassTeacherAssignmentInline(TabularInline):
    model = ClassTeacherAssignment
    extra = 0
    autocomplete_fields = ("student", "employee", "academic_year")
    fields = ("student", "employee", "academic_year", "is_active", "assigned_by", "deactivated_at", "reason")
    readonly_fields = ("assigned_by", "deactivated_at", "deactivated_by", "created_at", "updated_at")

@admin.register(AcademicYear)
class AcademicYearAdmin(ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

@admin.register(Weekday)
class WeekdayAdmin(ModelAdmin):
    list_display = ("weekday", "day_of_week", "tenant")
    list_filter = ("day_of_week", "tenant")
    search_fields = ("weekday",)
    ordering = ("day_of_week",)
    readonly_fields = ("tenant",)

    def get_queryset(self, request):
        """Filter by tenant if available"""
        qs = super().get_queryset(request)
        if hasattr(request, "tenant") and request.tenant:
            return qs.filter(tenant=request.tenant)
        return qs

    def save_model(self, request, obj, form, change):
        """Set tenant on save if not already set"""
        if hasattr(request, "tenant") and request.tenant and not obj.tenant_id:
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)

@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ("course_name", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("course_name",)

class EmployeeLeaveInline(TabularInline):
    model = EmployeeLeave
    extra = 0
    fk_name = "employee"
    fields = ("start_date", "end_date", "leave_type", "reason", "is_approved", "approved_by")
    autocomplete_fields = ("approved_by",)

class EmployeeSubjectInline(TabularInline):
    model = EmployeeSubject
    extra = 0
    autocomplete_fields = ("subject",)
    fields = ("subject", "is_active")

class EmployeeAdditionalDetailInline(TabularInline):
    model = EmployeeAdditionalDetail
    extra = 0
    autocomplete_fields = ("additional_field",)
    fields = ("additional_field", "additional_info")

@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    list_display = (
        "employee_number",
        "full_name",
        "job_title",
        "employee_department",
        "employee_position",
        "is_teaching_staff",
        "email",
        "status",
    )

    list_filter = (
        "status",
        "is_teaching_staff",
        "employee_category",
        "employee_position",
        "employee_department",
        "employee_grade",
        "joining_date",
    )

    search_fields = (
        "first_name",
        "middle_name",
        "last_name",
        "employee_number",
        "email",
        "mobile_phone",
    )

    autocomplete_fields = (
        "employee_category",
        "employee_position",
        "employee_department",
        "employee_grade",
        "reporting_manager",
        "nationality",
        "home_country",
        "office_country",
        "user",
    )

    ordering = ("-created_at",)
    date_hierarchy = "joining_date"

    inlines = [
        EmployeeLeaveInline,
        EmployeeSubjectInline,
        EmployeeAdditionalDetailInline,
    ]

    readonly_fields = (
        "signature_preview",
    )

    fieldsets = (
        (
            "Personal Information",
            {
                "fields": (
                    ("first_name", "middle_name", "last_name"),
                    ("gender", "date_of_birth"),
                    ("email", "mobile_phone"),
                ),
            },
        ),
        (
            "Employment Details",
            {
                "fields": (
                    ("employee_number", "joining_date"),
                    ("job_title", "is_teaching_staff"),
                    ("employee_category", "employee_position"),
                    ("employee_department", "employee_grade"),
                    ("status",),
                ),
            },
        ),
        (
            "Reporting Structure",
            {
                "fields": (
                    "reporting_manager",
                ),
            },
        ),
        (
            "Qualifications & Experience",
            {
                "fields": (
                    "qualification",
                    "experience_detail",
                    ("experience_year", "experience_month"),
                ),
            },
        ),
        (
            "Signature",
            {
                "fields": (
                    "signature_preview",
                    "signature_image",
                ),
            },
        ),
        (
            "Personal Details",
            {
                "fields": (
                    ("marital_status", "children_count"),
                    ("blood_group", "nationality"),
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Home Address",
            {
                "fields": (
                    "home_address_line1",
                    "home_address_line2",
                    ("home_city", "home_state"),
                    ("home_country", "home_pin_code"),
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Office Address",
            {
                "fields": (
                    "office_address_line1",
                    "office_address_line2",
                    ("office_city", "office_state"),
                    ("office_country", "office_pin_code"),
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "System",
            {
                "fields": (
                    "user",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Employee")
    def full_name(self, obj):
        return obj.full_name

    @admin.display(description="Signature")
    def signature_preview(self, obj):
        if obj.signature_image:
            return mark_safe(
                f"""
                <img src="{obj.signature_image}"
                     style="
                        max-height:120px;
                        max-width:300px;
                        border:1px solid #ddd;
                        border-radius:6px;
                        padding:6px;
                        background:#fff;
                     ">
                """
            )
        return "-"

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly.append("employee_number")
        return tuple(readonly)


@admin.register(ClassTeacherAssignment)
class ClassTeacherAssignmentAdmin(ModelAdmin):
    list_display = ("student_name", "batch_name", "employee_name", "academic_year_name", "is_active", "assigned_at")
    list_filter = ("is_active", "batch", "employee", "academic_year", "created_at")
    search_fields = ("student__first_name", "student__last_name", "student__admission_no", "employee__first_name", "employee__last_name", "batch__name")
    autocomplete_fields = ("student", "batch", "employee", "academic_year", "assigned_by", "deactivated_by")
    readonly_fields = ("tenant", "created_at", "updated_at", "assigned_by", "deactivated_by", "deactivated_at")
    fieldsets = (
        ("Assignment", {
            "fields": ("tenant", "student", "batch", "employee", "academic_year", "is_active"),
        }),
        ("Audit Trail", {
            "fields": ("reason", "assigned_by", "deactivated_by", "deactivated_at", "created_at", "updated_at"),
        }),
    )

    def student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"
    student_name.short_description = "Student"

    def batch_name(self, obj):
        return obj.batch.name
    batch_name.short_description = "Batch"

    def employee_name(self, obj):
        return obj.employee.full_name
    employee_name.short_description = "Teacher"

    def academic_year_name(self, obj):
        return obj.academic_year.name
    academic_year_name.short_description = "Academic Year"

    def assigned_at(self, obj):
        return obj.created_at
    assigned_at.short_description = "Assigned At"

    def save_model(self, request, obj, form, change):
        from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
        if not change:
            svc = ClassTeacherAssignmentService(obj.tenant)
            svc.assign(
                str(obj.student.id),
                str(obj.batch.id),
                str(obj.employee.id),
                user=request.user,
                reason=obj.reason
            )
            return
        super().save_model(request, obj, form, change)


@admin.register(EmployeeCategory)
class EmployeeCategoryAdmin(ModelAdmin):
    list_display = ("name", "prefix", "status")
    list_filter = ("status",)
    search_fields = ("name", "prefix")

@admin.register(EmployeePosition)
class EmployeePositionAdmin(ModelAdmin):
    list_display = ("name", "employee_category", "status")
    list_filter = ("status", "employee_category")
    search_fields = ("name",)
    autocomplete_fields = ("employee_category",)

@admin.register(EmployeeDepartment)
class EmployeeDepartmentAdmin(ModelAdmin):
    list_display = ("name", "code", "status")
    list_filter = ("status",)
    search_fields = ("name", "code")

@admin.register(EmployeeGrade)
class EmployeeGradeAdmin(ModelAdmin):
    list_display = ("name", "priority", "status", "max_hours_day", "max_hours_week")
    list_filter = ("status",)
    search_fields = ("name",)
    ordering = ("priority",)

@admin.register(Country)
class CountryAdmin(ModelAdmin):
    list_display = ("name", "code", "currency_code")
    search_fields = ("name", "code", "currency_code")
    ordering = ("name",)

@admin.register(AdditionalField)
class AdditionalFieldAdmin(ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(ExamGroup)
class ExamGroupAdmin(ModelAdmin):
    list_display = ("name", "is_published")
    list_filter = ("is_published",)
    search_fields = ("name",)

@admin.register(GradingScale)
class GradingScaleAdmin(ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(StudentCategory)
class StudentCategoryAdmin(ModelAdmin):
    list_display = ("name", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name",)

@admin.register(Batch)
class BatchAdmin(ModelAdmin):
    list_display = ("name", "course", "is_active")
    list_filter = ("is_active", "course")
    search_fields = ("name", "course__course_name")
    autocomplete_fields = ("course", "employee", "class_teachers")
    inlines = [BatchStudentInline, ClassTeacherAssignmentInline]

@admin.register(Student)
class StudentAdmin(ModelAdmin):
    list_display = ("first_name", "last_name", "email", "admission_no", "is_active")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("first_name", "last_name", "email", "admission_no")
    autocomplete_fields = ("immediate_contact",)

class ExamScoreInline(TabularInline):
    model = ExamScore
    extra = 0
    autocomplete_fields = ("student",)
    fields = ("student", "marks", "grade_value", "is_absent", "remarks")
    show_change_link = True

@admin.register(Exam)
class ExamAdmin(ModelAdmin):
    list_display = ("exam_name", "subject", "exam_group", "term", "term_academic_year", "start_time", "maximum_marks")
    list_filter = ("exam_group", "subject__batch", "assessment_slot", "term__academic_year")
    search_fields = ("exam_name", "subject__name")
    autocomplete_fields = ("subject", "exam_group", "grading_scale")
    list_select_related = ("subject", "exam_group", "term__academic_year")
    inlines = [ExamScoreInline]

    def term_academic_year(self, obj):
        if obj.term_id and obj.term.academic_year_id:
            return obj.term.academic_year.name
        return "—"
    term_academic_year.short_description = "Term Academic Year"

@admin.register(Subject)
class SubjectAdmin(ModelAdmin):
    list_display = ("name", "code", "batch", "employee", "is_deleted")
    list_filter = ("batch", "is_deleted", "language")
    search_fields = ("name", "code")
    autocomplete_fields = ("batch", "employee", "grading_scale")

@admin.register(ExtendedAdmissionApplication)
class ExtendedAdmissionApplicationAdmin(ModelAdmin):
    list_display = ("application_number", "first_name", "last_name", "status", "application_date")
    list_filter = ("status", "academic_year", "course_applied")
    search_fields = ("application_number", "first_name", "last_name", "email")
    autocomplete_fields = ("academic_year", "course_applied", "student_category")


@admin.register(Attendance)
class AttendanceAdmin(ModelAdmin):
    list_display = ("student", "batch", "month_date", "attendance_status")
    list_filter = ("batch", "month_date")
    search_fields = ("student__first_name", "student__last_name", "student__admission_no")
    autocomplete_fields = ("student", "batch")


class TermCorrectionMixin:
    """Shared "Recalculate correct term" admin action for models scoped by
    student + term (CharField) + academic_year (HomeworkAssessment,
    ProjectWorkAssessment, StudentActivity). Re-derives the ground-truth term
    via ReportGenerationService.resolve_term_for_student — the same logic
    core.management.commands.fix_activities_term_scoping uses — and
    re-points it where that's unambiguous. A row is left untouched (and
    reported) when another row already holds the correct term for that
    student, since picking a winner needs a human."""

    actions = ["recalculate_term"]

    def term_is_correct(self, obj):
        as_of = (obj.updated_at or obj.created_at).date()
        correct_term = ReportGenerationService.resolve_term_for_student(obj.student, obj.academic_year, as_of=as_of)
        return correct_term is None or correct_term == obj.term
    term_is_correct.boolean = True
    term_is_correct.short_description = "Term OK"

    @admin.action(description="Recalculate correct term")
    def recalculate_term(self, request, queryset):
        model = queryset.model
        fixed = conflicts = unresolved = 0
        for obj in queryset.select_related("student", "academic_year"):
            as_of = (obj.updated_at or obj.created_at).date()
            correct_term = ReportGenerationService.resolve_term_for_student(obj.student, obj.academic_year, as_of=as_of)
            if correct_term is None:
                unresolved += 1
                continue
            if correct_term == obj.term:
                continue
            clash = model.objects.filter(
                tenant=obj.tenant, student=obj.student, term=correct_term,
                academic_year=obj.academic_year,
            ).exclude(pk=obj.pk).exists()
            if clash:
                conflicts += 1
                continue
            obj.term = correct_term
            obj.save(update_fields=["term"])
            fixed += 1

        if fixed:
            self.message_user(request, f"Corrected term on {fixed} row(s).", level=messages.SUCCESS)
        if conflicts:
            self.message_user(
                request,
                f"Left {conflicts} row(s) unchanged — another row already holds the correct term "
                "for that student; compare and delete/edit manually.",
                level=messages.WARNING,
            )
        if unresolved:
            self.message_user(
                request,
                f"Couldn't determine a term for {unresolved} row(s) — no active batch/exam plan found.",
                level=messages.WARNING,
            )
        if not (fixed or conflicts or unresolved):
            self.message_user(request, "No changes needed — selected rows already have the correct term.", level=messages.INFO)


@admin.register(HomeworkAssessment)
class HomeworkAssessmentAdmin(TermCorrectionMixin, ModelAdmin):
    list_display = ("student", "term", "academic_year", "submission", "presentation", "effort", "term_is_correct")
    list_filter = ("term", "academic_year", "submission")
    search_fields = ("student__first_name", "student__last_name", "student__admission_no")
    autocomplete_fields = ("student", "academic_year")


@admin.register(ProjectWorkAssessment)
class ProjectWorkAssessmentAdmin(TermCorrectionMixin, ModelAdmin):
    list_display = ("student", "term", "academic_year", "submission", "presentation", "effort", "term_is_correct")
    list_filter = ("term", "academic_year", "submission")
    search_fields = ("student__first_name", "student__last_name", "student__admission_no")
    autocomplete_fields = ("student", "academic_year")


@admin.register(StudentActivity)
class StudentActivityAdmin(TermCorrectionMixin, ModelAdmin):
    list_display = ("student", "term", "academic_year", "activity_type", "activity_name", "term_is_correct")
    list_filter = ("term", "academic_year", "activity_type")
    search_fields = ("student__first_name", "student__last_name", "student__admission_no", "activity_name")
    autocomplete_fields = ("student", "academic_year")


class ReportSectionInline(TabularInline):
    model = ReportSection
    extra = 0
    ordering = ("order",)


@admin.register(ReportTemplate)
class ReportTemplateAdmin(ModelAdmin):
    list_display = ("name", "batch", "term", "academic_year", "layout_type", "is_default", "is_active", "term_is_correct")
    list_filter = ("layout_type", "is_active", "is_default", "academic_year")
    search_fields = ("name",)
    autocomplete_fields = ("batch", "academic_year", "grading_scale")
    inlines = [ReportSectionInline]
    actions = ["recalculate_term"]

    def _correct_term(self, obj):
        exam_group = (
            ExamGroup.objects.filter(batch=obj.batch, is_published=True)
            .order_by("-exam_date")
            .first()
        )
        if exam_group is None:
            return None
        return ReportGenerationService.resolve_exam_group_term(exam_group, as_of=obj.created_at.date())

    def term_is_correct(self, obj):
        correct = self._correct_term(obj)
        return correct is None or correct == (obj.term or "").strip()
    term_is_correct.boolean = True
    term_is_correct.short_description = "Term OK"

    @admin.action(description="Recalculate correct term")
    def recalculate_term(self, request, queryset):
        fixed = unresolved = 0
        for obj in queryset.select_related("batch"):
            correct = self._correct_term(obj)
            if correct is None:
                unresolved += 1
                continue
            if correct == (obj.term or "").strip():
                continue
            obj.term = correct
            obj.save(update_fields=["term"])
            fixed += 1
        if fixed:
            self.message_user(request, f"Corrected term on {fixed} template(s).", level=messages.SUCCESS)
        if unresolved:
            self.message_user(
                request,
                f"Couldn't determine a term for {unresolved} template(s) — no published exam plan found.",
                level=messages.WARNING,
            )
        if not fixed and not unresolved:
            self.message_user(request, "No changes needed — selected templates already have the correct term.", level=messages.INFO)

@admin.register(Term)
class TermAdmin(ModelAdmin):
    list_display = ("name", "academic_year", "start_date", "end_date", "order")
    list_filter = ("academic_year",)
    search_fields = ("name",)
    autocomplete_fields = ("academic_year",)


@admin.register(TeacherComment)
class TeacherCommentAdmin(ModelAdmin):
    list_display = ("student_name", "batch_name", "exam_group_name", "class_teacher_name", "updated_at")
    list_filter = ("exam_group", "class_teacher", "updated_at")
    search_fields = ("student__first_name", "student__last_name", "exam_group__batch__name", "class_teacher__first_name", "class_teacher__last_name")
    autocomplete_fields = ("student", "exam_group")
    # class_teacher is a stamp written by TeacherCommentService, not a field to
    # edit — see its help_text. It is still filterable/searchable above.
    readonly_fields = ("tenant", "comment", "class_teacher", "created_at", "updated_at")

    def student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"
    student_name.short_description = "Student"

    def batch_name(self, obj):
        return obj.exam_group.batch.name if obj.exam_group else "—"
    batch_name.short_description = "Batch"

    def exam_group_name(self, obj):
        return obj.exam_group.name if obj.exam_group else "—"
    exam_group_name.short_description = "Exam Group"

    def class_teacher_name(self, obj):
        return obj.class_teacher.full_name if obj.class_teacher else "—"
    class_teacher_name.short_description = "Teacher"


@admin.register(SkillsTeacherComment)
class SkillsTeacherCommentAdmin(ModelAdmin):
    list_display = ("student_name", "batch_name", "term_name", "class_teacher_name", "updated_at")
    list_filter = ("batch", "term", "class_teacher", "updated_at")
    search_fields = ("student__first_name", "student__last_name", "batch__name", "class_teacher__first_name", "class_teacher__last_name")
    autocomplete_fields = ("student", "batch", "term")
    # See TeacherCommentAdmin: class_teacher is a service-written stamp.
    readonly_fields = ("tenant", "comment", "class_teacher", "created_at", "updated_at")

    def student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"
    student_name.short_description = "Student"

    def batch_name(self, obj):
        return obj.batch.name
    batch_name.short_description = "Batch"

    def term_name(self, obj):
        return obj.term.name if obj.term else "—"
    term_name.short_description = "Term"

    def class_teacher_name(self, obj):
        return obj.class_teacher.full_name if obj.class_teacher else "—"
    class_teacher_name.short_description = "Teacher"


@admin.register(ActivityProfile)
class ActivityProfileAdmin(ModelAdmin):
    list_display = ("name", "display_name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "display_name")

@admin.register(Activity)
class ActivityAdmin(ModelAdmin):
    list_display = ("name", "activity_profile", "is_active")
    list_filter = ("activity_profile", "is_active")
    search_fields = ("name",)
    autocomplete_fields = ("activity_profile",)
