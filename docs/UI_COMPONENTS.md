# Pinewood UI components

Design tokens live in `static/css/pinewood-ui.css` (`--p-*` custom properties,
`pw-*` classes). Reusable structural components live in
`templates/core/components/`. Canonical page-layout skeletons (dashboard,
list, detail, form) live in `templates/core/layouts/`.

**Governing rule:** feature templates describe business content; components
and the design system describe presentation. A feature template should not
contain a `<style>` block, a hand-written button/card/table/badge/modal, or
its own header markup — it composes the components below instead. If several
pages need something a component doesn't do yet, extend the component with a
new parameter or variant; don't hand-roll a one-off.

## Component inventory

| Component | Key parameters |
|---|---|
| `page_header.html` | `title`, `description`/`subtitle`, `breadcrumbs`/`crumbs`, `icon`, `actions`, `back_url`, `variant` — see the file's own comment for the two layouts it renders |
| `button.html` | `label`, `variant` (primary/outline/danger), `url`, `type`, `icon`, `size`, `disabled`, `loading`, `attrs` |
| `badge.html` | `label`, `variant` (active/zero) |
| `card_open.html` / `card_close.html` | `title`, `meta`, `actions` — open/close pair (see note below) |
| `table_open.html` / `table_close.html` | `columns` (strings or `{label, sort_key}` dicts), `sortable` — open/close pair; renders the `.pinewood-table` system (dominant in production, not `.pw-table`) |
| `form_field.html` | `name`, `label`, `type` (text/number/email/date/textarea/select/checkbox), `value`, `placeholder`, `required`, `help_text`, `errors`, `options`, `rows`, `checked`, `attrs` |
| `modal.html` / `modal_close.html` | `id`, `title`, `size`, `variant` (danger), `icon`, `subtitle`, `title_id`, `footer` — open/close pair; confirmation/form/CRUD are usage patterns built on this foundation, not separate files |
| `pagination.html` | `page_obj`, `preserve_query`, `hx_target`, `show_first_last`, `numbered` (windowed page-number variant) |
| `empty_state.html` | `title`, `message`, `icon`, `action_url`, `action_label` |
| `alert.html` | `message`, `variant`, `dismissible` |
| `tabs.html` | `items`, `active` |
| `toolbar.html` | `search_name`, `search_value`, `search_placeholder`, `filters`, `clear_url` |
| `loading_state.html` | `message` |
| `stat_cards.html` | `stats` (list of `{label, value, small?, icon?, variant?}`) — `icon`+`variant` render a colored icon above the value |
| `nav_tile.html` | `icon`, `title`, `description`, `url` — one link-card in a dashboard's tile grid; feature template loops over a `dashboard_tiles` list and wraps each include in its own grid column |

**Why some components are file pairs, not one file:** Django's `{% include %}`
can't pass block content into the included template, so a component that
must wrap arbitrary caller content (a card body, a table's rows, a modal's
form) is implemented as an `_open`/`_close` pair with the caller's markup in
between. Components that only render a fixed, self-contained chunk
(`button`, `badge`, `pagination`, ...) are a single file.

## Page layouts

Each layout is a thin, structure-only skeleton — `{% extends 'core/base.html' %}`,
override `content` with a fixed sequence of empty named blocks, nothing else.
The rule this enforces: **layout = where things go, component = how things
look, feature template = what the business needs.** A layout never contains
business logic or a component's own markup — it just says "the header block
comes before the filters block."

| Layout | Blocks, in fixed order | Drafted against |
|---|---|---|
| `layouts/dashboard.html` | `layout_header` → `layout_stats` → `layout_primary` → `layout_secondary` | `core/hr/dashboard.html` |
| `layouts/list.html` | `layout_header` → `layout_filters` → `layout_table` → `layout_pagination` → `layout_extra` | `core/admission/list.html` |
| `layouts/detail.html` | `layout_header` → `layout_summary` → `layout_tabs` → `layout_sections` → `layout_extra` | `core/admission/detail.html`, `core/htmx/batch_detail_content.html` |
| `layouts/form.html` | `layout_header` → `layout_form` → `layout_validation` → `layout_actions` | `core/fees/payment_agreement_form.html` |

