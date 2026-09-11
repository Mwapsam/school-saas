"""
Management command to promote students into the active academic year's batches.

Each student's most recent batch determines their target: the section prefix
(everything before the 4-digit year in the batch name) is combined with the
active year to find the equivalent batch, e.g. "A 2024 | GRADE 4" → "A 2025 | GRADE 4".

Promoting a student deactivates their prior-year BatchStudent row (same pattern
as StudentService.transfer_batch() and the bulk transfer view in views.py) so
BatchStudent.is_active=True keeps meaning "currently enrolled" rather than
accumulating one active row per year a student has ever been promoted through.

Usage:
    # Dry run (default) – shows what would happen, writes nothing
    python manage.py promote_students --tenant=<schema>

    # Execute
    python manage.py promote_students --tenant=<schema> --execute

    # One-time cleanup of stale prior-year rows left by earlier runs of this
    # command (before the deactivation fix above existed)
    python manage.py promote_students --tenant=<schema> --fix-stale
    python manage.py promote_students --tenant=<schema> --fix-stale --execute
"""

import re
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context


class Command(BaseCommand):
    help = "Promote students from previous academic year batches into the active year's batches."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant schema name")
        parser.add_argument(
            "--execute",
            action="store_true",
            default=False,
            help="Write changes to the database (omit for dry run)",
        )
        parser.add_argument(
            "--fix-stale",
            action="store_true",
            default=False,
            help="Deactivate stale prior-year BatchStudent rows instead of promoting "
                 "(combine with --execute to write; dry run otherwise)",
        )

    def handle(self, *args, **options):
        from core.models import School

        schema = options["tenant"]
        execute = options["execute"]

        try:
            school = School.objects.get(schema_name=schema)
        except School.DoesNotExist:
            raise CommandError(f"No tenant found with schema_name={schema!r}")

        if not execute:
            self.stdout.write(self.style.WARNING("DRY RUN — pass --execute to apply changes\n"))

        # tenant_context (not schema_context) — schema_context sets
        # connection.tenant to a bare FakeTenant with no `pk`, which silently
        # disables TenantAwareManager's automatic tenant filter, making every
        # unscoped query below span ALL tenants instead of just this one.
        # We also pass `tenant=school` explicitly everywhere as a second,
        # independent guarantee — correctness here must not hinge on that
        # implicit mechanism alone.
        with tenant_context(school):
            if options["fix_stale"]:
                self._fix_stale(school, execute)
            else:
                self._run(school, execute)

    def _section_prefix(self, batch_name):
        """Strip trailing '2023'/'2024'/etc. and any trailing junk from batch name."""
        return re.sub(r"\s*\d{4}.*$", "", batch_name).strip()

    def _run(self, school, execute):
        from core.models import AcademicYear, Batch, BatchStudent, Student

        active_year = AcademicYear.objects.filter(tenant=school, is_active=True).first()
        if not active_year:
            raise CommandError("No active academic year found.")

        self.stdout.write(f"Active year: {active_year.name}\n")

        # Build a lookup: (section_prefix, course_id) → AY2025 Batch
        target_batches = {}
        for b in Batch.objects.filter(
            tenant=school, academic_year=active_year, is_deleted=False
        ).select_related("course"):
            prefix = self._section_prefix(b.name)
            target_batches[(prefix, b.course_id)] = b

        self.stdout.write(f"Target batches in {active_year.name}: {len(target_batches)}\n\n")

        # Students with no active enrollment in the active year
        already_enrolled_ids = set(
            BatchStudent.objects.filter(
                tenant=school, batch__academic_year=active_year, is_active=True
            ).values_list("student_id", flat=True)
        )

        unenrolled = (
            Student.objects.filter(tenant=school, is_active=True)
            .exclude(id__in=already_enrolled_ids)
            .prefetch_related("student_batches__batch__course", "student_batches__batch__academic_year")
        )

        total = unenrolled.count()
        self.stdout.write(f"Students needing promotion: {total}\n\n")

        promoted = []
        no_history = []
        no_target = []

        for student in unenrolled:
            # Most recent batch record (any year)
            last_bs = (
                student.student_batches
                .filter(tenant=school)
                .select_related("batch__course", "batch__academic_year")
                .order_by("-batch__academic_year__start_date", "-created_at")
                .first()
            )

            if last_bs is None:
                no_history.append(student)
                continue

            prefix = self._section_prefix(last_bs.batch.name)
            key = (prefix, last_bs.batch.course_id)
            target_batch = target_batches.get(key)

            if target_batch is None:
                no_target.append((student, last_bs.batch))
                continue

            promoted.append((student, last_bs, target_batch))

        # Report
        self.stdout.write(self.style.SUCCESS(f"✓ Can promote: {len(promoted)}"))
        self.stdout.write(self.style.WARNING(f"⚠ No previous batch history: {len(no_history)}"))
        self.stdout.write(self.style.WARNING(f"⚠ No matching target batch: {len(no_target)}"))

        if no_target:
            self.stdout.write("\nUnmappable students (no matching batch in active year):")
            for student, old_batch in no_target:
                self.stdout.write(
                    f"  {student.first_name} {student.last_name} | "
                    f"last batch: {old_batch.name!r} | course: {old_batch.course.course_name!r}"
                )

        if no_history:
            self.stdout.write("\nStudents with no batch history at all:")
            for student in no_history:
                self.stdout.write(f"  {student.first_name} {student.last_name} ({student.admission_no})")

        if not execute:
            self.stdout.write(self.style.WARNING("\nDry run complete. Pass --execute to apply.\n"))
            if promoted:
                self.stdout.write("\nSample of planned promotions (first 10):")
                for student, last_bs, new_batch in promoted[:10]:
                    old_batch = last_bs.batch
                    self.stdout.write(
                        f"  {student.first_name} {student.last_name}: "
                        f"{old_batch.name!r} ({old_batch.academic_year.name}) "
                        f"→ {new_batch.name!r} ({active_year.name})"
                    )
            return

        # Execute
        created = 0
        deactivated = 0
        for student, last_bs, target_batch in promoted:
            _, was_created = BatchStudent.objects.get_or_create(
                student=student,
                batch=target_batch,
                tenant=school,
                defaults={"is_active": True, "roll_number": None},
            )
            if was_created:
                created += 1

            if last_bs.is_active:
                last_bs.is_active = False
                last_bs.save(update_fields=["is_active"])
                deactivated += 1

        self.stdout.write(self.style.SUCCESS(f"\n✓ Created {created} BatchStudent records in {active_year.name}."))
        if created < len(promoted):
            self.stdout.write(
                self.style.WARNING(f"  {len(promoted) - created} already existed (skipped).")
            )
        self.stdout.write(self.style.SUCCESS(f"✓ Deactivated {deactivated} prior-year enrollment record(s)."))

    def _fix_stale(self, school, execute):
        """One-time cleanup for BatchStudent rows left is_active=True by
        promotion runs that predate the deactivation fix above: for every
        student with more than one active row, keep only the one in their
        most recent academic year and deactivate the rest.
        """
        from collections import Counter
        from django.db.models import Count
        from core.models import AcademicYear, BatchStudent

        active_year = AcademicYear.objects.filter(tenant=school, is_active=True).first()

        self.stdout.write("Scanning for students with multiple active BatchStudent rows across years...\n")

        dupe_student_ids = list(
            BatchStudent.objects.filter(tenant=school, is_active=True)
            .values("student_id")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .values_list("student_id", flat=True)
        )

        self.stdout.write(f"Students with >1 active enrollment: {len(dupe_student_ids)}\n")

        if not dupe_student_ids:
            self.stdout.write(self.style.SUCCESS("No stale rows found."))
            return

        deactivated = 0
        affected_students = 0
        kept_year_counts = Counter()
        stale_year_counts = Counter()
        kept_not_in_active_year = 0

        for student_id in dupe_student_ids:
            rows = list(
                BatchStudent.objects.filter(tenant=school, student_id=student_id, is_active=True)
                .select_related("batch__academic_year")
                .order_by("-batch__academic_year__start_date", "-created_at")
            )
            kept = rows[0]
            stale = rows[1:]  # rows[0] (most recent year) is kept as-is
            kept_year_counts[kept.batch.academic_year.name] += 1
            if active_year and kept.batch.academic_year_id != active_year.id:
                kept_not_in_active_year += 1
            if not stale:
                continue
            affected_students += 1
            for bs in stale:
                stale_year_counts[bs.batch.academic_year.name] += 1
                if execute:
                    bs.is_active = False
                    bs.save(update_fields=["is_active"])
                deactivated += 1

        self.stdout.write("\nBreakdown of the row each student KEEPS (their most recent year), by year:")
        for year_name, count in sorted(kept_year_counts.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"  {year_name}: {count}")
        if active_year:
            self.stdout.write(
                f"\n{kept_not_in_active_year} of these {len(dupe_student_ids)} student(s) have NO row in the "
                f"current active year ({active_year.name}) at all — they are not part of this year's roster; "
                f"their kept row is just the most recent one they have, from an earlier year."
            )

        self.stdout.write("\nBreakdown of rows being deactivated, by the year they belong to:")
        for year_name, count in sorted(stale_year_counts.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"  {year_name}: {count}")

        verb = "Deactivated" if execute else "Would deactivate"
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ {verb} {deactivated} stale BatchStudent row(s) across {affected_students} student(s)."
        ))
        if not execute:
            self.stdout.write(self.style.WARNING("\nDry run complete. Pass --execute to apply.\n"))
