"""Template context processor exposing the current user's permission codenames.

Registered in ``pinewood/settings.py`` TEMPLATES. In a template::

    {% if "hr.leave.approve" in perms %} ... {% endif %}

``perms`` is a set-like wrapper of codename strings, resolved from the user's
roles in the current tenant (``is_root`` users get the full set).
"""
from __future__ import annotations

from .access import request_permission_set


class _Perms:
    """Wraps the codename set so templates can also do ``perms.hr.employee.manage``
    style dotted lookups if desired, while ``in`` keeps working."""

    __slots__ = ("_codes",)

    def __init__(self, codes):
        self._codes = codes

    def __contains__(self, item):
        return item in self._codes

    def __iter__(self):
        return iter(self._codes)

    def __bool__(self):
        return bool(self._codes)

    def __len__(self):
        return len(self._codes)


def authz(request):
    try:
        codes = request_permission_set(request)
    except Exception:
        codes = frozenset()
    return {"perms": _Perms(codes)}
