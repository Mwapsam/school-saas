# Phase 3: Genuinely Neutral Product UI — Planning & Scoping

**Status:** Planning  
**Date:** 2026-09-13  
**Scope:** Extract tenant-neutral product design system from Pinewood-specific CSS  

---

## Problem Statement

**Current state:**
- `static/css/pinewood-ui.css` (~1200 lines) embeds Pinewood identity at the CSS token level
- Green color scheme (`#1a7a3c`, `#145f2e`, etc.) saturates typography, components, messaging
- Class names (`.pinewood-table`, `.pinewood-ui-*`) reinforce Pinewood specificity
- Design system is not tenant-agnostic; branding is architectural, not layered

**What this means:**
Creating a second tenant (different currency, colors, term structure) still renders with Pinewood green tables, badges, buttons, alerts, modals — even with different branding config.

**The fix:** 
Extract a **neutral product design system** (tokens, components, semantics) that is independent of any school's identity. Tenant branding becomes a **thin CSS layer** that only overrides:
- Primary/secondary colors
- Logo position
- School name in headers/footers

---

## Architecture

### Layer 1: Neutral Product Design System (NEW)
**File:** `static/css/product-ui.css`  
**Size:** ~800 lines (extracted from pinewood-ui.css)

Components (all neutral, no Pinewood green):
- Typography (Georgia for headings, Trebuchet for body — reusable)
- Surfaces (cards, modals, dialogs — gray/white base)
- Navigation (topbar, sidebar, breadcrumbs — neutral dark)
- Tables (neutral header, hover states)
- Forms (inputs, labels, validation — system colors)
- Status (badges, alerts, success/warning/danger — semantic only)
- Buttons (outline, primary, danger — semantic, no green default)
- Layout (spacing, grid, breakpoints)
- Data display (stat cards, empty states, reports)

**Key principle:** No color hardcoding except for semantic meanings (danger=red, success=green-ish, warning=orange, info=blue).

### Layer 2: Tenant Branding Overrides (NEW)
**File:** `static/css/tenant-branding.css`  
**Size:** ~100 lines

Root tokens that can be injected per-tenant:
```css
:root {
  /* Branding colors (tenant-specific) */
  --tenant-primary: var(--bootstrap-default-green);  /* Falls back to neutral if not set */
  --tenant-secondary: var(--bootstrap-default-teal);
  --tenant-accent: var(--bootstrap-default-blue);
  
  /* Semantic reuse of tenant primary */
  --product-brand: var(--tenant-primary);
  --product-brand-dark: adjust-darker(var(--tenant-primary));  /* Derived via CSS */
  --product-brand-bg: adjust-lighter(var(--tenant-primary));
}

/* Tenant branding applied narrowly */
.topbar { background: var(--product-brand); }  /* Only accent, not entire bar */
.pw-btn-primary { background: var(--product-brand); }  /* Semantic button only */
.stat-card__accent { color: var(--product-brand); }  /* Icon accent only */
```

The key difference: `product-ui.css` uses semantics (`--product-brand`); tenant overrides only provide the value via template context.

### Layer 3: Legacy Pinewood CSS (DEPRECATED)
**File:** `static/css/pinewood-ui.css` (will be phased out)

During Phase 3:
1. Extract neutral components → `product-ui.css`
2. Keep `.pinewood-*` class aliases → still work for old templates
3. Migrate high-value pages (dashboard, students, admissions, fees) to use product-ui + tenant-branding
4. Deprecate `.pinewood-table`, `.pinewood-card` etc. across rest of app

By end of Phase 3:
- New work uses only `product-ui` + `tenant-branding`
- Old templates still work via `pinewood-ui` aliases (compatibility layer)
- Slow migration path for remaining 200+ templates

---

## Detailed Scope

### Extract Neutral Components (product-ui.css)

