from django.shortcuts import render, redirect
from django.http import Http404, JsonResponse, HttpResponse
from django.views.generic import TemplateView, View
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Case, When, Value, DecimalField, Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from decimal import Decimal, InvalidOperation

import logging

from core.models import (
    FinanceFee,
    FinanceTransaction,
    Student,
    Employee,
    QuickBooksIntegration,
    FeeCollection,
)
from core.services.exceptions import BusinessLogicException
from core.services.finance_service import FinanceService
from core.services.quickbooks_service import QuickBooksService
from core.view_modules.finance_year_context import build_year_context, resolve_selected_year

logger = logging.getLogger(__name__)


class FinanceDashboardView(TemplateView):
    """Main finance dashboard showing all finance modules"""
    template_name = 'core/finance/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        # Resolve the selected academic year; all figures below are scoped to it.
        selected_year = resolve_selected_year(self.request, school)

        try:
            finance_service = FinanceService(school)
            # Get financial summary (scoped to the selected academic year)
            financial_summary = finance_service.get_financial_summary(academic_year=selected_year)
        except Exception:
            # Fallback if finance service fails
            financial_summary = {
                'total_income': Decimal('0.00'),
                'total_expenses': Decimal('0.00'),
                'collected_fees': Decimal('0.00'),
                'pending_fees': Decimal('0.00')
            }

        # Get outstanding fees summary (scoped to the selected academic year)
        try:
            outstanding_qs = FinanceFee.objects.filter(tenant=school, balance__gt=0)
            if selected_year is not None:
                outstanding_qs = outstanding_qs.filter(academic_year=selected_year)
            outstanding_fees = outstanding_qs.aggregate(
                total_amount=Sum('balance'),
                student_count=Count('student', distinct=True)
            )
        except Exception:
            outstanding_fees = {'total_amount': Decimal('0.00'), 'student_count': 0}

        # Get recent transactions (scoped to the selected academic year)
        try:
            recent_qs = FinanceTransaction.objects.filter(
                tenant=school,
                student__isnull=False
            )
            if selected_year is not None:
                recent_qs = recent_qs.filter(academic_year=selected_year)
            recent_transactions = recent_qs.select_related('student', 'category').order_by('-transaction_date')[:10]
        except Exception:
            recent_transactions = []
        
        # Get employee count for payroll module
        try:
            employee_count = Employee.objects.filter(
                tenant=school,
                is_deleted=False
            ).count()
        except Exception:
            employee_count = 0
        
        # Get active fee collections count (scoped to the selected academic year)
        try:
            collections_qs = FeeCollection.objects.filter(tenant=school, is_active=True)
            if selected_year is not None:
                collections_qs = collections_qs.filter(academic_year=selected_year)
            active_collections_count = collections_qs.count()
        except Exception:
            active_collections_count = 0

        # Calculate net income
        net_income = financial_summary.get('total_income', Decimal('0.00')) - financial_summary.get('total_expenses', Decimal('0.00'))

        context.update({
            'school': school,
            'financial_summary': financial_summary,
            'outstanding_fees': outstanding_fees,
            'recent_transactions': recent_transactions,
            'employee_count': employee_count,
            'net_income': net_income,
            'active_collections_count': active_collections_count,
            'header_actions': [
                {'label': 'Back', 'variant': 'outline', 'icon': 'fa-arrow-left', 'url': reverse('core:dashboard')},
            ],
            'dashboard_tiles': [
                {'icon': 'fa-sitemap', 'title': 'Build Fee Structure', 'description': 'Create fee groups with particulars, fine slabs and batch assignment', 'url': reverse('core:fee_structure')},
                {'icon': 'fa-layer-group', 'title': 'Generate Collections', 'description': 'Create term-wise collections. Generates student fee obligations', 'url': reverse('core:fee_collections')},
                {'icon': 'fa-cash-register', 'title': 'Collect Fees', 'description': 'Itemized collection from student/guardian. System issues receipt', 'url': reverse('core:collect_fees')},
                {'icon': 'fa-chart-line', 'title': 'Track & Monitor', 'description': 'Student ledgers, family accounts, outstanding dues', 'url': reverse('core:finance_track')},
                {'icon': 'fa-file-invoice', 'title': 'Reports', 'description': 'Collections, dues, day book and statistics', 'url': reverse('core:finance_reports')},
                {'icon': 'fa-tags', 'title': 'Category', 'description': 'Manage fee categories used across fee groups and particulars', 'url': reverse('core:fee_categories')},
                {'icon': 'fa-gear', 'title': 'Finance Settings', 'description': 'Configure finance module preferences and defaults', 'url': reverse('core:finance_settings')},
            ],
        })
        context.update(build_year_context(self.request, school))

        return context


