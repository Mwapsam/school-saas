"""
Module registry — the single authoritative source of truth for all feature/product modules.

This registry defines which modules (HR, Finance, Hostel, etc.) can be enabled/disabled
per school. Both the backend (DRF permission checks) and frontend (navigation, capabilities)
derive their available modules from this single definition, avoiding duplication and
ensuring consistency across layers.

Every module listed here corresponds to:
1. A Django app or feature area (e.g., HR payroll, Finance invoicing)
2. A SchoolModule database record (per school, tracks enabled/disabled + config)
3. Bootstrap response keys (frontend learns what's available)
4. API permission checks (ModuleEnabled DRF permission class)
"""

MODULES = {
    # Academic module — core student/course/exam/attendance management
    "academics": {
        "label": "Academics",
        "description": "Student enrollment, courses, exams, attendance, report cards",
        "category": "core",
        "required": True,  # Every school must have academics enabled
    },

    # Admissions — application intake, batch assignment
    "admissions": {
        "label": "Admissions",
        "description": "Student admissions management, applications, inquiries",
        "category": "enrollment",
    },

    # Finance — invoicing, fee collection, transactions
    "finance": {
        "label": "Finance",
        "description": "Fee management, invoicing, payments, financial transactions",
        "category": "operations",
    },

    # Human Resources — employees, payroll, leave, training, performance
    "hr": {
        "label": "Human Resources",
        "description": "Employee management, payroll, leave, training, performance reviews",
        "category": "operations",
    },

    # Hostel — dormitory management, room assignments, check-in/out
    "hostel": {
        "label": "Hostel",
        "description": "Hostel management, room assignments, occupancy tracking",
        "category": "operations",
    },

    # Transport — vehicles, routes, staff, student assignments
    "transport": {
        "label": "Transport",
        "description": "Transport management, vehicles, routes, staff, assignments",
        "category": "operations",
    },

    # Library — book inventory, borrowing, returns
    "library": {
        "label": "Library",
        "description": "Library management, book inventory, borrowing, returns",
        "category": "operations",
    },

    # Parent Portal — parent/guardian access to student info, fees
    "parent_portal": {
        "label": "Parent Portal",
        "description": "Parent/guardian portal for student info, fee statements, communications",
        "category": "engagement",
    },
}


def get_module_key(key: str) -> dict:
    """
    Retrieve a module definition by key, or raise KeyError if not found.
    Useful for validation: SchoolModule.module validates against this.
    """
    if key not in MODULES:
        raise KeyError(f"Unknown module: {key}. Valid modules: {list(MODULES.keys())}")
    return MODULES[key]


def get_all_module_keys() -> list:
    """Return all valid module keys for validation/iteration."""
    return list(MODULES.keys())


def is_module_required(key: str) -> bool:
    """Check if a module is required (always enabled, can't be disabled)."""
    return MODULES.get(key, {}).get("required", False)


def enabled_modules_for(tenant, request=None) -> set:
    """
    Return the set of module keys enabled for this tenant.

    Required modules are always included. Optional modules are included only if
    they have a SchoolModule record with enabled=True. A missing optional
    SchoolModule row means the module is disabled (opt-in model).

    For request-scoped caching: if request is provided, the result is cached
    on the request object itself (keyed by tenant.id) to avoid duplicate queries
    in a single request cycle. This guards against stale process-level caches
    and ensures tenant isolation (School B's request can never read School A's
    cached module set).

    Args:
        tenant: A School/tenant instance (from request.tenant via django-tenants)
        request: Optional request object for request-scoped caching

    Returns:
        set[str]: Module keys that are enabled for this tenant
    """
    required = {k for k in MODULES if is_module_required(k)}

    if not tenant:
        return required

    if request is not None:
        cache = getattr(request, "_module_access_cache", None)
        if cache is not None and cache.get("tenant_id") == tenant.id:
            return cache["modules"]

    from core.models import SchoolModule

    enabled = required | set(
        SchoolModule.objects.filter(school=tenant, enabled=True).values_list(
            "module", flat=True
        )
    )

    if request is not None:
        request._module_access_cache = {"tenant_id": tenant.id, "modules": enabled}

    return enabled
