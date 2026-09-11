# Finance Module UI Alignment + CRUD Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle 7 finance/fees staff screens to match the "pinewood" design system already used by `students/list.html`, and fix CRUD actions the UI currently exposes but the backend doesn't support.

**Architecture:** This is a Django server-rendered app (no SPA/build step for these screens — templates are edited directly and served on next request). Visual changes are template + one shared-CSS-partial edit. The one behavior fix (fee category edit/delete) is a Django view change following the exact `form_type`-dispatch pattern already used by the sibling `MasterFeesView` in the same file.

**Tech Stack:** Django templates, Bootstrap 5, vanilla JS / jQuery (mixed, per-file — match whatever the file already uses, don't introduce a new one), Django class-based views.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-05-finance-ui-alignment-design.md`.
- No pytest coverage exists for these views/templates and the harness is known-broken project-wide (stale conftest + shared-schema migration issue) — do not attempt to add pytest tests. Verify the one backend change via a `manage.py shell` script run inside the `pinewood-web-1` docker container (the project's established verification method for this subsystem), and verify all template changes by loading the page in a browser via `docker-compose up` + `python manage.py runserver`.
- Reuse `var(--color-brand)` (`#1a7a3c`), `var(--color-brand-bg)` (`#e8f5ed`), `var(--color-muted)`, `var(--p-gray-border)` (`#e0e0e0`) from `core/templates/core/base.html`'s `:root` — never introduce new hardcoded hex colors for brand green.
- Keep every existing URL name, view class name, and route unchanged — this is a template/behavior-fix pass, not a routing refactor.
- Don't touch `create_fees.html`'s working "Create Category" flow, `master_fees.html`'s working particular/discount CRUD, or `student_management.html`'s working payment/reversal/waiver flows — restyle only, no logic changes to those.
- Only re-theme *decorative* hardcoded-hex brand accents (headings, borders, hovers, breadcrumbs). Leave semantic Bootstrap classes alone (`btn-success` on action buttons, `text-danger`/`text-success` on owed/paid amounts) — those encode meaning, not brand styling.

---

## File Structure

- Modify: `core/templates/core/styles.html` — add shared `.stu-header`/`.stu-header-icon` classes (promoted out of `students/list.html`) plus a themed `.breadcrumb-item a` rule, so every finance screen (and any future screen) gets brand-colored headers/breadcrumbs for free instead of re-declaring them per page.
- Modify: `core/templates/core/students/list.html` — remove the now-duplicate local `.stu-header`/`.stu-header-icon` CSS (kept working, just de-duplicated).
- Modify: `core/view_modules/fee_management_views.py` — `FeeCategoryCreateView.post()` gains `action=='update'` and `action=='delete'` branches.
- Modify: `core/templates/core/fees/category_list.html` — pinewood header/table styling + bind the missing edit-form submit handler + send `action` param consistent with the new view branches.
- Modify: `core/templates/core/fees/create_fees.html` — pinewood header/table styling + remove the 3 stub tabs, replace with links to `master_fees` / `fine_slabs`.
- Modify: `core/templates/core/fees/master_fees.html` — pinewood header/table styling only.
- Modify: `core/templates/core/fees/student_management.html` — pinewood header styling only (table markup already reasonable, re-theme colors).
- Modify: `core/templates/core/finance/dashboard.html` — pinewood header + module-grid re-theme.
- Modify: `core/templates/core/fees/dashboard.html` — pinewood header + module-grid re-theme.
- Modify: `core/templates/core/finance/transactions.html` — pinewood header + module-grid re-theme + remove the 4 dead-link buttons.

---

### Task 1: Promote shared header/breadcrumb CSS to the global stylesheet

**Files:**
- Modify: `core/templates/core/styles.html`
- Modify: `core/templates/core/students/list.html:5-27`

**Interfaces:**
- Produces: global CSS classes `.stu-header`, `.stu-header-icon`, and a themed `.breadcrumb-item a` rule, available on every page that includes `core/base.html` (all of them, via `{% include 'core/styles.html' %}` at `base.html:781`). Every later task in this plan relies on `.stu-header`/`.stu-header-icon` existing globally — do not redefine them locally in any finance template.

- [ ] **Step 1: Add the shared classes to `styles.html`**

Append this block to the end of `core/templates/core/styles.html`, just before the closing `</style>` tag (i.e. insert before line 297 `</style>`):

```css
/* Shared page header — brand-accented card used across module landing/list pages */
.stu-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 24px;
    background: #fff;
    border: 1px solid var(--p-gray-border);
    border-left: 4px solid var(--color-brand);
    margin-bottom: 24px;
}
.stu-header-icon {
    width: 48px; height: 48px;
    background: var(--color-brand-bg);
    color: var(--color-brand);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
}
.stu-header h2 { margin: 0 0 2px; font-size: 1.3rem; }
.stu-header p  { margin: 0; font-size: 13px; color: var(--color-muted); }

/* Brand-themed breadcrumbs (was hardcoded #28a745 per-page) */
.breadcrumb-item a {
    color: var(--color-brand);
    text-decoration: none;
}
.breadcrumb-item a:hover {
    text-decoration: underline;
}
.breadcrumb-item.active {
    color: var(--color-muted);
}
.breadcrumb-item + .breadcrumb-item::before {
    content: ">";
    color: var(--color-muted);
}
```

- [ ] **Step 2: Remove the now-duplicate local CSS from `students/list.html`**

In `core/templates/core/students/list.html`, the `{% block extra_css %}` currently (lines 5-27) reads:

```html
{% block extra_css %}
<style>
.stu-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 24px;
    background: #fff;
    border: 1px solid var(--p-gray-border);
    border-left: 4px solid var(--color-brand);
    margin-bottom: 24px;
}
.stu-header-icon {
    width: 48px; height: 48px;
    background: var(--color-brand-bg);
    color: var(--color-brand);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
}
.stu-header h2 { margin: 0 0 2px; font-size: 1.3rem; }
.stu-header p  { margin: 0; font-size: 13px; color: var(--color-muted); }
</style>
{% endblock %}
```

Delete the whole `{% block extra_css %}...{% endblock %}` block (lines 5-27) — the classes now come from the global stylesheet. Leave everything else in the file untouched.

- [ ] **Step 3: Verify**

Run the dev server and load the students list page:

```bash
docker-compose up -d
docker exec -it $(docker ps --filter "name=web" -q) python manage.py runserver 0.0.0.0:8000
```

Visit `http://localhost:8000/students/` (or whatever host/port the project uses locally) and confirm the header still renders identically (brand-left-border card, icon tile, title/subtitle) — no visual regression from removing the local CSS block. Also visit any page with a `.breadcrumb` (e.g. `/fees/master-fees/` once reachable) and confirm breadcrumb links are brand-green, not Bootstrap-blue.

- [ ] **Step 4: Commit**

```bash
git add core/templates/core/styles.html core/templates/core/students/list.html
git commit -m "Promote stu-header and breadcrumb theming to shared stylesheet"
```

---

### Task 2: Fix `FeeCategoryCreateView` to support update and delete

**Files:**
- Modify: `core/view_modules/fee_management_views.py:131-168`

**Interfaces:**
- Consumes: `FeeCategory` model (`core/models.py:749`, fields `name`, `description`, `is_deleted`).
- Produces: `FeeCategoryCreateView.post()` now branches on `request.POST.get('action')`:
  - no `action` (or `action == 'create'`) → existing create behavior, unchanged.
  - `action == 'update'` → requires `category_id`, `name`; updates `name`/`description` on the matching `FeeCategory`, returns `{'success': True, 'message': ..., 'category_id': ...}`.
  - `action == 'delete'` → requires `category_id`; soft-deletes (`is_deleted = True`) the matching `FeeCategory`, returns `{'success': True, 'message': ...}`.
  - Task 3's template relies on exactly these three `action` values and this exact response shape.

- [ ] **Step 1: Replace `FeeCategoryCreateView` with update/delete branches**

In `core/view_modules/fee_management_views.py`, replace the existing class (currently lines 131-168):

```python
class FeeCategoryCreateView(View):
    """Create new fee category"""
    
    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            
            if not name:
                return JsonResponse({'error': 'Category name is required'}, status=400)
            
            # Check if category already exists
            if FeeCategory.objects.filter(
                tenant=school,
                name__iexact=name,
                is_deleted=False
            ).exists():
                return JsonResponse({'error': 'Fee category already exists'}, status=400)
            
            category = FeeCategory.objects.create(
                tenant=school,
                name=name,
                description=description
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Fee category "{name}" created successfully',
                'category_id': str(category.id)
            })
            
        except Exception as e:
            logger.error(f"Error creating fee category: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
```

with:

```python
class FeeCategoryCreateView(View):
    """Create, update, or delete a fee category"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        action = request.POST.get('action', 'create')

        try:
            if action == 'update':
                return self._update(request, school)
            elif action == 'delete':
                return self._delete(request, school)
            else:
                return self._create(request, school)
        except Exception as e:
            logger.error(f"Error in fee category POST: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    def _create(self, request, school):
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            return JsonResponse({'error': 'Category name is required'}, status=400)

        if FeeCategory.objects.filter(
            tenant=school,
            name__iexact=name,
            is_deleted=False
        ).exists():
            return JsonResponse({'error': 'Fee category already exists'}, status=400)

        category = FeeCategory.objects.create(
            tenant=school,
            name=name,
            description=description
        )

        return JsonResponse({
            'success': True,
            'message': f'Fee category "{name}" created successfully',
            'category_id': str(category.id)
        })

    def _update(self, request, school):
        category_id = request.POST.get('category_id')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not category_id:
            return JsonResponse({'error': 'Category ID is required'}, status=400)
        if not name:
            return JsonResponse({'error': 'Category name is required'}, status=400)

        try:
            category = FeeCategory.objects.get(id=category_id, tenant=school, is_deleted=False)
        except FeeCategory.DoesNotExist:
            return JsonResponse({'error': 'Fee category not found'}, status=404)

        if FeeCategory.objects.filter(
            tenant=school,
            name__iexact=name,
            is_deleted=False
        ).exclude(id=category.id).exists():
            return JsonResponse({'error': 'Fee category already exists'}, status=400)

        category.name = name
        category.description = description
        category.save(update_fields=['name', 'description'])

        return JsonResponse({
            'success': True,
            'message': f'Fee category "{name}" updated successfully',
            'category_id': str(category.id)
        })

    def _delete(self, request, school):
        category_id = request.POST.get('category_id')

        if not category_id:
            return JsonResponse({'error': 'Category ID is required'}, status=400)

        try:
            category = FeeCategory.objects.get(id=category_id, tenant=school, is_deleted=False)
        except FeeCategory.DoesNotExist:
            return JsonResponse({'error': 'Fee category not found'}, status=404)

        category.is_deleted = True
        category.save(update_fields=['is_deleted'])

        return JsonResponse({
            'success': True,
            'message': f'Fee category "{category.name}" deleted successfully'
        })
```

- [ ] **Step 2: Verify via dev-shell script**

Run inside the running web container (matches how this subsystem's earlier work — `FamilyInvoice`, fee reversal, etc. — was verified per project history):

```bash
docker exec -it pinewood-web-1 python manage.py shell
```

```python
from django_tenants.utils import schema_context
from core.models import School, FeeCategory
from django.test import RequestFactory
from core.view_modules.fee_management_views import FeeCategoryCreateView

school = School.objects.first()
with schema_context(school.schema_name):
    from django.db import transaction
    with transaction.atomic():
        cat = FeeCategory.objects.create(tenant=school, name="UI Test Category", description="orig")

        rf = RequestFactory()
        view = FeeCategoryCreateView.as_view()

        # update
        req = rf.post('/fees/categories/create/', {'action': 'update', 'category_id': str(cat.id), 'name': 'UI Test Category Renamed', 'description': 'updated'})
        req.tenant = school
        resp = view(req)
        print("UPDATE:", resp.status_code, resp.content)
        cat.refresh_from_db()
        assert cat.name == 'UI Test Category Renamed'

        # delete
        req = rf.post('/fees/categories/create/', {'action': 'delete', 'category_id': str(cat.id)})
        req.tenant = school
        resp = view(req)
        print("DELETE:", resp.status_code, resp.content)
        cat.refresh_from_db()
        assert cat.is_deleted is True

        transaction.set_rollback(True)  # discard test data
print("OK")
```

Expected: both `print` calls show `200` and `{"success": true, ...}`, both `assert`s pass, final line prints `OK`, and the rollback means no `UI Test Category` rows are left behind.

- [ ] **Step 3: Run `manage.py check`**

```bash
docker exec -it pinewood-web-1 python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add core/view_modules/fee_management_views.py
git commit -m "Fix fee category edit/delete: FeeCategoryCreateView now handles update and delete actions"
```

---

### Task 3: Restyle `category_list.html` and wire the edit form

**Files:**
- Modify: `core/templates/core/fees/category_list.html`

**Interfaces:**
- Consumes: `FeeCategoryCreateView.post()` from Task 2 (`action=update`/`action=delete`/default-create), route `core:fee_category_create`.
- Consumes global `.stu-header`/`.stu-header-icon`/`.pinewood-table-container`/`.pinewood-table` classes (Task 1 / pre-existing `styles.html`).

- [ ] **Step 1: Replace the header block**

Replace lines 5-13 (currently):

```html
{% block content %}
<div class="row">
    <div class="col-12">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2 class="h4 mb-0">Fee Categories</h2>
            <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#createCategoryModal">
                <i class="bi bi-plus-circle"></i> Add Category
            </button>
        </div>
```

with:

```html
{% block content %}
<div class="row">
    <div class="col-12">
        <div class="stu-header">
            <div class="stu-header-icon"><i class="fas fa-tags"></i></div>
            <div style="flex:1">
                <h2>Fee Categories</h2>
                <p>Manage the fee categories used across master fees and student billing</p>
            </div>
            <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#createCategoryModal">
                <i class="bi bi-plus-circle"></i> Add Category
            </button>
        </div>
```

- [ ] **Step 2: Replace the table markup**

Replace (currently lines 38-83, the `<!-- Categories Table -->` card):

```html
        <!-- Categories Table -->
        <div class="card">
            <div class="card-body">
                {% if categories %}
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
```

with:

```html
        <!-- Categories Table -->
        {% if categories %}
        <div class="pinewood-table-container">
            <div class="pinewood-table-header">
                <h5 class="mb-0">Categories</h5>
            </div>
            <div class="pinewood-table-responsive">
                <table class="pinewood-table">
                    <thead>
```

Then, further down, replace the matching closing tags. Currently (lines 82-134):

```html
                        </table>
                    </div>

                    <!-- Pagination -->
                    {% if is_paginated %}
                    <div class="d-flex justify-content-center mt-4">
                        <nav aria-label="Category pagination">
                            <ul class="pagination">
                                {% if page_obj.has_previous %}
                                    <li class="page-item">
                                        <a class="page-link" href="?{% if request.GET.search %}search={{ request.GET.search }}&{% endif %}page=1">First</a>
                                    </li>
                                    <li class="page-item">
                                        <a class="page-link" href="?{% if request.GET.search %}search={{ request.GET.search }}&{% endif %}page={{ page_obj.previous_page_number }}">Previous</a>
                                    </li>
                                {% endif %}

                                <li class="page-item active">
                                    <span class="page-link">{{ page_obj.number }} of {{ page_obj.paginator.num_pages }}</span>
                                </li>

                                {% if page_obj.has_next %}
                                    <li class="page-item">
                                        <a class="page-link" href="?{% if request.GET.search %}search={{ request.GET.search }}&{% endif %}page={{ page_obj.next_page_number }}">Next</a>
                                    </li>
                                    <li class="page-item">
                                        <a class="page-link" href="?{% if request.GET.search %}search={{ request.GET.search }}&{% endif %}page={{ page_obj.paginator.num_pages }}">Last</a>
                                    </li>
                                {% endif %}
                            </ul>
                        </nav>
                    </div>
                    {% endif %}
                {% else %}
                    <div class="text-center py-5">
                        <i class="bi bi-collection text-muted" style="font-size: 3rem;"></i>
                        <h5 class="mt-3">No Fee Categories Found</h5>
                        <p class="text-muted">
                            {% if request.GET.search %}
                                No categories match your search criteria.
                            {% else %}
                                Create your first fee category to get started.
                            {% endif %}
                        </p>
                        <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#createCategoryModal">
                            <i class="bi bi-plus-circle"></i> Add First Category
                        </button>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
```

with:

```html
                        </table>
            </div>

            {% if is_paginated %}
            <div class="pinewood-table-pagination">
                <nav aria-label="Category pagination">
                    <ul class="pagination">
                        {% if page_obj.has_previous %}
                            <li class="page-item">
                                <a class="page-link" href="?{% if request.GET.search %}search={{ request.GET.search }}&{% endif %}page=1">First</a>
                            </li>
                            <li class="page-item">
                                <a class="page-link" href="?{% if request.GET.search %}search={{ request.GET.search }}&{% endif %}page={{ page_obj.previous_page_number }}">Previous</a>
                            </li>
                        {% endif %}

                        <li class="page-item active">
                            <span class="page-link">{{ page_obj.number }} of {{ page_obj.paginator.num_pages }}</span>
                        </li>

                        {% if page_obj.has_next %}
                            <li class="page-item">
                                <a class="page-link" href="?{% if request.GET.search %}search={{ request.GET.search }}&{% endif %}page={{ page_obj.next_page_number }}">Next</a>
                            </li>
                            <li class="page-item">
                                <a class="page-link" href="?{% if request.GET.search %}search={{ request.GET.search }}&{% endif %}page={{ page_obj.paginator.num_pages }}">Last</a>
                            </li>
                        {% endif %}
                    </ul>
                </nav>
            </div>
            {% endif %}
        </div>
        {% else %}
        <div class="pinewood-table-container">
            <div class="text-center py-5">
                <i class="bi bi-collection text-muted" style="font-size: 3rem;"></i>
                <h5 class="mt-3">No Fee Categories Found</h5>
                <p class="text-muted">
                    {% if request.GET.search %}
                        No categories match your search criteria.
                    {% else %}
                        Create your first fee category to get started.
                    {% endif %}
                </p>
                <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#createCategoryModal">
                    <i class="bi bi-plus-circle"></i> Add First Category
                </button>
            </div>
        </div>
        {% endif %}
    </div>
</div>
```

Note the table body rows (lines 54-80, the `{% for category in categories %}` loop and its `<tbody>`/`</tbody>` wrapper) are unchanged — only the surrounding container markup and CSS classes changed, so no edit needed there beyond what's shown above.

- [ ] **Step 3: Bind the missing edit-form submit handler and align delete/update `action` param naming**

In the `{% block extra_js %}` section, replace the whole script block (lines 218-302) with:

```html
{% block extra_js %}
<script>
$(document).ready(function() {
    // Create Category Form Submission
    $('#createCategoryForm').on('submit', function(e) {
        e.preventDefault();

        $.ajax({
            url: '{% url "core:fee_category_create" %}',
            method: 'POST',
            data: $(this).serialize(),
            success: function(response) {
                if (response.success) {
                    alert('Success: ' + response.message);
                    location.reload();
                } else {
                    alert('Error: ' + response.error);
                }
            },
            error: function(xhr) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    alert('Error: ' + response.error);
                } catch (e) {
                    alert('Error: Failed to create category');
                }
            }
        });
    });

    // Edit Category Button Click
    $('.edit-category').on('click', function() {
        const categoryId = $(this).data('category-id');
        const categoryName = $(this).data('category-name');
        const categoryDescription = $(this).data('category-description');

        $('#editCategoryId').val(categoryId);
        $('#editCategoryName').val(categoryName);
        $('#editCategoryDescription').val(categoryDescription || '');

        $('#editCategoryModal').modal('show');
    });

    // Edit Category Form Submission
    $('#editCategoryForm').on('submit', function(e) {
        e.preventDefault();

        $.ajax({
            url: '{% url "core:fee_category_create" %}',
            method: 'POST',
            data: $(this).serialize() + '&action=update',
            success: function(response) {
                if (response.success) {
                    alert('Success: ' + response.message);
                    location.reload();
                } else {
                    alert('Error: ' + response.error);
                }
            },
            error: function(xhr) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    alert('Error: ' + response.error);
                } catch (e) {
                    alert('Error: Failed to update category');
                }
            }
        });
    });

    // Delete Category Button Click
    $('.delete-category').on('click', function() {
        const categoryId = $(this).data('category-id');
        const categoryName = $(this).data('category-name');

        $('#deleteCategoryName').text(categoryName);
        $('#confirmDeleteCategory').data('category-id', categoryId);

        $('#deleteCategoryModal').modal('show');
    });

    // Confirm Delete Category
    $('#confirmDeleteCategory').on('click', function() {
        const categoryId = $(this).data('category-id');

        $.ajax({
            url: '{% url "core:fee_category_create" %}',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('[name=csrfmiddlewaretoken]').val(),
                'action': 'delete',
                'category_id': categoryId
            },
            success: function(response) {
                if (response.success) {
                    alert('Success: Category deleted successfully');
                    location.reload();
                } else {
                    alert('Error: ' + response.error);
                }
            },
            error: function(xhr) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    alert('Error: ' + response.error);
                } catch (e) {
                    alert('Error: Failed to delete category');
                }
            }
        });
    });
});
</script>
{% endblock %}
```

(The only functional change here is the new `$('#editCategoryForm').on('submit', ...)` handler — everything else is unchanged from the current file, kept verbatim so create/delete keep working exactly as before.)

- [ ] **Step 4: Manual verification**

With the dev server running, visit `/fees/categories/` (route `core:fee_categories`):
- Confirm the header now shows the brand-accented `.stu-header` card with a tags icon.
- Confirm the table uses the pinewood green-header table style.
- Click "Add Category", create a category named "Verify Category" — confirm it appears in the list.
- Click "Edit" on "Verify Category", rename it to "Verify Category Edited", submit — confirm the page reloads and shows the new name (this is the previously-broken path).
- Click "Delete" on "Verify Category Edited", confirm — confirm it disappears from the list (this is the previously-broken path).

- [ ] **Step 5: Commit**

```bash
git add core/templates/core/fees/category_list.html
git commit -m "Restyle fee categories screen to pinewood design system and wire edit form"
```

---

### Task 4: Restyle `create_fees.html` and remove duplicate stub tabs

**Files:**
- Modify: `core/templates/core/fees/create_fees.html`

**Interfaces:**
- Consumes: `core:master_fees` and `core:fine_slabs` routes (existing, both already registered in `core/urls.py`).
- Produces: no JS-facing interface changes — `loadParticularsSection`/`loadDiscountSection`/`loadFineSection` and their 3 tabs are removed entirely; `showCreateSection`/`loadSectionContent` are simplified accordingly.

- [ ] **Step 1: Replace the header + tab navigation**

Replace lines 17-48 (currently the header `div` + 4-tab `row`):

```html
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2>Master Category <span class="text-muted">| Create Fees</span></h2>
    <div class="text-muted">Financial Year: 2025 - 2025</div>
</div>

<!-- Tab Navigation -->
<div class="row mb-4">
    <div class="col-md-3">
        <div class="create-fees-tab" id="create-category-tab" onclick="showCreateSection('category')">
            <h5 class="text-success mb-1">Create category</h5>
            <p class="text-muted mb-0 small">Create Master Category</p>
        </div>
    </div>
    <div class="col-md-3">
        <div class="create-fees-tab" id="create-particulars-tab" onclick="showCreateSection('particulars')">
            <h5 class="text-success mb-1">Create Particulars</h5>
            <p class="text-muted mb-0 small">Create Particulars</p>
        </div>
    </div>
    <div class="col-md-3">
        <div class="create-fees-tab" id="create-discount-tab" onclick="showCreateSection('discount')">
            <h5 class="text-success mb-1">Create Discount</h5>
            <p class="text-muted mb-0 small">Create Fee Discounts</p>
        </div>
    </div>
    <div class="col-md-3">
        <div class="create-fees-tab" id="generate-fine-tab" onclick="showCreateSection('fine')">
            <h5 class="text-success mb-1">Generate Fine</h5>
            <p class="text-muted mb-0 small">Generate Fine</p>
        </div>
    </div>
</div>
```

with:

```html
<div class="stu-header">
    <div class="stu-header-icon"><i class="fas fa-layer-group"></i></div>
    <div style="flex:1">
        <h2>Create Fees</h2>
        <p>Create master fee categories and assign them to batches</p>
    </div>
</div>

<!-- Related setup: particulars, discounts and fines already live on their own screens -->
<div class="row mb-4">
    <div class="col-md-6">
        <div class="create-fees-tab active" id="create-category-tab" onclick="showCreateSection('category')">
            <h5 class="mb-1" style="color: var(--color-brand)">Create category</h5>
            <p class="text-muted mb-0 small">Create Master Category</p>
        </div>
    </div>
    <div class="col-md-3">
        <a href="{% url 'core:master_fees' %}" class="text-decoration-none">
            <div class="create-fees-tab">
                <h5 class="mb-1" style="color: var(--color-brand)">Particulars &amp; Discounts</h5>
                <p class="text-muted mb-0 small">Manage on Master Fees</p>
            </div>
        </a>
    </div>
    <div class="col-md-3">
        <a href="{% url 'core:fine_slabs' %}" class="text-decoration-none">
            <div class="create-fees-tab">
                <h5 class="mb-1" style="color: var(--color-brand)">Fine Slabs</h5>
                <p class="text-muted mb-0 small">Manage fine slabs</p>
            </div>
        </a>
    </div>
</div>
```

- [ ] **Step 2: Remove the now-unused `create-particulars-section`/`create-discount-section`/`generate-fine-section` placeholder divs**

Replace (currently lines 97-110):

```html
<!-- Create Particulars Section -->
<div id="create-particulars-section" class="create-section" style="display: none;">
    <!-- This will be populated when "Create Particulars" tab is clicked -->
</div>

<!-- Create Discount Section -->
<div id="create-discount-section" class="create-section" style="display: none;">
    <!-- This will be populated when "Create Discount" tab is clicked -->
</div>

<!-- Generate Fine Section -->
<div id="generate-fine-section" class="create-section" style="display: none;">
    <!-- This will be populated when "Generate Fine" tab is clicked -->
</div>
```

with nothing — delete these 3 divs (the "Create Category Section" div immediately above them, lines 92-95, stays).

- [ ] **Step 3: Update JS — drop the stub-loading functions and simplify tab logic**

Replace the whole `{% block extra_js %}` (lines 237-379) with:

```html
{% block extra_js %}
<script>
function showCreateSection() {
    document.getElementById('create-category-section').style.display = 'block';
    document.getElementById('create-category-tab').classList.add('active');
    loadSectionContent();
}

function loadSectionContent() {
    const sectionElement = document.getElementById('create-category-section');
    sectionElement.innerHTML = `
        <div class="text-center">
            <button type="button" class="btn btn-success" data-bs-toggle="modal" data-bs-target="#createCategoryModal">
                Create Master Category
            </button>
        </div>
    `;
}

function loadBatchData() {
    const batchId = document.getElementById('batch-select').value;
    if (batchId) {
        // Show category list section
        document.getElementById('category-list-section').style.display = 'block';
        loadCategoriesForBatch(batchId);
    } else {
        document.getElementById('category-list-section').style.display = 'none';
    }
}

function loadCategoriesForBatch(batchId) {
    fetch(`{% url "core:create_fees" %}?action=get_categories&batch_id=${batchId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const tbody = document.getElementById('category-table-body');
                tbody.innerHTML = '';

                if (data.categories.length > 0) {
                    data.categories.forEach((category, index) => {
                        tbody.innerHTML += `
                            <tr>
                                <td>${index + 1}</td>
                                <td>${category.name}</td>
                                <td>${category.created_date}</td>
                            </tr>
                        `;
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">No categories found for this batch</td></tr>';
                }
            }
        })
        .catch(error => {
            console.error('Error loading categories:', error);
        });
}

function toggleAllBatches() {
    const selectAll = document.getElementById('select-all-batches').checked;
    document.querySelectorAll('.batch-checkbox').forEach(checkbox => {
        checkbox.checked = selectAll;
    });
}

function createCategory() {
    const form = document.getElementById('createCategoryForm');
    const formData = new FormData(form);

    fetch('{% url "core:create_fees" %}', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close modal and refresh the page or update the table
            bootstrap.Modal.getInstance(document.getElementById('createCategoryModal')).hide();
            location.reload();
        } else {
            alert('Error creating category: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error creating category: ' + error.message);
    });
}

// Initialize with category section active
document.addEventListener('DOMContentLoaded', function() {
    showCreateSection();
});
</script>
{% endblock %}
```

- [ ] **Step 4: Restyle CSS — drop stub-specific rules, brand-theme the remaining ones**

Replace the whole `{% block extra_css %}` (lines 172-235) with:

```html
{% block extra_css %}
<style>
.create-fees-tab {
    padding: 15px;
    border: 1px solid var(--p-gray-border);
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.3s ease;
    margin-bottom: 10px;
    background: white;
}

.create-fees-tab:hover {
    background: #f8f9fa;
    border-color: var(--color-brand);
}

.create-fees-tab.active {
    background: var(--color-brand-bg);
    border-color: var(--color-brand);
}

.create-section {
    border: 1px solid var(--p-gray-border);
    border-radius: 5px;
    padding: 20px;
    background: white;
}

.table td, .table th {
    vertical-align: middle;
}
</style>
{% endblock %}
```

- [ ] **Step 5: Manual verification**

Visit `/fees/create-fees/` (route `core:create_fees`):
- Confirm the header is now the `.stu-header` brand card.
- Confirm "Particulars & Discounts" links to `/fees/master-fees/` and "Fine Slabs" links to `/fees/fine-slabs/`.
- Confirm "Create category" tab still works: select a batch, click "Create Master Category", submit a new category, confirm success + reload.
- Confirm no JS console errors (the removed `loadParticularsSection`/etc. functions are no longer referenced anywhere).

- [ ] **Step 6: Commit**

```bash
git add core/templates/core/fees/create_fees.html
git commit -m "Restyle create_fees.html and replace stub particulars/discount/fine tabs with links to their real screens"
```

---

### Task 5: Restyle `master_fees.html`

**Files:**
- Modify: `core/templates/core/fees/master_fees.html`

**Interfaces:**
- No backend interface changes — pure template restyle. All existing `onclick` handlers (`editParticular`, `deleteParticular`, `createParticular`, etc.) and form structures stay exactly as-is.

- [ ] **Step 1: Replace the header block**

Replace lines 17-19 (currently):

```html
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2>Master Fees <span class="text-muted">| Manage Master Fees</span></h2>
</div>
```

with:

```html
<div class="stu-header">
    <div class="stu-header-icon"><i class="fas fa-list-check"></i></div>
    <div style="flex:1">
        <h2>Master Fees</h2>
        <p>Manage master particulars and discounts used across fee categories</p>
    </div>
</div>
```

- [ ] **Step 2: Re-theme the two tables to pinewood table styling**

Replace (currently lines 32-53, the Master Particulars table):

```html
        {% if particulars %}
            <table class="table table-bordered">
                <thead class="table-light">
                    <tr>
                        <th>Name</th>
                        <th>Description</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for particular in particulars %}
                        <tr>
                            <td>{{ particular.name }}</td>
                            <td>{{ particular.description|default:"" }}</td>
                            <td>
                                <a href="#" class="text-primary text-decoration-none me-3" onclick="editParticular('{{ particular.id }}')">Edit</a>
                                <a href="#" class="text-danger text-decoration-none" onclick="deleteParticular('{{ particular.id }}', '{{ particular.name }}')">Delete</a>
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
```

with:

```html
        {% if particulars %}
            <div class="pinewood-table-container">
                <table class="pinewood-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Description</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for particular in particulars %}
                            <tr>
                                <td>{{ particular.name }}</td>
                                <td>{{ particular.description|default:"" }}</td>
                                <td class="table-actions">
                                    <a href="#" class="text-primary text-decoration-none me-3" onclick="editParticular('{{ particular.id }}')">Edit</a>
                                    <a href="#" class="text-danger text-decoration-none" onclick="deleteParticular('{{ particular.id }}', '{{ particular.name }}')">Delete</a>
                                </td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