A feature template overrides only the blocks it needs (an empty block just
renders nothing — no crash, no placeholder). `layout_tabs` in particular is
meant to be omitted on the many detail pages that have no tabs. Fill each
block with `{% include %}`s of the components above; see each layout file's
own `{% comment %}` for a full worked example.

## A pitfall to avoid when extending these components

Django tolerates a missing/undefined variable when it's the *base* of an
output expression or an `{% if %}`/`{% for %}` test — it silently becomes
empty/falsy. It does **not** tolerate a missing variable used as a **filter
argument** (e.g. `{{ description|default:subtitle }}` where `subtitle` was
never passed in at all) — that raises `VariableDoesNotExist` and crashes the
page. This is exactly the bug the two-alias support in `page_header.html`
hit during Phase 1; the fix is `{% firstof description subtitle as x %}`
instead of `default:`. Prefer `{% firstof %}` (or restructure with
`{% if %}`) any time a component supports two alias names for the same
optional parameter.

## The `page_title` block

`core/base.html`'s `<title>` tag reads `{% block page_title %}`. Before
Phase 1, the majority of templates (104 of them) were overriding a
non-existent `{% block title %}` — Django silently discards a child block
that doesn't exist in any ancestor, so those pages' browser tabs all showed
the generic default title, not the page's own name. Phase 1 fixed
`core/base.html` and the 31 templates that had the wrong block name wired to
`core/base.html` (three other templates — `templates/admin/index.html` and
the two pages under `templates/core/portal/`— correctly use `{% block
title %}` against their own, different base templates and were left alone).
Use `{% block page_title %}Your Page Name{% endblock %}` in any new template
extending `core/base.html`.

## JS interaction direction

htmx is the standard for new or migrated interactive pages — it already
matches how `templates/core/htmx/**` fragments are built and swapped.
Existing jQuery/Alpine.js pages are **not** force-migrated; convert a page's
JS only when you're already touching that page for another reason (Phase 2
migration, a bug fix, etc.), not as a standalone task.

## Migration status (Phase 2)

| Module | Page | Pattern | Status |
|---|---|---|---|
| Students | List | `layouts/list` | migrated (golden module) |
| Students | Detail | `layouts/detail` | migrated (golden module) |
| Students | Edit | `layouts/form` | migrated (golden module) |
| Students | List (API/Alpine variant) | `layouts/list` | migrated (golden module) |
| Admission | Dashboard | `layouts/dashboard` | migrated |
| Gradebook | Index | `layouts/dashboard` | migrated |
| HR | Dashboard | `layouts/dashboard` | migrated |
| Finance | Dashboard | `layouts/dashboard` | migrated |
| Admission | List | `layouts/list` | migrated |
| Fees | Category List | `layouts/list` | migrated |
| Academic | Courses | `layouts/list` | migrated |
| Finance | Day Book | `layouts/list` | migrated |
| Admission | Detail | `layouts/detail` | migrated |
| Fees | Student Management (Collect Fees) | `layouts/detail` | migrated |
| Fees | Fee Masters | `layouts/detail` | migrated |

**Discovered during 2a:** the four dashboard pages shared one more
hand-written pattern beyond the header — a grid of link-cards (`.gb-card`)
pointing at each sub-module. Extracted as `nav_tile.html` above; each
dashboard view now passes a `dashboard_tiles` context list instead of the
template hardcoding `{% url %}` calls inline. `hr/dashboard.html` and
`finance/dashboard.html` also dropped their
`{% include 'core/finance/_finance_ui_styles.html' %}` — that partial only
re-declares `.page-header`/`.gb-card`, which Phase 0 already made global via
`pinewood-ui.css`. The partial itself is left in place (still included by
~14 other not-yet-migrated finance templates) — full removal is Phase 4,
once nothing references it.

**Discovered during 2b:**
- **`nav_tile.html` is unrelated; two other real gaps surfaced instead.**
  Course, category, and application list pages all had their own hand-rolled
  create/edit/delete `<div class="modal fade">` markup — migrated onto
  `modal.html`/`modal_close.html`. One case (`courses.html`'s Save button,
  which swaps to a spinner mid-submit) didn't fit the generic footer
  contract; kept a hand-written `.modal-footer` there since the lint only
  guards the outer `class="modal"` wrapper, not the footer's own classes.
