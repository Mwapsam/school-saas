# Generated migration for module access control

from django.db import migrations


def disable_non_required_modules(apps, schema_editor):
    """Set all non-required SchoolModule rows to enabled=False.

    This ensures module access is agreement-based: existing schools that had
    all modules enabled by default now start with only required modules enabled,
    and superusers must explicitly enable each paid module.
    """
    SchoolModule = apps.get_model('core', 'SchoolModule')

    # Only update non-required modules to disabled
    # Required modules (academics) stay enabled
    required_modules = ['academics']

    SchoolModule.objects.exclude(module__in=required_modules).update(enabled=False)


def reverse_disable_non_required_modules(apps, schema_editor):
    """Re-enable all non-required modules (reverse operation)."""
    SchoolModule = apps.get_model('core', 'SchoolModule')
    required_modules = ['academics']
    SchoolModule.objects.exclude(module__in=required_modules).update(enabled=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0165_rename_core_demorea_email_idx_core_demore_email_95c29b_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(disable_non_required_modules, reverse_disable_non_required_modules),
    ]