```

Then replace (currently lines 71-93, the Master Discounts table) the same way:

```html
        {% if discounts %}
            <table class="table table-bordered">
                <thead class="table-light">
                    <tr>
                        <th>Name</th>
                        <th>Description</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for discount in discounts %}
                        <tr>
                            <td>{{ discount.name }}</td>
                            <td>{{ discount.description|default:"" }}</td>
                            <td>
                                <a href="#" class="text-primary text-decoration-none me-3" onclick="editDiscount('{{ discount.id }}')">Edit</a>
                                <a href="#" class="text-danger text-decoration-none" onclick="deleteDiscount('{{ discount.id }}', '{{ discount.name }}')">Delete</a>
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
```

with:

```html
        {% if discounts %}
            <div class="pinewood-table-container">
                <table class="pinewood-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Description</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for discount in discounts %}
                            <tr>
                                <td>{{ discount.name }}</td>
                                <td>{{ discount.description|default:"" }}</td>
                                <td class="table-actions">
                                    <a href="#" class="text-primary text-decoration-none me-3" onclick="editDiscount('{{ discount.id }}')">Edit</a>
                                    <a href="#" class="text-danger text-decoration-none" onclick="deleteDiscount('{{ discount.id }}', '{{ discount.name }}')">Delete</a>
                                </td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
