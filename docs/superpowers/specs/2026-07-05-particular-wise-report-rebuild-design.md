# Particular-wise Student Transaction Report: rebuild + export + pagination + performance

## Goal

`/finance/particular-wise-student-transaction-report/` (`ParticularWiseStudentTransactionReportView`,
`core/view_modules/finance_dashboard_views.py:813`) currently:

- computes "expected"/PTA/tuition amounts from hardcoded placeholders
  (`Decimal('25000.00')`, `Decimal('100.00')`) instead of real fee data,
- filters "paid" amounts against `FinanceTransaction`/`FinanceTransactionCategory`
  (the generic income/expense ledger), while its `fee_account` dropdown is
  populated from the unrelated `FeeCategory` model — the filter can never
  match, so even "Total Paid" isn't reading real fee-payment data,
- renders a Grand Total row via a broken `{% widthratio %}` expression that
  produces nonsense text, not a real sum,
- has "CSV report"/"PDF report" buttons that are inert `<button type="button">`
  elements with no handler, href, or backend support at all,
- has non-functional pagination markup (page links 2/3/25/26 go to `href="#"`),
- runs 2-3 DB queries per matching student in a Python loop (N+1), making the
  page slow as the student count grows.

This spec rebuilds the report on the same fee-billing primitives the rest of
the finance module already trusts (`FinanceFee`/`FeeTransaction`/`FeeCategory`,
via the `FeeReportingService`-style ledger convention), adds working CSV/PDF
export, real pagination, and query-count optimization.

## Data model & scope

The report is scoped to one `AcademicYear` (the existing "Financial Year"
dropdown, currently captured but ignored — now required to see any fee data,
matching how `student_management.html`/`year_reports.html` already work).
If `from_date`/`to_date` are also supplied, they narrow which `FeeTransaction`
ledger rows count *within* that year (`transaction_date__range`). If no dates
are given, the window defaults to every ledger row tagged with that
`academic_year`.

All figures for a given student (and, when split, a given PTA/Tuition bucket)
derive from `FeeTransaction` rows in that window, using the same debit/credit
convention as `core/services/fee_reporting_service.py`:

- **Charged** = sum of `transaction_type in ('adjustment', 'fine')`
- **Paid** = sum of `transaction_type == 'payment'`
- **Balance** = Charged − sum of `transaction_type in ('payment', 'discount', 'refund')`

PTA vs Tuition split: a `FeeCategory` counts as PTA if `name__icontains='PTA'`;
every other category rolls into Tuition. This matches the existing (currently
dead) code's convention — no schema change.

## Filters

- `financial_year` → required `AcademicYear.id`. If omitted or invalid, the
  report shows the filter form only (no results, no crash) — mirrors how
  `year_reports.html`/`fee_batch_report` behave without a selected year.
- `from_date` / `to_date` → optional, narrow the ledger window as above.
- `fee_account` → `all` or one `FeeCategory.id`; narrows which categories'
  ledger rows count toward both the PTA/Tuition split and the category total.
  When a specific category is selected, the PTA/Tuition split still applies
  (a selected category is either PTA or Tuition, so one of the two columns
  will simply be zero for every row).
- `student_status`, `class` (course), `batch` → unchanged from current
  behavior: these filter which `Student` rows appear (via `BatchStudent`),
  not which ledger entries count. A student who changed batches mid-year
  still has all their in-year charges counted; only their *current*
  batch/class membership determines whether they appear in a batch/class-
  filtered view. This is the existing behavior and is out of scope to change.
- `with_expected` checkbox → now has real effect:
  - **Checked**: full table — Sl No, Student, Batch, Total Paid, PTA
    (Expected/Paid/Balance), Tuition (Expected/Paid/Balance).
  - **Unchecked**: simplified table — Sl No, Student, Batch, Charged, Paid,
    Balance (no PTA/Tuition split, cheaper to compute).

## Grand Total row

Computed once in the view as real aggregate sums over the *currently
displayed page's* rows (see Pagination below) and passed into context as
plain values — no template-side arithmetic, no `{% widthratio %}`.

