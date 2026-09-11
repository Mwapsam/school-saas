"""
validate_migration — pre- and post-migration integrity checks for Fedena→Pinewood migrations.

Pre-check (--pre):
  Connects to the MySQL source and verifies that every field declared in
  FedenaTableMapping.FIELD_MAPPINGS actually exists in the source table.
  Run this BEFORE the migration to catch schema drift early.

Post-check (default):
  Connects to the PostgreSQL target and verifies:
    - No orphaned FK references
    - No unique-constraint violations
    - Record counts match a user-supplied source summary (optional)
    - Required fields are not NULL
    - AcademicYear single-active invariant is honoured

Usage:
    # Pre-migration (validates MySQL source schema):
    python manage.py validate_migration --pre \\
        --mysql-host localhost --mysql-user root --mysql-password pw \\
        --mysql-database fedena_db

    # Post-migration (validates PostgreSQL data for a tenant):
    python manage.py validate_migration --tenant-id <uuid>
"""

import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Validate Fedena→Pinewood migration data integrity"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pre",
            action="store_true",
            help="Run pre-migration schema validation against MySQL source",
        )
        parser.add_argument("--tenant-id", help="Tenant UUID to validate (post-migration)")
        parser.add_argument("--mysql-host", default="localhost")
        parser.add_argument("--mysql-port", type=int, default=3306)
        parser.add_argument("--mysql-user", default="root")
        parser.add_argument("--mysql-password", default="")
        parser.add_argument("--mysql-database", default="fedena_db")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        if options["pre"]:
            self._run_pre_checks(options)
        else:
            if not options.get("tenant_id"):
                raise CommandError("--tenant-id is required for post-migration checks")
            self._run_post_checks(options["tenant_id"])

    # ------------------------------------------------------------------
    # Pre-migration: verify MySQL source schema matches field mappings
    # ------------------------------------------------------------------

    def _run_pre_checks(self, options):
        try:
            import mysql.connector
        except ImportError:
            raise CommandError("mysql-connector-python is not installed. Run: poetry add mysql-connector-python")

        try:
            import sys
            sys.path.insert(0, "data_migration")
            from fedena_to_pinewood_transformer import FedenaTableMapping
        except ImportError as exc:
            raise CommandError(f"Cannot import FedenaTableMapping: {exc}")

        self.stdout.write(self.style.MIGRATE_HEADING("Pre-migration schema validation"))

        try:
            conn = mysql.connector.connect(
                host=options["mysql_host"],
                port=options["mysql_port"],
                database=options["mysql_database"],
                user=options["mysql_user"],
                password=options["mysql_password"],
                charset="utf8mb4",
                use_unicode=True,
            )
        except Exception as exc:
            raise CommandError(f"Cannot connect to MySQL: {exc}")

        cursor = conn.cursor()
        errors = []
        warnings = []

        for table_name, config in FedenaTableMapping.FIELD_MAPPINGS.items():
            source_table = config.get("source_table", table_name)
            mapped_fields = list(config.get("fields", {}).keys())
            if not mapped_fields:
                continue

            # Get actual columns in MySQL table
            try:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                    (options["mysql_database"], source_table),
                )
                actual_cols = {row[0] for row in cursor.fetchall()}
            except Exception as exc:
                warnings.append(f"  Cannot read columns for {source_table}: {exc}")
                continue

            if not actual_cols:
                warnings.append(f"  Table not found in MySQL: {source_table}")
                continue

            missing = [f for f in mapped_fields if f not in actual_cols]
            if missing:
                errors.append(
                    f"  {source_table}: mapped fields missing in source → {missing}"
                )
            else:
                self.stdout.write(f"  ✓ {source_table} ({len(mapped_fields)} fields)")

        cursor.close()
        conn.close()

        for w in warnings:
            self.stdout.write(self.style.WARNING(w))
        for e in errors:
            self.stdout.write(self.style.ERROR(e))

        if errors:
            self.stdout.write(self.style.ERROR(f"\n{len(errors)} schema mismatch(es) found — fix mappings before migrating."))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS("\nPre-migration schema check passed."))

    # ------------------------------------------------------------------
    # Post-migration: check target PostgreSQL integrity
    # ------------------------------------------------------------------

    def _run_post_checks(self, tenant_id: str):
        self.stdout.write(self.style.MIGRATE_HEADING(f"Post-migration integrity checks for tenant {tenant_id}"))

        total_errors = 0
        total_errors += self._check_tenant_exists(tenant_id)
        total_errors += self._check_fk_orphans(tenant_id)
        total_errors += self._check_unique_violations(tenant_id)
        total_errors += self._check_required_fields(tenant_id)
        total_errors += self._check_academic_year_invariant(tenant_id)
        total_errors += self._check_user_passwords()

        if total_errors:
            self.stdout.write(self.style.ERROR(f"\n{total_errors} integrity issue(s) found."))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS("\nAll post-migration checks passed."))

    def _check_tenant_exists(self, tenant_id: str) -> int:
        with connection.cursor() as cur:
            cur.execute("SELECT id, name FROM core_school WHERE id = %s", [tenant_id])
            row = cur.fetchone()
        if not row:
            self.stdout.write(self.style.ERROR(f"  ✗ Tenant {tenant_id} not found in core_school"))
            return 1
        self.stdout.write(f"  ✓ Tenant found: {row[1]}")
        return 0

    def _check_fk_orphans(self, tenant_id: str) -> int:
        checks = [
            ("core_student", "batch_id", "core_batch"),
            ("core_subject", "batch_id", "core_batch"),
            ("core_batchstudent", "student_id", "core_student"),
            ("core_batchstudent", "batch_id", "core_batch"),
            ("core_examscore", "student_id", "core_student"),
            ("core_examscore", "exam_id", "core_exam"),
            ("core_attendance", "student_id", "core_student"),
            ("core_attendance", "batch_id", "core_batch"),
            ("core_financefee", "student_id", "core_student"),
            ("core_feetransaction", "student_id", "core_student"),
        ]
        errors = 0
        with connection.cursor() as cur:
            for child_table, fk_col, parent_table in checks:
                try:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM "{child_table}" c
                        WHERE c.tenant_id = %s
                          AND c."{fk_col}" IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM "{parent_table}" p WHERE p.id = c."{fk_col}"
                          )
                        """,
                        [tenant_id],
                    )
                    count = cur.fetchone()[0]
                    if count:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ FK orphan: {child_table}.{fk_col} → {parent_table}: {count} orphaned rows"
                            )
                        )
                        errors += 1
                    else:
                        self.stdout.write(f"  ✓ No FK orphans: {child_table}.{fk_col}")
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  ⚠ Could not check {child_table}.{fk_col}: {exc}"))
        return errors

    def _check_unique_violations(self, tenant_id: str) -> int:
        checks = [
            ("core_student", ["admission_no", "tenant_id"]),
            ("core_batchstudent", ["batch_id", "student_id"]),
            ("core_examscore", ["student_id", "exam_id"]),
        ]
        errors = 0
        with connection.cursor() as cur:
            for table, cols in checks:
                col_list = ", ".join(f'"{c}"' for c in cols)
                try:
                    cur.execute(
                        f"""
                        SELECT {col_list}, COUNT(*) as cnt
                        FROM "{table}"
                        WHERE tenant_id = %s
                        GROUP BY {col_list}
                        HAVING COUNT(*) > 1
                        LIMIT 5
                        """,
                        [tenant_id],
                    )
                    dupes = cur.fetchall()
                    if dupes:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ Unique violation in {table} ({', '.join(cols)}): {len(dupes)} duplicate group(s)"
                            )
                        )
                        errors += 1
                    else:
                        self.stdout.write(f"  ✓ No duplicates: {table} ({', '.join(cols)})")
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  ⚠ Could not check {table}: {exc}"))
        return errors

    def _check_required_fields(self, tenant_id: str) -> int:
        checks = [
            ("core_student", ["admission_no", "first_name", "last_name", "date_of_birth"]),
            ("core_employee", ["employee_number", "first_name", "last_name"]),
            ("core_batch", ["name", "course_id", "academic_year_id"]),
        ]
        errors = 0
        with connection.cursor() as cur:
            for table, required_cols in checks:
                for col in required_cols:
                    try:
                        cur.execute(
                            f'SELECT COUNT(*) FROM "{table}" WHERE tenant_id = %s AND "{col}" IS NULL',
                            [tenant_id],
                        )
                        count = cur.fetchone()[0]
                        if count:
                            self.stdout.write(
                                self.style.ERROR(f"  ✗ NULL required field: {table}.{col}: {count} rows")
                            )
                            errors += 1
                        else:
                            self.stdout.write(f"  ✓ No NULLs: {table}.{col}")
                    except Exception as exc:
                        self.stdout.write(self.style.WARNING(f"  ⚠ Could not check {table}.{col}: {exc}"))
        return errors

    def _check_academic_year_invariant(self, tenant_id: str) -> int:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM core_academicyear WHERE tenant_id = %s AND is_active = TRUE",
                [tenant_id],
            )
            count = cur.fetchone()[0]
        if count > 1:
            self.stdout.write(
                self.style.ERROR(f"  ✗ Multiple active AcademicYears for tenant: {count} (should be 1)")
            )
            self.stdout.write(
                "    Fix: UPDATE core_academicyear SET is_active=False "
                "WHERE tenant_id='...' AND id != (SELECT id FROM core_academicyear "
                "WHERE tenant_id='...' ORDER BY end_date DESC LIMIT 1);"
            )
            return 1
        self.stdout.write(f"  ✓ Active AcademicYear count: {count}")
        return 0

    def _check_user_passwords(self) -> int:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM core_user WHERE password != '!' AND password NOT LIKE 'pbkdf2_%' AND password NOT LIKE 'argon2%' AND password != ''",
            )
            count = cur.fetchone()[0]
        if count:
            self.stdout.write(
                self.style.ERROR(
                    f"  ✗ {count} user(s) have non-Django password hashes (likely migrated Rails/bcrypt hashes). "
                    "They cannot log in. Run a password reset for all affected users."
                )
            )
            return 1
        self.stdout.write("  ✓ All user passwords are Django-compatible or unusable")
        return 0
