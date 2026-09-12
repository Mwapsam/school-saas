# School Management Platform — Design System

## Guiding Principle

**Use MUI to build our own design system — don't try to make MUI itself look beautiful.**

If you're repeatedly writing `sx` to make an MUI component look right, the design system probably needs to absorb that decision.

---

## Architecture

The product is built in distinct layers, each with a clear purpose:

```
Product UI (Pages & Application Logic)
        ↓
Application / Product Components
(PageHeader, DataTable, FilterBar, StudentForm, StatCard)
        ↓
Design System Layer
├── Semantic Tokens (colors, typography, spacing, radius, shadows, motion, density)
├── MUI Theme (theme.components overrides mapped to tokens)
└── Design-System Components (Button, Input, Card, Dialog, Badge — visual primitives)
        ↓
MUI (Accessibility primitives, DataGrid, layout primitives, base components)
```

### Layer Separation

**Design-System Components** (`design-system/components/*`)
- Visual primitives concerned with *how things look*
- Button, Input, Card, Dialog, Badge, Chip, etc.
- Reusable across any product built on this design system
- Consume semantic tokens, never hardcoded values
- Example: `<Button variant="primary">Save</Button>` automatically gets the right color, padding, font weight from the theme

**Application / Product Components** (`components/*`)
- Product-specific patterns concerned with *how this application works*
- `layout/`: AppShell, Sidebar, TopBar, MobileNav
- `page/`: Page, PageHeader, PageSection, PageToolbar
- `data/`: DataTable, FilterBar, SearchField, Pagination, StatusBadge
- `forms/`: FormSection, FormActions, FormDialog
- `feedback/`: EmptyState, LoadingState, ErrorState, ConfirmDialog, Snackbar
- `dashboard/`: StatCard, Metric, ActivityList
- Built entirely on top of design-system primitives
- Example: `<Page><PageHeader title="Students" /><PageContent><DataTable /></PageContent></Page>`

---

## Design Principles

These principles inform every design decision:

### 1. Calm
The interface should not feel visually noisy. Use whitespace generously. Avoid unnecessary visual elements. Let the content speak.

### 2. Clear
Users should immediately understand:
- Where they are in the application
- What they're looking at
- What they can do
- What requires their attention

Information architecture and typography do this before color does.

### 3. Spacious
Use generous whitespace instead of excessive borders, cards, and compartmentalization. Three surface levels (Canvas, Surface, Elevated) instead of card-in-card-in-card.

### 4. Hierarchical
Typography should communicate importance before color does. Use the type scale consistently:
- Display & H1: page titles and primary headings
- H2 & H3: section headings and subsections
- Body: primary content
- Body Small: secondary information
- Caption: tertiary/helper text

Weight and size carry the hierarchy. Color is secondary.

### 5. Progressive
Don't expose complexity until the user needs it. Hide advanced filters until they're requested. Show essential information first. Use progressive disclosure.

### 6. Consistent
A button should behave and look the same everywhere. A form, table, or dialog should be consistent across the entire application. This is why we have a design system.

### 7. Responsive
Desktop should not simply be squeezed down into mobile. Layout, spacing, and interaction patterns should adapt thoughtfully to the medium.

---

## Semantic Tokens

Components consume *semantic* token names, never raw scale values. This indirection is what allows the entire application to be restyled centrally.

### Colors

```
colors.background.default      (app canvas)
colors.background.surface      (main content)
colors.background.elevated     (dialogs, menus, floating elements)

colors.text.primary            (primary content)
colors.text.secondary          (secondary content)
colors.text.muted              (hints, helper text)
colors.text.disabled           (disabled states)

colors.border.default          (standard borders)
colors.border.light            (subtle dividers)

colors.action.primary          (primary buttons, links)
colors.action.primaryHover     (primary button hover state)
colors.action.secondary        (secondary buttons)
colors.action.secondaryHover   (secondary button hover state)

colors.status.success          (success messages, valid states)
colors.status.warning          (warnings)
colors.status.error            (errors, destructive actions)
colors.status.info             (informational messages)
colors.status.pending          (pending states)
```

**Usage:**
- Button → `colors.action.primary`
- Table content → `colors.text.primary`
- Table headers → `colors.text.secondary` on `colors.background.surface`
- Success badge → `colors.status.success`
- Input border → `colors.border.default`
- Form helper text → `colors.text.muted`

### Typography

Explicit scale with fixed sizes, line heights, and weights:

