"""
Fix student names that were incorrectly set to last_name='Student' during migration.

Parses the Fedena MySQL dump, extracts first_name / middle_name / last_name by
admission_no, then bulk-updates the live tenant students.

Usage:
    # Dry run
    python manage.py fix_student_names --tenant=<schema>

    # Apply
    python manage.py fix_student_names --tenant=<schema> --execute
"""

import re
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

SQL_FILE = Path("/app/data_migration/fedena_pinewood.sql")

# Column positions in the students INSERT (0-indexed)
COL_ADMISSION_NO = 1
COL_FIRST_NAME   = 4
COL_MIDDLE_NAME  = 5
COL_LAST_NAME    = 6


def _split_row(row: str) -> list[str]:
    """Split a CSV row respecting single-quoted strings."""
    parts = re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", row)
    return [p.strip().strip("'") for p in parts]


def _parse_names(sql_path: Path) -> dict[str, dict]:
    """Return {admission_no: {first, middle, last}} from the students INSERT block.

    The dump format is:
        INSERT INTO `students` VALUES
        (row1...),
        (row2...),
        ...;
    Each row is on its own line.
    """
    names = {}
    in_block = False
    with open(sql_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()

            if not in_block:
                if "INSERT INTO `students`" in line:
                    in_block = True
                continue

            # Each data line starts with '('
            if not stripped.startswith("("):
                if stripped.startswith("INSERT") or stripped.startswith("CREATE") or stripped.startswith("UNLOCK"):
                    break  # left the students block
                continue

            # Strip leading '(' and trailing '),' or ');'
            raw = stripped.lstrip("(").rstrip(";").rstrip(")").rstrip(",").rstrip(")")
            parts = _split_row(raw)
            if len(parts) <= COL_LAST_NAME:
                continue
            adm = parts[COL_ADMISSION_NO]
            if not adm.startswith("PW"):
                continue
            names[adm] = {
                "first_name":  parts[COL_FIRST_NAME]  or "",
                "middle_name": parts[COL_MIDDLE_NAME] or None,
                "last_name":   parts[COL_LAST_NAME]   or "",
            }

    return names


class Command(BaseCommand):
    help = "Restore correct student names from the Fedena SQL dump."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--execute", action="store_true", default=False)

    def handle(self, *args, **options):
        schema  = options["tenant"]
        execute = options["execute"]

        if not SQL_FILE.exists():
            raise CommandError(f"SQL file not found: {SQL_FILE}")

        if not execute:
            self.stdout.write(self.style.WARNING("DRY RUN — pass --execute to apply\n"))

        self.stdout.write("Parsing SQL file …")
        source = _parse_names(SQL_FILE)
        self.stdout.write(f"Found {len(source):,} student records in SQL file.\n")

        with schema_context(schema):
            self._fix(source, execute)

    def _fix(self, source: dict, execute: bool):
        from core.models import Student

        students = Student.objects.all().only(
            "id", "admission_no", "first_name", "middle_name", "last_name"
        )

        to_update = []
        not_in_source = []

        for s in students:
            data = source.get(s.admission_no)
            if not data:
                not_in_source.append(s.admission_no)
                continue

            changed = False
            if data["first_name"] and s.first_name != data["first_name"]:
                s.first_name = data["first_name"]
                changed = True
            if s.middle_name != data["middle_name"]:
                s.middle_name = data["middle_name"] if data["middle_name"] else None
                changed = True
            if data["last_name"] and s.last_name != data["last_name"]:
                s.last_name = data["last_name"]
                changed = True

            if changed:
                to_update.append(s)

        self.stdout.write(f"Students to update: {len(to_update)}")
        self.stdout.write(f"Students not in source: {len(not_in_source)}")

        if to_update:
            self.stdout.write("\nSample of planned fixes (first 10):")
            for s in to_update[:10]:
                data = source[s.admission_no]
                self.stdout.write(
                    f"  {s.admission_no}: "
                    f"'{s.first_name} {s.last_name}' → "
                    f"'{data['first_name']} {data.get('middle_name') or ''} {data['last_name']}'.strip()"
                )

        if not execute:
            self.stdout.write(self.style.WARNING("\nDry run complete. Pass --execute to apply."))
            return

        updated = Student.objects.bulk_update(to_update, ["first_name", "middle_name", "last_name"])
        self.stdout.write(self.style.SUCCESS(f"\n✓ Updated {updated} student records."))

        if not_in_source:
            self.stdout.write(
                self.style.WARNING(f"⚠ {len(not_in_source)} students had no match in the SQL file:")
            )
            for adm in not_in_source:
                self.stdout.write(f"  {adm}")
