"""QuickBooks -> Pinewood reconciliation / linking.

Used at go-live for a school whose QuickBooks company is *ahead of* Pinewood:
instead of pushing (which would duplicate the invoices/payments the school
already has in QuickBooks), we find those existing QuickBooks records, match
them to their Pinewood counterparts on name + amount + date, and write the
QuickBooks ids into the QuickBooks*Sync tables as ``synced``. From then on the
normal forward-only sync *updates* those linked records.

Matching is fuzzy and never auto-applied: ``propose_*`` returns candidate rows
for a human to review (a CSV, via the ``quickbooks_link_propose`` command);
``apply_*`` consumes the reviewed rows (``quickbooks_link_apply``).
"""
import difflib
import logging
import re
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.utils import timezone

from core.models import (
    FamilyInvoice, FamilyInvoiceLine, FeeTransaction, Guardian, Student,
    QuickBooksCustomerSync, QuickBooksFeeInvoiceSync, QuickBooksFeeInvoiceLineSync,
    QuickBooksFeePaymentSync,
)
from core.services.quickbooks_service import QuickBooksService

logger = logging.getLogger(__name__)

try:
    from quickbooks.accounts import QuickBooksCustomerManager, QuickBooksInvoiceManager
except ImportError:  # pragma: no cover
    QuickBooksCustomerManager = None
    QuickBooksInvoiceManager = None


# --------------------------------------------------------------------------- #
# Pure matching helpers (no I/O - unit-tested directly)
# --------------------------------------------------------------------------- #