- **`pagination.html` gained a `numbered` variant** — a windowed
  Previous/1…5/Next pager, found hand-rolled identically in 9 templates
  (`courses.html` plus 8 more still pending migration). Added as an opt-in
  parameter rather than a second component, so those 8 pick it up for free
  when their turn comes.
- **`stat_cards.html` gained optional `icon`/`variant`** — `admission/list.html`'s
  four colored-icon summary cards were a second stat-card convention
  alongside the plain green `pw-stat-card` grid already used by
  `gradebook_management.html`. Consolidated onto one component/one visual
  style (colored icon, same green card) rather than keeping both.
- Promoted two more page-local `<style>` blocks to globals in
  `pinewood-ui.css`: `.avatar-sm`/`.avatar-title` (small initials badge,
  reused by several other still-unmigrated templates) and `.course-card`'s
  hover/header/footer rules (specific to the course grid, but a real style
  a feature template can no longer define inline post-Phase-0).
- `academic/courses.html`'s complex multi-section course card (dropdown
  menu, footer stats) was deliberately **not** forced onto `card_open.html` —
  that component's header slot only fits a title/meta/actions row, and
  bending it to fit would mean hand-rolling the dropdown/footer inside the
  body slot anyway. Left as page-owned markup, same judgment call as
  `layouts/detail.html` leaving nested tabs alone in Phase 1.5.

