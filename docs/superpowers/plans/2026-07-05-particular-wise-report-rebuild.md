# Particular-wise Student Transaction Report Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/finance/particular-wise-student-transaction-report/` on real fee-ledger data (replacing hardcoded placeholders and a mismatched data model), and add working CSV/PDF export, real pagination, and a fixed N+1 query pattern.

**Architecture:** One Django `TemplateView` (`ParticularWiseStudentTransactionReportView`) gains a `get()` override for export (`?format=csv`/`?format=pdf`) and rewritten `get_context_data()` for the paginated HTML path. Both paths share the same private aggregation helpers, which run a single grouped `FeeTransaction` query per request (not per student) using conditional (`Case`/`When`) aggregation to compute charged/paid/balance and PTA/Tuition sub-splits at once.

**Tech Stack:** Django views/templates, Django ORM conditional aggregation, WeasyPrint (already a project dependency, used by `receipt_pdf.html`/`invoice_pdf.html`/`transaction_report_pdf.html`), Django `Paginator`.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-05-particular-wise-report-rebuild-design.md`.
- No pytest coverage applies (project-wide known-broken harness). Verify via `manage.py shell` dev-shell scripts run inside the `pinewood-web-1` docker container, and `manage.py check`, matching this codebase's established practice for this subsystem.
- `FeeTransaction` debit/credit convention (must match `core/services/fee_reporting_service.py` exactly): debit types (charges) = `('adjustment', 'fine')`; credit types (reduce balance) = `('payment', 'discount', 'refund')`. Charged = sum(debit types). Paid = sum(`payment` only). Balance = Charged − sum(credit types).
- PTA vs Tuition split: a `FeeCategory` counts as PTA if `name__icontains='PTA'`; everything else is Tuition. No schema change (no new model field).
- "Financial Year" becomes the required academic-year scope, using the existing shared helpers `resolve_selected_year(request, school)` / `build_year_context(request, school)` / `core/templates/core/finance/_year_selector.html` (`core/view_modules/finance_year_context.py`) — the same pattern already used by `student_management.html`/`year_reports.html`. The GET param changes from `financial_year` (dead, never used) to `academic_year` (the shared convention's param name).
- `student_status`/`class`/`batch` filters keep their exact current semantics (filter which `Student` rows appear via `BatchStudent`) — do not change this logic, only refactor it into a method.
- Pagination: `paginate_by = 20` (this project's stated REST default per `CLAUDE.md`), via Django's `Paginator`, `?page=N`, preserving every other active filter param on each page link.
- CSV/PDF export always operate on the full filtered result set (all matching students, unpaginated) — never just the current page.
- `with_expected` toggles which *columns render*, not what's computed — a single aggregate query already computes the PTA/Tuition split at the same cost as the base charged/paid/balance figures, so there is no separate "cheap path"/"expensive path" query. (This is a deliberate simplification of the design spec's "cheaper to compute" framing: once the report is on one aggregate query, computing the PTA split is not meaningfully more expensive, so the code does not branch on `with_expected` when building rows — only the template conditionally displays the extra columns.)
- Never introduce a new hardcoded placeholder amount (`Decimal('25000.00')`-style) anywhere in this rebuild.

---

## File Structure

- Modify: `core/view_modules/finance_dashboard_views.py:813-1016` — replace `ParticularWiseStudentTransactionReportView` entirely with a version backed by real `FeeTransaction` aggregation, pagination, and export.
- Modify: `core/templates/core/finance/particular_wise_student_transaction_report.html` — swap the dead "Financial Year" dropdown for the shared `_year_selector.html` partial, fix the Grand Total row (real values, real `Balance Amount` column for Tuition), replace static pagination markup with real page links, replace the two inert export buttons with real links.
- Create: `core/templates/core/finance/particular_wise_student_transaction_report_pdf.html` — standalone WeasyPrint print template (landscape A4, matches `transaction_report_pdf.html`'s visual pattern).

---

### Task 1: Backend rebuild — real data, pagination, no export yet

**Files:**
- Modify: `core/view_modules/finance_dashboard_views.py:1-24` (imports)
- Modify: `core/view_modules/finance_dashboard_views.py:813-1016` (the view class)

**Interfaces:**
- Consumes: `resolve_selected_year(request, school)` / `build_year_context(request, school)` from `core/view_modules/finance_year_context.py` (already exist, unchanged).
- Produces (for Task 2 and Task 3 to consume):
  - `ParticularWiseStudentTransactionReportView._get_filtered_students(school, request)` → ordered `Student` queryset (unpaginated), applying `student_status`/`class`/`batch` filters.
  - `ParticularWiseStudentTransactionReportView._build_rows(school, selected_year, students, fee_account, from_date_obj, to_date_obj)` → `list[dict]`, one dict per student in `students`' order, each with exactly these keys: `student` (Student instance), `batch_name` (str), `expected_amount`, `paid_amount`, `balance_amount`, `pta_expected`, `pta_paid`, `pta_balance`, `tuition_expected`, `tuition_paid`, `tuition_balance` (all `Decimal`).
  - `ParticularWiseStudentTransactionReportView._compute_grand_totals(rows)` → `dict` with keys `grand_expected`, `grand_paid`, `grand_balance`, `grand_pta_expected`, `grand_pta_paid`, `grand_pta_balance`, `grand_tuition_expected`, `grand_tuition_paid`, `grand_tuition_balance` (all `Decimal`).
  - `get_context_data()` puts `page_obj`, `is_paginated`, `paginator`, `rows` (the current page's `_build_rows()` output), `grand_totals` (dict from `_compute_grand_totals`), plus the existing dropdown/filter echo keys, into context.

- [ ] **Step 1: Add required imports**

In `core/view_modules/finance_dashboard_views.py`, replace the import block (lines 1-24):

```python
from django.shortcuts import render, redirect
from django.http import Http404, JsonResponse
from django.views.generic import TemplateView, View
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Case, When, Value, DecimalField, Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from decimal import Decimal, InvalidOperation
import logging

