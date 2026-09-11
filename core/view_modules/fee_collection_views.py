"""Step 2 of the finance workflow: fee collections (term-wise billing runs)
and the per-student obligations they generate."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import escape
from django.views.generic import TemplateView, View
from datetime import datetime
import json

from core.models import AcademicYear, Batch, FeeCategory, BatchFeeCategory, FeeCollection, Term, FeeParticular, FineSlab
from core.services.fee_collection_service import FeeCollectionService
from core.services.currency_service import CurrencyService
from core.services.exceptions import NotFoundException, ValidationException


class FeeCollectionListView(TemplateView):
    template_name = 'core/finance/collections/list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        school = self.request.tenant
        svc = FeeCollectionService(school)
        year_id = self.request.GET.get('academic_year')
        year = None
        if year_id:
            try:
                year = AcademicYear.objects.filter(
                    tenant=school, id=year_id).first()
            except (ValidationError, ValueError):
                year = None
        else:
            year = svc.get_active_academic_year()
        ctx['grouped_collections'] = svc.list_collections_grouped(academic_year=year)
        ctx['selected_year'] = year
        ctx['academic_years'] = AcademicYear.objects.filter(
            tenant=school).order_by('-start_date')
        # Phase 3: Terms are year-scoped; get terms for the selected academic year
        if year:
            ctx['terms'] = Term.objects.filter(
                tenant=school, academic_year=year
            ).order_by('order').values_list('name', flat=True).distinct()
        else:
            ctx['terms'] = []
        ctx['status_choices'] = FeeCollection.STATUS_CHOICES
        ctx['fine_slabs'] = FineSlab.objects.filter(
            tenant=school, is_active=True
        ).values_list('fine_name', flat=True).distinct()

        # Master particulars (PTA, etc.) offered in the per-collection
        # "Add Particular" modal.
        from core.services.finance_service import FinanceService
        ctx['master_particulars'] = list(
            FinanceService(school).list_master_particulars(is_active=True)
        )
        ctx['currency_symbol'] = CurrencyService(school).get_currency_symbol()

        ctx['header_actions'] = [
            {'label': 'Publish Invoices', 'variant': 'primary', 'icon': 'fa-paper-plane', 'disabled': True,
             'attrs': 'id="publishInvoicesBtn" onclick="publishSelected()"'},
            {'label': 'Edit Selected', 'variant': 'outline', 'icon': 'fa-edit', 'disabled': True,
             'attrs': 'id="bulkEditBtn" data-bs-toggle="modal" data-bs-target="#bulkEditModal"'},
            {'label': 'Add Particular', 'variant': 'outline', 'icon': 'fa-plus', 'disabled': True,
             'attrs': 'id="bulkAddParticularBtn" onclick="openBulkAddParticular()"'},
            {'label': 'Delete Selected', 'variant': 'danger', 'icon': 'fa-trash', 'disabled': True,
             'attrs': 'id="deleteSelectedBtn" onclick="deleteSelected()"'},
            {'label': 'New Collection', 'variant': 'primary', 'icon': 'fa-plus', 'url': reverse('core:fee_collection_create')},
        ]
        ctx['bulk_edit_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Apply Changes', 'variant': 'primary', 'icon': 'fa-save', 'attrs': 'onclick="submitBulkEdit()"'},
        ]
        ctx['add_particular_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Add Particular', 'variant': 'primary', 'icon': 'fa-save', 'type': 'submit'},
        ]

        return ctx


class FeeCollectionCreateView(TemplateView):
    template_name = 'core/finance/collections/create.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        school = self.request.tenant
        ctx['fee_categories'] = FeeCategory.objects.filter(
            tenant=school, is_deleted=False).order_by('name')
        ctx['batches'] = Batch.objects.filter(
            tenant=school, is_active=True
        ).select_related('course').order_by('name')
        ctx['academic_years'] = AcademicYear.objects.filter(
            tenant=school).order_by('-start_date')
        # Terms are year-scoped; hand the template full term rows so it can
        # populate the term picker and derive start/end dates from the choice.
        ctx['terms'] = Term.objects.filter(
            tenant=school
        ).select_related('academic_year').order_by('academic_year', 'order')
        ctx['back_url'] = self.request.GET.get('back', reverse('core:fee_collections'))
        ctx['crumbs'] = [
            {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
            {'label': 'Collections', 'url': reverse('core:fee_collections')},
            {'label': 'New Collection'},
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        for field in ('name', 'fee_category', 'term'):
            if not request.POST.get(field):
                messages.error(request, 'Name, fee group and term are required.')
                return self.get(request, *args, **kwargs)

        school = request.tenant
        try:
            year = AcademicYear.objects.filter(
                tenant=school, id=request.POST.get('academic_year')
            ).first()

            # Start / end dates are derived from the selected term (year-scoped).
            term_name = request.POST.get('term')
            term = Term.objects.filter(
                tenant=school, name=term_name,
                **({'academic_year': year} if year else {}),
            ).order_by('order').first()
            if not term:
                messages.error(request, 'The selected term could not be found for this academic year.')
                return self.get(request, *args, **kwargs)

            due_date = request.POST.get('due_date') or term.end_date

            result = FeeCollectionService(school).create_collection(
                name=request.POST.get('name', ''),
                fee_category_id=request.POST.get('fee_category'),
                batch_ids=request.POST.getlist('batches'),
                due_date=due_date,
                start_date=term.start_date,
                end_date=term.end_date,
                academic_year=year,
                term_name=term_name or None,
            )
            messages.success(
                request,
                f"Collection created — {result['obligations_created']} student "
                f"obligations generated"
                + (f", {result['students_skipped']} already existed"
                   if result['students_skipped'] else ""),
            )
            return redirect('core:fee_collections')
        except (ValidationException, NotFoundException) as e:
            messages.error(request, str(e))
            return self.get(request, *args, **kwargs)
        except (ValidationError, ValueError):
            messages.error(request, 'Invalid input.')
            return self.get(request, *args, **kwargs)


class FeeCollectionDetailView(TemplateView):
    template_name = 'core/finance/collections/detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        school = self.request.tenant
        svc = FeeCollectionService(school)
        try:
            summary = svc.get_collection_summary(str(kwargs['pk']))
        except NotFoundException as e:
            raise Http404(str(e))
        status_filter = self.request.GET.get('status')
        rows = summary['rows']
        if status_filter in ('paid', 'partial', 'unpaid'):
            rows = [r for r in rows if r['status'] == status_filter]
        q = (self.request.GET.get('q') or '').strip().lower()
        if q:
            rows = [
                r for r in rows
                if q in f"{r['student'].first_name} {r['student'].last_name}".lower()
                or q in (r['student'].admission_no or '').lower()
            ]
        collection = summary['collection']
        totals = summary['totals']
        ctx.update(collection=collection, rows=rows,
                   totals=totals, status_filter=status_filter, q=q)
        ctx['collection_header_title'] = f"{collection.name} — Student Obligations"
        ctx['collection_description'] = (
            f"{collection.fee_category.name} · {collection.batch.name} · due {collection.due_date}"
        )
        ctx['header_actions'] = [
            {'label': 'Delete Collection', 'variant': 'danger', 'icon': 'fa-trash', 'size': 'sm',
             'attrs': 'data-collection-id="%s" data-collection-name="%s" onclick="deleteCollection(this.dataset.collectionId, this.dataset.collectionName)"' % (
                 escape(str(collection.id)), escape(collection.name),
             )},
        ]
        ctx['collection_stats'] = [
            {'label': 'Total Students', 'value': totals['students'], 'icon': 'fa-users', 'variant': 'primary'},
            {'label': 'Total Amount', 'value': CurrencyService(school).format_amount(totals['total']), 'icon': 'fa-file-invoice-dollar', 'variant': 'primary'},
            {'label': 'Collected', 'value': CurrencyService(school).format_amount(totals['collected']), 'icon': 'fa-check-circle', 'variant': 'success'},
            {'label': 'Outstanding', 'value': CurrencyService(school).format_amount(totals['outstanding']), 'icon': 'fa-exclamation-circle', 'variant': 'danger'},
        ]
        ctx['extra_particulars'] = collection.extra_particulars.filter(
            is_active=True
        ).order_by('name')
        ctx['currency_symbol'] = CurrencyService(school).get_currency_symbol()
        return ctx


class FeeCollectionDeleteView(View):
    """Delete a fee collection (blocked once payments exist against it)"""

    def post(self, request, *args, **kwargs):
        school = request.tenant
        try:
            FeeCollectionService(school).delete_collection(str(kwargs['pk']))
            return JsonResponse({'success': True, 'message': 'Collection deleted'})
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)


class FeeCollectionBulkPublishView(View):
    """Bulk-publish selected collections: upserts each covered charge onto
    the guardian's consolidated invoice and flips draft collections to
    published, making them visible on the parent portal."""

    def post(self, request, *args, **kwargs):
        ids = request.POST.getlist('collection_ids')
        if not ids:
            messages.error(request, 'Select at least one collection to publish.')
            return redirect('core:fee_collections')

        result = FeeCollectionService(request.tenant).publish_invoices(ids)
        messages.success(
            request,
            f"Published {result['collections_published']} collection(s) — "
            f"{result['charges_invoiced']} charges invoiced."
        )
        return redirect('core:fee_collections')


class FeeCollectionBatchesView(View):
    """JSON endpoint: return batches assigned to a fee category"""
    def get(self, request):
        category_id = request.GET.get('category_id')
        if not category_id:
            return JsonResponse({'error': 'Missing category_id'}, status=400)

        school = request.tenant
        try:
            assignments = BatchFeeCategory.objects.filter(
                tenant=school,
                fee_category_id=category_id
            ).select_related('batch', 'batch__course').order_by('batch__name')

            batches = [
                {
                    'id': str(a.batch.id),
                    'name': f"{a.batch.course.course_name} — {a.batch.name}",
                }
                for a in assignments
            ]
            return JsonResponse({'batches': batches})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class FeeCollectionParticularsView(View):
    """JSON endpoint: return the active particulars for one fee category."""
    def get(self, request):
        category_id = request.GET.get('category_id')
        if not category_id:
            return JsonResponse({'error': 'Missing category_id'}, status=400)

        school = request.tenant
        try:
            particulars = list(
                FeeParticular.objects.filter(
                    tenant=school,
                    fee_category_id=category_id,
                    is_active=True
                ).order_by('name').values('id', 'name', 'amount', 'due_date', 'fine_slab__fine_name')
            )
            return JsonResponse({'particulars': particulars})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class FeeCollectionAddParticularView(View):
    """POST: attach a master particular (e.g. PTA) to one collection and charge
    it to the students already billed in that collection."""

    def post(self, request, pk, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            result = FeeCollectionService(school).add_collection_particular(
                str(pk),
                master_particular_id=request.POST.get('master_particular_id'),
                amount=request.POST.get('amount'),
                due_date=request.POST.get('due_date') or None,
                fine_slab_name=request.POST.get('fine_slab') or None,
                description=request.POST.get('description', ''),
            )
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)

        verb = 'updated' if result['updated'] else 'added'
        return JsonResponse({
            'success': True,
            'message': f"Particular {verb} — {result['students_charged']} student(s) charged"
                       + (f", {result['students_skipped']} skipped"
                          if result['students_skipped'] else ''),
            **result,
        })


class FeeCollectionBulkAddParticularView(View):
    """POST: attach one master particular to several selected collections at once."""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        collection_ids = request.POST.getlist('collection_ids')
        if not collection_ids:
            return JsonResponse({'error': 'Select at least one collection'}, status=400)

        try:
            result = FeeCollectionService(school).bulk_add_collection_particular(
                collection_ids,
                master_particular_id=request.POST.get('master_particular_id'),
                amount=request.POST.get('amount'),
                due_date=request.POST.get('due_date') or None,
                fine_slab_name=request.POST.get('fine_slab') or None,
                description=request.POST.get('description', ''),
            )
        except (NotFoundException, ValidationException) as e:
            return JsonResponse({'error': str(e)}, status=400)

        msg = (f"Applied to {result['collections_applied']} collection(s) — "
               f"{result['students_charged']} student charge(s)")
        if result['collections_skipped']:
            msg += f", {result['collections_skipped']} skipped"
        return JsonResponse({'success': True, 'message': msg, **result})


class FeeCollectionRemoveParticularView(View):
    """POST: remove a per-collection particular and refund it from every
    student's charge."""

    def post(self, request, pk, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            result = FeeCollectionService(school).remove_collection_particular(
                str(pk), request.POST.get('particular_id'),
            )
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)

        return JsonResponse({
            'success': True,
            'message': f"Particular removed — {result['students_updated']} student(s) updated",
            **result,
        })


