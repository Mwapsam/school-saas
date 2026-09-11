"""Transport module — dashboard, list screens, and htmx CRUD endpoints.

Structure mirrors ``core/view_modules/hr_settings_views.py``: a thin ``ListView``
per entity that only ever renders an htmx table fragment, plus plain
``@require_http_methods(["POST"])`` function endpoints that mutate via
``TransportService`` and return the re-rendered fragment (or a ``JsonResponse``
error the modal script surfaces inline).
"""
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, TemplateView

from core.models import Student, TransportRoute
from core.services.exceptions import ServiceException
from core.services.transport_service import TransportService, TransportSettingsService
from core.views import HTMXResponseMixin, _render_paginated_fragment

# entity key -> (fragment template, service list-method name, context key)
FRAGMENTS = {
    "stops": "core/htmx/transport/stop_list_content.html",
    "vehicles": "core/htmx/transport/vehicle_list_content.html",
    "staff": "core/htmx/transport/staff_list_content.html",
    "routes": "core/htmx/transport/route_list_content.html",
    "assignments": "core/htmx/transport/assignment_list_content.html",
}


def _tenant(request):
    return getattr(request, "tenant", None)


def _err(exc: ServiceException, status=400):
    return JsonResponse({"error": str(getattr(exc, "message", exc))}, status=status)


# --------------------------------------------------------------------------
# Fragment rendering
# --------------------------------------------------------------------------

def _list_queryset(tenant, entity, request):
    service = TransportService(tenant)
    search = request.GET.get("search", "").strip() or None
    if entity == "stops":
        return service.list_stops(search=search)
    if entity == "vehicles":
        return service.list_vehicles(
            search=search, status=request.GET.get("status") or None
        )
    if entity == "staff":
        return service.list_staff(
            staff_type=request.GET.get("staff_type") or None, search=search
        )
    if entity == "routes":
        return service.list_routes(search=search)
    if entity == "assignments":
        return service.list_assignments(
            route_id=request.GET.get("route") or None, search=search
        )
    raise Http404("Unknown transport entity")


def _fragment_extra(tenant, entity):
    """Lookup data the fragment/modal needs (stops, routes, staff dropdowns)."""
    service = TransportService(tenant)
    extra = {"entity": entity}
    if entity == "routes":
        extra["all_stops"] = service.list_stops()
        extra["all_vehicles"] = service.list_vehicles()
        extra["all_drivers"] = service.list_staff(staff_type="driver")
        extra["all_attendants"] = service.list_staff(staff_type="attendant")
    if entity == "assignments":
        extra["all_routes"] = TransportRoute.objects.filter(
            tenant=tenant, is_active=True
        ).order_by("route_name")
    return extra


def _render_transport_fragment(request, entity):
    tenant = _tenant(request)
    queryset = _list_queryset(tenant, entity, request)
    return _render_paginated_fragment(
        request, queryset, FRAGMENTS[entity], "items",
        paginate_by=15, extra_context=_fragment_extra(tenant, entity),
    )


# --------------------------------------------------------------------------
# Page views
# --------------------------------------------------------------------------

class TransportDashboardView(HTMXResponseMixin, TemplateView):
    template_name = "core/transport/dashboard.html"
    htmx_template_name = "core/htmx/transport/dashboard_content.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        if not tenant:
            return ctx
        stats = TransportService(tenant).dashboard_stats()
        ctx["stats"] = stats
        ctx["warnings"] = stats["warnings"]
        ctx["stat_cards"] = [
            {"label": "Active Routes", "value": stats["route_count"], "icon": "fa-route", "variant": "primary"},
            {"label": "Vehicles", "value": stats["vehicle_count"], "icon": "fa-bus", "variant": "primary"},
            {"label": "Stops", "value": stats["stop_count"], "icon": "fa-map-marker-alt", "variant": "primary"},
            {"label": "Drivers", "value": stats["driver_count"], "icon": "fa-id-card", "variant": "primary"},
            {"label": "Students on Transport", "value": stats["students_assigned"], "icon": "fa-user-graduate", "variant": "success"},
            {"label": "In Maintenance", "value": stats["vehicles_maintenance"], "icon": "fa-wrench", "variant": "warning"},
        ]
        ctx["dashboard_tiles"] = [
            {"icon": "fa-map-marker-alt", "title": "Stops", "description": "Pickup & drop-off points", "url": "/transport/stops/"},
            {"icon": "fa-bus", "title": "Vehicles", "description": "Fleet & compliance records", "url": "/transport/vehicles/"},
            {"icon": "fa-id-card", "title": "Drivers & Attendants", "description": "Transport staff", "url": "/transport/staff/"},
            {"icon": "fa-route", "title": "Routes", "description": "Stops, schedule, vehicle & crew", "url": "/transport/routes/"},
            {"icon": "fa-user-graduate", "title": "Assign Transport", "description": "Put students on routes & bill them", "url": "/transport/assignments/"},
            {"icon": "fa-cog", "title": "Settings", "description": "Defaults & billing", "url": "/transport/settings/"},
        ]
        return ctx


