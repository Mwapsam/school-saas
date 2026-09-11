import logging
from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.generic import TemplateView, View
from django.contrib import messages
from django.urls import reverse
from django.db import transaction

from core.models import CurrencyConfiguration
from core.services.exceptions import ValidationException, ServiceException

logger = logging.getLogger(__name__)


class CurrencyConfigurationView(TemplateView):
    """Currency configuration page"""
    template_name = 'core/finance/currency_configuration.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        # Get active currency configuration
        try:
            active_currency = CurrencyConfiguration.objects.get(
                tenant=school,
                is_active=True
            )
        except CurrencyConfiguration.DoesNotExist:
            active_currency = None
        
        # Predefined currency options (Zambian Kwacha first as default)
        currency_options = [
            {'code': 'ZMW', 'symbol': 'K', 'name': 'Zambian Kwacha'},
            {'code': 'USD', 'symbol': '$', 'name': 'US Dollar'},
            {'code': 'EUR', 'symbol': '€', 'name': 'Euro'},
            {'code': 'GBP', 'symbol': '£', 'name': 'British Pound'},
            {'code': 'KES', 'symbol': 'KSh', 'name': 'Kenyan Shilling'},
            {'code': 'UGX', 'symbol': 'USh', 'name': 'Ugandan Shilling'},
            {'code': 'TZS', 'symbol': 'TSh', 'name': 'Tanzanian Shilling'},
            {'code': 'ZAR', 'symbol': 'R', 'name': 'South African Rand'},
            {'code': 'NGN', 'symbol': '₦', 'name': 'Nigerian Naira'},
            {'code': 'GHS', 'symbol': '₵', 'name': 'Ghanaian Cedi'},
            {'code': 'INR', 'symbol': '₹', 'name': 'Indian Rupee'},
            {'code': 'CAD', 'symbol': 'C$', 'name': 'Canadian Dollar'},
            {'code': 'AUD', 'symbol': 'A$', 'name': 'Australian Dollar'},
            {'code': 'JPY', 'symbol': '¥', 'name': 'Japanese Yen'},
            {'code': 'CNY', 'symbol': '¥', 'name': 'Chinese Yuan'},
            {'code': 'CHF', 'symbol': 'CHF', 'name': 'Swiss Franc'},
        ]
        
        context.update({
            'school': school,
            'active_currency': active_currency,
            'currency_options': currency_options,
            'back_url': self.request.GET.get('back', reverse('core:finance_settings')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Settings', 'url': reverse('core:finance_settings')},
                {'label': 'Currency Configuration'},
            ],
        })

        return context


class CurrencyConfigurationUpdateView(View):
    """Update currency configuration"""
    
    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            currency_code = request.POST.get('currency_code', '').strip()
            currency_symbol = request.POST.get('currency_symbol', '').strip()
            currency_name = request.POST.get('currency_name', '').strip()
            symbol_position = request.POST.get('symbol_position', 'before')
            decimal_places = request.POST.get('decimal_places', '2')
            thousands_separator = request.POST.get('thousands_separator', ',')
            decimal_separator = request.POST.get('decimal_separator', '.')
            
            # Validation
            if not all([currency_code, currency_symbol, currency_name]):
                return JsonResponse({
                    'error': 'Currency code, symbol, and name are required'
                }, status=400)
            
            try:
                decimal_places = int(decimal_places)
                if decimal_places < 0 or decimal_places > 4:
                    return JsonResponse({
                        'error': 'Decimal places must be between 0 and 4'
                    }, status=400)
            except ValueError:
                return JsonResponse({
                    'error': 'Invalid decimal places value'
                }, status=400)
            
            if symbol_position not in ['before', 'after', 'before_space', 'after_space']:
                return JsonResponse({
                    'error': 'Invalid symbol position'
                }, status=400)
            
            if thousands_separator not in [',', '.', ' ']:
                return JsonResponse({
                    'error': 'Invalid thousands separator'
                }, status=400)
            
            if decimal_separator not in ['.', ',']:
                return JsonResponse({
                    'error': 'Invalid decimal separator'
                }, status=400)
            
            with transaction.atomic():
                # Deactivate any existing active currency
                CurrencyConfiguration.objects.filter(
                    tenant=school,
                    is_active=True
                ).update(is_active=False)
                
                # Create or update currency configuration
                currency_config, created = CurrencyConfiguration.objects.update_or_create(
                    tenant=school,
                    currency_code=currency_code,
                    defaults={
                        'currency_symbol': currency_symbol,
                        'currency_name': currency_name,
                        'symbol_position': symbol_position,
                        'decimal_places': decimal_places,
                        'thousands_separator': thousands_separator,
                        'decimal_separator': decimal_separator,
                        'is_active': True,
                    }
                )
            
            # Test format example
            example_amount = currency_config.format_amount(1234.56)
            
            action = 'created' if created else 'updated'
            return JsonResponse({
                'success': True,
                'message': f'Currency configuration {action} successfully',
                'currency': {
                    'code': currency_config.currency_code,
                    'symbol': currency_config.currency_symbol,
                    'name': currency_config.currency_name,
                    'example': example_amount
                }
            })
            
        except Exception as e:
            logger.error(f"Error updating currency configuration: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class CurrencyPreviewView(View):
    """Preview currency formatting"""
    
    def get(self, request, *args, **kwargs):
        try:
            currency_symbol = request.GET.get('currency_symbol', '$')
            symbol_position = request.GET.get('symbol_position', 'before')
            decimal_places = int(request.GET.get('decimal_places', '2'))
            thousands_separator = request.GET.get('thousands_separator', ',')
            decimal_separator = request.GET.get('decimal_separator', '.')
            
            # Create temporary currency config for preview
            temp_config = CurrencyConfiguration(
                currency_symbol=currency_symbol,
                symbol_position=symbol_position,
                decimal_places=decimal_places,
                thousands_separator=thousands_separator,
                decimal_separator=decimal_separator
            )
            
            # Preview examples
            examples = {
                'small': temp_config.format_amount(25.50),
                'medium': temp_config.format_amount(1234.56),
                'large': temp_config.format_amount(123456.78),
                'zero': temp_config.format_amount(0),
            }
            
            return JsonResponse({
                'success': True,
                'examples': examples
            })
            
        except Exception as e:
            logger.error(f"Error generating currency preview: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)