| Component | Lines | Neutrality Issues | Migration Path |
|-----------|-------|-------------------|-----------------|
| Typography (.pw-serif, .pw-ui) | 2 | None — fonts are already neutral | Keep exact |
| Page header (.page-header, .pw-page-title) | 50 | Gray background, no green | Keep exact |
| Card (.pw-card, .pw-card-header) | 20 | Gray border, neutral | Keep exact |
| Stat cards (.pw-stat-card, .pw-stat-grid) | 25 | ❌ Green-only colors hardcoded | Extract green → --product-brand |
| Badges (.pw-badge, .pw-badge-active) | 15 | ❌ Green hardcoded | Extract green → --product-brand |
| Buttons (.pw-btn, .pw-btn-primary) | 35 | ❌ Green primary hardcoded | Extract green → --product-brand |
| Table (.pw-table, .pinewood-table) | 150 | ❌ Green header, green hover | Extract green → --product-brand |
| Alerts (.pw-alert, .pw-alert-success) | 20 | ✅ Semantic (success/warning/error) | Keep exact |
| Modals (.pw-modal, .pw-modal-header) | 40 | ❌ Green header | Extract green → --product-brand |
| Breadcrumb (.pw-breadcrumb) | 15 | ❌ Green links | Extract green → --product-brand |
| Empty state (.empty-state) | 40 | ❌ Green icon bg | Extract green → --product-brand |
| Form controls (.pw-form-control) | 10 | ❌ Green focus outline | Extract green → --product-brand |
| Tabs (.pw-tabs) | 5 | ❌ Green active state | Extract green → --product-brand |
| **Total** | **~422** | **~15 hardcoded green** | Extract all |

**Neutral (no extraction needed):** Typography, page structure, spacing, spacing, grids, breakpoints, status semantic colors (danger/warning/info stay red/orange/blue).

**Needs extraction:** Every component that uses `--p-green` or `--color-brand` (currently aliased to green).

### Tenant Branding Layer (tenant-branding.css)

Provided by template context (Django variable):
```python
# views/base.py or settings loader
TENANT_COLORS = {
    'pinewood': {
        'primary': '#1a7a3c',
        'primary_dark': '#145f2e',
        'primary_light': '#e8f5ed',
    },
    'example_intl': {
        'primary': '#1565c0',  # Blue
        'primary_dark': '#0d47a1',
        'primary_light': '#e3f2fd',
    }
}
```

CSS generation:
```html
<style>
:root {
  --product-primary: {{ tenant.primary_color }};
  --product-primary-dark: {{ tenant.primary_color_dark }};
  --product-primary-light: {{ tenant.primary_color_light }};
}
</style>
```

Selectively applied to key visual elements:
- `.topbar { border-left: 4px solid var(--product-primary); }`
- `.pw-btn-primary { background: var(--product-primary); }`
- `.stat-card__accent { color: var(--product-primary); }`
- `.page-header { border-left-color: var(--product-primary); }`

NOT applied (remain neutral):
- Table headers (use system gray instead of brand color)
- Body backgrounds
- Form inputs
- Borders
- Text colors

---

## Implementation Plan

### Phase 3a: Extract Neutral Design System (~4 hours)

1. **Create `static/css/product-ui.css`** (800 lines)
   - Copy all `.pw-*` components from `pinewood-ui.css`
   - Replace `--p-green` with `--product-brand` in:
     - `.pw-stat-card { background: var(--product-brand-light); }`
     - `.pw-btn-primary { background: var(--product-brand); }`
     - `.pw-badge-active { color: var(--product-brand); }`
     - `.pw-modal-header { background: var(--product-brand); }`
     - `.pw-table thead tr { background: var(--product-brand); }`
     - `.pw-breadcrumb a { color: var(--product-brand); }`
     - And ~15 other hardcoded green references
   - Ensure all semantic colors (danger, warning, info) remain independent

2. **Keep `pinewood-ui.css` as compatibility layer**
   - Import `product-ui.css` first
   - Override with green-specific values for old pages
   - Add deprecation note at top

3. **Create `static/css/tenant-branding.css`** (100 lines)
   - Define `--product-brand`, `--product-brand-dark`, `--product-brand-light` from tenant config
   - Apply only to high-value visual elements (icons, buttons, accents)

