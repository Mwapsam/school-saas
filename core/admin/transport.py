from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from core.models import (
    EmployeeTransportAssignment,
    StudentTransportAssignment,
    TransportRoute,
    TransportRouteStop,
    TransportSettings,
    TransportStaff,
    TransportStop,
    Vehicle,
)


class TransportRouteStopInline(TabularInline):
    model = TransportRouteStop
    extra = 0
    fields = ("order", "stop", "pickup_time", "dropoff_time")
    ordering = ("order",)


@admin.register(Vehicle)
class VehicleAdmin(ModelAdmin):
    list_display = ("vehicle_number", "vehicle_type", "seating_capacity", "status", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("vehicle_number", "vehicle_type", "make_model")


@admin.register(TransportStaff)
class TransportStaffAdmin(ModelAdmin):
    list_display = ("full_name", "staff_type", "phone", "is_active", "tenant")
    list_filter = ("staff_type", "is_active", "tenant")
    search_fields = ("full_name", "phone", "license_number")


@admin.register(TransportStop)
class TransportStopAdmin(ModelAdmin):
    list_display = ("name", "landmark", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("name", "address", "landmark")


@admin.register(TransportRoute)
class TransportRouteAdmin(ModelAdmin):
    list_display = ("route_name", "code", "fare", "vehicle", "driver", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("route_name", "code")
    inlines = [TransportRouteStopInline]


@admin.register(TransportSettings)
class TransportSettingsAdmin(ModelAdmin):
    list_display = ("academic_year", "billing_frequency", "fee_category", "tenant")
    list_filter = ("billing_frequency", "tenant")


@admin.register(StudentTransportAssignment)
class StudentTransportAssignmentAdmin(ModelAdmin):
    list_display = ("student", "route", "direction", "start_date", "end_date", "is_active", "tenant")
    list_filter = ("is_active", "direction", "tenant")
    search_fields = ("student__first_name", "student__last_name", "route__route_name")
    raw_id_fields = ("student", "route", "boarding_stop", "finance_fee")


@admin.register(EmployeeTransportAssignment)
class EmployeeTransportAssignmentAdmin(ModelAdmin):
    list_display = ("employee", "route", "direction", "start_date", "end_date", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
