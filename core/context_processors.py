"""Template context processors for the core app.

``terminology`` exposes the school's Custom Words (Configuration -> Custom Words)
as a ``terms`` mapping so any template can write::

    {{ terms.student }}          {# "Pupil"  — singular, capitalised #}
    {{ terms.student_plural }}   {# "Pupils" #}
    {% include '...page_header.html' with title=terms.student_plural %}

Unknown / unset terms fall back to the capitalised key itself, so
``{{ terms.student }}`` renders "Student" for a school that has not customised it.
Resolved once per request (cached on the request by ``terminology_map``).
"""
from __future__ import annotations


# English plural for the terms the templates actually use, so an un-customised
# school still reads "Classes"/"Batches", not "Classs"/"Batchs".
_DEFAULT_PLURALS = {
    "student": "Students", "class": "Classes", "batch": "Batches",
    "subject": "Subjects", "teacher": "Teachers", "guardian": "Guardians",
    "parent": "Parents", "admission": "Admissions", "term": "Terms",
    "exam": "Exams", "course": "Courses",
}


class _Terms:
    """Dict-ish: ``terms.student`` / ``terms.student_plural`` / ``terms['class']``.
    Missing key -> the key title-cased (``_DEFAULT_PLURALS`` for the ``_plural``
    form, else a naive trailing 's'). Never raises."""

    __slots__ = ("_map",)

    def __init__(self, mapping):
        self._map = mapping or {}

    def _lookup(self, key):
        key = str(key).replace(" ", "_").lower()
        plural = key.endswith("_plural")
        base = key[:-7] if plural else key
        name = base.replace("_", " ")
        entry = self._map.get(name)
        if entry:
            return entry["many"] if plural else entry["one"]
        if plural:
            return _DEFAULT_PLURALS.get(name, f"{name.title()}s")
        return name.title()

    def __getattr__(self, key):
        if key.startswith("_"):
            raise AttributeError(key)
        return self._lookup(key)

    def __getitem__(self, key):
        return self._lookup(key)

    def __contains__(self, key):
        k = str(key).replace(" ", "_").lower()
        base = k[:-7] if k.endswith("_plural") else k
        return base.replace("_", " ") in self._map


def terminology(request):
    try:
        from core.services.configuration_service import terminology_map
        tenant = getattr(request, "tenant", None)
        mapping = terminology_map(tenant) if tenant is not None else {}
    except Exception:
        mapping = {}
    return {"terms": _Terms(mapping)}


def module_access(request):
    """Expose enabled modules for the current tenant to templates."""
    try:
        from core.modules import enabled_modules_for

        tenant = getattr(request, "tenant", None)
        enabled = enabled_modules_for(tenant, request=request)
    except Exception:
        enabled = set()
    return {"enabled_modules": enabled}
