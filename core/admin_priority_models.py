# Priority Phase 1 Models - Enhanced Academic Features Admin Classes
# Import these into main admin.py

from django.contrib import admin
from .models import (
    AttendanceLabel, AssessmentMark, TimetableEntry, ClassTimingSet, ClassPeriod,
    EnhancedAttendance, SubjectAssessment
)

@admin.register(AttendanceLabel)
class AttendanceLabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'color_code', 'is_considered_present', 'affects_attendance_percentage', 'order', 'is_active')
    list_filter = ('is_considered_present', 'affects_attendance_percentage', 'is_active')
    search_fields = ('name', 'code')
    ordering = ('order', 'name')
    list_editable = ('order', 'is_active', 'color_code')

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'color_code', 'order', 'is_active')
        }),
        ('Attendance Rules', {
            'fields': ('is_considered_present', 'affects_attendance_percentage'),
            'description': 'Configure how this label affects attendance calculations',
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant') and request.tenant:
            return qs.filter(tenant=request.tenant)
        return qs

    def save_model(self, request, obj, form, change):
        if hasattr(request, 'tenant') and request.tenant and not obj.tenant_id:
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)


@admin.register(AssessmentMark)
class AssessmentMarkAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'assessment_name', 'assessment_type', 'marks_obtained', 'maximum_marks', 'percentage', 'grade', 'assessment_date', 'is_published')
    list_filter = ('assessment_type', 'is_published', 'assessment_date', 'academic_year', 'term')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_no', 'assessment_name', 'subject__name')
    ordering = ('-assessment_date', 'student__first_name')
    readonly_fields = ('percentage',)
    list_editable = ('is_published', 'grade')

    fieldsets = (
        (None, {
            'fields': ('student', 'subject', 'exam', 'assessment_name', 'assessment_type', 'assessment_date')
        }),
        ('Marks & Grading', {
            'fields': ('marks_obtained', 'maximum_marks', 'percentage', 'grade'),
        }),
        ('Academic Context', {
            'fields': ('term', 'academic_year', 'assessed_by'),
        }),
        ('Publishing', {
            'fields': ('is_published', 'remarks'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant') and request.tenant:
            return qs.filter(tenant=request.tenant)
        return qs

    def save_model(self, request, obj, form, change):
        if hasattr(request, 'tenant') and request.tenant and not obj.tenant_id:
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('batch', 'subject', 'employee', 'weekday', 'period_number', 'class_timing', 'classroom', 'is_substitution', 'is_active')
    list_filter = ('weekday', 'is_substitution', 'is_active', 'batch', 'subject')
    search_fields = ('batch__name', 'subject__name', 'employee__first_name', 'employee__last_name', 'classroom')
    ordering = ('batch', 'weekday__order', 'period_number')
    list_editable = ('classroom', 'is_active')

    fieldsets = (
        (None, {
            'fields': ('timetable', 'weekday', 'class_timing', 'period_number')
        }),
        ('Academic Details', {
            'fields': ('batch', 'subject', 'employee', 'classroom'),
        }),
        ('Substitution', {
            'fields': ('is_substitution', 'original_employee'),
            'classes': ('collapse',),
        }),
        ('Status & Notes', {
            'fields': ('is_active', 'notes'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant') and request.tenant:
            return qs.filter(tenant=request.tenant)
        return qs

    def save_model(self, request, obj, form, change):
        if hasattr(request, 'tenant') and request.tenant and not obj.tenant_id:
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)


@admin.register(ClassTimingSet)
class ClassTimingSetAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'is_default', 'is_active')
    list_filter = ('academic_year', 'is_default', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('academic_year', 'name')
    list_editable = ('is_default', 'is_active')

    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'academic_year')
        }),
        ('Settings', {
            'fields': ('is_default', 'is_active'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant') and request.tenant:
            return qs.filter(tenant=request.tenant)
        return qs

    def save_model(self, request, obj, form, change):
        if hasattr(request, 'tenant') and request.tenant and not obj.tenant_id:
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)


@admin.register(ClassPeriod)
class ClassPeriodAdmin(admin.ModelAdmin):
    list_display = ('timing_set', 'period_number', 'start_time', 'end_time', 'period_type', 'duration_minutes')
    list_filter = ('timing_set', 'period_type')
    ordering = ('timing_set', 'period_number')
    readonly_fields = ('duration_minutes',)

    fieldsets = (
        (None, {
            'fields': ('timing_set', 'period_number', 'period_type')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'duration_minutes'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant') and request.tenant:
            return qs.filter(tenant=request.tenant)
        return qs

    def save_model(self, request, obj, form, change):
        if hasattr(request, 'tenant') and request.tenant and not obj.tenant_id:
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)


@admin.register(EnhancedAttendance)
class EnhancedAttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'batch', 'attendance_date', 'attendance_label', 'period_number', 'subject', 'late_minutes')
    list_filter = ('attendance_date', 'attendance_label', 'batch', 'academic_year')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_no')
    ordering = ('-attendance_date', 'student__first_name')
    list_editable = ('attendance_label', 'late_minutes')

    fieldsets = (
        (None, {
            'fields': ('student', 'batch', 'attendance_date', 'attendance_label')
        }),
        ('Period Details', {
            'fields': ('period_number', 'subject'),
        }),
        ('Timing', {
            'fields': ('check_in_time', 'check_out_time', 'late_minutes'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('academic_year', 'marked_by', 'remarks'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant') and request.tenant:
            return qs.filter(tenant=request.tenant)
        return qs

    def save_model(self, request, obj, form, change):
        if hasattr(request, 'tenant') and request.tenant and not obj.tenant_id:
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)


@admin.register(SubjectAssessment)
class SubjectAssessmentAdmin(admin.ModelAdmin):
    list_display = ('subject', 'batch', 'assessment_name', 'assessment_type', 'weightage_percentage', 'maximum_marks', 'assessment_frequency', 'is_active')
    list_filter = ('assessment_type', 'assessment_frequency', 'is_active', 'academic_year')
    search_fields = ('subject__name', 'batch__name', 'assessment_name')
    ordering = ('subject', 'batch', 'assessment_name')
    list_editable = ('weightage_percentage', 'is_active')

    fieldsets = (
        (None, {
            'fields': ('subject', 'batch', 'assessment_name', 'assessment_type', 'academic_year')
        }),
        ('Scoring Configuration', {
            'fields': ('weightage_percentage', 'maximum_marks', 'minimum_marks'),
        }),
        ('Settings', {
            'fields': ('assessment_frequency', 'is_active'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant') and request.tenant:
            return qs.filter(tenant=request.tenant)
        return qs

    def save_model(self, request, obj, form, change):
        if hasattr(request, 'tenant') and request.tenant and not obj.tenant_id:
            obj.tenant = request.tenant
        super().save_model(request, obj, form, change)