"""Shared QuickBooks sync scheduling, usable by any service that creates a
FinanceFee charge or FeeTransaction payment - not just FinanceService.
"""
import logging


def enqueue_qb_sync(tenant, kind: str, object_id) -> None:
    """Schedule a QuickBooks sync for a charge/payment AFTER the current
    transaction commits, so a QB outage never blocks or rolls back the local
    fee operation. No-op when QuickBooks is not connected for the tenant.
    """
    from django.db import transaction

    try:
        from core.signals import is_quickbooks_enabled
        if not is_quickbooks_enabled(tenant):
            return
    except Exception:
        return

    tenant_id = str(tenant.id)
    oid = str(object_id)

    def _fire():
        try:
            from core.tasks import (
                sync_fee_charge_to_quickbooks,
                sync_fee_payment_to_quickbooks,
                resync_fee_invoice_to_quickbooks,
            )
            task = {
                'charge': sync_fee_charge_to_quickbooks,
                'payment': sync_fee_payment_to_quickbooks,
                'invoice_resync': resync_fee_invoice_to_quickbooks,
            }.get(kind)
            if task is None:
                logging.getLogger('finance').warning(
                    "enqueue_qb_sync: unknown kind %r", kind)
                return
            task.delay(tenant_id, oid)
        except Exception:
            logging.getLogger('finance').exception("Failed to enqueue QuickBooks sync")

    transaction.on_commit(_fire)