class FeeStructureView(TemplateView):
    """Finance workflow Step 1 hub: fee groups, particulars, fine slabs, batch assignment"""
    template_name = 'core/finance/fee_structure.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            return context

        from core.services.finance_service import FinanceService
        from core.models import FeeCategory, FeeParticular, FineSlab, BatchFeeCategory

        finance_service = FinanceService(school)

        context['fee_categories_count'] = FeeCategory.objects.filter(tenant=school, is_deleted=False).count()
        context['master_particulars_count'] = finance_service.list_master_particulars(is_active=None).count()
        context['master_discounts_count'] = finance_service.list_master_discounts(is_active=None).count()
        context['applicability_rules_count'] = finance_service.list_applicability_rules(is_active=None).count()
        context['fee_particulars_count'] = FeeParticular.objects.filter(tenant=school, is_active=True).count()
        context['fine_slabs_groups_count'] = FineSlab.objects.filter(tenant=school, is_active=True).values('fine_name').distinct().count()
        context['batch_assignments_count'] = BatchFeeCategory.objects.filter(tenant=school).count()
        context['back_url'] = self.request.GET.get('back', reverse('core:finance_dashboard'))
        context['crumbs'] = [
            {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
            {'label': 'Fee Structure'},
        ]

        return context


class FinanceSettingsView(TemplateView):
    """Finance settings page"""
    template_name = 'core/finance/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = self.request.GET.get('back', reverse('core:finance_dashboard'))
        context['crumbs'] = [
            {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
            {'label': 'Settings'},
        ]
        return context


class FinanceReportsView(TemplateView):
    """Finance reports page"""
    template_name = 'core/finance/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = self.request.GET.get('back', reverse('core:finance_dashboard'))
        context['crumbs'] = [
            {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
            {'label': 'Reports'},
        ]
        return context


class QuickBooksSettingsView(TemplateView):
    """QuickBooks integration settings page"""
    template_name = 'core/finance/quickbooks_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        qb_config = None
        config_warnings = []
        try:
            qb_service = QuickBooksService(school)
            connection_status = qb_service.get_connection_status()
            integration = qb_service.get_integration()
            config_warnings = qb_service.config_warnings()
            from core.models import QuickBooksConfiguration
            qb_config, _ = QuickBooksConfiguration.objects.get_or_create(tenant=school)
        except Exception as e:
            logger.error(f"Error getting QuickBooks status: {e}")
            connection_status = {
                'connected': False,
                'configured': False,
                'status': 'error',
                'message': 'Error loading QuickBooks integration'
            }
            integration = None

        context.update({
            'school': school,
            'connection_status': connection_status,
            'integration': integration,
            'qb_config': qb_config,
            'config_warnings': config_warnings,
            'back_url': self.request.GET.get('back', reverse('core:finance_settings')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Settings', 'url': reverse('core:finance_settings')},
                {'label': 'QuickBooks Integration'},
            ],
        })

        return context


class QuickBooksStatusView(View):
    """Lightweight GET endpoint returning the current QB connection status (DB-only, no QB API call)."""

    def get(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'connected': False, 'status': 'no_tenant'}, status=400)
        try:
            status = QuickBooksService(school).get_connection_status()
        except Exception as e:
            logger.error(f"QuickBooks status check failed: {e}")
            status = {'connected': False, 'status': 'error', 'message': 'Status check failed'}
        # last_sync may be a datetime; make it JSON-safe
        if status.get('last_sync'):
            status['last_sync'] = status['last_sync'].isoformat()
        return JsonResponse(status)


class QuickBooksConfigUpdateView(View):
    """Persist QuickBooks sync preferences: the auto-sync toggle and the
    default service item / income account fee charges are booked against."""

    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        from core.models import QuickBooksConfiguration
        qb_config, _ = QuickBooksConfiguration.objects.get_or_create(tenant=school)

        updated = []

        if 'auto_sync' in request.POST:
            auto_sync = request.POST.get('auto_sync', 'false').lower() in ('true', 'on', '1')
            qb_config.auto_sync_customers = auto_sync
            qb_config.auto_sync_invoices = auto_sync
            qb_config.auto_sync_payments = auto_sync
            updated += ['auto_sync_customers', 'auto_sync_invoices', 'auto_sync_payments']

        if 'default_service_item' in request.POST:
            item_id = (request.POST.get('default_service_item') or '').strip() or None
            if item_id:
                # Reject an id that is not a real Service/NonInventory item.
                from core.services.quickbooks_fee_sync_service import QuickBooksFeeSync
                try:
                    if not QuickBooksFeeSync(school).validate_service_item(item_id):
                        return JsonResponse(
                            {'error': f'Item {item_id} is not a valid QuickBooks service item'},
                            status=400,
                        )
                except Exception as e:
                    logger.warning(f"Could not validate QuickBooks item {item_id}: {e}")
            qb_config.default_service_item = item_id
            updated.append('default_service_item')

        if 'default_income_account' in request.POST:
            qb_config.default_income_account = (
                request.POST.get('default_income_account') or '').strip() or None
            updated.append('default_income_account')

        if updated:
            qb_config.save(update_fields=updated)

        return JsonResponse({
            'success': True,
            'auto_sync': qb_config.auto_sync_invoices,
            'default_service_item': qb_config.default_service_item,
        })


class QuickBooksItemsView(View):
    """GET -> the tenant's QuickBooks Service/NonInventory items, for the
    settings-page picker. Live QuickBooks call; returns [] on any failure."""

    def get(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        try:
            from core.services.quickbooks_fee_sync_service import QuickBooksFeeSync
            items = QuickBooksFeeSync(school).list_service_items()
            return JsonResponse({'items': items})
        except Exception as e:
            logger.warning(f"Failed to list QuickBooks items: {e}")
            return JsonResponse({'items': [], 'error': str(e)}, status=200)


class QuickBooksConnectView(View):
    """Handle QuickBooks OAuth connection initiation"""

    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            qb_service = QuickBooksService(school)

            # Get credentials from form
            client_id = request.POST.get('client_id')
            client_secret = request.POST.get('client_secret')
            environment = request.POST.get('environment', 'sandbox')

            if not client_id or not client_secret:
                return JsonResponse({
                    'error': 'Client ID and Client Secret are required'
                }, status=400)

            # Update credentials
            qb_service.update_credentials(client_id, client_secret, environment)

            # Get authorization URL (contains a CSRF 'state' param generated by the SDK)
            auth_url = qb_service.get_authorization_url()

            # Capture the state so we can validate it on the OAuth callback (CSRF protection)
            from urllib.parse import urlparse, parse_qs
            state_values = parse_qs(urlparse(auth_url).query).get('state', [])
            if state_values:
                request.session['qb_oauth_state'] = state_values[0]

            return JsonResponse({
                'success': True,
                'auth_url': auth_url,
                'message': 'Redirecting to QuickBooks for authorization...'
            })

        except Exception as e:
            # Avoid logging the client secret or full exception detail that may contain it
            logger.error("QuickBooks connect error for tenant %s", getattr(school, 'id', '?'))
            return JsonResponse({
                'error': f'Connection failed: {str(e)}'
            }, status=500)


class QuickBooksCallbackView(View):
    def get(self, request):
        school = getattr(request, "tenant", None)
        if not school:
            messages.error(request, "School not found")
            return redirect("core:quickbooks_settings")

        auth_code = request.GET.get("code")
        realm_id = request.GET.get("realmId")
        error = request.GET.get("error")
        returned_state = request.GET.get("state")

        if error:
            logger.error(f"QuickBooks OAuth error for tenant {school.id}: {error}")
            messages.error(request, f"QuickBooks authorization failed: {error}")
            return redirect("core:quickbooks_settings")

        # CSRF protection: the state returned by QuickBooks must match the one we stored
        expected_state = request.session.pop('qb_oauth_state', None)
        if not expected_state or returned_state != expected_state:
            logger.error(
                f"QuickBooks OAuth state mismatch for tenant {school.id} "
                f"(expected set={bool(expected_state)})"
            )
            messages.error(request, "Authorization failed: invalid or expired security token. Please try connecting again.")
            return redirect("core:quickbooks_settings")

        if not auth_code or not realm_id:
            logger.error(
                f"Missing OAuth parameters for tenant {school.id}: code={auth_code}, realmId={realm_id}"
            )
            messages.error(request, "Missing authorization parameters")
            return redirect("core:quickbooks_settings")

        try:
            qb_service = QuickBooksService(school)
            integration = qb_service.connect(auth_code, realm_id)
            messages.success(
                request, f"Successfully connected to QuickBooks! Company ID: {realm_id}"
            )

        except BusinessLogicException as e:
            logger.error(f"QuickBooks callback error for tenant {school.id}: {str(e)}")
            messages.error(request, f"Failed to connect to QuickBooks: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected QuickBooks callback error for tenant {school.id}: {str(e)}"
            )
            messages.error(
                request, "An unexpected error occurred while connecting to QuickBooks"
            )

        return redirect("core:quickbooks_settings")


class QuickBooksDisconnectView(View):
    """Handle QuickBooks disconnection"""
    
    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            qb_service = QuickBooksService(school)
            qb_service.disconnect()
            
            return JsonResponse({
                'success': True,
                'message': 'Successfully disconnected from QuickBooks'
            })
            
        except Exception as e:
            logger.error(f"QuickBooks disconnect error: {e}")
            return JsonResponse({
                'error': f'Disconnect failed: {str(e)}'
            }, status=500)


class QuickBooksTestConnectionView(View):
    """Test QuickBooks connection"""

    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            qb_service = QuickBooksService(school)
            result = qb_service.test_connection()

            if result['success']:
                return JsonResponse({
                    'success': True,
                    'message': result['message']
                })
            else:
                return JsonResponse({
                    'error': result['message']
                }, status=400)

        except Exception as e:
            logger.error(f"QuickBooks test connection error: {e}")
            return JsonResponse({
                'error': f'Connection test failed: {str(e)}'
            }, status=500)


class FeeReceiptsView(LoginRequiredMixin, TemplateView):
    """Fee receipts page under Finance Reports"""
    template_name = 'core/finance/fee_receipts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        # Permission gate: only admin users can generate receipts
        if not getattr(self.request.user, 'is_admin', False):
            raise PermissionDenied("Only admin users can access fee receipts.")

        # Get search parameters
        receipt_no = self.request.GET.get('receipt_no', '')
        from_date = self.request.GET.get('from_date', '')
        to_date = self.request.GET.get('to_date', '')

        # Start with all transactions for this tenant
        transactions = FinanceTransaction.objects.filter(tenant=school)

        # Apply filters if provided
        if receipt_no:
            transactions = transactions.filter(reference_number__icontains=receipt_no)

        if from_date:
            try:
                from datetime import datetime
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
                transactions = transactions.filter(transaction_date__gte=from_date_obj)
            except ValueError:
                pass

        if to_date:
            try:
                from datetime import datetime
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
                transactions = transactions.filter(transaction_date__lte=to_date_obj)
            except ValueError:
                pass

        # Filter transactions related to students (fee receipts)
        transactions = transactions.filter(student__isnull=False)

        # Order by most recent first
        transactions = transactions.order_by('-transaction_date', '-created_at')

        # Get only the fields we need
        transactions = transactions.select_related('student', 'employee', 'category')

        context.update({
            'school': school,
            'transactions': transactions,
            'receipt_no': receipt_no,
            'from_date': from_date,
            'to_date': to_date,
            'back_url': self.request.GET.get('back', reverse('core:finance_dashboard')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Receipts'},
            ],
        })

        return context


class FeeReceiptPDFView(LoginRequiredMixin, View):
    """Generate a printable PDF receipt for a single fee transaction."""

    def get(self, request, transaction_id):
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        from django.shortcuts import get_object_or_404
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.models import CurrencyConfiguration

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        # Permission gate: only admin users can generate receipts
        if not getattr(request.user, 'is_admin', False):
            raise PermissionDenied("Only admin users can access fee receipts.")

        txn = get_object_or_404(
            FinanceTransaction.objects.select_related('student', 'category', 'employee'),
            id=transaction_id, tenant=school,
        )

        currency = CurrencyConfiguration.get_active_currency(school)
        amount_display = currency.format_amount(txn.amount) if currency else f"{txn.amount:.2f}"

        # Build a stable receipt number if the transaction has none
        receipt_no = txn.reference_number or f"RCPT-{str(txn.id)[:8].upper()}"

        html_content = render_to_string('core/finance/receipt_pdf.html', {
            'school': school,
            'txn': txn,
            'receipt_no': receipt_no,
            'amount_display': amount_display,
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt_{receipt_no}.pdf"'
        return response


class InvoicePDFView(LoginRequiredMixin, View):
    """Generate a printable PDF for a guardian's consolidated FamilyInvoice."""

    def get(self, request, invoice_id):
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        from django.shortcuts import get_object_or_404
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.models import FamilyInvoice
        from core.services.invoice_service import build_invoice_pdf_context

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        invoice = get_object_or_404(
            FamilyInvoice.objects.select_related('guardian', 'academic_year'),
            id=invoice_id, tenant=school,
        )

        html_content = render_to_string('core/finance/invoice_pdf.html', build_invoice_pdf_context(invoice))
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice_{invoice.invoice_number}.pdf"'
        return response


class QuickBooksWebhookReviewView(View):
    """Staff-facing list of items flagged by the QuickBooks webhook handler
    (a change made directly in QuickBooks that didn't match local state).

    Never auto-resolves anything - staff investigate and mark reviewed once
    they've reconciled it manually (or confirmed it's a non-issue).
    """
    template_name = 'core/finance/quickbooks_webhook_review.html'

    def get(self, request):
        from core.models import QuickBooksCustomerSync, QuickBooksFeeInvoiceSync, QuickBooksFeePaymentSync

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        flagged = {
            'invoices': QuickBooksFeeInvoiceSync.objects.filter(
                tenant=school, needs_review=True
            ).select_related('guardian', 'academic_year').order_by('-synced_at'),
            'payments': QuickBooksFeePaymentSync.objects.filter(
                tenant=school, needs_review=True
            ).select_related('student').order_by('-payment_date'),
            'customers': QuickBooksCustomerSync.objects.filter(
                tenant=school, needs_review=True
            ).select_related('guardian').order_by('-last_synced'),
        }

        return render(request, self.template_name, {
            'school': school,
            'flagged': flagged,
            'flagged_count': sum(qs.count() for qs in flagged.values()),
            'back_url': request.GET.get('back', reverse('core:quickbooks_settings')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Settings', 'url': reverse('core:finance_settings')},
                {'label': 'QuickBooks', 'url': reverse('core:quickbooks_settings')},
                {'label': 'Webhook Review'},
            ],
        })

    def post(self, request):
        from core.models import QuickBooksCustomerSync, QuickBooksFeeInvoiceSync, QuickBooksFeePaymentSync

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        kind = request.POST.get('kind')
        item_id = request.POST.get('id')
        model_map = {
            'invoice': QuickBooksFeeInvoiceSync,
            'payment': QuickBooksFeePaymentSync,
            'customer': QuickBooksCustomerSync,
        }
        model = model_map.get(kind)
        if model is not None and item_id:
            model.objects.filter(tenant=school, id=item_id, needs_review=True).update(
                needs_review=False,
            )
            messages.success(request, "Marked as reviewed.")

        return redirect('core:quickbooks_webhook_review')


class DayBookReportView(TemplateView):
    """Fedena-style Day Book: per-day, per-payment-mode cash/bank
    reconciliation spanning fee collection and the general ledger
    (payroll, donations, etc). Calendar-date scoped, not academic-year
    scoped (a cash ledger, not a per-year statement)."""
    template_name = 'core/finance/day_book.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        from datetime import date, datetime, timedelta
        from core.services.fee_reporting_service import FeeReportingService

        today = date.today()
        from_date_str = self.request.GET.get('from_date', '')
        to_date_str = self.request.GET.get('to_date', '')

        try:
            date_from = datetime.strptime(from_date_str, '%Y-%m-%d').date() if from_date_str else today - timedelta(days=7)
        except ValueError:
            date_from = today - timedelta(days=7)
        try:
            date_to = datetime.strptime(to_date_str, '%Y-%m-%d').date() if to_date_str else today
        except ValueError:
            date_to = today

        day_book = None
        if date_from <= date_to:
            day_book = FeeReportingService(school).day_book(date_from, date_to)

        context.update({
            'school': school,
            'day_book': day_book,
            'date_from': date_from,
            'date_to': date_to,
        })
        if day_book:
            context['day_book_stats'] = [
                {'label': 'Total In', 'value': f"{day_book['total_in']:.2f}"},
                {'label': 'Total Out', 'value': f"{day_book['total_out']:.2f}"},
                {'label': 'Closing Balance', 'value': f"{day_book['closing_balance']:.2f}"},
            ]
            context['ledger_columns'] = ['Date', 'Opening', 'Total In', 'Total Out', 'Closing', 'By Mode']
        return context


class ParticularWiseStudentTransactionReportView(TemplateView):
    """Particular-wise Student Transaction Report page under Finance Reports"""
    template_name = 'core/finance/particular_wise_student_transaction_report.html'

    PAGE_SIZE = 20
    _DEBIT_TYPES = ('adjustment', 'fine')
    _CREDIT_TYPES = ('payment', 'discount', 'refund')

    def _get_filtered_students(self, school, request, selected_year=None):
        from core.models import Student, BatchStudent, Batch

        student_status = request.GET.get('student_status', 'active')
        class_filter = request.GET.get('class', 'all')
        batch_filter = request.GET.get('batch', 'all')

        students_query = Student.objects.filter(tenant=school)

        if student_status == 'active':
            students_query = students_query.filter(is_deleted=False)

        if class_filter != 'all':
            try:
                course_batches_query = Batch.objects.filter(
                    tenant=school,
                    course_id=class_filter
                )
                if selected_year:
                    course_batches_query = course_batches_query.filter(academic_year=selected_year)

                course_batches = course_batches_query.values_list('id', flat=True)

                batch_students = BatchStudent.objects.filter(
                    tenant=school,
                    batch_id__in=course_batches
                )
                student_ids = batch_students.values_list('student_id', flat=True)
                students_query = students_query.filter(id__in=student_ids)
            except (ValueError, ValidationError) as e:
                logger.debug("Invalid class_filter %r: %s", class_filter, e)

        elif batch_filter != 'all':
            try:
                batch_query = Batch.objects.filter(
                    tenant=school,
                    id=batch_filter
                )
                if selected_year:
                    batch_query = batch_query.filter(academic_year=selected_year)

                batch_students = BatchStudent.objects.filter(
                    tenant=school,
                    batch_id__in=batch_query.values_list('id', flat=True)
                )
                student_ids = batch_students.values_list('student_id', flat=True)
                students_query = students_query.filter(id__in=student_ids)
            except (ValueError, ValidationError) as e:
                logger.debug("Invalid batch_filter %r: %s", batch_filter, e)

        return students_query.order_by('first_name', 'last_name')

    def _ledger_aggregates(self, school, selected_year, student_ids, fee_account, from_date_obj, to_date_obj):
        """One grouped query: student_id -> dict of charged/paid/credited totals, split PTA vs not."""
        from core.models import FeeTransaction

        if not student_ids:
            return {}

        decimal_field = DecimalField(max_digits=15, decimal_places=2)

        ledger = FeeTransaction.objects.filter(
            tenant=school,
            academic_year=selected_year,
            student_id__in=student_ids,
        )
        if fee_account != 'all':
            try:
                ledger = ledger.filter(fee_category_id=fee_account)
            except (ValueError, ValidationError) as e:
                logger.debug("Invalid fee_account filter %r: %s", fee_account, e)
        if from_date_obj:
            ledger = ledger.filter(transaction_date__date__gte=from_date_obj)
        if to_date_obj:
            ledger = ledger.filter(transaction_date__date__lte=to_date_obj)

        pta_q = Q(fee_category__name__icontains='PTA')

        def total_case(extra_q=None, types=None, single_type=None):
            condition = Q(transaction_type=single_type) if single_type else Q(transaction_type__in=types)
            if extra_q is not None:
                condition &= extra_q
            return Sum(Case(When(condition, then='amount'), default=Value(0), output_field=decimal_field))

        rows = ledger.values('student_id').annotate(
            charged=total_case(types=self._DEBIT_TYPES),
            paid=total_case(single_type='payment'),
            credited=total_case(types=self._CREDIT_TYPES),
            pta_charged=total_case(extra_q=pta_q, types=self._DEBIT_TYPES),
            pta_paid=total_case(extra_q=pta_q, single_type='payment'),
            pta_credited=total_case(extra_q=pta_q, types=self._CREDIT_TYPES),
        )

        zero = Decimal('0.00')
        result = {}
        for row in rows:
            result[row['student_id']] = {
                'charged': row['charged'] or zero,
                'paid': row['paid'] or zero,
                'credited': row['credited'] or zero,
                'pta_charged': row['pta_charged'] or zero,
                'pta_paid': row['pta_paid'] or zero,
                'pta_credited': row['pta_credited'] or zero,
            }
        return result

    def _build_rows(self, school, selected_year, students, fee_account, from_date_obj, to_date_obj):
        from core.models import BatchStudent

        students = list(students)
        student_ids = [s.id for s in students]

        aggregates = self._ledger_aggregates(
            school, selected_year, student_ids, fee_account, from_date_obj, to_date_obj
        )

        batch_names = {}
        for bs in BatchStudent.objects.filter(tenant=school, student_id__in=student_ids).select_related('batch'):
            batch_names.setdefault(bs.student_id, bs.batch.name)

        zero = Decimal('0.00')
        rows = []
        for student in students:
            agg = aggregates.get(student.id, {
                'charged': zero, 'paid': zero, 'credited': zero,
                'pta_charged': zero, 'pta_paid': zero, 'pta_credited': zero,
            })
            tuition_charged = agg['charged'] - agg['pta_charged']
            tuition_paid = agg['paid'] - agg['pta_paid']
            tuition_credited = agg['credited'] - agg['pta_credited']

            rows.append({
                'student': student,
                'batch_name': batch_names.get(student.id, "Not Assigned"),
                'expected_amount': agg['charged'],
                'paid_amount': agg['paid'],
                'balance_amount': agg['charged'] - agg['credited'],
                'pta_expected': agg['pta_charged'],
                'pta_paid': agg['pta_paid'],
                'pta_balance': agg['pta_charged'] - agg['pta_credited'],
                'tuition_expected': tuition_charged,
                'tuition_paid': tuition_paid,
                'tuition_balance': tuition_charged - tuition_credited,
            })
        return rows

    def _compute_grand_totals(self, rows):
        zero = Decimal('0.00')
        totals = {
            'grand_expected': zero, 'grand_paid': zero, 'grand_balance': zero,
            'grand_pta_expected': zero, 'grand_pta_paid': zero, 'grand_pta_balance': zero,
            'grand_tuition_expected': zero, 'grand_tuition_paid': zero, 'grand_tuition_balance': zero,
        }
        for row in rows:
            totals['grand_expected'] += row['expected_amount']
            totals['grand_paid'] += row['paid_amount']
            totals['grand_balance'] += row['balance_amount']
            totals['grand_pta_expected'] += row['pta_expected']
            totals['grand_pta_paid'] += row['pta_paid']
            totals['grand_pta_balance'] += row['pta_balance']
            totals['grand_tuition_expected'] += row['tuition_expected']
            totals['grand_tuition_paid'] += row['tuition_paid']
            totals['grand_tuition_balance'] += row['tuition_balance']
        return totals

    def _parse_date_filters(self, request):
        from datetime import datetime

        from_date = request.GET.get('from_date', '')
        to_date = request.GET.get('to_date', '')
        from_date_obj = None
        to_date_obj = None
        if from_date:
            try:
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            except ValueError:
                from_date = ''
        if to_date:
            try:
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            except ValueError:
                to_date = ''
        return from_date, from_date_obj, to_date, to_date_obj

    def get(self, request, *args, **kwargs):
        export_format = request.GET.get('format')
        if export_format in ('csv', 'pdf'):
            school = getattr(request, 'tenant', None)
            if not school:
                raise Http404("School not found")

            selected_year = resolve_selected_year(request, school)
            if selected_year is None:
                raise Http404("No academic year selected")

            fee_account = request.GET.get('fee_account', 'all')
            _, from_date_obj, _, to_date_obj = self._parse_date_filters(request)
            with_expected = request.GET.get('with_expected', False) == 'on'

            students = self._get_filtered_students(school, request, selected_year)
            rows = self._build_rows(school, selected_year, students, fee_account, from_date_obj, to_date_obj)
            grand_totals = self._compute_grand_totals(rows)

            if export_format == 'csv':
                return self._render_csv(rows, grand_totals, with_expected)
            return self._render_pdf(school, selected_year, rows, grand_totals, with_expected)

        return super().get(request, *args, **kwargs)

    def _render_csv(self, rows, grand_totals, with_expected):
        import csv

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="particular_wise_student_transaction_report.csv"'

        writer = csv.writer(response)
        header = ['Sl No.', 'Student Name', 'Batch Name(s)', 'Expected Amount', 'Paid Amount', 'Balance Amount']
        if with_expected:
            header += [
                'PTA Expected', 'PTA Paid', 'PTA Balance',
                'Tuition Expected', 'Tuition Paid', 'Tuition Balance',
            ]
        writer.writerow(header)

        for i, row in enumerate(rows, 1):
            line = [
                i,
                f"{row['student'].first_name} {row['student'].last_name}",
                row['batch_name'],
                row['expected_amount'], row['paid_amount'], row['balance_amount'],
            ]
            if with_expected:
                line += [
                    row['pta_expected'], row['pta_paid'], row['pta_balance'],
                    row['tuition_expected'], row['tuition_paid'], row['tuition_balance'],
                ]
            writer.writerow(line)

        total_line = ['', 'Grand Total', '', grand_totals['grand_expected'], grand_totals['grand_paid'], grand_totals['grand_balance']]
        if with_expected:
            total_line += [
                grand_totals['grand_pta_expected'], grand_totals['grand_pta_paid'], grand_totals['grand_pta_balance'],
                grand_totals['grand_tuition_expected'], grand_totals['grand_tuition_paid'], grand_totals['grand_tuition_balance'],
            ]
        writer.writerow(total_line)

        return response

    def _render_pdf(self, school, selected_year, rows, grand_totals, with_expected):
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        html_content = render_to_string('core/finance/particular_wise_student_transaction_report_pdf.html', {
            'school': school,
            'selected_year': selected_year,
            'rows': rows,
            'grand_totals': grand_totals,
            'with_expected': with_expected,
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="particular_wise_student_transaction_report.pdf"'
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        request = self.request
        fee_account = request.GET.get('fee_account', 'all')
        from_date, from_date_obj, to_date, to_date_obj = self._parse_date_filters(request)
        student_status = request.GET.get('student_status', 'active')
        class_filter = request.GET.get('class', 'all')
        batch_filter = request.GET.get('batch', 'all')
        with_expected = request.GET.get('with_expected', False) == 'on'

        from core.models import FeeCategory, Course, Batch

        selected_year = resolve_selected_year(request, school)

        fee_categories = FeeCategory.objects.filter(tenant=school, is_deleted=False).order_by('name')

        if selected_year:
            batches = Batch.objects.filter(tenant=school, academic_year=selected_year).order_by('name')
            courses = Course.objects.filter(
                tenant=school,
                is_deleted=False,
                batches__academic_year=selected_year
            ).distinct().order_by('course_name')
        else:
            batches = Batch.objects.filter(tenant=school).order_by('name')
            courses = Course.objects.filter(tenant=school, is_deleted=False).order_by('course_name')

        rows = []
        grand_totals = self._compute_grand_totals([])
        page_obj = None
        is_paginated = False

        if request.GET.get('view_report') and selected_year is not None:
            students = self._get_filtered_students(school, request, selected_year)
            paginator = Paginator(students, self.PAGE_SIZE)
            page_obj = paginator.get_page(request.GET.get('page'))
            is_paginated = paginator.num_pages > 1

            rows = self._build_rows(
                school, selected_year, page_obj.object_list, fee_account, from_date_obj, to_date_obj
            )
            grand_totals = self._compute_grand_totals(rows)

        context.update({
            'school': school,
            'rows': rows,
            'grand_totals': grand_totals,
            'page_obj': page_obj,
            'is_paginated': is_paginated,
            'fee_account': fee_account,
            'from_date': from_date,
            'to_date': to_date,
            'student_status': student_status,
            'class_filter': class_filter,
            'batch_filter': batch_filter,
            'with_expected': with_expected,
            'fee_categories': fee_categories,
            'courses': courses,
            'batches': batches,
            'back_url': request.GET.get('back', reverse('core:finance_reports')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Reports', 'url': reverse('core:finance_reports')},
                {'label': 'Collection Report'},
            ],
        })
        context.update(build_year_context(request, school))
        return context


@require_http_methods(["GET"])
def batches_by_class_api(request):
    """Get batches for a specific class/course - simplified version for reports"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)

    course_id = request.GET.get('course_id')

    if not course_id:
        return JsonResponse({'error': 'Course ID is required'}, status=400)

    try:
        from core.models import Course, Batch

        # Verify course exists
        course = Course.objects.get(
            id=course_id,
            tenant=school,
            is_deleted=False
        )

        # Get batches for this course
        batches = Batch.objects.filter(
            tenant=school,
            course=course,
            is_deleted=False
        ).order_by('name')

        batch_data = []
        for batch in batches:
            batch_data.append({
                'id': str(batch.id),
                'name': batch.name,
            })

        return JsonResponse({
            'batches': batch_data,
            'course': course.course_name
        })

    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting batches by class: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