4. **Update `templates/core/base.html`**
   ```html
   <link rel="stylesheet" href="{% static 'css/product-ui.css' %}">
   <style>
     :root {
       --product-brand: {{ request.tenant.primary_color }};
       --product-brand-dark: {{ request.tenant.primary_color_dark }};
       --product-brand-light: {{ request.tenant.primary_color_light }};
     }
   </style>
   <link rel="stylesheet" href="{% static 'css/pinewood-ui.css' %}">
   ```

### Phase 3b: Migrate High-Value Pages (~6 hours)

Update templates for fastest ROI (most tenant-visible):
1. `templates/dashboard.html` — stat cards, report cards
2. `templates/students/list.html` — table headers, actions
3. `templates/admissions/list.html` — status badges, filters
4. `templates/finance/list.html` — balance cards, buttons
5. `templates/attendance/list.html` — tables, status

Change: Remove `.pinewood-table` → use `.pw-table` (now neutral + tenant branding)

### Phase 3c: Admin UI — Permission Codename Migration (~3 hours)

While design system extraction runs in parallel:
- Audit `core/admin/` for legacy codename references
- Update role admin UI to display canonical codenames
- Migrate fixture seeds (if any) from legacy → canonical

This work is independent of CSS refactoring.

---

## Success Criteria

✅ **Two tenants render distinctly:**
```
Pinewood: green tables, badges, buttons
Example Intl: blue tables, badges, buttons
Zero CSS changes needed — color comes from context only
```

✅ **New component work uses product-ui only**  
No new `.pinewood-*` classes created; all new work inherits tenant branding.

✅ **Old templates still work**  
Pages not yet migrated continue to render with Pinewood green via `pinewood-ui.css` compatibility layer. No broken pages.

✅ **Branding is thin**  
Logo, school name, and primary color accents are customizable per tenant. Neutral UI (tables, forms, dialogs, empty states) remain consistent across all tenants.

---

## Risk Mitigation

**Risk:** Extracting green from CSS breaks old pages  
**Mitigation:** Keep `pinewood-ui.css` as fallback; test all pages before full migration

**Risk:** Tenant branding colors don't derive properly (light/dark variants)  
**Mitigation:** Pre-compute color variants in backend (`TenantColorService.derive_variants()`) rather than CSS calc

**Risk:** High-value pages still have hardcoded green in templates  
**Mitigation:** Grep `style="color: #1a7a3c"` in templates during audit; replace with CSS variables

---

## Timeline

| Phase | Task | Est. Time | Owner |
|-------|------|-----------|-------|
| 3a | Extract product-ui.css | 2h | Design system |
| 3a | Create tenant-branding layer | 1h | Design system |
| 3a | Update base.html template load | 0.5h | Design system |
| 3a | QA: old pages still work | 0.5h | QA |
| 3b | Migrate 5 high-value pages | 3h | Frontend |
| 3b | QA & visual regression testing | 2h | QA |
| 3c | Permission codename admin UI | 2h | Backend |
| 3c | Audit & migrate role fixtures | 1h | Backend |
| **Total** | | **12 hours** | |

---

## Deliverables

1. ✅ `static/css/product-ui.css` — 800-line neutral design system
2. ✅ `static/css/tenant-branding.css` — tenant color injection
3. ✅ Updated `templates/core/base.html` — dynamic color loading
4. ✅ 5+ migrated templates — high-value pages using new system
5. ✅ `PHASE_3_DESIGN_SYSTEM.md` — component documentation
6. ✅ Git commit: "Extract neutral product design system; migrate high-value templates"

---

## What Happens After Phase 3

**Immediately ready:**
- Multi-tenant demo with distinct branding (Pinewood green, Example Intl blue, etc.)
- Role admin UI with canonical permission codenames
- Stable REST API (Phase 2.1)

**Phase 4:** Modernize remaining Django staff templates (280+ pages); apply product UI incrementally  
**Phase 5:** Build customer portal in Next.js against the now-hardened API + neutral design system

---

## Success Definition

A developer or product manager can:
1. Create a new tenant (TenantFactory with primary_color='#1565c0')
2. Login to that tenant
3. See the entire staff UI render in blue (not green)
4. See permission roles with canonical codenames in admin
5. All without changing Python, JavaScript, or CSS

That is the **moment Phase 3 is complete**.