class FeeCollectionBulkDeleteView(View):
    """Bulk-delete selected collections. Collections with recorded payments
    are skipped rather than failing the whole batch."""

    def post(self, request, *args, **kwargs):
        ids = request.POST.getlist('collection_ids')
        if not ids:
            messages.error(request, 'Select at least one collection to delete.')
            return redirect('core:fee_collections')

        svc = FeeCollectionService(request.tenant)
        deleted, skipped = 0, []
        for cid in ids:
            try:
                svc.delete_collection(cid)
                deleted += 1
            except NotFoundException:
                continue
            except ValidationException:
                skipped.append(cid)

        if deleted:
            messages.success(request, f"Deleted {deleted} collection(s).")
        if skipped:
            messages.warning(
                request,
                f"{len(skipped)} collection(s) skipped — payments already recorded against them."
            )
        return redirect('core:fee_collections')


class FeeCollectionBulkDeleteJSONView(View):
    """JSON/fetch variant of FeeCollectionBulkDeleteView. Same
    per-item skip-on-payments semantics; returns JSON instead of a
    redirect+django-messages round trip."""

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

        ids = payload.get('collection_ids') or []
        if not ids:
            return JsonResponse({'error': 'Select at least one collection to delete.'}, status=400)

        school = request.tenant
        valid_ids = list(FeeCollection.objects.filter(
            tenant=school, id__in=ids).values_list('id', flat=True))

        svc = FeeCollectionService(school)
        deleted, skipped = 0, []
        for cid in valid_ids:
            try:
                svc.delete_collection(str(cid))
                deleted += 1
            except NotFoundException:
                continue
            except ValidationException as e:
                skipped.append({'id': str(cid), 'reason': str(e)})

        return JsonResponse({
            'success': True,
            'deleted': deleted,
            'skipped_count': len(skipped),
            'skipped': skipped,
            'message': f"Deleted {deleted} collection(s)"
                       + (f", {len(skipped)} skipped (payments recorded)" if skipped else ''),
        })


