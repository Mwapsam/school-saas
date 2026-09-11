from django import template
from django.http import QueryDict

register = template.Library()


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Return the current request's query string with the given kwargs
    added/overridden — used by pagination links so filters/search terms
    survive a page change without each page hand-writing which GET params
    to preserve."""
    request = context.get('request')
    params = request.GET.copy() if request else QueryDict(mutable=True)
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key."""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def lookup(dictionary, key):
    """Lookup an item in a dictionary - alias for get_item for template readability."""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def split(value, separator):
    """Split a string by a separator."""
    if value is None:
        return []
    return value.split(separator)

@register.simple_tag
def get_score(score_lookup, exam_id, student_id):
    """Get score for a specific exam and student."""
    key = f"{exam_id}_{student_id}"
    return score_lookup.get(key)