from core.models import (
    FinanceFee, 
    FinanceTransaction, 
    Student,
    Employee,
    QuickBooksIntegration
)
from core.services.exceptions import BusinessLogicException
from core.services.finance_service import FinanceService
from core.services.quickbooks_service import QuickBooksService
from core.view_modules.finance_year_context import build_year_context, resolve_selected_year

logger = logging.getLogger(__name__)
```

(Only change from the original: added `Case, When, Value, DecimalField, Q` to the `django.db.models` import, and added `from django.core.paginator import Paginator`.)

- [ ] **Step 2: Replace the view class**

Replace `ParticularWiseStudentTransactionReportView` (currently lines 813-1016 — the whole class, from `class ParticularWiseStudentTransactionReportView(TemplateView):` down to the final `return context` of its `get_context_data`) with:

```python
class ParticularWiseStudentTransactionReportView(TemplateView):
    """Particular-wise Student Transaction Report page under Finance Reports"""
    template_name = 'core/finance/particular_wise_student_transaction_report.html'

    PAGE_SIZE = 20
    _DEBIT_TYPES = ('adjustment', 'fine')
    _CREDIT_TYPES = ('payment', 'discount', 'refund')

    def _get_filtered_students(self, school, request):
        from core.models import Student, BatchStudent, Batch

        student_status = request.GET.get('student_status', 'active')
        class_filter = request.GET.get('class', 'all')
        batch_filter = request.GET.get('batch', 'all')

        students_query = Student.objects.filter(tenant=school)

        if student_status == 'active':
            students_query = students_query.filter(is_deleted=False)

        if class_filter != 'all':
            try:
                course_batches = Batch.objects.filter(
                    tenant=school,
                    course_id=class_filter
                ).values_list('id', flat=True)

                batch_students = BatchStudent.objects.filter(
                    tenant=school,
                    batch_id__in=course_batches
                )
                student_ids = batch_students.values_list('student_id', flat=True)
                students_query = students_query.filter(id__in=student_ids)
            except (ValueError, ValidationError) as e:
                logger.debug("Invalid class_filter %r: %s", class_filter, e)

        elif batch_filter != 'all':
            try:
                batch_students = BatchStudent.objects.filter(
                    tenant=school,
                    batch_id=batch_filter
                )
                student_ids = batch_students.values_list('student_id', flat=True)
                students_query = students_query.filter(id__in=student_ids)
            except (ValueError, ValidationError) as e:
                logger.debug("Invalid batch_filter %r: %s", batch_filter, e)

        return students_query.order_by('first_name', 'last_name')

    def _ledger_aggregates(self, school, selected_year, student_ids, fee_account, from_date_obj, to_date_obj):
        """One grouped query: student_id -> dict of charged/paid/credited totals, split PTA vs not."""
        from core.models import FeeTransaction

        if not student_ids:
            return {}

        decimal_field = DecimalField(max_digits=15, decimal_places=2)

        ledger = FeeTransaction.objects.filter(
            tenant=school,
            academic_year=selected_year,
            student_id__in=student_ids,
        )
        if fee_account != 'all':
            ledger = ledger.filter(fee_category_id=fee_account)
        if from_date_obj:
            ledger = ledger.filter(transaction_date__date__gte=from_date_obj)
        if to_date_obj:
            ledger = ledger.filter(transaction_date__date__lte=to_date_obj)

        pta_q = Q(fee_category__name__icontains='PTA')

        def total_case(extra_q=None, types=None, single_type=None):
            condition = Q(transaction_type=single_type) if single_type else Q(transaction_type__in=types)
            if extra_q is not None:
                condition &= extra_q
            return Sum(Case(When(condition, then='amount'), default=Value(0), output_field=decimal_field))

        rows = ledger.values('student_id').annotate(
            charged=total_case(types=self._DEBIT_TYPES),
            paid=total_case(single_type='payment'),
            credited=total_case(types=self._CREDIT_TYPES),
            pta_charged=total_case(extra_q=pta_q, types=self._DEBIT_TYPES),
            pta_paid=total_case(extra_q=pta_q, single_type='payment'),
            pta_credited=total_case(extra_q=pta_q, types=self._CREDIT_TYPES),
        )

        zero = Decimal('0.00')
        result = {}
        for row in rows:
            result[row['student_id']] = {
                'charged': row['charged'] or zero,
                'paid': row['paid'] or zero,
                'credited': row['credited'] or zero,
                'pta_charged': row['pta_charged'] or zero,
                'pta_paid': row['pta_paid'] or zero,
                'pta_credited': row['pta_credited'] or zero,
            }
        return result

    def _build_rows(self, school, selected_year, students, fee_account, from_date_obj, to_date_obj):
        from core.models import BatchStudent

        students = list(students)
        student_ids = [s.id for s in students]

        aggregates = self._ledger_aggregates(
            school, selected_year, student_ids, fee_account, from_date_obj, to_date_obj
        )

        batch_names = {}
        for bs in BatchStudent.objects.filter(tenant=school, student_id__in=student_ids).select_related('batch'):
            batch_names.setdefault(bs.student_id, bs.batch.name)

        zero = Decimal('0.00')
        rows = []
        for student in students:
            agg = aggregates.get(student.id, {
                'charged': zero, 'paid': zero, 'credited': zero,
                'pta_charged': zero, 'pta_paid': zero, 'pta_credited': zero,
            })
            tuition_charged = agg['charged'] - agg['pta_charged']
            tuition_paid = agg['paid'] - agg['pta_paid']
            tuition_credited = agg['credited'] - agg['pta_credited']

            rows.append({
                'student': student,
                'batch_name': batch_names.get(student.id, "Not Assigned"),
                'expected_amount': agg['charged'],
                'paid_amount': agg['paid'],
                'balance_amount': agg['charged'] - agg['credited'],
                'pta_expected': agg['pta_charged'],
                'pta_paid': agg['pta_paid'],
                'pta_balance': agg['pta_charged'] - agg['pta_credited'],
                'tuition_expected': tuition_charged,
                'tuition_paid': tuition_paid,
                'tuition_balance': tuition_charged - tuition_credited,
            })
        return rows

    def _compute_grand_totals(self, rows):
        zero = Decimal('0.00')
        totals = {
            'grand_expected': zero, 'grand_paid': zero, 'grand_balance': zero,
            'grand_pta_expected': zero, 'grand_pta_paid': zero, 'grand_pta_balance': zero,
            'grand_tuition_expected': zero, 'grand_tuition_paid': zero, 'grand_tuition_balance': zero,
        }
        for row in rows:
            totals['grand_expected'] += row['expected_amount']
            totals['grand_paid'] += row['paid_amount']
            totals['grand_balance'] += row['balance_amount']
            totals['grand_pta_expected'] += row['pta_expected']
            totals['grand_pta_paid'] += row['pta_paid']
            totals['grand_pta_balance'] += row['pta_balance']
            totals['grand_tuition_expected'] += row['tuition_expected']
            totals['grand_tuition_paid'] += row['tuition_paid']
            totals['grand_tuition_balance'] += row['tuition_balance']
        return totals

    def _parse_date_filters(self, request):
        from datetime import datetime

        from_date = request.GET.get('from_date', '')
        to_date = request.GET.get('to_date', '')
        from_date_obj = None
        to_date_obj = None
        if from_date:
            try:
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            except ValueError:
                from_date = ''
        if to_date:
            try:
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            except ValueError:
                to_date = ''
        return from_date, from_date_obj, to_date, to_date_obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        request = self.request
        fee_account = request.GET.get('fee_account', 'all')
        from_date, from_date_obj, to_date, to_date_obj = self._parse_date_filters(request)
        student_status = request.GET.get('student_status', 'active')
        class_filter = request.GET.get('class', 'all')
        batch_filter = request.GET.get('batch', 'all')
        with_expected = request.GET.get('with_expected', False) == 'on'

        from core.models import FeeCategory, Course, Batch

        fee_categories = FeeCategory.objects.filter(tenant=school, is_deleted=False).order_by('name')
        courses = Course.objects.filter(tenant=school, is_deleted=False).order_by('course_name')
        batches = Batch.objects.filter(tenant=school).order_by('name')

        selected_year = resolve_selected_year(request, school)

        rows = []
        grand_totals = self._compute_grand_totals([])
        page_obj = None
        is_paginated = False

        if request.GET.get('view_report') and selected_year is not None:
            students = self._get_filtered_students(school, request)
            paginator = Paginator(students, self.PAGE_SIZE)
            page_obj = paginator.get_page(request.GET.get('page'))
            is_paginated = paginator.num_pages > 1

            rows = self._build_rows(
                school, selected_year, page_obj.object_list, fee_account, from_date_obj, to_date_obj
            )
            grand_totals = self._compute_grand_totals(rows)

        context.update({
            'school': school,
            'rows': rows,
            'grand_totals': grand_totals,
            'page_obj': page_obj,
            'is_paginated': is_paginated,
            'fee_account': fee_account,
            'from_date': from_date,
            'to_date': to_date,
            'student_status': student_status,
            'class_filter': class_filter,
            'batch_filter': batch_filter,
            'with_expected': with_expected,
            'fee_categories': fee_categories,
            'courses': courses,
            'batches': batches,
        })
        context.update(build_year_context(request, school))
        return context
