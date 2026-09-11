"""
Dashboard re-exports for backward compatibility.

The actual implementation is in core.admin_utils which is referenced
from settings.py:
    UNFOLD["DASHBOARD_CALLBACK"] = "core.admin_utils.dashboard_callback"
"""

from core.admin_utils import (  # noqa
    dashboard_callback,
    is_public_schema,
    is_tenant_schema,
)