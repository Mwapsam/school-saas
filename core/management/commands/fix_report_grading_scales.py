"""
Management command to align report grading scales with the official
Pinewood report-card scales.

The report's "Scholastic Grade Scale" table renders GradeValue rows of the
grading scale linked to each ReportTemplate (description column comes from
GradeValue.code). This command rewrites those rows to the canonical scales:

    SIMPLE_ACADEMIC (Grade 1-2, 4-point):
        A 80  Very Good | B 60 Good | C 50 Satisfactory | D 0 Weak
    FULL_ACADEMIC (Grade 3-7, 5-point):
        A 80  Very Good | B 60 Good | C 50 Satisfactory | D 40 Weak | E 0 Very Weak

Existing GradeValue rows are updated in place (matched by letter name) so
ExamScore.grade_value references stay intact. Rows that are not part of the
canonical scale get min_percentage cleared, which removes them from the
printed table without deleting them.

Usage:
    python manage.py fix_report_grading_scales --all [--dry-run]
    python manage.py fix_report_grading_scales --tenant=<tenant_id> [--dry-run]
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import School, ReportTemplate, GradeValue


CANONICAL_SCALES = {
    'SIMPLE_ACADEMIC': [
        # (name, code/description, min_pct, max_pct, order, passing)
        ('A', 'Very Good',    80, 100, 1, True),
        ('B', 'Good',         60, 79,  2, True),
        ('C', 'Satisfactory', 50, 59,  3, True),
        ('D', 'Weak',         0,  49,  4, False),
    ],
    'FULL_ACADEMIC': [
        ('A', 'Very Good',    80, 100, 1, True),
        ('B', 'Good',         60, 79,  2, True),
        ('C', 'Satisfactory', 50, 59,  3, True),
        ('D', 'Weak',         40, 49,  4, True),
        ('E', 'Very Weak',    0,  39,  5, False),
    ],
}


class Command(BaseCommand):
    help = 'Fix grading scales linked to report templates so reports print the official scale'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Tenant ID to fix')
        parser.add_argument('--all', action='store_true', help='Fix all tenants')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show current vs target values without writing')

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

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written\n"))

        for tenant in tenants:
            self.stdout.write(f"\nTenant: {tenant.name}")
            self.fix_tenant(tenant, dry_run)

        self.stdout.write(self.style.SUCCESS(
            "\nDone." if not dry_run else "\nDry run complete."))

    def fix_tenant(self, tenant, dry_run):
        templates = (ReportTemplate.objects
                     .filter(tenant=tenant, grading_scale__isnull=False)
                     .select_related('grading_scale'))
        if not templates:
            self.stdout.write("  No report templates with a linked grading scale.")
            return

        seen_scales = set()
        for tpl in templates:
            layout = tpl.layout_type
            target = CANONICAL_SCALES.get(layout)
            label = f"  Template '{tpl}' ({layout}) -> scale '{tpl.grading_scale.name}'"
            if target is None:
                self.stdout.write(f"{label}: layout has no printed scale, skipped.")
                continue
            if tpl.grading_scale_id in seen_scales:
                self.stdout.write(f"{label}: scale already processed.")
                continue
            seen_scales.add(tpl.grading_scale_id)
            self.stdout.write(label)
            self.fix_scale(tenant, tpl.grading_scale, target, dry_run)

    @transaction.atomic
    def fix_scale(self, tenant, scale, target, dry_run):
        existing = {gv.name.strip().upper(): gv
                    for gv in GradeValue.objects.filter(tenant=tenant, grading_scale=scale)}
        target_names = set()

        for name, desc, min_pct, max_pct, order, passing in target:
            target_names.add(name)
            gv = existing.get(name)
            wanted = dict(code=desc, min_percentage=min_pct, max_percentage=max_pct,
                          display_order=order, is_passing=passing)
            if gv is None:
                self.stdout.write(f"    CREATE {name}: min={min_pct} desc='{desc}'")
                if not dry_run:
                    GradeValue.objects.create(
                        tenant=tenant, grading_scale=scale, name=name, **wanted)
                continue

            current = dict(code=gv.code, min_percentage=gv.min_percentage,
                           max_percentage=gv.max_percentage,
                           display_order=gv.display_order, is_passing=gv.is_passing)
            diffs = {k: (current[k], v) for k, v in wanted.items()
                     if (float(current[k]) if k.endswith('percentage') and current[k] is not None else current[k])
                     != v}
            if not diffs:
                self.stdout.write(f"    OK     {name}: already correct")
                continue
            pretty = ', '.join(f"{k}: {a!r} -> {b!r}" for k, (a, b) in diffs.items())
            self.stdout.write(f"    UPDATE {name}: {pretty}")
            if not dry_run:
                for k, v in wanted.items():
                    setattr(gv, k, v)
                gv.save(update_fields=list(wanted.keys()) + ['updated_at'])

        # Rows outside the canonical scale: clear min_percentage so they no
        # longer appear in the printed table, but keep the row because
        # ExamScore.grade_value may reference it.
        for name, gv in existing.items():
            if name in target_names:
                continue
            if gv.min_percentage is None:
                self.stdout.write(f"    SKIP   {gv.name}: extra row, already hidden")
                continue
            self.stdout.write(
                f"    HIDE   {gv.name}: extra row, clearing min_percentage "
                f"(was {gv.min_percentage})")
            if not dry_run:
                gv.min_percentage = None
                gv.save(update_fields=['min_percentage', 'updated_at'])
