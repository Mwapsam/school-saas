"""Transport module service layer.

Business logic for the core operational transport subset: settings, stops,
vehicles, drivers/attendants, routes (with stops + schedule), student/employee
route assignment, and the bridge that turns an assignment into a finance charge.

Transport billing is NOT stored on the legacy ``TransportFee`` model. A charge
is a real ``FinanceFee`` in the finance subsystem, created via
``FinanceService.record_student_fee`` so it lands on the guardian's
``FamilyInvoice`` like every other fee.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from django.db import transaction
from django.db.models import Count, Q

from core.models import (
    AcademicYear,
    EmployeeTransportAssignment,
    FeeCategory,
    Student,
    StudentTransportAssignment,
    TransportRoute,
    TransportRouteStop,
    TransportSettings,
    TransportStaff,
    TransportStop,
    Vehicle,
)

from .exceptions import (
    BusinessLogicException,
    DuplicateException,
    NotFoundException,
    ValidationException,
)
from .finance_service import FinanceService
from .logging_service import ServiceLogger, logged_operation

# A vehicle document within this many days of expiry is "expiring soon".
COMPLIANCE_WARNING_DAYS = 30


def _parse_decimal(value, field="amount") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationException(f"Invalid number for {field}: {value!r}")


def _parse_date(value, field="date"):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValidationException(f"Invalid date for {field}: {value!r}")


class TransportSettingsService:
    """Per-academic-year transport configuration."""

    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = ServiceLogger("transport", tenant)

    def _resolve_year(self, academic_year=None) -> AcademicYear:
        if academic_year is not None:
            return academic_year
        year = AcademicYear.objects.filter(
            tenant=self.tenant, is_active=True
        ).first()
        if year is None:
            raise BusinessLogicException(
                "No active academic year is set. Create one before configuring transport."
            )
        return year

    def get_or_create(self, academic_year=None) -> TransportSettings:
        year = self._resolve_year(academic_year)
        settings, created = TransportSettings.objects.get_or_create(
            tenant=self.tenant, academic_year=year
        )
        if settings.fee_category_id is None:
            settings.fee_category = self._ensure_fee_category(year)
            settings.save(update_fields=["fee_category"])
        return settings

    def _ensure_fee_category(self, year: AcademicYear) -> FeeCategory:
        existing = FeeCategory.objects.filter(
            tenant=self.tenant, name="Transport Fee", is_deleted=False
        ).first()
        if existing:
            return existing
        return FinanceService(self.tenant).create_fee_category(
            name="Transport Fee",
            description="Auto-created for the Transport module.",
            academic_year=year,
        )

    @logged_operation(action="update", resource_type="transport_settings")
    def update(self, academic_year=None, user=None, **data: Dict[str, Any]) -> TransportSettings:
        settings = self.get_or_create(academic_year)
        allowed = {
            "default_pickup_time",
            "default_dropoff_time",
            "billing_frequency",
            "attendance_tracking_enabled",
            "notify_on_changes",
        }
        for field, value in data.items():
            if field in allowed:
                setattr(settings, field, value)
        settings.save()
        return settings


class TransportService:
    """Operational CRUD + assignment logic for the transport module."""

    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = ServiceLogger("transport", tenant)

    # -- helpers ---------------------------------------------------------------

    def _get(self, model, obj_id):
        try:
            return model.objects.get(tenant=self.tenant, id=obj_id)
        except (model.DoesNotExist, ValueError, TypeError):
            raise NotFoundException(f"{model.__name__} {obj_id} not found")

    # -- stops --------------------------------------------------------------

    def list_stops(self, search: Optional[str] = None):
        qs = TransportStop.objects.filter(tenant=self.tenant)
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(address__icontains=search)
                | Q(landmark__icontains=search)
            )
        return qs.order_by("name")

    @logged_operation(action="create", resource_type="transport_stop")
    def create_stop(self, user=None, **data) -> TransportStop:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationException("Stop name is required.")
        if TransportStop.objects.filter(
            tenant=self.tenant, name__iexact=name
        ).exists():
            raise DuplicateException(f"A stop named '{name}' already exists.")
        return TransportStop.objects.create(
            tenant=self.tenant,
            name=name,
            address=data.get("address", "") or "",
            landmark=data.get("landmark", "") or "",
            latitude=data.get("latitude") or None,
            longitude=data.get("longitude") or None,
        )

    @logged_operation(action="update", resource_type="transport_stop")
    def update_stop(self, obj_id, user=None, **data) -> TransportStop:
        stop = self._get(TransportStop, obj_id)
        for field in ("name", "address", "landmark"):
            if field in data:
                setattr(stop, field, (data.get(field) or "").strip())
        if "latitude" in data:
            stop.latitude = data.get("latitude") or None
        if "longitude" in data:
            stop.longitude = data.get("longitude") or None
        if not stop.name:
            raise ValidationException("Stop name is required.")
        stop.save()
        return stop

    def toggle_stop(self, obj_id) -> TransportStop:
        stop = self._get(TransportStop, obj_id)
        stop.is_active = not stop.is_active
        stop.save(update_fields=["is_active"])
        return stop

    def delete_stop(self, obj_id) -> None:
        stop = self._get(TransportStop, obj_id)
        if TransportRouteStop.objects.filter(tenant=self.tenant, stop=stop).exists():
            raise BusinessLogicException(
                "This stop is used by a route. Remove it from the route first."
            )
        stop.delete()

    # -- vehicles ---------------------------------------------------------------

    _VEHICLE_FIELDS = (
        "vehicle_number", "vehicle_type", "seating_capacity", "make_model",
        "manufacture_year", "insurance_provider", "insurance_expiry",
        "roadworthiness_expiry", "registration_expiry", "status", "odometer_km",
    )
    _VEHICLE_DATE_FIELDS = (
        "insurance_expiry", "roadworthiness_expiry", "registration_expiry",
    )
    _VEHICLE_INT_FIELDS = ("seating_capacity", "manufacture_year", "odometer_km")

    def list_vehicles(self, search: Optional[str] = None, status: Optional[str] = None):
        qs = Vehicle.objects.filter(tenant=self.tenant)
        if search:
            qs = qs.filter(
                Q(vehicle_number__icontains=search)
                | Q(vehicle_type__icontains=search)
                | Q(make_model__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("vehicle_number")

    def _clean_vehicle_data(self, data) -> dict:
        cleaned = {}
        for field in self._VEHICLE_FIELDS:
            if field not in data:
                continue
            value = data.get(field)
            if field in self._VEHICLE_DATE_FIELDS:
                cleaned[field] = _parse_date(value, field)
            elif field in self._VEHICLE_INT_FIELDS:
                cleaned[field] = int(value) if value not in (None, "") else None
            else:
                cleaned[field] = value or ""
        return cleaned

    @logged_operation(action="create", resource_type="transport_vehicle")
    def create_vehicle(self, user=None, **data) -> Vehicle:
        cleaned = self._clean_vehicle_data(data)
        if not cleaned.get("vehicle_number"):
            raise ValidationException("Vehicle number is required.")
        if cleaned.get("seating_capacity") is None:
            raise ValidationException("Seating capacity is required.")
        if Vehicle.objects.filter(
            tenant=self.tenant, vehicle_number__iexact=cleaned["vehicle_number"]
        ).exists():
            raise DuplicateException(
                f"Vehicle '{cleaned['vehicle_number']}' already exists."
            )
        cleaned.setdefault("status", "active")
        return Vehicle.objects.create(tenant=self.tenant, **cleaned)

    @logged_operation(action="update", resource_type="transport_vehicle")
    def update_vehicle(self, obj_id, user=None, **data) -> Vehicle:
        vehicle = self._get(Vehicle, obj_id)
        for field, value in self._clean_vehicle_data(data).items():
            setattr(vehicle, field, value)
        if not vehicle.vehicle_number:
            raise ValidationException("Vehicle number is required.")
        vehicle.save()
        return vehicle

    def set_vehicle_status(self, obj_id, status: str) -> Vehicle:
        valid = {c[0] for c in Vehicle.VEHICLE_STATUS_CHOICES}
        if status not in valid:
            raise ValidationException(f"Unknown vehicle status '{status}'.")
        vehicle = self._get(Vehicle, obj_id)
        vehicle.status = status
        vehicle.save(update_fields=["status"])
        return vehicle

    def delete_vehicle(self, obj_id) -> None:
        vehicle = self._get(Vehicle, obj_id)
        if vehicle.assigned_routes.exists():
            raise BusinessLogicException(
                "This vehicle is assigned to a route. Reassign the route first."
            )
        vehicle.delete()

    def compliance_flags(self, vehicle: Vehicle) -> Dict[str, str]:
        """Map of label -> 'expired' | 'expiring' for docs needing attention."""
        return vehicle.compliance_flags

    # -- drivers & attendants -------------------------------------------------

    _STAFF_FIELDS = (
        "staff_type", "full_name", "phone", "alt_phone", "email", "national_id",
        "license_number", "license_expiry", "emergency_contact_name",
        "emergency_contact_phone",
    )

    def list_staff(self, staff_type: Optional[str] = None, search: Optional[str] = None):
        qs = TransportStaff.objects.filter(tenant=self.tenant)
        if staff_type:
            qs = qs.filter(staff_type=staff_type)
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) | Q(phone__icontains=search)
                | Q(license_number__icontains=search)
            )
        return qs.order_by("staff_type", "full_name")

    def _clean_staff_data(self, data) -> dict:
        cleaned = {}
        for field in self._STAFF_FIELDS:
            if field not in data:
                continue
            value = data.get(field)
            if field == "license_expiry":
                cleaned[field] = _parse_date(value, field)
            else:
                cleaned[field] = value or ""
        return cleaned

    @logged_operation(action="create", resource_type="transport_staff")
    def create_staff(self, user=None, **data) -> TransportStaff:
        cleaned = self._clean_staff_data(data)
        if cleaned.get("staff_type") not in {"driver", "attendant"}:
            raise ValidationException("Staff type must be 'driver' or 'attendant'.")
        if not cleaned.get("full_name"):
            raise ValidationException("Full name is required.")
        if not cleaned.get("phone"):
            raise ValidationException("Phone is required.")
        return TransportStaff.objects.create(tenant=self.tenant, **cleaned)

    @logged_operation(action="update", resource_type="transport_staff")
    def update_staff(self, obj_id, user=None, **data) -> TransportStaff:
        staff = self._get(TransportStaff, obj_id)
        for field, value in self._clean_staff_data(data).items():
            setattr(staff, field, value)
        if not staff.full_name:
            raise ValidationException("Full name is required.")
        staff.save()
        return staff

    def toggle_staff(self, obj_id) -> TransportStaff:
        staff = self._get(TransportStaff, obj_id)
        staff.is_active = not staff.is_active
        staff.save(update_fields=["is_active"])
        return staff

    def delete_staff(self, obj_id) -> None:
        staff = self._get(TransportStaff, obj_id)
        if staff.driver_routes.exists() or staff.attendant_routes.exists():
            raise BusinessLogicException(
                "This person is assigned to a route. Reassign the route first."
            )
        staff.delete()

    # -- routes -------------------------------------------------------------

    def list_routes(self, search: Optional[str] = None):
        qs = TransportRoute.objects.filter(tenant=self.tenant).select_related(
            "vehicle", "driver", "attendant"
        ).annotate(
            stop_count=Count("route_stops", distinct=True),
            student_count=Count("student_assignments", distinct=True),
        )
        if search:
            qs = qs.filter(
                Q(route_name__icontains=search) | Q(code__icontains=search)
            )
        return qs.order_by("route_name")

    @logged_operation(action="create", resource_type="transport_route")
    def create_route(self, user=None, **data) -> TransportRoute:
        name = (data.get("route_name") or "").strip()
        code = (data.get("code") or "").strip()
        if not name:
            raise ValidationException("Route name is required.")
        if not code:
            raise ValidationException("Route code is required.")
        if TransportRoute.objects.filter(
            tenant=self.tenant, code__iexact=code
        ).exists():
            raise DuplicateException(f"Route code '{code}' already exists.")
        return TransportRoute.objects.create(
            tenant=self.tenant,
            route_name=name,
            code=code,
            fare=_parse_decimal(data.get("fare") or 0, "fare"),
            description=data.get("description", "") or "",
            estimated_duration_minutes=(
                int(data["estimated_duration_minutes"])
                if data.get("estimated_duration_minutes") else None
            ),
        )

    @logged_operation(action="update", resource_type="transport_route")
    def update_route(self, obj_id, user=None, **data) -> TransportRoute:
        route = self._get(TransportRoute, obj_id)
        if "route_name" in data:
            route.route_name = (data.get("route_name") or "").strip()
        if "code" in data:
            code = (data.get("code") or "").strip()
            if code and TransportRoute.objects.filter(
                tenant=self.tenant, code__iexact=code
            ).exclude(id=route.id).exists():
                raise DuplicateException(f"Route code '{code}' already exists.")
            route.code = code
        if "fare" in data:
            route.fare = _parse_decimal(data.get("fare") or 0, "fare")
        if "description" in data:
            route.description = data.get("description", "") or ""
        if "estimated_duration_minutes" in data:
            route.estimated_duration_minutes = (
                int(data["estimated_duration_minutes"])
                if data.get("estimated_duration_minutes") else None
            )
        if not route.route_name or not route.code:
            raise ValidationException("Route name and code are required.")
        route.save()
        return route

    @transaction.atomic
    def set_route_stops(self, route_id, stops: list) -> TransportRoute:
        """Replace a route's stop list. ``stops`` = [{stop_id, order,
        pickup_time, dropoff_time}, ...]."""
        route = self._get(TransportRoute, route_id)
        route.route_stops.all().delete()
        seen = set()
        for index, row in enumerate(stops, start=1):
            stop_id = row.get("stop_id")
            if not stop_id or stop_id in seen:
                continue
            seen.add(stop_id)
            stop = self._get(TransportStop, stop_id)
            TransportRouteStop.objects.create(
                tenant=self.tenant,
                route=route,
                stop=stop,
                order=int(row.get("order") or index),
                pickup_time=row.get("pickup_time") or None,
                dropoff_time=row.get("dropoff_time") or None,
            )
        return route

    def assign_route_resources(self, route_id, vehicle_id=None, driver_id=None,
                               attendant_id=None) -> TransportRoute:
        route = self._get(TransportRoute, route_id)
        route.vehicle = self._get(Vehicle, vehicle_id) if vehicle_id else None
        if driver_id:
            driver = self._get(TransportStaff, driver_id)
            if driver.staff_type != "driver":
                raise ValidationException("Selected person is not a driver.")
            route.driver = driver
        else:
            route.driver = None
        if attendant_id:
            route.attendant = self._get(TransportStaff, attendant_id)
        else:
            route.attendant = None
        route.save(update_fields=["vehicle", "driver", "attendant"])
        return route

    def delete_route(self, obj_id) -> None:
        route = self._get(TransportRoute, obj_id)
        if route.student_assignments.filter(is_active=True).exists():
            raise BusinessLogicException(
                "This route has active student assignments. End them first."
            )
        route.route_stops.all().delete()
        route.delete()

    def get_route_stops(self, route_id):
        route = self._get(TransportRoute, route_id)
        return route.route_stops.select_related("stop").order_by("order")

    # -- student assignment -------------------------------------------------

    def list_assignments(self, route_id: Optional[str] = None,
                         search: Optional[str] = None, active_only: bool = False):
        qs = StudentTransportAssignment.objects.filter(
            tenant=self.tenant
        ).select_related("student", "route", "boarding_stop__stop", "finance_fee")
        if route_id:
            qs = qs.filter(route_id=route_id)
        if active_only:
            qs = qs.filter(is_active=True)
        if search:
            qs = qs.filter(
                Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(route__route_name__icontains=search)
            )
        return qs.order_by("student__first_name", "student__last_name")

    @logged_operation(action="create", resource_type="transport_assignment")
    def assign_student(self, student_id, route_id, boarding_stop_id=None,
                       direction="both", start_date=None, end_date=None,
                       notes="", user=None) -> StudentTransportAssignment:
        try:
            student = Student.objects.get(tenant=self.tenant, id=student_id)
        except (Student.DoesNotExist, ValueError, TypeError):
            raise NotFoundException(f"Student {student_id} not found")
        route = self._get(TransportRoute, route_id)
        start = _parse_date(start_date, "start_date") or date.today()
        end = _parse_date(end_date, "end_date")
        if end and end < start:
            raise ValidationException("End date cannot be before the start date.")

        overlap = StudentTransportAssignment.objects.filter(
            tenant=self.tenant, student=student, is_active=True
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=start))
        if overlap.exists():
            raise BusinessLogicException(
                "This student already has an active transport assignment for this period."
            )

        boarding_stop = None
        if boarding_stop_id:
            boarding_stop = self._get(TransportRouteStop, boarding_stop_id)
            if boarding_stop.route_id != route.id:
                raise ValidationException(
                    "The boarding stop does not belong to the selected route."
                )
        if direction not in {"both", "pickup", "dropoff"}:
            direction = "both"

        return StudentTransportAssignment.objects.create(
            tenant=self.tenant,
            student=student,
            route=route,
            boarding_stop=boarding_stop,
            direction=direction,
            start_date=start,
            end_date=end,
            notes=notes or "",
        )

    @logged_operation(action="charge", resource_type="transport_assignment")
    def charge_assignment(self, assignment_id, amount=None, academic_year=None,
                          user=None) -> StudentTransportAssignment:
        assignment = self._get(StudentTransportAssignment, assignment_id)
        if assignment.finance_fee_id:
            raise BusinessLogicException("This assignment has already been charged.")

        settings = TransportSettingsService(self.tenant).get_or_create(academic_year)
        charge_amount = (
            _parse_decimal(amount, "amount") if amount not in (None, "")
            else Decimal(assignment.route.fare or 0)
        )
        if charge_amount <= 0:
            raise ValidationException("Charge amount must be greater than zero.")

        finance_fee = FinanceService(self.tenant).record_student_fee(
            student_id=str(assignment.student_id),
            fee_category_id=str(settings.fee_category_id),
            balance=charge_amount,
            transaction_date=date.today(),
            academic_year=settings.academic_year,
        )
        assignment.finance_fee = finance_fee
        assignment.save(update_fields=["finance_fee"])
        return assignment

    def end_assignment(self, assignment_id, end_date=None) -> StudentTransportAssignment:
        assignment = self._get(StudentTransportAssignment, assignment_id)
        assignment.end_date = _parse_date(end_date, "end_date") or date.today()
        assignment.is_active = False
        assignment.save(update_fields=["end_date", "is_active"])
        return assignment

    def delete_assignment(self, assignment_id) -> None:
        assignment = self._get(StudentTransportAssignment, assignment_id)
        if assignment.finance_fee_id:
            raise BusinessLogicException(
                "This assignment has been charged. End it instead of deleting."
            )
        assignment.delete()

    # -- employee assignment ------------------------------------------------

    def list_employee_assignments(self, route_id: Optional[str] = None):
        qs = EmployeeTransportAssignment.objects.filter(
            tenant=self.tenant
        ).select_related("employee", "route", "boarding_stop__stop")
        if route_id:
            qs = qs.filter(route_id=route_id)
        return qs.order_by("employee__first_name")

    @logged_operation(action="create", resource_type="employee_transport_assignment")
    def assign_employee(self, employee_id, route_id, boarding_stop_id=None,
                        direction="both", start_date=None, end_date=None,
                        notes="", user=None) -> EmployeeTransportAssignment:
        from core.models import Employee
        try:
            employee = Employee.objects.get(tenant=self.tenant, id=employee_id)
        except (Employee.DoesNotExist, ValueError, TypeError):
            raise NotFoundException(f"Employee {employee_id} not found")
        route = self._get(TransportRoute, route_id)
        start = _parse_date(start_date, "start_date") or date.today()
        end = _parse_date(end_date, "end_date")
        if end and end < start:
            raise ValidationException("End date cannot be before the start date.")
        boarding_stop = None
        if boarding_stop_id:
            boarding_stop = self._get(TransportRouteStop, boarding_stop_id)
        return EmployeeTransportAssignment.objects.create(
            tenant=self.tenant,
            employee=employee,
            route=route,
            boarding_stop=boarding_stop,
            direction=direction if direction in {"both", "pickup", "dropoff"} else "both",
            start_date=start,
            end_date=end,
            notes=notes or "",
        )

    def end_employee_assignment(self, assignment_id, end_date=None):
        assignment = self._get(EmployeeTransportAssignment, assignment_id)
        assignment.end_date = _parse_date(end_date, "end_date") or date.today()
        assignment.is_active = False
        assignment.save(update_fields=["end_date", "is_active"])
        return assignment

    # -- dashboard --------------------------------------------------------------

    def dashboard_stats(self) -> Dict[str, Any]:
        vehicles = list(Vehicle.objects.filter(tenant=self.tenant))
        warnings = []
        for vehicle in vehicles:
            for label, state in vehicle.compliance_flags.items():
                warnings.append({
                    "vehicle": vehicle.vehicle_number,
                    "detail": f"{label} {state}",
                    "state": state,
                })
        today = date.today()
        for staff in TransportStaff.objects.filter(
            tenant=self.tenant, staff_type="driver", is_active=True,
            license_expiry__isnull=False,
        ):
            delta = (staff.license_expiry - today).days
            if delta < 0:
                warnings.append({"vehicle": staff.full_name,
                                 "detail": "Licence expired", "state": "expired"})
            elif delta <= COMPLIANCE_WARNING_DAYS:
                warnings.append({"vehicle": staff.full_name,
                                 "detail": "Licence expiring", "state": "expiring"})

        return {
            "route_count": TransportRoute.objects.filter(
                tenant=self.tenant, is_active=True
            ).count(),
            "vehicle_count": len(vehicles),
            "vehicles_active": sum(1 for v in vehicles if v.status == "active"),
            "vehicles_maintenance": sum(1 for v in vehicles if v.status == "maintenance"),
            "stop_count": TransportStop.objects.filter(tenant=self.tenant).count(),
            "driver_count": TransportStaff.objects.filter(
                tenant=self.tenant, staff_type="driver", is_active=True
            ).count(),
            "attendant_count": TransportStaff.objects.filter(
                tenant=self.tenant, staff_type="attendant", is_active=True
            ).count(),
            "students_assigned": StudentTransportAssignment.objects.filter(
                tenant=self.tenant, is_active=True
            ).count(),
            "warnings": warnings,
        }
