"""CRUD + assignment for RBAC roles (``core.models.Role`` and friends).

All access *decisions* live in :mod:`core.authz.access`; this service only
mutates the underlying rows. Tenant-scoped like every other service here.
"""
from __future__ import annotations

from typing import Any, Iterable

from django.db import transaction
from django.utils.text import slugify

from core.authz.registry import is_valid_codename
from core.models import Role, RolePermission, UserRoleAssignment
from .base import TenantAwareService
from .exceptions import (
    BusinessLogicException,
    DuplicateException,
    NotFoundException,
    ValidationException,
)
from .logging_service import ServiceLogger, logged_operation


class RoleService(TenantAwareService[Role]):
    def __init__(self, tenant):
        super().__init__(Role, tenant)
        self.logger = ServiceLogger("role", tenant)

    # ------------------------------------------------------------------ reads
    def list_roles(self, *, include_inactive: bool = True):
        qs = self.get_base_queryset()
        if not include_inactive:
            qs = qs.filter(is_active=True)
        return qs.order_by("name")

    def get_role(self, role_id: Any) -> Role:
        return self.get_by_id(role_id)

    def roles_for_user(self, user_id):
        return (
            self.get_base_queryset()
            .filter(
                is_active=True,
                assignments__user_id=user_id,
                assignments__is_active=True,
            )
            .distinct()
            .order_by("name")
        )

    # --------------------------------------------------------------- mutations
    @logged_operation(action="create", resource_type="role", log_result=True)
    def create_role(self, name: str, *, description: str = "", codenames: Iterable[str] = (), user=None) -> Role:
        name = (name or "").strip()
        if not name:
            raise ValidationException("Role name is required", details={"name": ["This field is required"]})
        slug = slugify(name)
        if self.exists(slug=slug):
            raise DuplicateException(f"A role named '{name}' already exists", details={"name": [f"'{name}' already exists"]})

        with transaction.atomic():
            role = self.create(name=name, slug=slug, description=description or "", is_system=False)
            self._replace_permissions(role, codenames)
        return role

    @logged_operation(action="update", resource_type="role")
    def update_role(self, role_id: Any, *, name: str = None, description: str = None, is_active: bool = None, user=None) -> Role:
        role = self.get_by_id(role_id)
        data = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationException("Role name is required", details={"name": ["This field is required"]})
            if role.is_system and name != role.name:
                raise BusinessLogicException("A system role cannot be renamed")
            new_slug = slugify(name)
            if new_slug != role.slug and self.exists(slug=new_slug):
                raise DuplicateException(f"A role named '{name}' already exists", details={"name": [f"'{name}' already exists"]})
            data["name"] = name
            if not role.is_system:
                data["slug"] = new_slug
        if description is not None:
            data["description"] = description
        if is_active is not None:
            if role.is_system and not is_active:
                raise BusinessLogicException("A system role cannot be deactivated")
            data["is_active"] = is_active
        if data:
            role = self.update(role_id, **data)
        return role

    @logged_operation(action="set_permissions", resource_type="role")
    def set_permissions(self, role_id: Any, codenames: Iterable[str], *, user=None) -> Role:
        role = self.get_by_id(role_id)
        with transaction.atomic():
            self._replace_permissions(role, codenames)
        return role

    @logged_operation(action="delete", resource_type="role")
    def delete_role(self, role_id: Any, *, user=None) -> bool:
        role = self.get_by_id(role_id)
        if role.is_system:
            raise BusinessLogicException("System roles cannot be deleted")
        role.delete()
        return True

    # ------------------------------------------------------------- assignments
    @logged_operation(action="assign", resource_type="user_role")
    def assign_role(self, user_id, role_id: Any, *, assigned_by_id=None, user=None) -> UserRoleAssignment:
        role = self.get_by_id(role_id)
        assignment, _ = UserRoleAssignment.objects.get_or_create(
            tenant=self.tenant, user_id=user_id, role=role,
            defaults={"assigned_by_id": assigned_by_id, "is_active": True},
        )
        if not assignment.is_active:
            assignment.is_active = True
            assignment.assigned_by_id = assigned_by_id
            assignment.save(update_fields=["is_active", "assigned_by_id", "updated_at"])
        return assignment

    @logged_operation(action="revoke", resource_type="user_role")
    def revoke_role(self, user_id, role_id: Any, *, user=None) -> bool:
        self._guard_role_management_survives(removing={(str(user_id), str(role_id))})
        updated = UserRoleAssignment.objects.filter(
            tenant=self.tenant, user_id=user_id, role_id=role_id, is_active=True,
        ).update(is_active=False)
        return bool(updated)

    def set_user_roles(self, user_id, role_ids: Iterable[Any], *, assigned_by_id=None, user=None) -> None:
        """Make the user's active assignments exactly ``role_ids`` (within tenant)."""
        wanted = {str(r) for r in role_ids if r}
        current_active = set(
            UserRoleAssignment.objects.filter(
                tenant=self.tenant, user_id=user_id, is_active=True,
            ).values_list("role_id", flat=True)
        )
        removing = {(str(user_id), str(rid)) for rid in current_active if str(rid) not in wanted}
        if removing:
            self._guard_role_management_survives(removing=removing)
        with transaction.atomic():
            current = UserRoleAssignment.objects.filter(tenant=self.tenant, user_id=user_id)
            for a in current:
                should = str(a.role_id) in wanted
                if a.is_active != should:
                    a.is_active = should
                    a.assigned_by_id = assigned_by_id
                    a.save(update_fields=["is_active", "assigned_by_id", "updated_at"])
            existing_ids = {str(a.role_id) for a in current}
            for role_id in wanted - existing_ids:
                if self.exists(id=role_id):
                    UserRoleAssignment.objects.create(
                        tenant=self.tenant, user_id=user_id, role_id=role_id,
                        assigned_by_id=assigned_by_id, is_active=True,
                    )

    # ---------------------------------------------------------------- internal
    def _guard_role_management_survives(self, *, removing: set) -> None:
        """Refuse a change that would leave the tenant with nobody able to
        manage roles: no ``is_root`` user and no active assignment of a role
        carrying ``settings.roles.manage``. ``removing`` is a set of
        ``(user_id_str, role_id_str)`` pairs about to be deactivated."""
        from core.models import User

        if User.objects.filter(is_root=True, tenants=self.tenant).exists():
            return

        manager_role_ids = set(
            RolePermission.objects.filter(
                tenant=self.tenant, codename="settings.roles.manage", role__is_active=True,
            ).values_list("role_id", flat=True)
        )
        if not manager_role_ids:
            return  # nothing to protect (feature not in use yet)

        survivors = {
            (str(u), str(r))
            for u, r in UserRoleAssignment.objects.filter(
                tenant=self.tenant, is_active=True, role_id__in=manager_role_ids,
            ).values_list("user_id", "role_id")
        }
        if survivors - removing:
            return
        raise BusinessLogicException(
            "This change would leave no one able to manage roles. Assign the "
            "role to another user first, or keep a break-glass owner account."
        )

    def _replace_permissions(self, role: Role, codenames: Iterable[str]) -> None:
        clean = {c for c in codenames if is_valid_codename(c)}
        RolePermission.objects.filter(role=role).exclude(codename__in=clean).delete()
        existing = set(RolePermission.objects.filter(role=role).values_list("codename", flat=True))
        RolePermission.objects.bulk_create(
            [RolePermission(tenant=self.tenant, role=role, codename=c) for c in clean - existing]
        )
