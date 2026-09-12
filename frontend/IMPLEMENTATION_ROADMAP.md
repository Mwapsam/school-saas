# Design System Implementation Roadmap

## ✅ Completed Phases (1-7)

### Phase 1: Design Principles
- ✅ [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) — comprehensive design philosophy and principles
- ✅ Principles: Calm, Clear, Spacious, Hierarchical, Progressive, Consistent, Responsive

### Phase 2: Tokens
- ✅ `design-system/tokens/colors.ts` — semantic color tokens with tenant branding support
- ✅ `design-system/tokens/typography.ts` — fixed typography scale (Display/H1-H3/Body/Caption)
- ✅ `design-system/tokens/spacing.ts` — responsive spacing scale
- ✅ `design-system/tokens/radius.ts` — border radius scale
- ✅ `design-system/tokens/shadows.ts` — elevation levels (none/subtle/floating)
- ✅ `design-system/tokens/motion.ts` — animation durations and easing
- ✅ `design-system/tokens/density.ts` — density presets (comfortable/compact/dense)

### Phase 3: MUI Theme
- ✅ `design-system/theme/createTheme.ts` — full component overrides for Button, TextField, Card, Dialog, etc.
- ✅ Palette configuration with automatic light/dark shades from tenant colors
- ✅ Readable text color selection (WCAG luminance)
- ✅ `lib/theme.ts` — updated to use new token-based factory

### Phase 4: App Shell
- ✅ `components/layout/DashboardShell.tsx` — responsive, collapsible sidebar layout
- ✅ `components/layout/TopBar.tsx` — modern top bar with logo and user menu
- ✅ `components/layout/Sidebar.tsx` — icon-based navigation with search and collapsible groups
- ✅ Responsive widths: Desktop (280→72px), Tablet (240→64px), Mobile (drawer overlay)

### Phase 5: Core Components
- ✅ `components/page/Page.tsx` — consistent page wrapper
- ✅ `components/page/PageHeader.tsx` — title + description + actions
- ✅ `components/page/PageContent.tsx` — content area wrapper
- ✅ `components/feedback/ConfirmDialog.tsx` — styled confirmation dialogs
- ✅ `components/feedback/EmptyState.tsx` — empty list/table state
- ✅ `components/feedback/LoadingState.tsx` — loading spinner/skeleton
- ✅ `components/feedback/ErrorState.tsx` — error display with retry
- ✅ `components/forms/FormSection.tsx` — grouped form fields
- ✅ `components/forms/FormActions.tsx` — save/cancel button group
- ✅ `components/data/StatusBadge.tsx` — semantic status display

### Phase 6: Design System Playground
- ✅ `/design-system` route — visual testing page showing all tokens and components

### Phase 7: Students Reference Module
- ✅ `app/dashboard/students/page.tsx` — list page with new components
- ✅ `app/dashboard/students/create/page.tsx` — create page with new layout
- ✅ `app/dashboard/students/[id]/page.tsx` — detail page using Page/PageHeader/PageContent
- ✅ `app/dashboard/students/[id]/edit/page.tsx` — edit page with design system components

---

## ✅ Completed Phases (continued)

### Phase 8: Validate & Refine
**Goal:** Ensure design system works across all page types and edge cases

**Completed tasks:**
1. ✅ Complete Students module (detail + edit pages)
   - ✅ Updated [students/[id]/page.tsx](app/dashboard/students/[id]/page.tsx) with Page/PageHeader/PageContent, LoadingState, ErrorState
   - ✅ Updated [students/[id]/edit/page.tsx](app/dashboard/students/[id]/edit/page.tsx) with new design system layout
   - Ready for browser testing of all CRUD flows

---

## 🚀 Phase 9: Migrate Remaining Modules (95% Complete)
**Goal:** Apply design system to all other module pages

**List pages completed (8 modules):**
- ✅ `app/dashboard/students/` — full CRUD (list, create, edit, detail)
- ✅ `app/dashboard/admissions/page.tsx` — list page 
- ✅ `app/dashboard/invoices/page.tsx` — list page
- ✅ `app/dashboard/books/page.tsx` — list page (Library)
- ✅ `app/dashboard/employees/page.tsx` — list page (HR) with ConfirmDialog for delete
- ✅ `app/dashboard/routes/page.tsx` — list page (Transport)
- ✅ `app/dashboard/hostel-rooms/page.tsx` — list page (Hostel)
- ✅ `app/dashboard/inquiries/page.tsx` — list page (Admissions Enquiries)

**Create pages completed:**
- ✅ `app/dashboard/admissions/create/page.tsx` — new application form
- ✅ `app/dashboard/employees/create/page.tsx` — new employee form
- ✅ `app/dashboard/inquiries/create/page.tsx` — new enquiry form