```

- [ ] **Step 3: Verify data correctness and query count via dev-shell script**

Run inside the running web container:

```bash
docker exec -it pinewood-web-1 python manage.py shell
```

```python
from django_tenants.utils import schema_context
from core.models import School, Student, FeeCategory, FeeTransaction, AcademicYear
from django.test import RequestFactory
from django.db import transaction
from django.test.utils import CaptureQueriesContext
from django.db import connection
from decimal import Decimal
from core.view_modules.finance_dashboard_views import ParticularWiseStudentTransactionReportView

school = School.objects.first()
with schema_context(school.schema_name):
    with transaction.atomic():
        year = AcademicYear.objects.filter(tenant=school).first()
        assert year is not None, "dev tenant needs at least one AcademicYear for this check"

        category = FeeCategory.objects.filter(tenant=school, is_deleted=False).first()
        assert category is not None, "dev tenant needs at least one FeeCategory for this check"

        # Make >20 students so pagination + the query-count check are meaningful.
        students = list(Student.objects.filter(tenant=school, is_deleted=False)[:25])
        assert len(students) >= 1, "dev tenant needs at least one Student for this check"

        # Give the first student a real charge + partial payment to verify reconciliation.
        s = students[0]
        FeeTransaction.objects.create(
            tenant=school, student=s, fee_category=category, academic_year=year,
            transaction_type='adjustment', amount=Decimal('500.00'), description='test charge',
        )
        FeeTransaction.objects.create(
            tenant=school, student=s, fee_category=category, academic_year=year,
            transaction_type='payment', amount=Decimal('200.00'), description='test payment',
        )

        rf = RequestFactory()
        view = ParticularWiseStudentTransactionReportView()
        req = rf.get('/finance/particular-wise-student-transaction-report/', {
            'view_report': '1', 'academic_year': str(year.id),
        })
        req.tenant = school
        view.request = req
        view.kwargs = {}

        with CaptureQueriesContext(connection) as ctx:
            context = view.get_context_data()
        print("QUERY COUNT (page render):", len(ctx.captured_queries))

        row = next(r for r in context['rows'] if r['student'].id == s.id)
        print("charged:", row['expected_amount'], "paid:", row['paid_amount'], "balance:", row['balance_amount'])
        assert row['expected_amount'] == Decimal('500.00')
        assert row['paid_amount'] == Decimal('200.00')
        assert row['balance_amount'] == Decimal('300.00')
        assert row['balance_amount'] == row['expected_amount'] - row['paid_amount']

        gt = context['grand_totals']
        assert gt['grand_expected'] >= Decimal('500.00')

        transaction.set_rollback(True)