class _TransportListView(ListView):
    """Base for the five entity list screens — always an htmx fragment."""
    entity = None
    paginate_by = 15
    context_object_name = "items"

    def get_template_names(self):
        return [FRAGMENTS[self.entity]]

    def get_queryset(self):
        tenant = _tenant(self.request)
        if not tenant:
            return []
        return _list_queryset(tenant, self.entity, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        if tenant:
            ctx.update(_fragment_extra(tenant, self.entity))
        return ctx


class TransportStopListView(_TransportListView):
    entity = "stops"


class TransportVehicleListView(_TransportListView):
    entity = "vehicles"


class TransportStaffListView(_TransportListView):
    entity = "staff"


class TransportRouteListView(_TransportListView):
    entity = "routes"


class TransportAssignmentListView(_TransportListView):
    entity = "assignments"


class TransportEntityPageView(TemplateView):
    """The full-page shell for one entity list (hosts the toolbar + modal;
    the table itself is hx-get'd into a container)."""
    entity = None
    _TITLES = {
        "stops": ("Transport Stops", "fa-map-marker-alt", "Add Stop"),
        "vehicles": ("Vehicles", "fa-bus", "Add Vehicle"),
        "staff": ("Drivers & Attendants", "fa-id-card", "Add Person"),
        "routes": ("Routes", "fa-route", "Add Route"),
        "assignments": ("Assign Transport", "fa-user-graduate", "Assign Student"),
    }

    def get_template_names(self):
        return [f"core/transport/{self.entity}.html"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        title, icon, add_label = self._TITLES[self.entity]
        ctx.update({
            "entity": self.entity,
            "page_title_text": title,
            "page_icon": icon,
            "add_label": add_label,
        })
        if tenant:
            ctx.update(_fragment_extra(tenant, self.entity))
        ctx["vehicle_status_options"] = [
            {"value": "active", "label": "Active"},
            {"value": "maintenance", "label": "In Maintenance"},
            {"value": "inactive", "label": "Inactive"},
        ]
        ctx["staff_type_options"] = [
            {"value": "driver", "label": "Driver"},
            {"value": "attendant", "label": "Attendant"},
        ]
        ctx["direction_options"] = [
            {"value": "both", "label": "Pickup & Drop-off"},
            {"value": "pickup", "label": "Pickup only"},
            {"value": "dropoff", "label": "Drop-off only"},
        ]
        return ctx


class TransportSettingsView(TemplateView):
    template_name = "core/transport/settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        if not tenant:
            return ctx
        try:
            ctx["settings"] = TransportSettingsService(tenant).get_or_create()
        except ServiceException as exc:
            ctx["settings_error"] = str(getattr(exc, "message", exc))
        ctx["frequency_choices"] = [
            {"value": "one_time", "label": "One Time"},
            {"value": "monthly", "label": "Monthly"},
            {"value": "termly", "label": "Termly"},
            {"value": "yearly", "label": "Yearly"},
        ]
        return ctx


# --------------------------------------------------------------------------
# htmx CRUD endpoints
# --------------------------------------------------------------------------

def _post(request, key, default=""):
    return request.POST.get(key, default)


@require_http_methods(["POST"])
@login_required
def transport_entity_write(request, entity, action, pk=None):
    """Single dispatcher for create/update/toggle/delete across all entities."""
    tenant = _tenant(request)
    if not tenant:
        return JsonResponse({"error": "Tenant not found"}, status=400)
    if entity not in FRAGMENTS:
        raise Http404("Unknown transport entity")

    service = TransportService(tenant)
    P = request.POST
    try:
        if entity == "stops":
            _stop_write(service, action, pk, P, request.user)
        elif entity == "vehicles":
            _vehicle_write(service, action, pk, P, request.user)
        elif entity == "staff":
            _staff_write(service, action, pk, P, request.user)
        elif entity == "routes":
            _route_write(service, action, pk, P, request.user)
        elif entity == "assignments":
            _assignment_write(service, action, pk, P, request.user)
        return HttpResponse(_render_transport_fragment(request, entity))
    except ServiceException as exc:
        status = 404 if exc.__class__.__name__ == "NotFoundException" else 400
        return _err(exc, status)


def _stop_write(service, action, pk, P, user):
    if action == "create":
        service.create_stop(user=user, name=P.get("name"), address=P.get("address"),
                            landmark=P.get("landmark"), latitude=P.get("latitude"),
                            longitude=P.get("longitude"))
    elif action == "update":
        service.update_stop(pk, user=user, name=P.get("name"), address=P.get("address"),
                            landmark=P.get("landmark"), latitude=P.get("latitude"),
                            longitude=P.get("longitude"))
    elif action == "toggle":
        service.toggle_stop(pk)
    elif action == "delete":
        service.delete_stop(pk)
    else:
        raise Http404


def _vehicle_write(service, action, pk, P, user):
    fields = dict(
        vehicle_number=P.get("vehicle_number"), vehicle_type=P.get("vehicle_type"),
        seating_capacity=P.get("seating_capacity"), make_model=P.get("make_model"),
        manufacture_year=P.get("manufacture_year"),
        insurance_provider=P.get("insurance_provider"),
        insurance_expiry=P.get("insurance_expiry"),
        roadworthiness_expiry=P.get("roadworthiness_expiry"),
        registration_expiry=P.get("registration_expiry"),
        status=P.get("status") or "active", odometer_km=P.get("odometer_km"),
    )
    if action == "create":
        service.create_vehicle(user=user, **fields)
    elif action == "update":
        service.update_vehicle(pk, user=user, **fields)
    elif action == "delete":
        service.delete_vehicle(pk)
    elif action == "toggle":
        service.set_vehicle_status(
            pk, "inactive" if P.get("current") == "active" else "active"
        )
    else:
        raise Http404


def _staff_write(service, action, pk, P, user):
    fields = dict(
        staff_type=P.get("staff_type"), full_name=P.get("full_name"),
        phone=P.get("phone"), alt_phone=P.get("alt_phone"), email=P.get("email"),
        national_id=P.get("national_id"), license_number=P.get("license_number"),
        license_expiry=P.get("license_expiry"),
        emergency_contact_name=P.get("emergency_contact_name"),
        emergency_contact_phone=P.get("emergency_contact_phone"),
    )
    if action == "create":
        service.create_staff(user=user, **fields)
    elif action == "update":
        service.update_staff(pk, user=user, **fields)
    elif action == "toggle":
        service.toggle_staff(pk)
    elif action == "delete":
        service.delete_staff(pk)
    else:
        raise Http404


def _route_write(service, action, pk, P, user):
    fields = dict(
        route_name=P.get("route_name"), code=P.get("code"), fare=P.get("fare"),
        description=P.get("description"),
        estimated_duration_minutes=P.get("estimated_duration_minutes"),
    )
    if action == "create":
        route = service.create_route(user=user, **fields)
        _apply_route_stops(service, route.id, P)
        service.assign_route_resources(
            route.id, vehicle_id=P.get("vehicle") or None,
            driver_id=P.get("driver") or None, attendant_id=P.get("attendant") or None,
        )
    elif action == "update":
        service.update_route(pk, user=user, **fields)
        _apply_route_stops(service, pk, P)
        service.assign_route_resources(
            pk, vehicle_id=P.get("vehicle") or None,
            driver_id=P.get("driver") or None, attendant_id=P.get("attendant") or None,
        )
    elif action == "delete":
        service.delete_route(pk)
    else:
        raise Http404


def _apply_route_stops(service, route_id, P):
    """Stop rows arrive as parallel lists: stop_id[], pickup_time[], dropoff_time[]."""
    stop_ids = P.getlist("stop_id")
    pickups = P.getlist("pickup_time")
    dropoffs = P.getlist("dropoff_time")
    rows = []
    for i, stop_id in enumerate(stop_ids):
        if not stop_id:
            continue
        rows.append({
            "stop_id": stop_id,
            "order": i + 1,
            "pickup_time": pickups[i] if i < len(pickups) else None,
            "dropoff_time": dropoffs[i] if i < len(dropoffs) else None,
        })
    if rows or P.get("clear_stops") == "1":
        service.set_route_stops(route_id, rows)


def _assignment_write(service, action, pk, P, user):
    if action == "create":
        assignment = service.assign_student(
            student_id=P.get("student"), route_id=P.get("route"),
            boarding_stop_id=P.get("boarding_stop") or None,
            direction=P.get("direction") or "both",
            start_date=P.get("start_date"), end_date=P.get("end_date") or None,
            notes=P.get("notes"), user=user,
        )
        if P.get("charge_now") == "1":
            service.charge_assignment(
                assignment.id, amount=P.get("amount") or None, user=user
            )
    elif action == "charge":
        service.charge_assignment(pk, amount=P.get("amount") or None, user=user)
    elif action == "end":
        service.end_assignment(pk, end_date=P.get("end_date") or None)
    elif action == "delete":
        service.delete_assignment(pk)
    else:
        raise Http404


@require_http_methods(["GET"])
@login_required
def transport_route_stops_options(request, pk):
    """Boarding-stop <option>s for a route — used by the assignment modal."""
    tenant = _tenant(request)
    if not tenant:
        return JsonResponse({"stops": []})
    try:
        stops = TransportService(tenant).get_route_stops(pk)
    except ServiceException:
        return JsonResponse({"stops": []})
    return JsonResponse({"stops": [
        {
            "id": str(rs.id),
            "stop_id": str(rs.stop_id),
            "name": f"#{rs.order} {rs.stop.name}",
            "order": rs.order,
            "pickup_time": rs.pickup_time.strftime("%H:%M") if rs.pickup_time else "",
            "dropoff_time": rs.dropoff_time.strftime("%H:%M") if rs.dropoff_time else "",
        }
        for rs in stops
    ]})


@require_http_methods(["GET"])
@login_required
def transport_student_search(request):
    """Typeahead for the assignment modal's student picker."""
    tenant = _tenant(request)
    q = request.GET.get("q", "").strip()
    if not tenant or len(q) < 2:
        return JsonResponse({"results": []})
    qs = Student.objects.filter(
        tenant=tenant, is_active=True, is_deleted=False
    ).filter(
        Q(first_name__icontains=q) | Q(last_name__icontains=q)
        | Q(admission_no__icontains=q)
    )[:20]
    return JsonResponse({"results": [
        {"id": str(s.id),
         "text": f"{s.first_name} {s.last_name} ({s.admission_no or '—'})"}
        for s in qs
    ]})


@require_http_methods(["POST"])
@login_required
def transport_settings_update(request):
    tenant = _tenant(request)
    if not tenant:
        return JsonResponse({"error": "Tenant not found"}, status=400)
    P = request.POST
    try:
        TransportSettingsService(tenant).update(
            user=request.user,
            default_pickup_time=P.get("default_pickup_time") or None,
            default_dropoff_time=P.get("default_dropoff_time") or None,
            billing_frequency=P.get("billing_frequency") or "termly",
            attendance_tracking_enabled=P.get("attendance_tracking_enabled") == "1",
            notify_on_changes=P.get("notify_on_changes") == "1",
        )
    except ServiceException as exc:
        return _err(exc)
    from django.contrib import messages
    from django.shortcuts import redirect
    messages.success(request, "Transport settings saved.")
    return redirect("core:transport_settings")