| Level | Size | Line Height | Weight | Use |
|-------|------|------------|--------|-----|
| Display | 32px | 40px | 700 | Rare, only app-level titles |
| H1 | 28px | 36px | 700 | Page titles |
| H2 | 24px | 32px | 650 | Section headings |
| H3 | 20px | 28px | 650 | Subsection headings |
| Body | 15px | 24px | 400 | Primary content, default text |
| Body Small | 14px | 20px | 400 | Secondary content |
| Caption | 12px | 18px | 500 | Helper text, labels |

**Key rule:** Font size, line height, and weight never change per tenant. Tenants can only swap the typeface (e.g., Inter → Roboto), and only from a curated list.

### Spacing

Consistent spacing scale based on 4px base unit (MUI default):

```
spacing.xs     = 4px
spacing.sm     = 8px
spacing.md     = 12px
spacing.lg     = 16px
spacing.xl     = 24px
spacing.2xl    = 32px
spacing.3xl    = 48px

// Semantic spacing
spacing.page           = 32px   (page padding)
spacing.section        = 24px   (section margins, group spacing)
spacing.card           = 20px   (card padding)
spacing.component      = 16px   (component internal spacing)
spacing.element        = 12px   (element internal spacing)
```

### Radius

Small, intentional radius values:

```
radius.sm      = 6px    (small elements: badges, small buttons)
radius.md      = 10px   (standard: buttons, inputs, small cards)
radius.lg      = 14px   (larger: cards, dropdowns)
radius.xl      = 20px   (dialogs, major containers)
```

### Shadows / Elevation

Three elevation levels:

```
shadow.none     = none
shadow.subtle   = 0px 1px 2px rgba(0,0,0,0.05)          (hover states, subtle depth)
shadow.floating = 0px 10px 25px rgba(0,0,0,0.1)         (dialogs, menus, floating elements)
```

### Motion

A small, subtle motion scale:

```
motion.fast     = 120ms   (quick feedback: hover states, icon changes)
motion.normal   = 180ms   (standard transitions: drawer open, menu open)
motion.slow     = 250ms   (longer transitions: dialog enter, major state changes)

// Easing: cubic-bezier(0.4, 0, 0.2, 1) (MUI standard)
```

### Density

**Default: Comfortable** (ship only this initially)

```
Comfortable:
  Page spacing         32px
  Section spacing      24px
  Table row height     52px
  Input height         40px
  Button height        40px

Compact (defined for future):
  Page spacing         24px
  Section spacing      16px
  Table row height     44px
  Input height         36px
  Button height        36px

Dense (defined for future):
  Page spacing         16px
  Section spacing      12px
  Table row height     36px
  Input height         32px
  Button height        32px
```

Density is not a user toggle initially. It's a system-wide preset, useful for high-density data-entry screens.

---

## Surface Levels

Don't use excessive nesting. Three levels only:

### Canvas
The application background. Typically a subtle gray or white. Never place content directly on Canvas — always use Surface.

### Surface
The main content surface. Tables, forms, lists, content blocks. Has subtle elevation above Canvas.

### Elevated
For dialogs, menus, popovers, floating elements. Has clear elevation above Surface.

**Wrong:**
```
<Card>              ← Surface
  <Card>            ← Surface (nested)
    <Card>          ← Surface (nested)
      Content
    </Card>
  </Card>
</Card>
```

**Right:**
```
<Container>         ← Canvas
  <DataTable />     ← Surface
  <Dialog>          ← Elevated
    <Form />        ← Content
  </Dialog>
</Container>
```

---

## Component Inventory

### Design-System Components (`design-system/components/*`)
- **Button** — Primary, secondary, outlined, text variants
- **Input** — TextField, TextArea
- **Select** — Dropdown select
- **Card** — Surface-level container
- **Dialog** — Modal dialog
- **Badge** — Status and category badges
- **Chip** — Removable/interactive chips
- **Checkbox** — Standard checkbox
- **Radio** — Standard radio button
- **Switch** — Toggle switch
- **Tabs** — Tab navigation
- **Breadcrumbs** — Breadcrumb navigation
- **Snackbar** — Toast notifications

### Application Components (`components/*`)

**Layout & Navigation**
- **AppShell** — Main application wrapper (Sidebar, TopBar, content)
- **Sidebar** — Persistent/temporary navigation drawer (capability-gated)
- **TopBar** — Application header with branding, search, user menu
- **MobileNav** — Mobile bottom navigation / drawer

