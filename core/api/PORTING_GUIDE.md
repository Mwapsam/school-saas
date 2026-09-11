# API Porting Guide: Template Routes → DRF ViewSets

This guide explains how to port the remaining ~140 Django template routes to DRF API endpoints.

## Quick Reference

**Reference Implementation**: `core/api/students.py`
- Shows the complete pattern for a domain module
- Includes serializers, viewsets, permission classes, and drf-spectacular decorators

**Bootstrap Endpoint**: `core/api/bootstrap.py`
- Tenant configuration contract for Next.js BFF
- Returns branding, user info, capabilities, terminology, modules

**URL Registration**: `core/api_urls.py`
- ViewSets registered with DefaultRouter
- Endpoints mounted under `/api/v1/`
- drf-spectacular schema at `/api/v1/schema/`

---

## Architecture Principles

### 1. **Reuse Existing Services**
Business logic is already split into `core/services/`. Don't duplicate it in viewsets.

```python
# ❌ Don't do this (duplicates business logic)
class InvoiceViewSet(viewsets.ModelViewSet):
    def create(self, request, *args, **kwargs):
        # ... inline invoice creation logic ...

# ✅ Do this (uses service layer)
class InvoiceViewSet(viewsets.ModelViewSet):
    def create(self, request, *args, **kwargs):
        service = FinanceService(tenant=request.tenant)
        invoice = service.create_invoice(serializer.validated_data)
        return Response(InvoiceSerializer(invoice).data)
```

### 2. **Permission Stack: Module First**
Permission classes run in order. Module enablement must be checked **before** business permissions:

```python
permission_classes = [
    IsAuthenticated,
    ModuleEnabled("finance"),  # ← BEFORE business permission
    HasPermission("finance.invoices.manage"),
]
```

Why? If the Finance module is disabled for a school, return 403 immediately. Don't let the user's permission matter.

### 3. **Serializers for Contracts**
Serializers define the request/response contract. They handle validation and transformation.

```python
class InvoiceSerializer(serializers.ModelSerializer):
    # Nested fields for common lookups
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = ['id', 'student', 'student_name', 'amount', 'status', ...]
        read_only_fields = ['id', 'created_at', 'updated_at']
```

### 4. **Capabilities, Not Roles**
Frontend checks capabilities (permission strings), not role names. Backend enforces via `HasPermission`.

```python
# ❌ Don't require role-based checks in frontend
if user.role == "admin":
    show_edit_button()

# ✅ Frontend checks capability
if "finance.invoices.manage" in capabilities:
    show_edit_button()

# Backend enforces it
@permission_classes([HasPermission("finance.invoices.manage")])
```

### 5. **Documentation via drf-spectacular**
Add decorators to viewset methods for OpenAPI schema generation:

```python
@extend_schema(
    description="List all invoices (paginated, filterable)",
    parameters=[OpenApiParameter(name='status', description='Filter by status')],
)
def list(self, request, *args, **kwargs):
    return super().list(request, *args, **kwargs)
```

---

## Step-by-Step Porting Process

### Step 1: Identify the Domain and Routes

List all template routes for one domain (e.g., Finance):
```bash
grep -n "finance" core/urls.py core/view_modules/finance*.py
```

Example Finance routes:
- `/finance/invoices/` — list invoices
- `/finance/invoices/<id>/` — retrieve one
- `/finance/invoices/create/` — create
- `/finance/invoices/<id>/edit/` — update
- `/finance/invoices/<id>/delete/` — delete

### Step 2: Create Serializers

In `core/api/finance.py`, define serializers for each model:

```python
from rest_framework import serializers
from core.models import Invoice, FeeCategory

class InvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = ['id', 'student', 'student_name', 'amount', 'due_date', 'status', ...]
        read_only_fields = ['id', 'created_at']

class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ['id', 'name', 'description', 'amount', ...]
```

### Step 3: Create ViewSets

```python
from rest_framework import viewsets
from core.authz.drf import ModuleEnabled, HasPermission

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("finance"),
        HasPermission(read="finance.invoices.view", write="finance.invoices.manage"),
    ]
    module = "finance"  # For ModuleEnabled permission
    filterset_fields = ['status', 'student', 'due_date']
    search_fields = ['student__full_name', 'invoice_number']
    ordering_fields = ['due_date', 'amount']

    def get_queryset(self):
        return super().get_queryset().select_related('student')
```

### Step 4: Register ViewSet in Router

In `core/api_urls.py`, add to the router:

```python
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'fee-categories', FeeCategoryViewSet, basename='fee-category')
```

This auto-generates:
- `GET /api/v1/invoices/` — list
- `POST /api/v1/invoices/` — create
- `GET /api/v1/invoices/{id}/` — retrieve
- `PUT /api/v1/invoices/{id}/` — update
- `PATCH /api/v1/invoices/{id}/` — partial update
- `DELETE /api/v1/invoices/{id}/` — delete

### Step 5: Add drf-spectacular Decorators (Optional but Recommended)

```python
from drf_spectacular.utils import extend_schema

@extend_schema(
    description="List all invoices (paginated, filterable by status)",
    parameters=[
        OpenApiParameter(name='status', enum=['draft', 'sent', 'paid']),
        OpenApiParameter(name='search', description='Search by invoice number or student name'),
    ],
)
def list(self, request, *args, **kwargs):
    return super().list(request, *args, **kwargs)
```

### Step 6: Test