```

- [ ] **Step 3: Re-theme the extra_css block**

Replace lines 287-329 (`{% block extra_css %}`) with:

```html
{% block extra_css %}
<style>
.card {
    border: 1px solid var(--p-gray-border);
    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
    border-radius: 0.375rem;
}

.table td, .table th {
    vertical-align: middle;
}

@media (max-width: 768px) {
    .btn-sm {
        font-size: 0.75rem;
    }
}
</style>
{% endblock %}
```

(The `.breadcrumb`/`.breadcrumb-item` rules are dropped here since Task 1 already made those global. `btn-success` on the "+ New master particular"/"+ New master discount" buttons stays as-is — semantic Bootstrap button colors are out of scope, only decorative hardcoded-hex accents get themed.)

- [ ] **Step 4: Manual verification**

Visit `/fees/master-fees/` (route `core:master_fees`):
- Confirm the `.stu-header` brand card renders.
- Confirm both tables use the pinewood green-header table style.
- Create, edit, and delete a Master Particular and a Master Discount — confirm all 3 actions still work exactly as before (this screen's CRUD was already fully wired; this task must not break it).

- [ ] **Step 5: Commit**

```bash
git add core/templates/core/fees/master_fees.html
git commit -m "Restyle master_fees.html to pinewood design system"
```

---

### Task 6: Restyle `student_management.html`

**Files:**
- Modify: `core/templates/core/fees/student_management.html`

**Interfaces:**
- No backend interface changes — pure template restyle. All `onclick` handlers and form IDs (`paymentForm`, `reversalForm`, `waiverForm`, etc.) stay exactly as-is.

- [ ] **Step 1: Replace the header block**

Replace lines 8-20 (currently):

```html
    <!-- Header Section -->
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h2 class="h3 mb-1">Student Fee Management</h2>
            <p class="text-muted mb-0">Manage individual student fees and payments</p>
        </div>
        <div class="d-flex align-items-center gap-3">
            {% include 'core/finance/_year_selector.html' %}
            <a href="{% url 'core:fee_dashboard' %}" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left me-1"></i> Back to Dashboard
            </a>
        </div>
    </div>
