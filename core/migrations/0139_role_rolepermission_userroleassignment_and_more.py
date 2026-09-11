# RBAC foundation: Role / RolePermission / UserRoleAssignment + User.is_root

import django.db.models.deletion
import uuid
from django.db import migrations, models


def seed_and_grandfather(apps, schema_editor):
    """Seed per-tenant system roles, then preserve today's behaviour with zero
    lockout risk: every existing ``is_admin`` user is marked ``is_root`` (full
    bypass) *and* granted the ``super-admin`` role. Operators then dial specific
    staff down by clearing ``is_root`` and assigning a narrower role.

    Core models are row-level multi-tenant (all in the public schema), so this
    runs once, on the public/shared migration pass, and iterates every School.
    """
    try:
        from core.models import School, User
        from core.management.commands.seed_roles import seed_roles_for_tenant
        from core.services.role_service import RoleService
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[0139] RBAC seed skipped: {exc}")
        return

    admin_users = list(User.objects.filter(is_admin=True))
    User.objects.filter(is_admin=True, is_root=False).update(is_root=True)

    for school in School.objects.all():
        try:
            seed_roles_for_tenant(school)
        except Exception as exc:  # pragma: no cover
            print(f"[0139] seed_roles failed for {school.schema_name}: {exc}")
            continue
        svc = RoleService(school)
        super_admin = svc.get_base_queryset().filter(slug="super-admin").first()
        if super_admin is None:
            continue
        for user in admin_users:
            if user.tenants.filter(id=school.id).exists():
                svc.assign_role(user.id, super_admin.id)


def unseed(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    Role.objects.filter(is_system=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0138_school_fee_note_early_bird_discount_enabled_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_root',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100)),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('is_system', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='core.school')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('codename', models.CharField(max_length=100)),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissions', to='core.role')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='core.school')),
            ],
        ),
        migrations.CreateModel(
            name='UserRoleAssignment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user_id', models.UUIDField(db_index=True)),
                ('assigned_by_id', models.UUIDField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.role')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='core.school')),
            ],
        ),
        migrations.AddIndex(
            model_name='role',
            index=models.Index(fields=['tenant', 'slug'], name='core_role_tenant__180cbf_idx'),
        ),
        migrations.AddIndex(
            model_name='role',
            index=models.Index(fields=['tenant', 'is_active'], name='core_role_tenant__2f085a_idx'),
        ),
        migrations.AddConstraint(
            model_name='role',
            constraint=models.UniqueConstraint(fields=('tenant', 'slug'), name='uniq_role_tenant_slug'),
        ),
        migrations.AddIndex(
            model_name='rolepermission',
            index=models.Index(fields=['tenant', 'codename'], name='core_rolepe_tenant__2479a5_idx'),
        ),
        migrations.AddConstraint(
            model_name='rolepermission',
            constraint=models.UniqueConstraint(fields=('role', 'codename'), name='uniq_rolepermission_role_codename'),
        ),
        migrations.AddIndex(
            model_name='userroleassignment',
            index=models.Index(fields=['tenant', 'user_id', 'is_active'], name='core_userro_tenant__bc93bc_idx'),
        ),
        migrations.AddConstraint(
            model_name='userroleassignment',
            constraint=models.UniqueConstraint(fields=('user_id', 'role'), name='uniq_userroleassignment_user_role'),
        ),
        migrations.RunPython(seed_and_grandfather, unseed),
    ]