def normalize_name(value: Optional[str]) -> str:
    """Lower-case, drop any ``(...)`` suffix, strip punctuation, sort tokens.

    So ``"Banda, John"``, ``"John Banda"`` and ``"John Banda (G-1a2b3c4d)"`` all
    normalize to ``"banda john"``.
    """
    s = (value or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(sorted(t for t in s.split() if t))


def name_score(a: Optional[str], b: Optional[str]) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return round(difflib.SequenceMatcher(None, na, nb).ratio(), 4)


def _to_date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def txn_score(local_amount, local_date, qbo_amount, qbo_date,
              window_days: int = 14, amount_tolerance: Decimal = Decimal("0.01")) -> float:
    """Confidence (0..1) that a local charge/payment is the same as a
    QuickBooks one, from amount closeness (weighted 0.6) and date proximity
    (0.4). Amounts within ``amount_tolerance`` and same-day score 1.0.
    """
    la = Decimal(str(local_amount or 0))
    qa = Decimal(str(qbo_amount or 0))
    amt_diff = abs(la - qa)
    if amt_diff <= amount_tolerance:
        amt_component = 1.0
    else:
        amt_component = max(0.0, 1.0 - float(amt_diff) / max(float(la), 1.0))

    ld, qd = _to_date(local_date), _to_date(qbo_date)
    if ld and qd:
        day_diff = abs((ld - qd).days)
        date_component = max(0.0, 1.0 - day_diff / max(window_days, 1))
    else:
        date_component = 0.0

    return round(0.6 * amt_component + 0.4 * date_component, 4)


# --------------------------------------------------------------------------- #

class QuickBooksLinkService:
    def __init__(self, tenant):
        self.tenant = tenant
        self.qb_service = QuickBooksService(tenant)
        self._customer_manager = None
        self._invoice_manager = None

    @property
    def customer_manager(self):
        if self._customer_manager is None:
            auth = self.qb_service.get_auth_client()
            auth.ensure_valid_token()
            self._customer_manager = QuickBooksCustomerManager(auth)
        return self._customer_manager

    @property
    def invoice_manager(self):
        if self._invoice_manager is None:
            auth = self.qb_service.get_auth_client()
            auth.ensure_valid_token()
            self._invoice_manager = QuickBooksInvoiceManager(auth)
        return self._invoice_manager

    # ---- billable-guardian helpers -------------------------------------- #

    def _billable_guardians(self) -> List[Guardian]:
        """Guardians that have at least one local invoice - the only ones worth
        matching to a QuickBooks customer."""
        guardian_ids = FamilyInvoice.objects.filter(
            tenant=self.tenant
        ).values_list("guardian_id", flat=True).distinct()
        return list(
            Guardian.objects.filter(tenant=self.tenant, id__in=list(guardian_ids))
        )

    @staticmethod
    def _guardian_name(guardian: Guardian) -> str:
        return f"{guardian.first_name} {guardian.last_name}".strip()

    # ---- PROPOSE ------------------------------------------------------- #

    def propose_customer_links(self, min_score: float = 0.85) -> List[Dict[str, Any]]:
        qbo_customers = self.customer_manager.list_all_customers(active_only=False)
        already_linked = set(
            QuickBooksCustomerSync.objects.filter(
                tenant=self.tenant, sync_status="synced",
            ).exclude(quickbooks_customer_id__isnull=True)
            .exclude(quickbooks_customer_id="")
            .values_list("guardian_id", flat=True)
        )

        rows: List[Dict[str, Any]] = []
        for guardian in self._billable_guardians():
            if guardian.id in already_linked:
                continue
            gname = self._guardian_name(guardian)
            best, best_score = None, 0.0
            for cust in qbo_customers:
                score = max(
                    name_score(gname, getattr(cust, "DisplayName", None)),
                    name_score(gname, " ".join(
                        p for p in [getattr(cust, "GivenName", None),
                                    getattr(cust, "FamilyName", None)] if p)),
                )
                if score > best_score:
                    best, best_score = cust, score
            rows.append({
                "decision": "",
                "score": best_score,
                "match_type": "exact" if best_score >= 0.999 else (
                    "candidate" if best_score >= min_score else "weak"),
                "guardian_id": str(guardian.id),
                "guardian_name": gname,
                "qbo_customer_id": getattr(best, "Id", "") if best else "",
                "qbo_display_name": getattr(best, "DisplayName", "") if best else "",
                "qbo_balance": getattr(best, "Balance", "") if best else "",
            })
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows

    def _linked_customer_map(self) -> Dict[str, QuickBooksCustomerSync]:
        """{qbo_customer_id: QuickBooksCustomerSync} for already-linked guardians."""
        out = {}
        for cs in QuickBooksCustomerSync.objects.filter(
            tenant=self.tenant, sync_status="synced",
        ).exclude(quickbooks_customer_id__isnull=True).exclude(quickbooks_customer_id=""):
            out[str(cs.quickbooks_customer_id)] = cs
        return out

    def propose_invoice_links(self, academic_year=None, window_days: int = 21,
                              amount_tolerance: Decimal = Decimal("0.01"),
                              since: Optional[str] = None) -> List[Dict[str, Any]]:
        cust_map = self._linked_customer_map()
        if not cust_map:
            logger.warning("propose_invoice_links: no linked customers yet - "
                           "apply customer links first")

        qbo_invoices = self.invoice_manager.list_invoices(since=since)
        # index QBO invoices by customer id
        by_customer: Dict[str, list] = {}
        for inv in qbo_invoices:
            cid = str(getattr(getattr(inv, "CustomerRef", None), "value", "") or "")
            by_customer.setdefault(cid, []).append(inv)

        local = FamilyInvoice.objects.filter(tenant=self.tenant).select_related(
            "guardian", "academic_year")
        if academic_year is not None:
            local = local.filter(academic_year=academic_year)
        already = set(
            QuickBooksFeeInvoiceSync.objects.filter(
                tenant=self.tenant, sync_status="synced",
            ).exclude(family_invoice__isnull=True).values_list("family_invoice_id", flat=True)
        )

        rows: List[Dict[str, Any]] = []
        for fi in local:
            if fi.id in already:
                continue
            cs = None
            for cid, sync in cust_map.items():
                if sync.guardian_id == fi.guardian_id:
                    cs = (cid, sync)
                    break
            candidates = by_customer.get(cs[0], []) if cs else []
            best, best_score = None, 0.0
            for inv in candidates:
                score = txn_score(
                    fi.total_amount, fi.due_date or fi.generated_at,
                    getattr(inv, "TotalAmt", None), getattr(inv, "TxnDate", None),
                    window_days, amount_tolerance)
                if score > best_score:
                    best, best_score = inv, score
            rows.append({
                "decision": "",
                "score": best_score,
                "family_invoice_id": str(fi.id),
                "invoice_number": fi.invoice_number,
                "guardian_name": self._guardian_name(fi.guardian),
                "academic_year": fi.academic_year.name if fi.academic_year else "",
                "local_total": str(fi.total_amount),
                "local_balance_due": str(fi.balance_due),
                "qbo_invoice_id": getattr(best, "Id", "") if best else "",
                "qbo_doc_number": getattr(best, "DocNumber", "") if best else "",
                "qbo_txn_date": getattr(best, "TxnDate", "") if best else "",
                "qbo_total": getattr(best, "TotalAmt", "") if best else "",
                "qbo_balance": getattr(best, "Balance", "") if best else "",
                "qbo_candidates_count": len(candidates),
                "customer_linked": bool(cs),
            })
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows

    def propose_payment_links(self, academic_year=None, window_days: int = 14,
                              amount_tolerance: Decimal = Decimal("0.01"),
                              since: Optional[str] = None) -> List[Dict[str, Any]]:
        cust_map = self._linked_customer_map()
        guardian_to_cid = {sync.guardian_id: cid for cid, sync in cust_map.items()}

        qbo_payments = self.invoice_manager.list_payments(since=since)
        by_customer: Dict[str, list] = {}
        for p in qbo_payments:
            cid = str(getattr(getattr(p, "CustomerRef", None), "value", "") or "")
            by_customer.setdefault(cid, []).append(p)

        local = FeeTransaction.objects.filter(
            tenant=self.tenant, transaction_type="payment",
        ).select_related("student", "student__immediate_contact", "academic_year")
        if academic_year is not None:
            local = local.filter(academic_year=academic_year)
        already = set(
            QuickBooksFeePaymentSync.objects.filter(
                tenant=self.tenant,
            ).exclude(fee_transaction__isnull=True).values_list("fee_transaction_id", flat=True)
        )

        rows: List[Dict[str, Any]] = []
        for ft in local:
            if ft.id in already:
                continue
            guardian = getattr(ft.student, "immediate_contact", None) if ft.student else None
            cid = guardian_to_cid.get(guardian.id) if guardian else None
            candidates = by_customer.get(cid, []) if cid else []
            best, best_score = None, 0.0
            for p in candidates:
                score = txn_score(
                    ft.amount, ft.transaction_date,
                    getattr(p, "TotalAmt", None), getattr(p, "TxnDate", None),
                    window_days, amount_tolerance)
                if score > best_score:
                    best, best_score = p, score
            rows.append({
                "decision": "",
                "score": best_score,
                "fee_transaction_id": str(ft.id),
                "student_name": f"{ft.student.first_name} {ft.student.last_name}" if ft.student else "",
                "guardian_name": self._guardian_name(guardian) if guardian else "",
                "local_amount": str(ft.amount),
                "local_date": ft.transaction_date.date().isoformat()
                    if hasattr(ft.transaction_date, "date") else str(ft.transaction_date),
                "reference_number": ft.reference_number or "",
                "qbo_payment_id": getattr(best, "Id", "") if best else "",
                "qbo_txn_date": getattr(best, "TxnDate", "") if best else "",
                "qbo_total": getattr(best, "TotalAmt", "") if best else "",
                "qbo_candidates_count": len(candidates),
                "customer_linked": bool(cid),
            })
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows

    # ---- APPLY -------------------------------------------------------- #

    @staticmethod
    def _resolve_decision(row: Dict[str, str], id_field: str) -> Optional[str]:
        """Return the QuickBooks id to link, or None to skip.

        ``approve`` -> the proposed id in ``row[id_field]``;
        ``manual:<id>`` -> ``<id>``; anything else (blank, ``reject``) -> skip.
        """
        decision = (row.get("decision") or "").strip().lower()
        if decision in ("approve", "approved", "yes", "y"):
            return (row.get(id_field) or "").strip() or None
        if decision.startswith("manual:"):
            return decision.split(":", 1)[1].strip() or None
        return None

    def apply_customer_links(self, rows: List[Dict[str, str]], dry_run: bool = False) -> Dict[str, Any]:
        result = {"linked": 0, "skipped": 0, "errors": []}
        seen_qbo_ids = set()
        for row in rows:
            qbo_id = self._resolve_decision(row, "qbo_customer_id")
            if not qbo_id:
                result["skipped"] += 1
                continue
            guardian_id = row.get("guardian_id")
            if qbo_id in seen_qbo_ids or QuickBooksCustomerSync.objects.filter(
                tenant=self.tenant, quickbooks_customer_id=qbo_id,
            ).exclude(guardian_id=guardian_id).exists():
                result["errors"].append(
                    f"guardian {guardian_id}: QBO customer {qbo_id} already linked elsewhere")
                continue
            seen_qbo_ids.add(qbo_id)
            if dry_run:
                result["linked"] += 1
                continue
            QuickBooksCustomerSync.objects.update_or_create(
                tenant=self.tenant, guardian_id=guardian_id,
                defaults={
                    "quickbooks_customer_id": qbo_id,
                    "customer_display_name": row.get("qbo_display_name") or row.get("guardian_name") or "",
                    "sync_status": "synced",
                    "last_synced": timezone.now(),
                    "sync_error": None,
                    "review_note": "linked via reconciliation "
                                   f"{timezone.now().date().isoformat()}",
                },
            )
            result["linked"] += 1
        return result

    def apply_invoice_links(self, rows: List[Dict[str, str]], dry_run: bool = False) -> Dict[str, Any]:
        result = {"linked": 0, "skipped": 0, "needs_review": 0, "errors": []}
        for row in rows:
            qbo_id = self._resolve_decision(row, "qbo_invoice_id")
            if not qbo_id:
                result["skipped"] += 1
                continue
            fi = FamilyInvoice.objects.filter(
                tenant=self.tenant, id=row.get("family_invoice_id"),
            ).select_related("guardian", "academic_year").first()
            if fi is None:
                result["errors"].append(f"family_invoice {row.get('family_invoice_id')} not found")
                continue

            cs = QuickBooksCustomerSync.objects.filter(
                tenant=self.tenant, guardian_id=fi.guardian_id, sync_status="synced",
            ).first()
            if cs is None:
                result["errors"].append(
                    f"invoice {fi.invoice_number}: guardian not linked to a QBO customer yet")
                continue

            clash = QuickBooksFeeInvoiceSync.objects.filter(
                tenant=self.tenant, quickbooks_invoice_id=qbo_id,
            ).exclude(family_invoice_id=fi.id).first()
            if clash is not None:
                result["errors"].append(
                    f"invoice {fi.invoice_number}: QBO invoice {qbo_id} already linked")
                continue

            try:
                qb_invoice = self.invoice_manager.get_invoice(qbo_id)
            except Exception as e:
                result["errors"].append(f"invoice {fi.invoice_number}: QBO lookup failed: {e}")
                continue
            if qb_invoice is None:
                result["errors"].append(f"invoice {fi.invoice_number}: QBO invoice {qbo_id} not found")
                continue

            qb_balance = Decimal(str(getattr(qb_invoice, "Balance", None) or fi.balance_due))
            lines = list(fi.lines.select_related("finance_fee", "student").all())
            qb_lines = getattr(qb_invoice, "Line", []) or []
            unmatched_lines = 0

            if dry_run:
                result["linked"] += 1
                continue

            header, _ = QuickBooksFeeInvoiceSync.objects.update_or_create(
                tenant=self.tenant, guardian_id=fi.guardian_id, academic_year=fi.academic_year,
                defaults={
                    "family_invoice": fi,
                    "quickbooks_customer_sync": cs,
                    "quickbooks_invoice_id": qbo_id,
                    "quickbooks_doc_number": getattr(qb_invoice, "DocNumber", "") or "",
                    "total_amount": fi.total_amount,
                    "due_date": fi.due_date or timezone.now().date(),
                    "balance_remaining": qb_balance,
                    "is_paid": qb_balance <= Decimal("0"),
                    "sync_status": "synced",
                    "synced_at": timezone.now(),
                    "sync_error": None,
                    "review_note": "linked via reconciliation "
                                   f"{timezone.now().date().isoformat()}",
                },
            )

            for line in lines:
                qb_line_id = _match_qb_line_id(line, qb_lines)
                if qb_line_id is None:
                    unmatched_lines += 1
                QuickBooksFeeInvoiceLineSync.objects.update_or_create(
                    tenant=self.tenant, finance_fee=line.finance_fee,
                    defaults={
                        "invoice_sync": header,
                        "student": line.student,
                        "description": line.description,
                        "amount": line.amount,
                        "qb_line_id": qb_line_id,
                        "sync_status": "synced",
                        "synced_at": timezone.now(),
                        "sync_error": None,
                    },
                )

            if unmatched_lines:
                header.needs_review = True
                header.review_note = (
                    f"linked via reconciliation; {unmatched_lines}/{len(lines)} "
                    f"line(s) could not be matched to a QBO line id")
                header.save(update_fields=["needs_review", "review_note"])
                result["needs_review"] += 1
            result["linked"] += 1
        return result

    def apply_payment_links(self, rows: List[Dict[str, str]], dry_run: bool = False) -> Dict[str, Any]:
        result = {"linked": 0, "skipped": 0, "errors": []}
        for row in rows:
            qbo_id = self._resolve_decision(row, "qbo_payment_id")
            if not qbo_id:
                result["skipped"] += 1
                continue
            ft = FeeTransaction.objects.filter(
                tenant=self.tenant, id=row.get("fee_transaction_id"),
                transaction_type="payment",
            ).select_related("student", "student__immediate_contact").first()
            if ft is None:
                result["errors"].append(f"fee_transaction {row.get('fee_transaction_id')} not found")
                continue

            clash = QuickBooksFeePaymentSync.objects.filter(
                tenant=self.tenant, quickbooks_payment_id=qbo_id,
            ).exclude(fee_transaction_id=ft.id).first()
            if clash is not None:
                result["errors"].append(f"payment {ft.id}: QBO payment {qbo_id} already linked")
                continue

            guardian = getattr(ft.student, "immediate_contact", None) if ft.student else None
            cs = QuickBooksCustomerSync.objects.filter(
                tenant=self.tenant, guardian=guardian, sync_status="synced",
            ).first() if guardian else None
            related_invoice = QuickBooksFeeInvoiceSync.objects.filter(
                tenant=self.tenant, guardian=guardian,
                academic_year_id=ft.academic_year_id, sync_status="synced",
            ).first() if guardian else None

            if dry_run:
                result["linked"] += 1
                continue

            payment_date = ft.transaction_date.date() if hasattr(ft.transaction_date, "date") \
                else ft.transaction_date
            QuickBooksFeePaymentSync.objects.update_or_create(
                tenant=self.tenant, fee_transaction=ft,
                defaults={
                    "student": ft.student,
                    "related_invoice": related_invoice,
                    "quickbooks_customer_sync": cs,
                    "quickbooks_payment_id": qbo_id,
                    "amount": ft.amount,
                    "payment_date": payment_date,
                    "payment_method": ft.payment_method,
                    "reference_number": ft.reference_number,
                    "sync_status": "synced",
                    "synced_at": timezone.now(),
                    "sync_error": None,
                    "review_note": "linked via reconciliation "
                                   f"{timezone.now().date().isoformat()}",
                },
            )
            result["linked"] += 1
        return result


def _match_qb_line_id(line: FamilyInvoiceLine, qb_lines: list) -> Optional[str]:
    """Best-effort: a QBO line with the same amount (and, preferably, the
    student name in its description). Returns its ``Id`` or None.
    """
    target = Decimal(str(line.amount))
    student_name = ""
    if getattr(line, "student", None):
        student_name = f"{line.student.first_name} {line.student.last_name}".lower()

    amount_matches = []
    for ql in qb_lines:
        if not isinstance(ql, dict):
            continue
        # Only item lines carry a charge; skip SubTotal/Discount lines.
        if ql.get("DetailType") not in ("SalesItemLineDetail", None):
            continue
        amt = ql.get("Amount")
        if amt is None:
            continue
        if abs(Decimal(str(amt)) - target) <= Decimal("0.01"):
            amount_matches.append(ql)

    if not amount_matches:
        return None
    if len(amount_matches) == 1:
        return amount_matches[0].get("Id")
    for ql in amount_matches:
        desc = (ql.get("Description") or "").lower()
        if student_name and student_name in desc:
            return ql.get("Id")
    return amount_matches[0].get("Id")