```

with:

```html
    <!-- Header Section -->
    <div class="stu-header">
        <div class="stu-header-icon"><i class="fas fa-user-graduate"></i></div>
        <div style="flex:1">
            <h2>Student Fee Management</h2>
            <p>Manage individual student fees and payments</p>
        </div>
        <div class="d-flex align-items-center gap-3">
            {% include 'core/finance/_year_selector.html' %}
            <a href="{% url 'core:fee_dashboard' %}" class="btn btn-outline-secondary btn-sm">
                <i class="fas fa-arrow-left me-1"></i> Back to Dashboard
            </a>
        </div>
    </div>
```

- [ ] **Step 2: Re-theme the outstanding-fees and ledger tables to pinewood table styling**

Replace (currently lines 94-140, the Outstanding Fees `<div class="table-responsive">`):

```html
                <div class="table-responsive">
                    {% if outstanding_fees %}
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
```

with:

```html
                <div class="pinewood-table-responsive">
                    {% if outstanding_fees %}
                    <table class="pinewood-table mb-0">
                        <thead>
```

and its closing (currently lines 132-140):

```html
                    </table>
                    {% else %}
                    <div class="card-body text-center py-4">
                        <i class="fas fa-check-circle fa-3x text-success mb-3"></i>
                        <h6 class="text-success">No Outstanding Fees</h6>
                        <p class="text-muted">This student has no outstanding fee balances</p>
                    </div>
                    {% endif %}
                </div>
