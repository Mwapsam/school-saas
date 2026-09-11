"""Tenant-scoped role-based access control (RBAC) for the staff dashboard.

This package is the single black box for authorization. Nothing outside it
should read ``User.is_admin`` directly to make an access decision — call
:func:`core.authz.access.has_permission` (or use the mixins/decorators/DRF
class built on it) instead.

Primitive: a **permission codename** string (see :mod:`core.authz.registry`),
e.g. ``"hr.employee.manage"``. Roles (``core.models.Role``) are bags of
codenames; users are granted roles per tenant (``core.models.UserRoleAssignment``).
``is_admin`` users implicitly hold every codename (superuser bypass).
"""
