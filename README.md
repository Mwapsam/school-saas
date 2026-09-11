## Project Overview

Pinewood is a Django-based multi-tenant school management system built for managing academic institutions. It uses django-tenants for multi-tenancy, allowing each school to operate as an isolated tenant with their own data and schema.

## Development Commands

### Environment Setup
```bash
# Start all services (Django, PostgreSQL, Redis, Celery)
docker-compose up

# Run database migrations for shared and tenant schemas
python manage.py migrate_schemas --shared
python manage.py migrate_schemas

# Create initial tenant
python manage.py create_initial_tenant

# Start development server
python manage.py runserver 0.0.0.0:8000
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run tests with verbose output
poetry run pytest -v

# Run specific test markers
poetry run pytest -m "not slow"
poetry run pytest -m integration
pytest run pytest -m unit

# Test configuration is in pytest.ini with custom markers for slow, integration, unit, django_db, and external tests
```

### Package Management
```bash
# Install dependencies
poetry install

# Add new dependency
poetry add package-name

# Add development dependency
poetry add --group dev package-name
```

## Architecture

### Multi-Tenant Structure
- **Shared Apps**: Core functionality, tenants, auth, and REST framework
- **Tenant Apps**: Tenant-specific admin functionality
- **Models**: Use `TenantAwareModel` base class for tenant isolation
- **Schema**: Each tenant gets its own PostgreSQL schema

### Core Components

#### Models (`core/models.py`)
- **BaseModel**: UUID primary key, created_at/updated_at timestamps
- **TenantAwareModel**: Extends BaseModel with automatic tenant filtering via custom manager
- **School**: Main tenant model with domain configuration
- **User**: Custom user model with tenant relationships
- **Student/Employee**: Main entity models with comprehensive academic tracking

#### Services (`core/services/`)
- **Service Pattern**: Business logic separated from views
- **TenantAwareService**: Base service class with automatic tenant scoping
- **Logged Operations**: Automatic logging of service operations
- **Exception Hierarchy**: Custom exceptions for validation, not found, duplicates, and business logic

#### API Structure
- **REST Framework**: JSON API endpoints with session authentication
- **Permissions**: Tenant-aware permissions system
- **Pagination**: 20 items per page default
- **Filtering**: Django Filter backend with search and ordering

### Key Models and Relationships

#### Academic Management
- `Course` → `Batch` → `Subject` hierarchy
- `Student` ↔ `BatchStudent` (many-to-many through table)
- `Timetable` links Batch, Subject, Employee, and ClassTiming

#### Admission System
- **Legacy**: `AdmissionApplication` (basic fields)
- **Extended**: `ExtendedAdmissionApplication` with comprehensive fields, document uploads, status tracking, and academic year integration

#### Student Information
- Student personal details, guardian relationships, previous school data
- Academic performance tracking, attendance, exams, assignments
- Health information, emergency contacts, transport/hostel arrangements

#### Staff Management
- Employee hierarchy with departments, positions, categories, grades
- Reporting manager relationships, qualification tracking

## Development Guidelines

### Model Development
- Always extend `TenantAwareModel` for tenant-specific data
- Use UUID fields for primary keys
- Add appropriate database indexes for query performance
- Include proper `__str__` methods for admin interface

### Service Layer
- Implement business logic in service classes inheriting from `TenantAwareService`
- Use `@logged_operation` decorator for auditing
- Handle exceptions with custom exception types
- Always pass tenant context to services

### API Development
- Use DRF viewsets with tenant-aware querysets
- Implement proper permissions checking tenant access
- Follow REST conventions for URL patterns
- Use serializers for data validation and transformation

### Testing Strategy
- Mark tests with appropriate markers (unit, integration, slow, external)
- Use `django_db` marker for database-dependent tests
- Mock external services for unit tests
- Test tenant isolation in multi-tenant features

### Database Considerations
- Migrations run on both shared and tenant schemas
- Use `migrate_schemas` commands for tenant-aware migrations
- Be cautious with schema changes affecting existing tenants
- Test migrations on development tenants before production

## Configuration

### Environment Variables
- `DEBUG`: Development mode (default: False)
- `SECRET_KEY`: Django secret key
- `DATABASE_*`: PostgreSQL connection settings
- `BASE_DOMAIN`: Domain for tenant routing
- `TENANT_USERS_DOMAIN`: Domain for tenant user management

### Key Settings
- **Time Zone**: Africa/Lusaka
- **Authentication**: Custom User model with tenant relationships
- **File Storage**: Media files organized by tenant
- **Logging**: Console + file logging with tenant context

## Common Development Tasks

