"""Template access to the Custom Words configuration.

    {% load custom_words %}
    {% custom_word "student" %}            → "Pupil"      (or "student" if unset)
    {% custom_word "student" plural=True %} → "Pupils"
    {{ "class"|word }}                      → filter form, singular only

Terminology is resolved once per request and cached on the request object.
"""
from __future__ import annotations

from django import template

from core.services.configuration_service import terminology_map

register = template.Library()

_CACHE_ATTR = "_terminology_map"


def _map_for(context):
    request = context.get("request")
    tenant = getattr(request, "tenant", None) if request else None
    if tenant is None:
        return {}
    if request is not None:
        cached = getattr(request, _CACHE_ATTR, None)
        if cached is None:
            cached = terminology_map(tenant)
            setattr(request, _CACHE_ATTR, cached)
        return cached
    return terminology_map(tenant)


def _resolve(mapping, term, plural=False):
    entry = mapping.get((term or "").lower())
    if entry:
        return entry["many" if plural else "one"]
    return f"{term}s" if plural else term


@register.simple_tag(takes_context=True)
def custom_word(context, term, plural=False):
    return _resolve(_map_for(context), term, plural)


@register.simple_tag(takes_context=True)
def custom_word_cap(context, term, plural=False):
    return _resolve(_map_for(context), term, plural).capitalize()


@register.filter(name="word")
def word_filter(term):
    # Filters get no context; falls back to the raw term when no request is
    # in scope. Use the {% custom_word %} tag where a tenant lookup matters.
    return term