class FeeCollectionBulkEditView(View):
    """Bulk-edit term/dates/status on selected collections. JSON in, JSON
    out — validates input before calling the service, so a bad payload
    never reaches the DB layer."""

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

        ids = payload.get('collection_ids') or []
        if not ids:
            return JsonResponse({'error': 'Select at least one collection.'}, status=400)

        school = request.tenant
        fields = {}

        # term (optional, by name) — passed as term_name to service, resolved per collection
        if 'term' in payload:
            fields['term_name'] = payload['term'] or None

        # dates (optional) — parse + basic sanity before hitting the service
        for key in ('start_date', 'end_date', 'due_date'):
            if key in payload and payload[key]:
                try:
                    fields[key] = datetime.strptime(payload[key], '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({'error': f'Invalid {key}.'}, status=400)

        # status (optional)
        if 'status' in payload and payload['status']:
            status_choices_dict = dict(FeeCollection.STATUS_CHOICES)
            if payload['status'] not in status_choices_dict:
                return JsonResponse({'error': 'Invalid status.'}, status=400)
            fields['status'] = payload['status']

        if not fields:
            return JsonResponse({'error': 'No editable fields supplied.'}, status=400)

        # cross-field sanity before hitting DB (service re-checks per-row too)
        sd = fields.get('start_date')
        for k in ('due_date', 'end_date'):
            if sd and fields.get(k) and fields[k] < sd:
                k_name = k.replace("_", " ").title()
                return JsonResponse({'error': f'{k_name} cannot be before start date.'}, status=400)

        # tenant-scope the ids up front (defense in depth — service also filters by tenant)
        valid_ids = list(FeeCollection.objects.filter(
            tenant=school, id__in=ids).values_list('id', flat=True))
        if not valid_ids:
            return JsonResponse({'error': 'None of the selected collections were found.'}, status=404)

        svc = FeeCollectionService(school)
        result = svc.bulk_update_collections([str(i) for i in valid_ids], **fields)

        return JsonResponse({
            'success': True,
            'updated': result['updated'],
            'skipped_count': len(result['skipped']),
            'skipped': result['skipped'],
            'message': f"Updated {result['updated']} collection(s)"
                       + (f", {len(result['skipped'])} skipped" if result['skipped'] else ''),
        })