from django import template
from django.utils.safestring import mark_safe
from core.services.currency_service import CurrencyService

register = template.Library()


def _get_service(request):
    """Resolve a CurrencyService for the request's tenant, or None."""
    tenant = getattr(request, 'tenant', None)
    return CurrencyService(tenant) if tenant else None


@register.filter
def format_currency(amount, request=None):
    """Format amount using the tenant's active currency configuration"""
    service = _get_service(request)
    if service:
        try:
            return mark_safe(service.format_amount(amount or 0))
        except Exception:
            pass
    defaults = CurrencyService.get_default_currency_context()
    try:
        return f"{defaults['currency_symbol']}{float(amount or 0):.2f}"
    except (TypeError, ValueError):
        return f"{defaults['currency_symbol']}0.00"


@register.simple_tag(takes_context=True)
def currency_format(context, amount):
    """Template tag to format currency using tenant's configuration"""
    request = context.get('request')
    return format_currency(amount, request)


@register.simple_tag(takes_context=True)
def currency_symbol(context):
    """Get the current tenant's currency symbol"""
    service = _get_service(context.get('request'))
    if service:
        try:
            return service.get_currency_symbol()
        except Exception:
            pass
    return CurrencyService.get_default_currency_context()['currency_symbol']


@register.simple_tag(takes_context=True)
def currency_code(context):
    """Get the current tenant's currency code"""
    service = _get_service(context.get('request'))
    if service:
        try:
            return service.get_currency_code()
        except Exception:
            pass
    return CurrencyService.get_default_currency_context()['currency_code']


@register.simple_tag(takes_context=True)
def currency_info(context):
    """Get the current tenant's currency information as a dict"""
    service = _get_service(context.get('request'))
    if service:
        try:
            config = service.currency_config
            return {
                'code': config.currency_code,
                'symbol': config.currency_symbol,
                'name': config.currency_name,
                'position': config.symbol_position,
                'decimal_places': config.decimal_places,
            }
        except Exception:
            pass
    defaults = CurrencyService.get_default_currency_context()
    return {
        'code': defaults['currency_code'],
        'symbol': defaults['currency_symbol'],
        'name': defaults['currency_name'],
        'position': defaults['symbol_position'],
        'decimal_places': defaults['decimal_places'],
    }
