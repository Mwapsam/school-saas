# Finance module UI alignment + CRUD audit

## Goal

Bring the finance module's staff-facing screens visually in line with the rest of
the app (the "pinewood" design system established in `core/templates/core/students/list.html`),
and fix CRUD actions that the UI currently promises but the backend doesn't deliver.

## Scope

Seven screens, chosen as the dashboards + core CRUD screens staff touch daily:

- `core/templates/core/finance/dashboard.html` (`FinanceDashboardView`, route `core:finance_dashboard`)
- `core/templates/core/fees/dashboard.html` (`FeeManagementDashboardView`, route `core:fee_dashboard`)
- `core/templates/core/fees/master_fees.html` (`MasterFeesView`, route `core:master_fees`)
- `core/templates/core/fees/create_fees.html` (`CreateFeesView`, route `core:create_fees`)
- `core/templates/core/fees/category_list.html` (`FeeCategoryListView` / `FeeCategoryCreateView`, routes `core:fee_categories` / `core:fee_category_create`)
- `core/templates/core/fees/student_management.html` (`StudentFeeManagementView`, route `core:fee_student_management`)
- `core/templates/core/finance/transactions.html` (`FinanceTransactionsView`, route `core:finance_transactions`)

Out of scope for this pass: reports, PDFs, payroll/payslip screens, tally export,
QuickBooks settings/webhook-review screens, donations. These get a later pass.

## Audit findings (baseline, verified by code inspection)

**Visual**: all 7 screens currently use generic Bootstrap with hardcoded hex
colors (`#28a745`, `#e9ecef`, `#dee2e6`) and `text-success`/plain `.card`/
`.table.table-bordered` markup. None use the pinewood classes
(`.stu-header`, `.pinewood-table-container`, `var(--color-brand)`, etc.)
that `students/list.html` uses.

**CRUD**:
- `master_fees.html` — full working CRUD for Master Particulars and Master
  Discounts (create modals, edit/delete wired through `MasterFeesView.post()`
  dispatch on `form_type`). No fix needed.
- `student_management.html` — Pay / Reverse payment / Grant Waiver / View
  Statement all wired to real views. No fix needed.
- `fee_categories` (`category_list.html`) — **broken**: the Edit modal's
  `#editCategoryForm` has no submit handler bound anywhere, so "Update
  Category" does nothing. Delete posts `action=delete` to
  `FeeCategoryCreateView.post()`, but that method only ever attempts a
  create (reads `name`/`description`, no branch on `action`) — delete
  silently fails.
- `create_fees.html` — only the "Create Category" tab works end-to-end.
  "Create Particulars", "Create Discount", and "Generate Fine" tabs are
  literal placeholder stubs ("...will be implemented here"), and duplicate
  functionality `master_fees.html` already implements for real (particulars,
  discounts) or that exists elsewhere (`fine_slabs.html` for fine slabs).
- `transactions.html` — "Add expense", "Add income", "Reverted
  transactions", "Bulk revert transactions" are dead `href="#"` links with
  zero backing (the resolved view, `views.py:4808`'s
  `FinanceTransactionsView`, is GET-only — no `post()` method at all).
- Both dashboards (`finance/dashboard.html`, `fees/dashboard.html`) are
  navigation-only grids of real, working links — nothing broken, just
  off-brand styling.

Reference pattern to align toward (`students/list.html` / `edit.html`):
- `.stu-header`: brand-left-border header card (`border-left: 4px solid var(--color-brand)`),
  48x48 icon tile (`.stu-header-icon`, `var(--color-brand-bg)`/`var(--color-brand)`),
  title + one-line subtitle, action buttons right-aligned.
- `.pinewood-table-container` / `.pinewood-table-header` / table markup for
  list views instead of plain `.table.table-bordered`.
- Design tokens from `core/static/css/pinewood-ui.css` and the `:root` vars
  in `base.html` (`--color-brand`, `--color-brand-bg`, `--p-gray-border`,
  `--color-muted`) instead of hardcoded hex.
- Bootstrap modals for create/edit/delete confirms (already the pattern used
  in `master_fees.html`/`category_list.html`) — keep using Bootstrap modals,
  just re-themed.
- Existing `_finance_nav.html` / `_year_selector.html` includes and
  breadcrumbs stay as-is structurally, just re-themed to brand colors.

## Changes

### Visual (all 7 templates)

- Replace the `d-flex justify-content-between` + icon + breadcrumb header
  block with the `.stu-header` pattern (icon tile, title, subtitle, actions).
- Replace hardcoded colors (`#28a745`, `#e9ecef`, `#dee2e6`, `text-success`)
  with the shared CSS vars.
- Replace `.table.table-bordered` / `.table-striped` list markup with
  `.pinewood-table-container` / `.pinewood-table` markup.
- Dashboard module-item grids (`finance-module-item` / `fees-module-item`):
  re-theme hover/border/heading colors to brand green instead of Bootstrap
  green, keep the two-column grid layout.
- No changes to `_finance_nav.html` / `_year_selector.html` behavior — only
  their color theming inherits from the vars already.

### CRUD fixes

- **`fee_categories`**: add a real submit handler for `#editCategoryForm`
  (posts to `core:fee_category_create` with `action=update` + the category
  id); add an `action == 'delete'` branch to `FeeCategoryCreateView.post()`
  that deletes the target `FeeCategory` (guard: block delete if the
  category has dependent particulars/fees, mirroring whatever guard pattern
  `MasterFeesView`'s delete already uses for its entities — reuse, don't
  reinvent).
- **`create_fees.html`**: remove the 3 stub tabs and their placeholder JS
  (`loadParticularsSection`/`loadDiscountSection`/`loadFineSection`).
  Replace with a small card/links section pointing to `master_fees.html`
  (particulars & discounts) and `fine_slabs.html` (fine slabs). Keep the
  working "Create Category" tab as-is.
- **`transactions.html`**: remove the 4 dead-link buttons (Add expense, Add
  income, Reverted transactions, Bulk revert transactions) from the
  template. No backend changes — nothing else references these buttons.

## Verification

No automated test coverage exists for these templates (pytest harness is
currently broken per prior finance-subsystem-state notes). Verify manually
per screen via the dev docker container / browser:

- Load each of the 7 screens, visually confirm pinewood styling (header,
  table, colors) renders correctly in both the finance and fees sections.
- `fee_categories`: create a category, edit it (confirm the update
  persists), delete a category with and without dependents (confirm the
  guard blocks deletion where appropriate).
- `create_fees.html`: confirm Create Category still works; confirm the new
  links to master_fees/fine_slabs resolve correctly; confirm no leftover
  JS errors from removed stub functions.
- `transactions.html`: confirm the page still loads and shows real data
  (transaction summary / recent transactions) with the dead buttons gone.
- `manage.py check` clean if `FeeCategoryCreateView` changes.

## Explicitly out of scope

- Building real Add expense/income/bulk-revert functionality for
  `transactions.html` (deferred — substantial new feature, not a UI pass).
- Building standalone particular/discount/fine creation flows inside
  `create_fees.html` (deferred — `master_fees.html`/`fine_slabs.html`
  already own this responsibility; duplicating it would create two places
  that mutate the same entities).
- Reports, PDFs, payroll/payslip screens, tally export, QuickBooks
  settings/webhook-review, donations — later pass.
