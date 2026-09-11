# Archive — One-Off Migration & Legacy Data

This directory contains school-specific and one-off migration tooling that should **not be shipped** with the platform codebase.

## Contents

- **data_migration/** — Fedena → current schema migration scripts (one-off, Pinewood-specific)
  - `migrate_fedena_data.py` — Fedena DB → current schema transformer
  - `fedena_to_pinewood_transformer.py` — Transformation logic
  - `fedena_pinewood.sql` — Legacy Fedena database dump

- **pinewood.sql** — Historical Pinewood database snapshot

## Usage

These files are kept for operational reference only and are not executed as part of the deployment or test suite. If a new school needs to migrate from Fedena, these tools can be adapted as a starting point, but they are not guaranteed to work with the current schema and should be carefully reviewed.

## Not Shipped

The `archive/` directory is excluded from Docker builds and production deployments. It exists only in the development repository for historical reference.

## Future: Data Migrations

When a new school is provisioned, use the management commands:
```bash
python manage.py provision_tenant --schema-name new_school --name "New School" --domain-name new-school.example.com
python manage.py provision_school_modules --school-code <code>
```

These commands seed fresh database schemas, not migrate from legacy systems.
