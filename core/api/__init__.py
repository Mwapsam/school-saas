"""
API-first DRF endpoints for the school management platform.

Organized by domain to keep related functionality together and avoid massive single files.
Each domain (students, finance, hr, etc.) gets its own module with serializers and viewsets.

Pattern:
    core/api/
    ├── students.py          # Student/batch/course/subject viewsets + serializers
    ├── academics.py         # Exams, attendance, assessments, reports
    ├── finance.py           # Invoices, fees, transactions
    ├── hr.py                # Employees, payroll, leave, training, etc.
    ├── hostel.py            # Hostel assignments, occupancy
    ├── transport.py         # Routes, vehicles, assignments
    ├── library.py           # Book inventory, borrowing
    ├── admissions.py        # Admission applications
    └── bootstrap.py         # Tenant configuration contract (bootstrap endpoint)

Each module should:
1. Reuse existing services from core/services/ (business logic)
2. Add serializers for request/response
3. Define viewsets with proper permission_classes (ModuleEnabled first)
4. Use drf-spectacular decorators for schema generation

See students.py for a complete reference implementation.
"""