print("OK")
```

Expected: `QUERY COUNT (page render)` prints a small constant number (roughly 5-8 — students page query, count query, ledger aggregate query, batch-name query, fee_categories/courses/batches dropdown queries, year-context queries — NOT scaling with the number of students), all `assert`s pass, `OK` prints, and the rollback discards the test `FeeTransaction` rows.

- [ ] **Step 4: Run `manage.py check`**

```bash
docker exec -it pinewood-web-1 python manage.py check
```

Expected: only the 2 pre-existing unrelated `fields.W342` warnings (from an ancestor commit, unrelated to this file) — no new errors or warnings.

- [ ] **Step 5: Commit**

```bash
git add core/view_modules/finance_dashboard_views.py
git commit -m "Rebuild particular-wise student transaction report on real FeeTransaction data with pagination"
```

Note: the template still expects the old context shape at this point (it references `student_transactions`, `financial_year`, a `<select name="financial_year">`, etc.) — the page will 500 or render incorrectly until Task 2 lands. This is expected; Task 1's verification is the dev-shell script above, not a live page load.

---

### Task 2: Template rebuild — year selector, real grand totals, real pagination

**Files:**
- Modify: `core/templates/core/finance/particular_wise_student_transaction_report.html`

**Interfaces:**
- Consumes context keys from Task 1: `rows` (list of dicts with `student`, `batch_name`, `expected_amount`, `paid_amount`, `balance_amount`, `pta_expected`, `pta_paid`, `pta_balance`, `tuition_expected`, `tuition_paid`, `tuition_balance`), `grand_totals` (dict with `grand_expected`, `grand_paid`, `grand_balance`, `grand_pta_expected`, `grand_pta_paid`, `grand_pta_balance`, `grand_tuition_expected`, `grand_tuition_paid`, `grand_tuition_balance`), `page_obj`, `is_paginated`, `with_expected`, `fee_account`, `from_date`, `to_date`, `student_status`, `class_filter`, `batch_filter`, `fee_categories`, `courses`, `batches`, plus `academic_years`/`selected_year`/`selected_year_id` from `build_year_context` (already used by `core/templates/core/finance/_year_selector.html`, unchanged).

- [ ] **Step 1: Replace the header and add the year selector**

Replace lines 9-18 (currently):

```html
    <!-- Header Section -->
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <div class="d-flex align-items-center">
                <i class="fas fa-users me-2 text-muted"></i>
                <h2 class="h3 mb-0">Reports</h2>
                <span class="mx-2 text-muted">|</span>
                <span class="text-primary">Particular-wise Student Transaction Report</span>
            </div>
        </div>
    </div>
