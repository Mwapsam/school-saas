"""
Management command to repair skills-checklist text that has literal
JS/JSON unicode-escape sequences (e.g. "one\\u002Dto\\u002Done" instead of
"one-to-one", "others\\u0027" instead of "others'") baked into the database
column instead of the real characters.

Confirmed this is corrupted data, not a template/rendering bug: no file in
the repo (seed command, migration, fixture) contains these escape sequences,
so whatever originally wrote SkillItem.description / SkillCategory.name for
the affected rows saved the JS/JSON-escaped string as literal text.

Usage:
    python manage.py fix_skill_item_text --all              # dry-run (default)
    python manage.py fix_skill_item_text --tenant=<id>       # dry-run (default)
    python manage.py fix_skill_item_text --all --apply       # write changes
"""

import re

from django.core.management.base import BaseCommand

from core.models import School, SkillCategory, SkillItem


_ESCAPE_RE = re.compile(r'\\u([0-9a-fA-F]{4})')


def _decode(text):
    if not text or '\\u' not in text:
        return text
    return _ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


class Command(BaseCommand):
    help = 'Decode literal \\uXXXX escape sequences left in skill checklist text'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Tenant ID to fix')
        parser.add_argument('--all', action='store_true', help='Fix all tenants')
        parser.add_argument('--apply', action='store_true',
                             help='Write the decoded text back (default: dry-run only)')

    def handle(self, *args, **options):
        if options['all']:
            tenants = list(School.objects.all())
        elif options['tenant']:
            try:
                tenants = [School.objects.get(id=options['tenant'])]
            except School.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Tenant with ID {options['tenant']} not found"))
                return
        else:
            self.stdout.write(self.style.ERROR("Please specify --tenant=<id> or --all"))
            return

        apply_changes = options['apply']
        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                "DRY RUN — no changes will be written. Pass --apply to save.\n"))

        total_changed = 0
        for tenant in tenants:
            self.stdout.write(f"\nTenant: {tenant.name}")
            total_changed += self.fix_tenant(tenant, apply_changes)

        self.stdout.write(self.style.SUCCESS(
            f"\n{'Applied' if apply_changes else 'Would change'} {total_changed} row(s)."))

    def fix_tenant(self, tenant, apply_changes):
        changed = 0

        for item in SkillItem.objects.filter(tenant=tenant):
            fixed = _decode(item.description)
            if fixed != item.description:
                self.stdout.write(
                    f"  SkillItem {item.id}: {item.description!r} -> {fixed!r}")
                changed += 1
                if apply_changes:
                    item.description = fixed
                    item.save(update_fields=['description', 'updated_at'])

        for cat in SkillCategory.objects.filter(tenant=tenant):
            fixed = _decode(cat.name)
            if fixed != cat.name:
                self.stdout.write(f"  SkillCategory {cat.id}: {cat.name!r} -> {fixed!r}")
                changed += 1
                if apply_changes:
                    cat.name = fixed
                    cat.save(update_fields=['name', 'updated_at'])

        if not changed:
            self.stdout.write("  No corrupted skill text found.")

        return changed
