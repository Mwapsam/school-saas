# Fedena to Pinewood Data Transformation

This directory contains scripts for transforming legacy Fedena data to the modern Pinewood system.

## Overview

The transformation process maps 719 Fedena MySQL tables to Pinewood's ~85 Django models with:
- **Field mapping**: Converts field names and data types
- **UUID conversion**: Transforms integer IDs to UUIDs with consistent mapping
- **Tenant awareness**: Adds tenant context for multi-tenancy
- **Data cleaning**: Handles MySQL to PostgreSQL conversion
- **Dependency management**: Processes tables in correct order

## Prerequisites

1. **Dependencies**: Install required packages
   ```bash
   poetry add psycopg2-binary python-dotenv
   ```

2. **Database**: Ensure Pinewood PostgreSQL is running
   ```bash
   docker-compose up db
   ```

3. **Migrations**: Run Django migrations first
   ```bash
   poetry run python manage.py migrate_schemas --shared
   poetry run python manage.py migrate_schemas
   ```

4. **Tenant**: Get your tenant ID
   ```bash
   # Create tenant if needed
   poetry run python manage.py create_initial_tenant

   # List existing tenants
   poetry run python manage.py shell -c "from core.models import School; print([(s.id, s.name) for s in School.objects.all()])"
   ```

## Usage

### 1. Dry Run (Recommended First)
Test the transformation without making changes:
```bash
python data_migration/fedena_to_pinewood_transformer.py \
  --dry-run \
  --tenant-id "your-tenant-uuid-here"
```

### 2. Transform Specific Table
Process one table to test:
```bash
python data_migration/fedena_to_pinewood_transformer.py \
  --table academic_years \
  --tenant-id "your-tenant-uuid-here"
```

### 3. Transform All Data
Process all configured tables:
```bash
python data_migration/fedena_to_pinewood_transformer.py \
  --tenant-id "your-tenant-uuid-here"
```

## Supported Table Mappings

| Fedena Table | Pinewood Model | Key Features |
|--------------|----------------|--------------|
| `academic_years` | `core_academicyear` | Basic academic year info |
| `courses` | `core_course` | Course/class definitions |
| `batches` | `core_batch` | Class sections with academic year |
| `students` | `core_student` | Student personal information |
| `employees` | `core_employee` | Staff information |
| `employee_departments` | `core_employeedepartment` | Department structure |
| `employee_positions` | `core_employeeposition` | Job positions |
| `employee_categories` | `core_employeecategory` | Staff categories |
| `employee_grades` | `core_employeegrade` | Staff grades/levels |
| `student_categories` | `core_studentcategory` | Student classifications |
| `subjects` | `core_subject` | Subject/course offerings |

## Transformation Features

### ID Mapping
- Converts Fedena integer IDs to deterministic UUIDs
- Maintains referential integrity across tables
- Stores mapping for foreign key relationships

### Data Type Conversion
- `tinyint(1)` → `BOOLEAN`
- `int(11)` → `INTEGER` → `UUID` (for IDs)
- `varchar(255)` → `VARCHAR(255)`
- `datetime` → `TIMESTAMP`
- `date` → `DATE`

### Field Mappings Examples
```python
# Academic Years
fedena.name → pinewood.name
fedena.start_date → pinewood.start_date
fedena.is_active → pinewood.is_active (converted from tinyint)

# Students
fedena.admission_no → pinewood.admission_no
fedena.first_name → pinewood.first_name
fedena.date_of_birth → pinewood.date_of_birth

# Employees
fedena.employee_number → pinewood.employee_number
fedena.employee_department_id → pinewood.department_id (UUID conversion)
```

## Processing Order

Tables are processed in dependency order:
1. **Reference tables**: `employee_departments`, `employee_positions`, etc.
2. **Academic structure**: `academic_years`, `courses`
3. **Classes**: `batches`, `subjects`
4. **People**: `students`, `employees`
5. **Relationships**: `batch_students`, etc.

## Error Handling

The script provides detailed error reporting:
- **Field mapping errors**: Missing or invalid field transformations
- **Data type errors**: Invalid data format conversions
- **Foreign key errors**: Referenced records not found
- **Database errors**: Connection or SQL execution issues

## Extending Mappings

To add new table mappings, edit `FedenaTableMapping.FIELD_MAPPINGS` in the transformer script:

```python
'new_fedena_table': {
    'target_model': 'core_newmodel',
    'fields': {
        'fedena_field': {'target': 'pinewood_field'},
        'fedena_id': {'target': 'id', 'transform': 'fedena_id_to_uuid'},
        'fedena_bool': {'target': 'is_active', 'transform': 'mysql_bool_to_pg'},
    },
    'tenant_field': True,
    'dependencies': ['other_tables'],
    'filters': ['is_deleted = 0']
}
```

## Verification

After transformation, verify data integrity:

```sql
-- Check record counts
SELECT 'academic_years' as table_name, COUNT(*) as count FROM core_academicyear
UNION ALL
SELECT 'courses', COUNT(*) FROM core_course
UNION ALL
SELECT 'students', COUNT(*) FROM core_student;

-- Check foreign key integrity
SELECT s.first_name, s.last_name, b.name as batch_name
FROM core_student s
LEFT JOIN core_batch b ON s.batch_id = b.id
WHERE s.batch_id IS NOT NULL
LIMIT 10;
```

## Troubleshooting

### Common Issues

1. **"Table not found in mapping"**: Add table configuration to `FIELD_MAPPINGS`
2. **"Foreign key constraint"**: Process dependency tables first
3. **"UUID format error"**: Check ID transformation logic
4. **"Tenant not found"**: Verify tenant ID exists in database

### Debug Mode
Add verbose logging by modifying the script:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Manual Data Review
Check specific records:
```bash
# Before transformation (Fedena data)
grep -A 5 "INSERT INTO \`students\`" data_migration/fedena_pinewood.sql | head -20

# After transformation (Pinewood data)
poetry run python manage.py shell -c "from core.models import Student; print(Student.objects.first().__dict__)"
```

## Performance Notes

- **Large datasets**: Process tables individually during off-peak hours
- **Memory usage**: Script loads full table data into memory
- **Database locks**: Use transactions for consistency
- **Batch processing**: Consider chunking for very large tables (>100k records)

For large datasets, consider splitting the process:
```bash
# Process in smaller batches
python transformer.py --table students --tenant-id uuid
python transformer.py --table employees --tenant-id uuid
# etc.
```