```

with:

```html
    <!-- Header Section -->
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <div class="d-flex align-items-center">
                <i class="fas fa-users me-2 text-muted"></i>
                <h2 class="h3 mb-0">Reports</h2>
                <span class="mx-2 text-muted">|</span>
                <span class="text-primary">Particular-wise Student Transaction Report</span>
            </div>
        </div>
        <div>
            {% include 'core/finance/_year_selector.html' %}
        </div>
    </div>

    {% if not selected_year %}
    <div class="alert alert-warning" role="alert">
        No academic year configured for this school — set one up before running this report.
    </div>
    {% endif %}
```

- [ ] **Step 2: Remove the dead "Financial Year" dropdown and add a hidden `academic_year` field to the filter form**

Replace lines 46-58 (currently):

```html
            <!-- Financial Year -->
            <div class="col-md-6">
                <label for="financial_year" class="form-label">Financial Year</label>
                <select class="form-select" id="financial_year" name="financial_year">
                    <option value="">Select Financial Year</option>
                    {% for year in academic_years %}
                        <option value="{{ year.id }}" {% if financial_year == year.id|stringformat:"s" %}selected{% endif %}>
                            {{ year.name }}
                        </option>
                    {% endfor %}
                    <option value="2025-2025" {% if financial_year == '2025-2025' %}selected{% endif %}>2025 - 2025</option>
                </select>
            </div>
```

with nothing (delete this block entirely — the year is now controlled solely by the year-selector form above, not the filter form).

Then, immediately after the `<form method="get" class="mb-4">` opening tag (line 31), add a hidden field so the selected year survives a "View report" submit from the filter form:

```html
    <form method="get" class="mb-4">
        <input type="hidden" name="academic_year" value="{{ selected_year_id }}">
        <div class="row g-3">
```

(This replaces the original `<form method="get" class="mb-4">\n        <div class="row g-3">` two-line opening with the three-line version above.)

- [ ] **Step 3: Rewrite the Results Section — table structure, real headers, with_expected toggle**

Replace the entire Results Section (from `<!-- Results Section -->` through the closing `{% endif %}` right before `<!-- Export Buttons -->` — currently lines 131-236, the whole `{% if student_transactions %}` block including thead/tbody/pagination) with:

```html
    <!-- Results Section -->
    {% if rows %}
    <div class="card">
        <div class="card-body p-0">
            <!-- Results Table -->
            <div class="table-responsive">
                <table class="table table-hover mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>Sl No.</th>
                            <th>Student Name</th>
                            <th>Batch Name (s)</th>
                            <th class="text-center">Expected Amount</th>
                            <th class="text-center">Paid Amount</th>
                            <th class="text-center">Balance Amount</th>
                            {% if with_expected %}
                            <th colspan="3" class="text-center">PTA</th>
                            <th colspan="3" class="text-center">Tuition Fee</th>
                            {% endif %}
                        </tr>
                        {% if with_expected %}
                        <tr class="table-light">
                            <th></th>
                            <th></th>
                            <th></th>
                            <th></th>
                            <th></th>
                            <th></th>
                            <th class="text-center">Expected Amount</th>
                            <th class="text-center">Paid Amount</th>
                            <th class="text-center">Balance Amount</th>
                            <th class="text-center">Expected Amount</th>
                            <th class="text-center">Paid Amount</th>
                            <th class="text-center">Balance Amount</th>
                        </tr>
                        {% endif %}
                    </thead>
                    <tbody>
                        {% for row in rows %}
                        <tr>
                            <td>{{ page_obj.start_index|add:forloop.counter0 }}</td>
                            <td>{{ row.student.first_name }} {{ row.student.last_name }}</td>
                            <td>{{ row.batch_name }}</td>
                            <td class="text-center">{{ row.expected_amount|floatformat:2 }}</td>
                            <td class="text-center">{{ row.paid_amount|floatformat:2 }}</td>
                            <td class="text-center">{{ row.balance_amount|floatformat:2 }}</td>
                            {% if with_expected %}
                            <td class="text-center">{{ row.pta_expected|floatformat:2 }}</td>
                            <td class="text-center">{{ row.pta_paid|floatformat:2 }}</td>
                            <td class="text-center">{{ row.pta_balance|floatformat:2 }}</td>
                            <td class="text-center">{{ row.tuition_expected|floatformat:2 }}</td>
                            <td class="text-center">{{ row.tuition_paid|floatformat:2 }}</td>
                            <td class="text-center">{{ row.tuition_balance|floatformat:2 }}</td>
                            {% endif %}
                        </tr>
                        {% endfor %}

                        <!-- Grand Total Row -->
                        <tr class="table-warning fw-bold">
                            <td colspan="3">Grand Total</td>
                            <td class="text-center">{{ grand_totals.grand_expected|floatformat:2 }}</td>
                            <td class="text-center">{{ grand_totals.grand_paid|floatformat:2 }}</td>
                            <td class="text-center">{{ grand_totals.grand_balance|floatformat:2 }}</td>
                            {% if with_expected %}
                            <td class="text-center">{{ grand_totals.grand_pta_expected|floatformat:2 }}</td>
                            <td class="text-center">{{ grand_totals.grand_pta_paid|floatformat:2 }}</td>
                            <td class="text-center">{{ grand_totals.grand_pta_balance|floatformat:2 }}</td>
                            <td class="text-center">{{ grand_totals.grand_tuition_expected|floatformat:2 }}</td>
                            <td class="text-center">{{ grand_totals.grand_tuition_paid|floatformat:2 }}</td>
                            <td class="text-center">{{ grand_totals.grand_tuition_balance|floatformat:2 }}</td>
                            {% endif %}
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Pagination -->
            <div class="d-flex justify-content-between align-items-center p-3 border-top">
                <div class="text-muted small">
                    Showing {{ page_obj.start_index }} - {{ page_obj.end_index }} out of {{ page_obj.paginator.count }}
                </div>
                {% if is_paginated %}
                <nav>
                    <ul class="pagination pagination-sm mb-0">
                        {% if page_obj.has_previous %}
                        <li class="page-item">
                            <a class="page-link" href="?{% for key, value in request.GET.items %}{% if key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}page={{ page_obj.previous_page_number }}">&laquo; previous</a>
                        </li>
                        {% else %}
                        <li class="page-item disabled"><span class="page-link">&laquo; previous</span></li>
                        {% endif %}

                        {% for page_num in page_obj.paginator.page_range %}
                        <li class="page-item {% if page_num == page_obj.number %}active{% endif %}">
                            <a class="page-link" href="?{% for key, value in request.GET.items %}{% if key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}page={{ page_num }}">{{ page_num }}</a>
                        </li>
                        {% endfor %}

                        {% if page_obj.has_next %}
                        <li class="page-item">
                            <a class="page-link" href="?{% for key, value in request.GET.items %}{% if key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}page={{ page_obj.next_page_number }}">next &raquo;</a>
                        </li>
                        {% else %}
                        <li class="page-item disabled"><span class="page-link">next &raquo;</span></li>
                        {% endif %}
                    </ul>
                </nav>
                {% endif %}
            </div>