**Discovered during 2c** (`admission/detail.html`, `fees/fee_masters.html`,
`fees/student_management.html` — the three highest-risk, largest files in
the plan):
- **`modal.html` gained `icon`, `subtitle`, and `title_id`.** Several CRUD
  modals (fee masters' particular/discount/rule modals) have a title that
  swaps between "Create X" / "Edit X" via JS acting on a specific inner
  `<span>` id, plus a muted subtitle line under the title — neither fit the
  original plain-string `title`. Added as optional params rather than a
  second modal component.
- **Bootstrap-native tabs, again left alone.** `fee_masters.html`'s three
  tabs (Particulars/Discounts/Rules) use Bootstrap's own
  `data-bs-toggle="tab"` mechanism. `components/tabs.html` renders a
  different DOM shape (`data-tab-key` buttons with no built-in show/hide
  JS) — forcing the switch would mean writing new JS for behavior Bootstrap
  already provides for free. Same call as Students detail.html in Phase 1.5.
- **A conservative rule for these three files specifically:** each page's
  `extra_css`/`extra_js` block was left **byte-for-byte untouched** — only
  the `content` block was restructured into layout blocks. This was a
  deliberate risk reduction for the highest-stakes files: it keeps the
  diff small enough to review at a glance, and (checked via `git diff`)
  guarantees the diff-aware lint never sees the JS-generated modal HTML
  strings inside `admission/detail.html`'s `admitStudent()`/`assignBatch()`
  functions as new violations. `student_management.html` had no separate
  `extra_js` block at all (its `<script>` sat directly in `content`) — it
  was relocated verbatim into a proper `{% block extra_js %}`, which is a
  strict improvement (matches the convention every other migrated page
  uses) and safe here specifically because the whole script turned out to
  already be `DOMContentLoaded`-gated with no top-level side effects.
- Dead CSS was knowingly left behind in the untouched style blocks —
  `.adm-detail-header` (admission/detail.html), `.page-header`/
  `.breadcrumb-sm` (fee_masters.html, which also collided with
  `pinewood-ui.css`'s own `.page-header` class before this migration).
  Removing it would have required touching the style blocks, which the
  rule above avoids. Left for the Phase 4 dead-CSS sweep.
- Button-color semantics (success/info/warning) don't map 1:1 onto
  `button.html`'s three variants (primary/outline/danger). Where the
  original button was `btn-success`/`btn-info`/`btn-warning`, it was mapped
  to `primary` (green, closest visual match); genuinely destructive actions
  (`btn-danger`) mapped to `danger`. This is a real, intentional palette
  narrowing — consistent with the plan's "one design system" goal — not an
  oversight.

## Phase 3 — consistency and accessibility audit

Ran a full (non-diff) scan of every migrated template for the anti-patterns
the Phase 1 lint only catches going forward, plus a layout-compliance check
and a token contrast check.

**Layout compliance:** every migrated template extends exactly one of the
four canonical layouts — confirmed for all 15 (Students golden module,
Phase 2a dashboards, 2b lists, 2c detail/CRUD). No page has reverted to
hand-rolled top-level structure.

**Real violations found and fixed** (all in the Students golden module —
the reference implementation, so held to the highest bar):
- `students/list.html` / `list_api.html` — the bulk-actions and single-allocate
  modals were still hand-written `<div class="modal fade">` markup from
  before `modal.html` existed in its current form. Converted both.
- `students/detail.html` — two label/value `<table class="table table-sm">`
  blocks (admission info, contact info) and the Attach Guardian modal were
  still raw. Converted all three.
- **Component gap this surfaced:** the bulk-actions modal has no distinct
  footer row — its actions live inline in the body next to their own
  controls (an "Allocate" button beside a batch `<select>`, then separate
  Deactivate/Reactivate buttons). `modal_close.html` always rendered a
  footer (default: a lone "Close" button), so it gained a `no_footer` param
  to suppress that row entirely rather than forcing an unwanted extra button
  onto a modal that never had one.

**A shared-component accessibility fix that benefits every consumer, not
just one page:** `students/list_api.html`'s Alpine-driven table already had
`scope="col"` on every header and a visually-hidden `<caption>` —
*better* accessibility markup than `table_open.html` itself provided at the
time. Rather than strip that down to fit the component, `table_open.html`
was upgraded: every `<th>` now gets `scope="col"`, and a new optional
`caption` param renders a visually-hidden `<caption>`. This is exactly the
kind of fix Phase 3 is for — corrected once in the component, inherited by
every one of its ~20 consumers immediately, no per-page work.

**Findings deliberately left as documented exceptions, not bugs:**
- `admission/detail.html`'s `admitStudent()`/`assignBatch()`/
  `showParentAccountModal()` JS functions build modal HTML as JS template
  strings (client-injected, not server-rendered), and `fee_masters.html`'s
  `viewParticularUsage()`/`viewDiscountUsage()` do the same for a small
  results table. A naive text scan flags the `class="modal"`/`class="table"`
  tokens inside those JS strings, but they aren't Django template markup —
  there's nothing to "convert onto a component" here.
- `fees/student_management.html`'s statement table (`.table-statement`,
  with section/summary/grand-total row styling) and payment-history table
  (`.table-payment-history`) are intentionally distinct from the generic
  `.pinewood-table` grid look — they're a financial-statement layout, not a
  data grid, and forcing them onto `table_open.html` would both change a
  live payment page's visual output and lose row-type styling the component
  doesn't support. Left as page-owned markup; would only be worth
  generalizing into a `table_open` "statement" variant if this pattern
  recurs elsewhere.
- The three pre-existing `<style>` blocks left untouched in `admission/detail.html`,
  `fee_masters.html`, and `student_management.html` during Phase 2c (a
  deliberate risk-reduction choice, documented above) still contain dead
  rules (`.adm-detail-header`, `.page-header`/`.breadcrumb-sm`). Not touched
  now for the same reason; tracked for the Phase 4 dead-CSS sweep.

**Color contrast:** spot-checked the core `pinewood-ui.css` tokens actually
used by text-on-background pairs in the shared components — primary green
on white (`.pw-btn-primary`), green-dark on green-light (`.pw-badge-active`,
`.pw-stat-card`), muted gray on white (`.pw-stat-label`, subtitles), and
danger red on white (`.pw-btn-danger`, `.pw-btn-outline` variants). All
comfortably clear WCAG AA's 4.5:1 text threshold (roughly 5.4:1 to 7.5:1).
No token changes needed.

**Verification:** `manage.py check` and the lint pass clean; every touched
template re-rendered with realistic fake context; confirmed the two
shared-component additions (`table_open.html`'s `scope`/`caption`,
`modal_close.html`'s `no_footer`) are additive and don't affect existing
callers (`gradebook_management.html`, and every Phase 2 template).

## Phase 4 — remove legacy UI

With Phases 0-3 complete, this phase deleted what they made obsolete rather
than leaving old and new conventions sitting side by side indefinitely.
Every removal below was confirmed dead first (grep for remaining references,
or diff-and-render-test where behavior could plausibly change) — nothing
was deleted from memory of what Phase 0-3 intended.

**Deleted outright:**
- `templates/core/styles.html` — already an empty "retired" stub since
  Phase 0 (not `{% include %}`'d anywhere); the file itself is now gone.
- `static/css/tables.css` — its entire `.pinewood-table*` rule set was
  moved into `pinewood-ui.css` back in Phase 0 and has been loaded on every
  page via `base.html` ever since. Its only two remaining consumers
  (`academic/attendance_management.html`, `academic/attendance_reports.html`)
  linked it directly, which made those two pages the last things depending
  on a file that was, in practice, dead weight duplicating rules already in
  force. Removed the `<link>` from both templates and deleted the file.
- `core/templatetags/currency_filters.py` (+ its orphaned
  `currency_display.html` inclusion template, which had no callers anywhere
  in the tree). Per the plan, kept `currency_tags.py` as canonical — it's
  the more consistently `CurrencyService`-backed of the two, with a single
  `_get_service()` helper instead of repeating the tenant-lookup fallback
  logic inline in every function. `currency_filters.py` was still the one
  actually used by more templates at Phase 0 (7 files vs. 4), so retiring
  it meant migrating those 7 call sites, not just deleting a dead file:
  `{% load currency_filters %}` → `{% load currency_tags %}`, and
  `{% format_currency X %}` → `{% currency_format X %}` (the two files
  named their tag-usable entry point differently even though both also
  define same-named `currency_symbol`/`currency_code` tags, which needed no
  change). Touched: `students/detail.html`, `htmx/reports/profile_report.html`,
  `htmx/reports/fee_report.html`, `htmx/student_detail_content.html`,
  `finance/collections/list.html`, `finance/collections/detail.html`.
  `subjects/center.html` had a dead `{% load currency_filters %}` with no
  actual usage — the load line was just removed.

**Dead CSS removed from the three Phase 2c "untouched `extra_css`" blocks**
(flagged as deferred debt at the time, per the Phase 3 write-up above):
- `admission/detail.html` — `.adm-detail-header`/`.adm-detail-icon` rules;
  the markup they styled was replaced by `page_header.html` back in Phase 2c,
  so nothing in the page referenced these classes any more.
- `fees/fee_masters.html` — the `.page-header`/`.page-header h1` rule (the
  page no longer has a `class="page-header"` element — same cause). This one
  mattered slightly more than a plain dead-code removal: `pinewood-ui.css`
  defines its own `.page-header` for the `page_header.html` component this
  page now uses, so the page's dead copy was a live collision risk, not
  just inert bytes. `.breadcrumb-sm` in the same block is still real markup
  (`<ol class="breadcrumb breadcrumb-sm">`) and was left alone, as were the
  page's generic `.card`/`.card-header` overrides — those weren't flagged as
  dead and touching them wasn't part of this phase's scope.
- `fees/student_management.html`'s untouched block had no similarly-dead
  rules to remove (its CSS backs the statement/payment-history tables kept
  as a documented Phase 3 exception, still very much in use).

**Verification:** `manage.py check` and `scripts/lint_ui_consistency.py`
both pass clean (the lint briefly flagged a false positive on the two
attendance templates — collapsing `{% block extra_css %}` and `<style>`
onto one line during the `tables.css` `<link>` removal made a pre-existing
`<style>` tag look, to the diff, like a newly-added line; re-splitting them
back onto separate lines fixed it, since nothing about the style block
itself was actually new). Repo-wide grep confirms zero remaining references
to `core/styles.html`, `tables.css`, or `currency_filters`. A scratch
render test (written, run, deleted) exercised `htmx/reports/fee_report.html`
and `finance/collections/list.html` under their migrated `currency_tags`
calls, and `admission/detail.html` to confirm the removed `.adm-detail-header`
CSS wasn't referenced anywhere in the rendered output — all three rendered
correctly with realistic fake context.

**Left alone, deliberately:**
- `static/css/multi-step-form.css` — genuinely still used by
  `admission/register.html` (never in this plan's migration scope), and its
  rules are page-specific multi-step-form/progress-bar styling with no
  overlap against `pinewood-ui.css` tokens. Not legacy duplication, just a
  live stylesheet for an unmigrated page — nothing to remove.
- Wiring `scripts/lint_ui_consistency.py` into CI (`.github/workflows/django.yml`)
  remains a decision left to the user, as throughout this plan.

This closes the 8-phase UI consolidation plan.