```python
# tests/test_invoice_api_unit.py
import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
class TestInvoiceAPI:
    def test_list_invoices(self, client, school):
        user = create_user(school=school)
        client.force_authenticate(user)
        response = client.get('/api/v1/invoices/')
        assert response.status_code == 200

    def test_module_disabled(self, client, school):
        # Disable finance module
        SchoolModule.objects.filter(school=school, module='finance').update(enabled=False)
        
        user = create_user(school=school)
        client.force_authenticate(user)
        response = client.get('/api/v1/invoices/')
        assert response.status_code == 403  # Module disabled
```

### Step 7: Delete Old Template

Once API endpoint is tested and working:
1. Verify in Next.js (when frontend exists) that it calls the new `/api/v1/invoices/` endpoint
2. Delete old template from `core/views.py` or `core/view_modules/finance*.py`
3. Remove URL pattern from `core/urls.py`

---

## Domains to Port (Priority Order)

### Tier 1: Core (Already Ported)
- ✅ **Students/Academics** — `core/api/students.py` (reference implementation)

### Tier 2: High Priority (Reuse Existing Services)
- **Finance** → `core/api/finance.py`
  - Services: `FinanceService`, `FeeService`, etc. (already exist in `core/services/`)
  - Models: `Invoice`, `FeeCategory`, `FinanceTransaction`, `FeeDiscount`, `FineSlab`
  - Viewsets: `InvoiceViewSet`, `FeeCategoryViewSet`, `TransactionViewSet`, etc.

- **HR** → `core/api/hr.py`
  - Services: `HRService`, `PayrollService`, `LeaveService`, etc. (9 view modules → single domain)
  - Models: `Employee`, `PayrollRun`, `LeaveRequest`, `Training`, `Performance`, etc.
  - Viewsets: One per sub-domain (employees, payroll, leave, training, performance, etc.)

- **Admissions** → `core/api/admissions.py`
  - Services: `AdmissionService` (already exists)
  - Models: `AdmissionApplication`, `AdmissionInquiry`, etc.
  - Viewsets: `AdmissionApplicationViewSet`, `AdmissionInquiryViewSet`, etc.

### Tier 3: Operations
- **Hostel** → `core/api/hostel.py`
  - Services: `HostelService`
  - Models: `HostelAssignment`, `HostelRoom`, etc.

- **Transport** → `core/api/transport.py`
  - Services: `TransportService`
  - Models: `Vehicle`, `Route`, `TransportAssignment`, etc.

- **Library** → `core/api/library.py`
  - Services: `LibraryService`
  - Models: `Book`, `BookBorrow`, `BookReturn`, etc.

---

## Common Patterns

### Filtering & Search
```python
class InvoiceViewSet(viewsets.ModelViewSet):
    filterset_fields = ['status', 'student', 'due_date']  # Exact match filters
    search_fields = ['invoice_number', 'student__full_name']  # Full-text search
    ordering_fields = ['created_at', 'due_date', 'amount']  # Sortable fields
```

### Nested Resources
```python
# List invoices for a specific student
# GET /api/v1/invoices/?student=<student-id>

# Or custom action (if you want explicit endpoint):
class InvoiceViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """List line items for this invoice."""
        invoice = self.get_object()
        items = invoice.items.all()
        return Response(InvoiceItemSerializer(items, many=True).data)

# GET /api/v1/invoices/<id>/items/
```

### Bulk Operations
```python
@action(detail=False, methods=['post'])
def bulk_mark_paid(self, request):
    """Mark multiple invoices as paid."""
    invoice_ids = request.data.get('ids', [])
    count = Invoice.objects.filter(id__in=invoice_ids, tenant=request.tenant).update(status='paid')
    return Response({'updated': count})

# POST /api/v1/invoices/bulk_mark_paid/
# Body: {"ids": ["uuid1", "uuid2"]}
```

---

## Testing Checklist

For each domain/endpoint:

- [ ] Endpoint exists and returns 200 for list/retrieve
- [ ] Pagination works (`?page=1&limit=50`)
- [ ] Filtering works (`?status=paid`)
- [ ] Search works (`?search=john`)
- [ ] Sorting works (`?ordering=-due_date`)
- [ ] Create/update/delete work (POST/PUT/PATCH/DELETE)
- [ ] Module disabled returns 403
- [ ] User without permission returns 403
- [ ] Authenticated user can access
- [ ] Unauthenticated user gets 401
- [ ] Tenant isolation: can't access other tenant's data
- [ ] OpenAPI schema is correct (if drf-spectacular decorators added)

---

## Troubleshooting

### "ModuleEnabled not found"
Make sure `core/authz/drf.py` has the `ModuleEnabled` class. If not, it was added in Step 3 of the plan.

### "Permission denied for module X"
Check that:
1. `SchoolModule` row exists for this school + module
2. `enabled=True` in that row
3. ViewSet has `module = "modulename"` attribute

### "Serializer validation fails"
Add validation logic to serializer:
```python
class InvoiceSerializer(serializers.ModelSerializer):
    def validate(self, data):
        if data['amount'] <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return data
```

### "API response doesn't match old template data"
Check the old template view to see what data it returned. Adjust serializer `fields` list to include those fields.

---

## Next Steps

1. **Finance** (Tier 2): Port the most commonly used endpoints first
2. **HR** (Tier 2): Consolidate the 9 view modules into a single cohesive API
3. **Admissions** (Tier 2): Small, self-contained domain
4. **Operations** (Tier 3): Hostel, Transport, Library — can be done in parallel

Each fully ported domain unlocks:
- ✅ Next.js frontend page for that domain
- ✅ API documentation (OpenAPI/Swagger)
- ✅ Mobile client support (same API endpoint)
- ✅ Module on/off toggle in Unfold admin