```

Leave the `<!-- Export Buttons -->` block and its wrapping `</div></div>{% endif %}` (currently lines 237-252) in place for now — Task 3 replaces just the two `<button>` elements inside it.

- [ ] **Step 4: Manual verification**

With the dev server running, visit `/finance/particular-wise-student-transaction-report/`:
- Confirm the year selector renders in the header and changing it reloads the page with `?academic_year=...`.
- If no academic year exists for the tenant, confirm the warning alert shows instead of a crash.
- Select a year, click "View report" with no other filters — confirm the table renders with real Expected/Paid/Balance figures (matching what Task 1's dev-shell script verified) and a correct Grand Total row.
- Toggle "With Expected" on/off — confirm the PTA/Tuition column groups appear/disappear and the base columns always show.
- If there are more than 20 matching students, confirm pagination links appear, preserve the current filters in their `href`, and load a distinct page of students.

- [ ] **Step 5: Commit**

```bash
git add core/templates/core/finance/particular_wise_student_transaction_report.html
git commit -m "Wire particular-wise report template to real data, year selector, and pagination"
```

---

### Task 3: CSV/PDF export

**Files:**
- Modify: `core/view_modules/finance_dashboard_views.py` (add `get()` override + `_render_csv`/`_render_pdf` to `ParticularWiseStudentTransactionReportView`)
- Modify: `core/templates/core/finance/particular_wise_student_transaction_report.html` (replace the two inert export buttons)
- Create: `core/templates/core/finance/particular_wise_student_transaction_report_pdf.html`

**Interfaces:**
- Consumes: `_get_filtered_students`, `_build_rows`, `_compute_grand_totals`, `_parse_date_filters` from Task 1 (unchanged signatures).
- Produces: `GET .../?...&format=csv` and `GET .../?...&format=pdf` return real file downloads; all other query strings continue to render the normal paginated HTML page (Task 1/2 behavior unchanged).

- [ ] **Step 1: Add the `get()` override and render helpers**

In `core/view_modules/finance_dashboard_views.py`, inside `ParticularWiseStudentTransactionReportView`, add these methods (place them right after `_parse_date_filters`, before `get_context_data`):

```python
    def get(self, request, *args, **kwargs):
        export_format = request.GET.get('format')
        if export_format in ('csv', 'pdf'):
            school = getattr(request, 'tenant', None)
            if not school:
                raise Http404("School not found")

            selected_year = resolve_selected_year(request, school)
            if selected_year is None:
                raise Http404("No academic year selected")

            fee_account = request.GET.get('fee_account', 'all')
            _, from_date_obj, _, to_date_obj = self._parse_date_filters(request)
            with_expected = request.GET.get('with_expected', False) == 'on'

            students = self._get_filtered_students(school, request)
            rows = self._build_rows(school, selected_year, students, fee_account, from_date_obj, to_date_obj)
            grand_totals = self._compute_grand_totals(rows)

            if export_format == 'csv':
                return self._render_csv(rows, grand_totals, with_expected)
            return self._render_pdf(school, selected_year, rows, grand_totals, with_expected)

        return super().get(request, *args, **kwargs)

    def _render_csv(self, rows, grand_totals, with_expected):
        import csv

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="particular_wise_student_transaction_report.csv"'

        writer = csv.writer(response)
        header = ['Sl No.', 'Student Name', 'Batch Name(s)', 'Expected Amount', 'Paid Amount', 'Balance Amount']
        if with_expected:
            header += [
                'PTA Expected', 'PTA Paid', 'PTA Balance',
                'Tuition Expected', 'Tuition Paid', 'Tuition Balance',
            ]
        writer.writerow(header)

        for i, row in enumerate(rows, 1):
            line = [
                i,
                f"{row['student'].first_name} {row['student'].last_name}",
                row['batch_name'],
                row['expected_amount'], row['paid_amount'], row['balance_amount'],
            ]
            if with_expected:
                line += [
                    row['pta_expected'], row['pta_paid'], row['pta_balance'],
                    row['tuition_expected'], row['tuition_paid'], row['tuition_balance'],
                ]
            writer.writerow(line)

        total_line = ['', 'Grand Total', '', grand_totals['grand_expected'], grand_totals['grand_paid'], grand_totals['grand_balance']]
        if with_expected:
            total_line += [
                grand_totals['grand_pta_expected'], grand_totals['grand_pta_paid'], grand_totals['grand_pta_balance'],
                grand_totals['grand_tuition_expected'], grand_totals['grand_tuition_paid'], grand_totals['grand_tuition_balance'],
            ]
        writer.writerow(total_line)

        return response

    def _render_pdf(self, school, selected_year, rows, grand_totals, with_expected):
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        html_content = render_to_string('core/finance/particular_wise_student_transaction_report_pdf.html', {
            'school': school,
            'selected_year': selected_year,
            'rows': rows,
            'grand_totals': grand_totals,
            'with_expected': with_expected,
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="particular_wise_student_transaction_report.pdf"'
        return response
```

- [ ] **Step 2: Create the PDF template**

Create `core/templates/core/finance/particular_wise_student_transaction_report_pdf.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Particular-wise Student Transaction Report</title>
<style>
@page { size: A4 landscape; margin: 12mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 8.5pt; color: #1a1a1a; }

.hdr { text-align: center; border-bottom: 2pt solid #17833f; padding-bottom: 6pt; margin-bottom: 8pt; }
.hdr-name { font-size: 14pt; font-weight: bold; color: #17833f; }
.hdr-sub { font-size: 7.5pt; color: #555; margin-top: 2pt; }

.title { text-align: center; font-size: 11pt; font-weight: bold; letter-spacing: 1pt;
         background: #e8f5e8; color: #125e2d; padding: 4pt; margin-bottom: 4pt; }
.range { text-align: center; font-size: 8.5pt; color: #555; margin-bottom: 8pt; }

table.report { width: 100%; border-collapse: collapse; margin-top: 4pt; }
table.report th, table.report td { border: 0.5pt solid #9c9c9c; padding: 3pt 4pt; }
table.report th { background: #17833f; color: #fff; text-align: center; font-size: 7.5pt; }
table.report td.num { text-align: right; }
tr.grand td { background: #343a40; color: #fff; font-weight: bold; }

.note { text-align: center; font-size: 7pt; color: #999; margin-top: 10pt; font-style: italic; }
</style>
</head>
<body>

<div class="hdr">
    <div class="hdr-name">{{ school.name }}</div>
    <div class="hdr-sub">
        {% if school.address_line1 %}{{ school.address_line1 }}{% endif %}{% if school.city %}, {{ school.city }}{% endif %}
        {% if school.phone %} | {{ school.phone }}{% endif %}{% if school.email %} | {{ school.email }}{% endif %}
    </div>
</div>

<div class="title">PARTICULAR-WISE STUDENT TRANSACTION REPORT</div>
<div class="range">Academic Year: {{ selected_year.name }}</div>

<table class="report">
    <thead>
        <tr>
            <th>Sl No.</th>
            <th>Student Name</th>
            <th>Batch</th>
            <th>Expected</th>
            <th>Paid</th>
            <th>Balance</th>
            {% if with_expected %}
            <th>PTA Expected</th>
            <th>PTA Paid</th>
            <th>PTA Balance</th>
            <th>Tuition Expected</th>
            <th>Tuition Paid</th>
            <th>Tuition Balance</th>
            {% endif %}
        </tr>
    </thead>
    <tbody>
        {% for row in rows %}
        <tr>
            <td>{{ forloop.counter }}</td>
            <td>{{ row.student.first_name }} {{ row.student.last_name }}</td>
            <td>{{ row.batch_name }}</td>
            <td class="num">{{ row.expected_amount|floatformat:2 }}</td>
            <td class="num">{{ row.paid_amount|floatformat:2 }}</td>
            <td class="num">{{ row.balance_amount|floatformat:2 }}</td>
            {% if with_expected %}
            <td class="num">{{ row.pta_expected|floatformat:2 }}</td>
            <td class="num">{{ row.pta_paid|floatformat:2 }}</td>
            <td class="num">{{ row.pta_balance|floatformat:2 }}</td>
            <td class="num">{{ row.tuition_expected|floatformat:2 }}</td>
            <td class="num">{{ row.tuition_paid|floatformat:2 }}</td>
            <td class="num">{{ row.tuition_balance|floatformat:2 }}</td>
            {% endif %}
        </tr>
        {% endfor %}
        <tr class="grand">
            <td colspan="3">Grand Total</td>
            <td class="num">{{ grand_totals.grand_expected|floatformat:2 }}</td>
            <td class="num">{{ grand_totals.grand_paid|floatformat:2 }}</td>
            <td class="num">{{ grand_totals.grand_balance|floatformat:2 }}</td>
            {% if with_expected %}
            <td class="num">{{ grand_totals.grand_pta_expected|floatformat:2 }}</td>
            <td class="num">{{ grand_totals.grand_pta_paid|floatformat:2 }}</td>
            <td class="num">{{ grand_totals.grand_pta_balance|floatformat:2 }}</td>
            <td class="num">{{ grand_totals.grand_tuition_expected|floatformat:2 }}</td>
            <td class="num">{{ grand_totals.grand_tuition_paid|floatformat:2 }}</td>
            <td class="num">{{ grand_totals.grand_tuition_balance|floatformat:2 }}</td>
            {% endif %}
        </tr>
    </tbody>
</table>

<div class="note">This is a computer-generated report.</div>

</body>
</html>
```

- [ ] **Step 3: Wire real export links in the HTML template**

In `core/templates/core/finance/particular_wise_student_transaction_report.html`, replace the Export Buttons block (currently, after Task 2's edits, still at the same relative position — search for `<!-- Export Buttons -->`):

```html
            <!-- Export Buttons -->
            <div class="p-3 border-top bg-light">
                <div class="d-flex gap-2">
                    <button type="button" class="btn btn-outline-success btn-sm">
                        <i class="fas fa-file-csv me-1"></i>
                        CSV report
                    </button>
                    <button type="button" class="btn btn-outline-danger btn-sm">
                        <i class="fas fa-file-pdf me-1"></i>
                        PDF report
                    </button>
                </div>
            </div>
```

with:

```html
            <!-- Export Buttons -->
            <div class="p-3 border-top bg-light">
                <div class="d-flex gap-2">
                    <a href="?{% for key, value in request.GET.items %}{% if key != 'format' and key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}format=csv"
                       class="btn btn-outline-success btn-sm">
                        <i class="fas fa-file-csv me-1"></i>
                        CSV report
                    </a>
                    <a href="?{% for key, value in request.GET.items %}{% if key != 'format' and key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}format=pdf"
                       class="btn btn-outline-danger btn-sm">
                        <i class="fas fa-file-pdf me-1"></i>
                        PDF report
                    </a>
                </div>
            </div>
```

- [ ] **Step 4: Verify export via dev-shell script**

```bash
docker exec -it pinewood-web-1 python manage.py shell
```

```python
from django_tenants.utils import schema_context
from core.models import School, AcademicYear
from django.test import RequestFactory
from core.view_modules.finance_dashboard_views import ParticularWiseStudentTransactionReportView

school = School.objects.first()
with schema_context(school.schema_name):
    year = AcademicYear.objects.filter(tenant=school).first()
    rf = RequestFactory()
    view = ParticularWiseStudentTransactionReportView.as_view()

    for fmt in ('csv', 'pdf'):
        req = rf.get('/finance/particular-wise-student-transaction-report/', {
            'view_report': '1', 'academic_year': str(year.id), 'format': fmt,
        })
        req.tenant = school
        resp = view(req)
        print(fmt.upper(), "STATUS:", resp.status_code, "CONTENT-TYPE:", resp.get('Content-Type'), "LEN:", len(resp.content))
print("OK")
```

Expected: both print `STATUS: 200` with `text/csv`/`application/pdf` content types and non-trivial `LEN` values.

- [ ] **Step 5: Run `manage.py check`**

```bash
docker exec -it pinewood-web-1 python manage.py check
```

Expected: only the 2 pre-existing unrelated `fields.W342` warnings.

- [ ] **Step 6: Commit**

```bash
git add core/view_modules/finance_dashboard_views.py core/templates/core/finance/particular_wise_student_transaction_report.html core/templates/core/finance/particular_wise_student_transaction_report_pdf.html
git commit -m "Add working CSV/PDF export to the particular-wise student transaction report"
```

---

## Final Verification

- [ ] Run `docker exec -it pinewood-web-1 python manage.py check` — only the 2 pre-existing unrelated warnings.
- [ ] Load `/finance/particular-wise-student-transaction-report/` in a browser: select a year, apply each filter (fee account, date range, student status, class, batch, with_expected) one at a time and confirm the table updates plausibly; confirm Grand Total always equals the sum of the visible rows' columns.
- [ ] With more than 20 matching students, click through pagination and confirm each page shows a distinct 20 (or fewer, on the last page) students, and all filters remain active in the URL.
- [ ] Click "CSV report" and "PDF report" and confirm both download real files containing every matching student (not just the current page).
- [ ] Confirm no console/template errors and no 500s across all of the above.
