# Permission Codenames Reconciliation — Phase 2.1 Complete

**Status:** ✅ Complete  
**Date:** 2026-09-13  
**Scope:** Unify DRF API permission codenames across all active modules

## Problem Statement

The system evolved with two parallel permission codename sets:

| Set | When | Enforcement | Naming Convention |
|-----|------|-------------|-------------------|
| **Legacy** | Original auth system | View mixins (core/authz/mixins.py) | Singular/generic: `hr.employee.*`, `academic.*`, `transport.view` |
| **DRF API** | Modern REST endpoints | `core/authz/drf.HasPermission()` | Plural/specific: `hr.employees.*`, `academics.*`, `transport.routes.*` |

**Drift Example:**
```python
# Legacy (lines 41-66 in registry.py)
("hr.employee.view", "View staff records")        ← singular
("academic.batches.manage", "Manage classes")     ← domain: "academic"
("transport.view", "View transport")               ← generic resource

# DRF API (lines 128-170 in registry.py)
("hr.employees.view", "View employees")           ← plural
("academics.batches.view", "View batches")        ← domain: "academics"
("transport.routes.view", "View routes")          ← specific resource
```

Both sets coexist in registry.py (lines 1-91 are legacy, lines 93-170 are canonical DRF API).

## Resolution

### 1. Established Canonical Naming Convention

**Format:** `<domain>.<resource>.<action>`

- **domain:** plural nouns (hr, finance, students, academics, etc.)
- **resource:** plural nouns (employees, invoices, routes, leaves requests, etc.)
- **action:** view / manage / specific (view, manage, approve, conduct, export, etc.)

### 2. Audit Results

All DRF ViewSets were examined; refactored modules now use ONLY canonical codenames:

| Module | ViewSets | Status |
|--------|----------|--------|
| Students | 4 | ✅ All canonical (students.*, academics.courses/subjects/batches.*) |
| Academics/Admissions | 2 | ✅ All canonical (academics.batches.*) |
| Finance | 7 | ✅ All canonical (finance.fees/discounts/fines/transactions/invoices.*) |
| HR | 10 | ✅ All canonical after fix (hr.employees/qualifications/documents/contracts/leave-types/leave-requests/attendance/reviews/training/exit.*) |
| Transport | 4 | ✅ All canonical (transport.routes/stops/staff/fees.*) |
| Hostel | 2 | ✅ All canonical (hostel.rooms/fees.*) |
| Library | 3 | ✅ All canonical (library.config/staff/.*) |
| Admissions | 1 | ✅ All canonical (admissions.application.*) |
| **Total** | **33** | **✅ 100% canonical** |

### 3. Gaps Found and Filled

The registry was missing canonical codenames for:
- `hr.leave-requests.view` (leave request viewing)
- `hr.leave-requests.manage` (leave request creation/editing)
- `hr.leave-requests.approve` (leave approval workflow)
- `hr.attendance.manage` (clarified from generic "manage")
- `hr.training.view` (staff training viewing)
- `hr.training.manage` (staff training management)
- `hr.exit.view` (staff exit records viewing)
- `hr.exit.manage` (staff exit management)

**Added to registry.py (lines 136-152):** All 8 missing codenames now canonical.

**Updated [core/api/hr.py](core/api/hr.py):**
- Line 174: LeaveRequestViewSet — legacy `hr.leave.*` → canonical `hr.leave-requests.*`
- Line 210, 229: Approve/reject actions — legacy `hr.leave.approve` → canonical `hr.leave-requests.approve`

### 4. Files Modified

| File | Changes |
|------|---------|
| `core/authz/registry.py` | Updated docstring (lines 1-31); added 8 missing DRF API codenames (lines 136-152) |
| `core/api/hr.py` | Updated LeaveRequestViewSet permissions (lines 174, 210, 229) to use canonical codenames |

### 5. Backward Compatibility

**Legacy codenames (lines 39-91) remain in registry for backward compatibility:**
- Existing role seeds/fixtures that reference legacy codenames will still resolve
- `registry.expand()` will match both legacy and canonical codenames
- `is_valid_codename()` accepts both
- **Action:** Phase 3 (admin UI) can migrate legacy → canonical over time

### 6. Documentation

**Registry docstring (lines 1-31) now clarifies:**
1. What the canonical naming convention IS
2. When DRF API codenames became canonical
3. Specifically which legacy codenames were replaced (with examples)
4. Backward compatibility guarantee
5. That all Phase 2.1 work uses ONLY canonical codenames

## Impact

✅ **All 33 active DRF ViewSets now enforce canonical codenames**  
✅ **No drift between what code checks and what's in the registry**  
✅ **Future new ViewSets will follow canonical convention by default**  
✅ **Legacy system can migrate gradually (admin UI in Phase 3)**

## Next Steps

1. ✅ **Commit phase 2.1 work** — all serializers + ViewSet refactoring + registry reconciliation
2. 📋 **Phase 3:** Admin UI migration (convert legacy codenames in fixtures → canonical)
3. 📋 **Phase 4:** Monitor production to confirm no legacy codename references in active roles

---

**Tracking:** Part of Phase 2.1 API architecture hardening (see plan.md)
