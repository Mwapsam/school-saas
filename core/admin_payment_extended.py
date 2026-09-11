"""
Admin interfaces for extended payment models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import FeeWaiver


@admin.register(FeeWaiver)
class FeeWaiverAdmin(admin.ModelAdmin):
    list_display = [
        'student_name', 'fee_category', 'waiver_type', 'amount',
        'percentage', 'approved_by', 'approval_date', 'is_active'
    ]
    list_filter = ['waiver_type', 'fee_category', 'approved_by', 'approval_date', 'is_active']
    search_fields = ['student__first_name', 'student__last_name', 'reason']
    autocomplete_fields = ['student', 'approved_by']
    date_hierarchy = 'approval_date'

    def student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"
    student_name.short_description = 'Student'

    def save_model(self, request, obj, form, change):
        # Auto-assign tenant if not set
        if not obj.tenant_id:
            from .utils import get_current_tenant
            obj.tenant = get_current_tenant()
        super().save_model(request, obj, form, change)