**Page Structure**
- **Page** — Page wrapper with standard padding/layout
- **PageHeader** — Title + description + action buttons + breadcrumb
- **PageSection** — Grouped content section with heading
- **PageToolbar** — Toolbar for actions, filters, etc.

**Data & Tables**
- **DataTable** — MUI DataGrid wrapper with consistent search, pagination, sorting, loading states
- **FilterBar** — Filter/search controls
- **SearchField** — Standalone search input
- **Pagination** — Pagination control
- **StatusBadge** — Semantic status display (Active, Pending, Inactive, etc.)

**Forms**
- **FormSection** — Grouped form fields with heading
- **FormActions** — Save/Cancel button group at form bottom
- **FormDialog** — Dialog wrapping a form

**Feedback States**
- **EmptyState** — Empty table/list state with icon and action
- **LoadingState** — Skeleton or spinner state
- **ErrorState** — Error display with retry option
- **ConfirmDialog** — Confirmation dialog (replaces window.confirm)
- **Snackbar** — Toast notifications

**Dashboard**
- **StatCard** — Stat tile (icon + count + label)
- **Metric** — Metric display (for dashboards)
- **ActivityList** — Simple activity list

---

## Tenant Branding

Tenants can customize **identity**, not the design system.

### Tenants CAN Configure:
- `primary_color` (hex)
- `secondary_color` (hex)
- `logo` (image upload)
- `favicon` (image upload)
- `font_family` (curated selection only: Inter, Roboto, Poppins, system default)

### Tenants CANNOT Configure:
- Spacing scale
- Border radius scale
- Component styling/overrides
- Typography scale (sizes, line heights, weights)
- Semantic status colors (success/warning/error/info)

The product looks and behaves identically across all tenants. Only brand identity changes.

---

## Typeface Strategy

### Platform Default
- **Typeface:** Inter (self-hosted via `next/font`)
- **Strategy:** Fixed platform-wide. Never changes per tenant.

### If Tenant Font Swapping is Needed
- Tenant can select from a curated list: Inter (default), Roboto, Poppins, system default
- **Only the typeface changes.** The typography scale (size/weight/line-height) never changes.
- Typography tokens are platform-owned in all cases.

---

## Building New Features

When building a new page or component:

1. **Start with a Design-System Component** — is there already a Button, Input, Card, etc. that fits?
2. **Compose with Application Components** — use Page, PageHeader, DataTable, FormSection, etc. to structure the page
3. **Never write raw MUI** — if you're importing `Box`, `Grid`, `Typography` directly, you're doing it wrong. Use design-system/application components instead.
4. **Never hardcode colors, spacing, radius** — import from tokens
5. **Never use inline `sx` for styling** — if you need styling, add it to the theme or a component

### Example: New Student List Page

```tsx
'use client';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { DataTable } from '@/components/data/DataTable';
import { Button } from '@/design-system/components/Button';
import { Plus as PlusIcon } from 'lucide-react';

export default function StudentsPage() {
  return (
    <Page>
      <PageHeader
        title="Students"
        description="Manage students enrolled at your school."
        actions={
          <Button
            variant="primary"
            startIcon={<PlusIcon />}
          >
            Add Student
          </Button>
        }
      />
      
      <PageContent>
        <DataTable columns={columns} rows={students} />
      </PageContent>
    </Page>
  );
}
```

No `Box`, no `sx`, no hardcoded spacing or colors. Pure composition.

---

## Verification Checklist

- [ ] Can I explain why every component uses a semantic token, not a raw value?
- [ ] Are all hardcoded hex colors in components replaced with token references?
- [ ] Are all hardcoded spacing values replaced with the spacing scale?
- [ ] Does every component use the typography scale (Display/H1–H3/Body/Caption)?
- [ ] Can I check the entire design system visually in one place (the playground route)?
- [ ] Do all pages use Page/PageHeader/PageContent instead of raw Container/Box?
- [ ] Is window.confirm() completely replaced with ConfirmDialog?
- [ ] Does every school look and feel identical, with only branding identity changing?

---

## Next Steps

1. Build the token layer (`design-system/tokens/*`)
2. Build the MUI theme consuming those tokens
3. Redesign the AppShell (Sidebar, TopBar, layout)
4. Build design-system components (Button, Input, Card, Dialog, etc.)
5. Build application components (PageHeader, DataTable, etc.)
6. Create the `/design-system` playground for visual testing
7. Rebuild Students module as the reference implementation
8. Migrate remaining modules
9. Implement tenant branding