### Adding New Models
1. Extend `TenantAwareModel` if tenant-specific
2. Add appropriate indexes and relationships
3. Create and run migrations with `migrate_schemas`
4. Add to relevant services with proper validation

### Creating API Endpoints
1. Create serializers in `core/serializers/`
2. Add viewsets to `core/views.py`
3. Configure URL patterns in `core/urls.py` or `core/api_urls.py`
4. Test tenant isolation and permissions

### Service Implementation
1. Inherit from `TenantAwareService`
2. Implement business logic methods with proper error handling
3. Use `@logged_operation` for audit trails
4. Write unit tests with mocked dependencies


# Systems Architecture Expert - Black Box Design

Eskil Steenberg's principles for building large-scale systems that last decades.

## Core Philosophy

**"It's faster to write five lines of code today than to write one line today and then have to edit it in the future."**

Your goal is to create software that:

- Maintains constant developer velocity regardless of project size
- Can be understood and maintained by any developer
- Has modules that can be completely replaced without breaking the system
- Optimizes for human cognitive load, not code cleverness

## Architecture Principles

### 1. Black Box Interfaces

- Every module should be a black box with a clean, documented API
- Implementation details must be completely hidden
- Modules communicate only through well-defined interfaces
- Think: "What does this module DO, not HOW it does it"

### 2. Replaceable Components

- Any module should be rewritable from scratch using only its interface
- If you can't understand a module, it should be easy to replace
- Design APIs that will work even if the implementation changes completely
- Never expose internal implementation details in the interface

### 3. Single Responsibility Modules

- One module = one person should be able to build/maintain it
- Each module should have a single, clear purpose
- Avoid modules that try to do everything
- Split complex functionality into multiple focused modules

### 4. Primitive-First Design

- Identify the core "primitive" data types that flow through your system
- Design everything around these primitives (like Unix files, or graphics polygons)
- Keep primitives simple and consistent
- Build complexity through composition, not complicated primitives

### 5. Format/Interface Design

- Make interfaces as simple as possible to implement
- Prefer one good way over multiple complex options
- Choose semantic meaning over structural complexity
- Design for implementability - others must be abl



## Finance Module
# Core Fee Management:

`FeeCategory` — Top-level fee groups (tuition, transport, etc.)
`FeeParticular` — Line items within a category with amounts and due dates
`FeeDiscount` — Discounts applied to particulars or fees
`FeeWaiver` — Fee waivers for individual students
`FineSlab` — Late-payment fine ladders
`FeeReconciliation` — Fee reconciliation records
`Fee Masters` (Reusable Templates):

`FeeMasterParticular` — Master template for particulars (name, description, default values)
`FeeMasterDiscount` — Master template for discounts
`FeeApplicabilityRule` — Rules for targeting particulars/discounts to specific students

# Invoice & Ledger:

`FinanceFee` — Per-student fee invoice (one row per student × category)
`FinanceFeeItem` — Itemized line items on an invoice (snapshot of particulars + amounts)
`FeeTransaction` — Payment records against fees
`FeeCollection` — Grouping of fees published at one time
`FeeAmountChangeLog` — Audit trail of fee amount changes

# Transaction & Reporting:

`FinanceTransaction` — General finance transactions
`FinanceTransactionCategory` — Categories for general transactions
`FinanceTransactionLedger` — Ledger entries
`FinanceTransactionReceiptRecord` — Receipt tracking
`FinancialYear` — Financial year definitions

# Fine Management:

`Fine` — Individual fine records
`FineRule` — Fine calculation rules
`BatchFeeCategory` — Links batches to fee categories
# Guardian/QuickBooks Integration:

`FamilyInvoice` — Guardian-level consolidated `invoice` (guardian-centric, not per-student)
FamilyInvoiceLine — Line items on family invoices
`QuickBooksIntegration`, `QuickBooksConfiguration`, `QuickBooksRealmMapping` — QB sync setup
`QuickBooksFeeInvoiceSync`, `QuickBooksFeeInvoiceLineSync`, `QuickBooksFeePaymentSync` — QB payment/invoice sync
`QuickBooksCustomerSync` — QB customer (guardian) sync
`QuickBooksSyncLog` — Audit log for QB operations
`CurrencyConfiguration` — Multi-currency settings




# 1. Clean up existing stale rows (per tenant schema)
    docker compose run web python manage.py promote_students --tenant=pinewood --fix-stale
    docker compose run web python manage.py promote_students --tenant=pinewood --fix-stale --execute

# 2. Re-check the backfill — "checked" should now land near 500-600, not 1435
    docker compose run web python manage.py sync_fee_collection_enrollment --dry-run

# 3. If that number looks right, apply it for real
    docker compose run web python manage.py sync_fee_collection_enrollment
#   s c h o o l - s a a s  
 