**Detail pages completed:**
- ✅ `app/dashboard/invoices/[id]/page.tsx` — invoice detail with StatusBadge
- ✅ `app/dashboard/books/[id]/page.tsx` — book detail with design system
- ✅ `app/dashboard/employees/[id]/page.tsx` — employee detail with StatusBadge
- ✅ `app/dashboard/inquiries/[id]/page.tsx` — enquiry detail with tabs and ConfirmDialog
- ✅ `app/dashboard/routes/[id]/page.tsx` — route detail with design system
- ✅ `app/dashboard/hostel-rooms/[id]/page.tsx` — room detail with design system
- ✅ `app/dashboard/admissions/multi-step/[id]/page.tsx` — multi-step admission wizard

**Edit pages completed:**
- ✅ `app/dashboard/employees/[id]/edit/page.tsx` — employee edit with design system

**Placeholder pages (not yet implemented):**
- `app/dashboard/batches/page.tsx` — ComingSoon
- `app/dashboard/courses/page.tsx` — ComingSoon
- `app/dashboard/vehicles/page.tsx` — ComingSoon (Transport)
- `app/dashboard/hostel-assignments/page.tsx` — ComingSoon
- `app/dashboard/borrowing/page.tsx` — ComingSoon (Library)
- `app/dashboard/transport-staff/page.tsx` — ComingSoon

**Remaining work for Phase 9:**
- Nested detail/edit pages for invoices (fee-categories, fee-discounts)
- Admissions applicants list/detail page
- Browser testing of all updated modules

**Phase 10 (Pending):**
- Tenant branding (colors, logo, fonts, favicon)
- Settings page for branding customization

---

### Phase 9: Migrate Remaining Modules
**Goal:** Apply design system to all other module pages

**Modules to migrate** (in priority order):

#### High Priority (data-heavy, most-used):
1. **Admissions** (`app/dashboard/admissions/` + `app/dashboard/inquiries/`)
   - List, Create, Edit, Detail for Applications
   - Inquiries list and detail
   - Multi-step form for new applications

2. **Finance / Invoices** (`app/dashboard/invoices/`)
   - Invoice list with filtering/export
   - Invoice detail with payment info
   - Fee categories, discounts, transactions
   - Student ledger views

3. **Library** (`app/dashboard/books/` + `app/dashboard/borrowing/`)
   - Books list with search
   - Borrowing records and returns
   - Inventory management

#### Medium Priority:
4. **HR** (`app/dashboard/employees/`)
   - Employee list
   - Leave management
   - Attendance tracking

5. **Hostel** (`app/dashboard/hostel-rooms/` + `app/dashboard/hostel-assignments/`)
   - Rooms and assignments
   - Occupancy management

6. **Transport** (`app/dashboard/routes/` + `app/dashboard/vehicles/`)
   - Routes list
   - Vehicle management
   - Staff assignments

#### Template per module:
```tsx
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { DataTable } from '@/components/data-table/DataTable';
import { Button } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';

export default function ModuleListPage() {
  // ... module-specific logic
  
  return (
    <Page>
      <PageHeader
        title="Module Title"
        description="Brief description"
        actions={
          <Button variant="contained" startIcon={<AddIcon />}>
            New Item
          </Button>
        }
      />
      
      <PageContent>
        <DataTable
          rows={data}
          columns={columns}
          // ... table props
        />
      </PageContent>
    </Page>
  );
}
```

**Batch migration approach:**
- Week 1: Admissions + Invoices
- Week 2: Library + HR
- Week 3: Hostel + Transport + Settings

**Success criteria:**
- All module pages use Page/PageHeader/PageContent
- No raw Container/Box/Typography patterns
- StatusBadge used for semantic display
- ConfirmDialog replaces all window.confirm() calls
- Consistent spacing and typography across all pages

---

### Phase 10: Tenant Branding
**Goal:** Enable per-school brand customization (colors, logo, font)

#### Backend Work:

1. **Model fields** (`core/models.py`, School model)
   ```python
   primary_color = CharField(max_length=7, default='#3b82f6')  # hex color
   secondary_color = CharField(max_length=7, default='#7c3aed')
   font_family = CharField(max_length=50, choices=FONT_CHOICES, default='inter')
   favicon = ImageField(upload_to='school_logos/', null=True, blank=True)
   ```

2. **Migration**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

3. **Django admin** (`core/admin/tenant.py`, SchoolAdmin)
   - Add color picker widgets for primary/secondary
   - Add favicon upload field
   - Add font family dropdown
   - Group these in "Branding" fieldset

4. **Bootstrap serializer** (`core/api/bootstrap.py`)
   ```python
   tenant_data = {
     ...existing fields...,
     'primary_color': school.primary_color,
     'secondary_color': school.secondary_color,
     'font_family': school.font_family,
     'favicon_url': school.favicon.url if school.favicon else None,
   }
   ```