```

stays exactly as-is (only the opening `<div>`/`<table>`/`<thead>` tags changed — no need to touch the closing tags or the `{% else %}` branch).

Similarly for the Fee Ledger table (currently lines 201-251), replace:

```html
                <div class="table-responsive">
                    {% if fee_transactions %}
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
```

with:

```html
                <div class="pinewood-table-responsive">
                    {% if fee_transactions %}
                    <table class="pinewood-table mb-0">
                        <thead>
```

(again, only these opening tags — everything below, including the closing `{% else %}` empty-state block, is unchanged).

Note: `btn-success`/`text-danger`/`text-success` on Pay/Make-Payment buttons and balance/status text stay untouched — these are semantic (danger=owed, success=paid), not decorative brand accents. The `.card` rule in `extra_css` (currently lines 441-462, generic shadow/radius) also stays untouched — no hardcoded brand color there to theme.

- [ ] **Step 3: Manual verification**

Visit `/fees/student-management/` (route `core:fee_student_management`), search for a student, open their record:
- Confirm the `.stu-header` brand card renders with the year selector and back-link still in place.
- Confirm both tables (Outstanding Fees, Fee Ledger) show the pinewood green-header table style.
- Confirm Pay, Reverse, Grant Waiver, and View Statement still all work (this screen's CRUD was already fully wired; this task must not break it).

- [ ] **Step 4: Commit**

```bash
git add core/templates/core/fees/student_management.html
git commit -m "Restyle student_management.html to pinewood design system"
```

---

### Task 7: Restyle `finance/dashboard.html`

**Files:**
- Modify: `core/templates/core/finance/dashboard.html`

**Interfaces:**
- No backend interface changes — pure template restyle. All `{% url %}` links stay exactly as-is.

- [ ] **Step 1: Replace the header block**

Replace lines 6-24 (currently):

```html
<div class="container-lg py-4">
    <!-- Header Section -->
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <div class="d-flex align-items-center">
                <i class="fas fa-briefcase me-2 text-muted"></i>
                <h2 class="h3 mb-0">Finance</h2>
                <span class="mx-2 text-muted">|</span>
                <span class="text-muted">Manage Finance</span>
            </div>
        </div>
        <div class="d-flex align-items-center gap-3">
            {% include 'core/finance/_year_selector.html' %}
            <a href="{% url 'core:dashboard' %}" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left me-1"></i> Back to Main Dashboard
            </a>
        </div>
    </div>

    <!-- Breadcrumb -->
    <nav aria-label="breadcrumb" class="mb-4">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{% url 'core:dashboard' %}">Home</a></li>
            <li class="breadcrumb-item active" aria-current="page">Finance</li>
        </ol>
    </nav>
