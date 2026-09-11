"""
Currency Service for handling currency formatting and configuration.
"""

from typing import Optional, Any
from decimal import Decimal
from django.utils import timezone
from ..models import CurrencyConfiguration


class CurrencyService:
    """Service for currency operations and formatting"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self._currency_config = None
    
    @property
    def currency_config(self) -> CurrencyConfiguration:
        """Get the active currency configuration for the tenant"""
        if self._currency_config is None:
            self._currency_config = CurrencyConfiguration.get_active_currency(self.tenant)
        return self._currency_config
    
    def format_amount(self, amount: Any) -> str:
        """
        Format an amount using the tenant's currency configuration
        
        Args:
            amount: The amount to format (can be int, float, Decimal, str)
            
        Returns:
            Formatted currency string
        """
        return self.currency_config.format_amount(amount)
    
    def get_currency_symbol(self) -> str:
        """Get the currency symbol for the tenant"""
        return self.currency_config.currency_symbol
    
    def get_currency_code(self) -> str:
        """Get the currency code for the tenant"""
        return self.currency_config.currency_code
    
    def get_currency_name(self) -> str:
        """Get the currency name for the tenant"""
        return self.currency_config.currency_name
    
    def get_currency_context(self) -> dict:
        """
        Get currency context data for templates
        
        Returns:
            Dictionary with currency information
        """
        config = self.currency_config
        return {
            'currency_symbol': config.currency_symbol,
            'currency_code': config.currency_code,
            'currency_name': config.currency_name,
            'symbol_position': config.symbol_position,
            'decimal_places': config.decimal_places,
            'thousands_separator': config.thousands_separator,
            'decimal_separator': config.decimal_separator,
        }
    
    @staticmethod
    def get_default_currency_context() -> dict:
        """
        Get default currency context when no tenant is available
        
        Returns:
            Dictionary with default Zambian Kwacha information
        """
        return {
            'currency_symbol': 'K',
            'currency_code': 'ZMW',
            'currency_name': 'Zambian Kwacha',
            'symbol_position': 'before',
            'decimal_places': 2,
            'thousands_separator': ',',
            'decimal_separator': '.',
        }


class CurrencyContextMixin:
    """Mixin to add currency context to views"""
    
    def get_currency_service(self):
        """Get currency service for the current tenant"""
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return CurrencyService(tenant)
        return None
    
    def get_currency_context(self):
        """Get currency context for templates"""
        service = self.get_currency_service()
        if service:
            return service.get_currency_context()
        return CurrencyService.get_default_currency_context()
    
    def get_context_data(self, **kwargs):
        """Add currency context to template context"""
        context = super().get_context_data(**kwargs)
        
        # Add currency context
        currency_context = self.get_currency_context()
        context.update(currency_context)
        
        # Add currency service for template use
        service = self.get_currency_service()
        if service:
            context['currency_service'] = service
            context['format_currency'] = service.format_amount
        
        return context