5. **Self-service PATCH endpoint**
   - Route: `PATCH /api/v1/schools/{id}/` or `PATCH /api/v1/settings/branding/`
   - Permission: school-admin role, scoped to own tenant
   - Accept: `primary_color`, `secondary_color`, `font_family`, `logo`, `favicon`
   - Response: updated bootstrap data

#### Frontend Work:

1. **Bootstrap contract** (`frontend/lib/tenant/bootstrap.ts`)
   ```typescript
   interface TenantBranding {
     primary_color?: string;
     secondary_color?: string;
     font_family?: string;  // 'inter' | 'roboto' | 'poppins' | 'system'
     favicon_url?: string;
     logo_url?: string;
     logo_secondary_url?: string;
   }
   ```

2. **Theme integration** (`frontend/design-system/theme/createTheme.ts`)
   - Accept tenant branding in buildTheme()
   - Apply primary/secondary color overrides
   - Load appropriate font via next/font if not default
   - Auto-compute light/dark shades using buildPaletteConfig()

3. **Settings page** (`frontend/app/dashboard/settings/branding/page.tsx`)
   - Form with color pickers for primary/secondary
   - Curated font dropdown (Inter, Roboto, Poppins, system)
   - Logo upload preview
   - Favicon upload preview
   - Live preview of button/badge/form with chosen colors
   - Save button that calls PATCH endpoint
   - Refresh bootstrap and theme on save

4. **TopBar logo rendering**
   - Already done: `components/layout/TopBar.tsx` displays `logo_url`

5. **Favicon injection** (`frontend/app/layout.tsx`)
   ```tsx
   <link rel="icon" href={bootstrap?.tenant.favicon_url} />
   ```

#### Curated font list:
```typescript
const FONT_CHOICES = [
  { value: 'inter', label: 'Inter', installed: true },
  { value: 'roboto', label: 'Roboto', installed: true },
  { value: 'poppins', label: 'Poppins', installed: true },
  { value: 'system', label: 'System Font', installed: true },
];
```

**Success criteria:**
- School can set primary/secondary colors via Django admin
- School admin can change branding in self-service settings page
- Colors apply to buttons, forms, badges, links, etc.
- Font selection persists and loads via next/font
- Logo displays in TopBar
- Favicon renders in browser tab
- Theme updates immediately on save (no page reload required)
- Multi-tenant: each school sees only its own branding

---

## 🎯 Summary of Remaining Work

**Phase 8:** ~2-3 hours
- Complete Students CRUD pages
- Test all components and responsive behavior
- Bug fixes as needed

**Phase 9:** ~1-2 weeks
- Update 6+ modules following the template
- Batch work: frontend + backend in parallel
- ~3-4 pages per module × 6 modules = 18-24 page updates

**Phase 10:** ~2-3 days
- Backend: model fields + admin + serializer + endpoint
- Frontend: settings page + theme integration + favicon
- Testing: multi-tenant branding

**Total:** ~2-3 weeks of development for full design system rollout

---

## 📊 Feature Completeness Matrix

| Feature | Phase | Status | Notes |
|---------|-------|--------|-------|
| Design tokens | 2 | ✅ | All tokens defined |
| MUI theme | 3 | ✅ | Component overrides in place |
| App shell | 4 | ✅ | Collapsible sidebar, responsive |
| Page components | 5 | ✅ | Page, PageHeader, PageContent |
| Feedback states | 5 | ✅ | Dialog, EmptyState, Loading, Error |
| Form components | 5 | ✅ | FormSection, FormActions |
| Playground | 6 | ✅ | Visual testing route |
| Students module | 8 | ✅ | List, Create, Edit, Detail all done (ready for browser test) |
| Other modules | 9 | ⏳ | Admissions, Finance, Library, HR, etc. |
| Tenant branding | 10 | ⏳ | Model fields, settings page, API |

---

## 🚀 Quick Start Next Steps

1. **Immediate** (today):
   - Test `/design-system` playground in browser
   - Complete Students detail + edit pages
   - Test full Students CRUD flow

2. **This week**:
   - Fix any issues found during testing
   - Start Admissions + Invoices migration
   - Set up database migrations for Phase 10

3. **Next week**:
   - Complete module migrations
   - Begin tenant branding work
   - User acceptance testing

---

## 📝 Notes

- Each migrated page should follow the Students template exactly
- Use consistent naming: Page, PageHeader, PageContent, DataTable, ConfirmDialog
- All destructive actions (delete) should use ConfirmDialog
- All empty states should use EmptyState component
- All loading states should use LoadingState component
- All error states should use ErrorState component
- Leverage existing hooks and data-fetching patterns (useServerTable, useXxxList, useDeleteXxx)
- No exceptions: the design system is the source of truth for styling