```

with:

```html
<div class="container-lg py-4">
    <!-- Breadcrumb -->
    <nav aria-label="breadcrumb" class="mb-3">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{% url 'core:dashboard' %}">Home</a></li>
            <li class="breadcrumb-item active" aria-current="page">Finance</li>
        </ol>
    </nav>

    <!-- Header Section -->
    <div class="stu-header">
        <div class="stu-header-icon"><i class="fas fa-briefcase"></i></div>
        <div style="flex:1">
            <h2>Finance</h2>
            <p>Manage fees, payroll, transactions and reports</p>
        </div>
        <div class="d-flex align-items-center gap-3">
            {% include 'core/finance/_year_selector.html' %}
            <a href="{% url 'core:dashboard' %}" class="btn btn-outline-secondary btn-sm">
                <i class="fas fa-arrow-left me-1"></i> Back to Main Dashboard
            </a>
        </div>
    </div>
```

- [ ] **Step 2: Re-theme the module-grid CSS**

Replace lines 127-197 (`{% block extra_css %}`) with:

```html
{% block extra_css %}
<style>
.finance-module-item {
    padding: 1.5rem 2rem;
    border: 1px solid var(--p-gray-border);
    background: #fff;
    transition: all 0.2s ease;
}

.finance-module-item:hover {
    border-color: var(--color-brand);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transform: translateY(-1px);
}