## Pagination

Real Django pagination, `paginate_by = 20` (this project's stated REST
default per `CLAUDE.md`), driven by `?page=N` alongside the existing filter
params (all filters must be preserved across page links, same pattern as
`students/list.html`'s pagination). CSV/PDF export always operate on the
**full filtered result set**, ignoring the current page — that is the
expected meaning of "export."

## Performance

Replace the per-student Python loop with aggregate queries:

1. Resolve the filtered `Student` queryset first (status/class/batch filters
   — unchanged logic), then paginate it (`Paginator`) to get the current
   page's student ID list (≤20 students).
2. One `FeeTransaction.objects.filter(tenant=school, academic_year=..., student_id__in=page_student_ids, transaction_date__range=[...])` query,
   `.values('student_id', 'fee_category__name')` grouped, with conditional
   aggregation (`Sum(Case(When(transaction_type__in=DEBIT_TYPES, then='amount'), default=0))` etc.)
   to get charged/paid/balance per student in one round trip — computed
   separately for the PTA bucket and the non-PTA (Tuition) bucket via a
   `Case`/`When` on whether `fee_category__name__icontains='PTA'`.
3. One `BatchStudent.objects.filter(student_id__in=page_student_ids).select_related('batch')`
   query to resolve batch names for the current page only.
4. Grand Total row sums are computed from the same per-student aggregate
   results already fetched for the page — no extra query.

This changes the query count from "≈3N queries for N matching students" to a
small constant number of queries regardless of how many students match,
and — combined with pagination — means only the current page's 20 students
are ever touched by the per-student aggregation queries.

## Export

Same pattern as the already-shipped fix for `TransactionReportResultView`
(`core/views.py`, commit `0f604e4`):

- Extract the data-building logic (filtered/aggregated student rows, for the
  *full* filtered set, not just one page) into a private method on the view.
- Add a `get()` override: if `request.GET.get('format')` is `csv` or `pdf`,
  build the full-result-set data and return the corresponding response;
  otherwise fall through to the normal paginated HTML render.
- CSV via `csv.writer`, column set matching whichever table shape
  (`with_expected` on/off) was requested.
- PDF via a new standalone WeasyPrint template
  (`core/templates/core/finance/particular_wise_student_transaction_report_pdf.html`),
  following the same visual pattern as `transaction_report_pdf.html`
  (branded header, bordered table, grand total row) — landscape A4 given the
  wider column set when `with_expected` is checked.
- The template's two export buttons become real links carrying the current
  filter querystring plus `format=csv`/`format=pdf`, replacing the current
  inert `<button type="button">` elements — same link-building pattern
  already used on `transaction_report_view.html`.

## Explicitly out of scope

- No schema/model changes (no new `is_pta` flag, no new export-log model).
- No change to `student_status`/`class`/`batch` filter *semantics* (only to
  how they compose with the rebuilt fee-data query).
- No change to how batch/class changes mid-year are handled (uses current
  batch/class membership, not point-in-time snapshots).

## Verification

No pytest coverage applies (project-wide known-broken harness, documented in
prior finance work). Verify via:

- `manage.py shell` dev-shell script exercising the aggregate query against
  real dev data: confirm charged/paid/balance reconcile per student
  (balance == charged − paid − discounts − refunds, matching
  `FeeReportingService.student_statement`'s own invariant).
- Confirm CSV/PDF exports produce non-empty, correctly-formatted output for
  a filtered result set larger than one page (proving export ignores
  pagination).
- Confirm pagination links preserve all active filters and load distinct
  pages of students.
- `manage.py check` clean (aside from the two pre-existing unrelated
  `fields.W342` warnings already present before this work).
- Query count check: use `django.test.utils.CaptureQueriesContext` (or the
  Debug Toolbar / raw `connection.queries` in a dev-shell script) around a
  request with e.g. 50 matching students, confirm total query count is a
  small constant (not scaling with student count).