.finance-module-item h5 {
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: var(--color-brand);
}

.finance-module-item h5:hover {
    color: var(--color-brand-dark) !important;
}

.finance-module-item p {
    margin-bottom: 0;
    color: var(--color-muted);
    font-size: 0.9rem;
    line-height: 1.4;
}

.card {
    border: none;
    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
    border-radius: 0.5rem;
}

.list-group-item {
    border-left: none;
    border-right: none;
    border-top: none;
}

.list-group-item:last-child {
    border-bottom: none;
}
</style>
{% endblock %}
```

- [ ] **Step 3: Replace `text-success` module headings with the themed class**

Every module link heading in the file currently reads `<h5 class="text-success mb-1">...</h5>` (7 occurrences across the "Finance Modules Grid" section, e.g. lines 42, 49, 56, 63, 70, 77, 87, 94, 101, 108, 115). Replace each `class="text-success mb-1"` with `class="mb-1"` — the color now comes from the `.finance-module-item h5` rule added in Step 2, so the inline Bootstrap class is redundant and would otherwise override it.

Use a project-wide-safe find/replace scoped to this file only:

```bash
sed -i 's/class="text-success mb-1"/class="mb-1"/g' core/templates/core/finance/dashboard.html
```

- [ ] **Step 4: Manual verification**

Visit `/finance/` (route `core:finance_dashboard`):
- Confirm the `.stu-header` brand card renders above the breadcrumb... actually confirm breadcrumb renders first, then the header card below it.
- Confirm all module links (Fees, Transactions, Payslip Management, Asset Liability, Tally Export, Ledger Integrity, Category, Donations, Finance Reports, Finance Settings, QuickBooks Reconciliation) still navigate correctly and now render in brand green with the hover effect.

- [ ] **Step 5: Commit**

```bash
git add core/templates/core/finance/dashboard.html
git commit -m "Restyle finance dashboard to pinewood design system"
```

---

### Task 8: Restyle `fees/dashboard.html`

**Files:**
- Modify: `core/templates/core/fees/dashboard.html`

**Interfaces:**
- No backend interface changes — pure template restyle. All `{% url %}` links stay exactly as-is.

- [ ] **Step 1: Replace the header block**

Replace lines 6-24 (same structure as Task 7's finance dashboard, mirrored here for fees):

```html
<div class="container-lg py-4">
    <!-- Header Section -->
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <div class="d-flex align-items-center">
                <i class="fas fa-money-bill-wave me-2 text-muted"></i>
                <h2 class="h3 mb-0">Fees</h2>
                <span class="mx-2 text-muted">|</span>
                <span class="text-primary">Manage Fees</span>
            </div>
        </div>
        <div class="d-flex align-items-center gap-3">
            {% include 'core/finance/_year_selector.html' %}
            <a href="{% url 'core:finance_dashboard' %}" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left me-1"></i> Back to Finance
            </a>
        </div>
    </div>

    <!-- Breadcrumb -->
    <nav aria-label="breadcrumb" class="mb-4">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{% url 'core:dashboard' %}">Home</a></li>
            <li class="breadcrumb-item"><a href="{% url 'core:finance_dashboard' %}">Finance</a></li>
            <li class="breadcrumb-item active" aria-current="page">Fees</li>
        </ol>
    </nav>
```

with:

```html
<div class="container-lg py-4">
    <!-- Breadcrumb -->
    <nav aria-label="breadcrumb" class="mb-3">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{% url 'core:dashboard' %}">Home</a></li>
            <li class="breadcrumb-item"><a href="{% url 'core:finance_dashboard' %}">Finance</a></li>
            <li class="breadcrumb-item active" aria-current="page">Fees</li>
        </ol>
    </nav>

    <!-- Header Section -->
    <div class="stu-header">
        <div class="stu-header-icon"><i class="fas fa-money-bill-wave"></i></div>
        <div style="flex:1">
            <h2>Fees</h2>
            <p>Manage fee categories, master particulars, discounts and student billing</p>
        </div>
        <div class="d-flex align-items-center gap-3">
            {% include 'core/finance/_year_selector.html' %}
            <a href="{% url 'core:finance_dashboard' %}" class="btn btn-outline-secondary btn-sm">
                <i class="fas fa-arrow-left me-1"></i> Back to Finance
            </a>
        </div>
    </div>
```

- [ ] **Step 2: Re-theme the module-grid CSS**

Replace lines 91-146 (`{% block extra_css %}`) with:

```html
{% block extra_css %}
<style>
.fees-module-item {
    padding: 1.5rem 2rem;
    border: 1px solid var(--p-gray-border);
    background: #fff;
    border-radius: 0.375rem;
    transition: all 0.2s ease;
}

.fees-module-item:hover {
    border-color: var(--color-brand);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transform: translateY(-1px);
}

.fees-module-item h5 {
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: var(--color-brand);
}

.fees-module-item h5:hover {
    color: var(--color-brand-dark) !important;
}

.fees-module-item p {
    margin-bottom: 0;
    color: var(--color-muted);
    font-size: 0.9rem;
    line-height: 1.4;
}
</style>
{% endblock %}
```

- [ ] **Step 3: Replace `text-success` module headings with the themed class**

Same as Task 7 Step 3, scoped to this file (6 occurrences: Master Fees, Create & Assign Fees, Fee Categories, Student Fees & Payments, Batch Report / Defaulters, Reports & Exports):

```bash
sed -i 's/class="text-success mb-1"/class="mb-1"/g' core/templates/core/fees/dashboard.html
```

- [ ] **Step 4: Manual verification**

Visit `/fees/` (route `core:fee_dashboard`):
- Confirm breadcrumb, then `.stu-header` brand card render in that order.
- Confirm all 6 module links still navigate correctly and render in brand green with hover effect.

- [ ] **Step 5: Commit**

```bash
git add core/templates/core/fees/dashboard.html
git commit -m "Restyle fees dashboard to pinewood design system"
```

---

### Task 9: Restyle `finance/transactions.html` and remove the 4 dead-link buttons

**Files:**
- Modify: `core/templates/core/finance/transactions.html`

**Interfaces:**
- No backend interface changes.
- Produces: the "Add expense", "Add income", "Reverted transactions", "Bulk revert transactions" links are removed entirely from the template — nothing else in the codebase references them (confirmed during the audit: the resolved `FinanceTransactionsView` at `views.py:4808` has no `post()` handler and no other template links to these hrefs).

- [ ] **Step 1: Replace the header block**

Replace lines 6-32 (currently):

```html
<div class="container-lg py-4">
    <!-- Header Section -->
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <div class="d-flex align-items-center">
                <i class="fas fa-exchange-alt me-2 text-muted"></i>
                <h2 class="h3 mb-0">Finance Transactions</h2>
                <span class="mx-2 text-muted">|</span>
                <span class="text-primary">Expenses And Income</span>
            </div>
        </div>
        <div>
            <a href="{% url 'core:finance_dashboard' %}" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left me-1"></i> Back to Finance
            </a>
        </div>
    </div>

    <!-- Breadcrumb -->
    <nav aria-label="breadcrumb" class="mb-4">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{% url 'core:dashboard' %}">Home</a></li>
            <li class="breadcrumb-item"><a href="{% url 'core:finance_dashboard' %}">Finance</a></li>
            <li class="breadcrumb-item active" aria-current="page">Transactions</li>
        </ol>
    </nav>

    <!-- Transaction Modules Grid -->
    <div class="row g-3">
        <!-- Left Column -->
        <div class="col-md-6">
            <div class="finance-module-item mb-3">
                <a href="#" class="text-decoration-none">
                    <h5 class="text-success mb-1">Add expense</h5>
                    <p class="text-muted mb-0 small">Create new expenses</p>
                </a>
            </div>

            <div class="finance-module-item">
                <a href="#" class="text-decoration-none">
                    <h5 class="text-success mb-1">Reverted transactions</h5>
                    <p class="text-muted mb-0 small">Reverted transactions</p>
                </a>
            </div>
        </div>

        <!-- Right Column -->
        <div class="col-md-6">
            <div class="finance-module-item mb-3">
                <a href="#" class="text-decoration-none">
                    <h5 class="text-success mb-1">Add income</h5>
                    <p class="text-muted mb-0 small">Create new income</p>
                </a>
            </div>

            <div class="finance-module-item">
                <a href="#" class="text-decoration-none">
                    <h5 class="text-success mb-1">Bulk revert transactions</h5>
                    <p class="text-muted mb-0 small">Revert transactions collection-wise in bulk</p>
                </a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

with:

```html
<div class="container-lg py-4">
    <!-- Breadcrumb -->
    <nav aria-label="breadcrumb" class="mb-3">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{% url 'core:dashboard' %}">Home</a></li>
            <li class="breadcrumb-item"><a href="{% url 'core:finance_dashboard' %}">Finance</a></li>
            <li class="breadcrumb-item active" aria-current="page">Transactions</li>
        </ol>
    </nav>

    <!-- Header Section -->
    <div class="stu-header">
        <div class="stu-header-icon"><i class="fas fa-exchange-alt"></i></div>
        <div style="flex:1">
            <h2>Finance Transactions</h2>
            <p>Expenses and income</p>
        </div>
        <div>
            <a href="{% url 'core:finance_dashboard' %}" class="btn btn-outline-secondary btn-sm">
                <i class="fas fa-arrow-left me-1"></i> Back to Finance
            </a>
        </div>
    </div>
</div>
{% endblock %}
```

Note this removes the entire "Transaction Modules Grid" `<div class="row g-3">` along with all 4 dead-link buttons, since the underlying `FinanceTransactionsView` (resolved from `views.py:4808`) already renders `transaction_summary`/`recent_transactions` context that this template doesn't currently display at all — that's a separate, larger gap (out of scope per the design spec) but means there is no working content this grid was gatekeeping; removing it leaves a valid, if sparse, page.

- [ ] **Step 2: Re-theme the extra_css block**

Replace lines 73-128 (`{% block extra_css %}`) with nothing — delete the whole block. The `.finance-module-item`/`.breadcrumb` rules it contained are no longer used on this page (module grid removed in Step 1, breadcrumb theming now comes from the Task 1 global rule).

- [ ] **Step 3: Manual verification**

Visit `/finance/transactions/` (route `core:finance_transactions`):
- Confirm the `.stu-header` brand card and breadcrumb render.
- Confirm there are no more dead `href="#"` buttons on the page.
- Confirm no JS console errors and the page loads without a 500.

- [ ] **Step 4: Commit**

```bash
git add core/templates/core/finance/transactions.html
git commit -m "Restyle finance transactions screen and remove non-functional expense/income/revert buttons"
```

---

## Final Verification

After all 9 tasks are complete:

- [ ] Run `docker exec -it pinewood-web-1 python manage.py check` — expect `System check identified no issues (0 silenced).`
- [ ] Click through all 7 in-scope screens in a browser end to end (Finance dashboard → Fees dashboard → Master Fees → Create Fees → Fee Categories → Student Fee Management → Transactions), confirming consistent `.stu-header` styling and pinewood table styling throughout, and that every CRUD action that's supposed to work (create/edit/delete category, create/edit/delete particular, create/edit/delete discount, create category, pay/reverse/waiver/statement) still works.
- [ ] Confirm the 3 previously-broken/removed items are resolved: fee category Edit persists, fee category Delete removes the row, `create_fees.html` no longer shows "will be implemented here" stub text, `transactions.html` no longer shows dead `href="#"` buttons.
