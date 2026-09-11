"""Shared academic-year context for the finance UI (Phase 1).

The finance backend is fully year-scoped; these helpers let every finance screen
resolve and display the *selected* academic year consistently. Selection comes
from a ``?academic_year=<id>`` query param and defaults to the tenant's active
year (falling back to the most recent).
"""
from core.models import AcademicYear, FeeCollection


def get_academic_years(school):
    """All academic years for a tenant, newest first."""
    return AcademicYear.objects.filter(tenant=school).order_by("-start_date")


def resolve_selected_year(request, school):
    """Return the AcademicYear the user is currently viewing.

    Order: explicit ``?academic_year`` (validated against the tenant) →
    active year → most recent year → None.
    """
    years = get_academic_years(school)
    requested = request.GET.get("academic_year")
    if requested:
        ay = years.filter(id=requested).first()
        if ay is not None:
            return ay
    return years.filter(is_active=True).first() or years.first()


def build_year_context(request, school):
    """Context dict for the shared year-selector partial."""
    selected = resolve_selected_year(request, school)
    return {
        "academic_years": list(get_academic_years(school)),
        "selected_year": selected,
        "selected_year_id": str(selected.id) if selected else "",
    }


def resolve_student_fee_collections(request, school, student, academic_year):
    """FeeCollections with a FinanceFee for this student/year, plus the
    selected-or-latest id from ``?fee_collection=``.

    Returns (collections_queryset, selected_fee_collection_id).
    """
    if not student or not academic_year:
        return FeeCollection.objects.none(), None

    collections = FeeCollection.objects.filter(
        tenant=school, financefee__student=student, financefee__academic_year=academic_year,
    ).distinct().order_by('start_date')

    requested_id = request.GET.get('fee_collection')
    if requested_id and collections.filter(id=requested_id).exists():
        return collections, requested_id

    last_collection = collections.last()
    return collections, (str(last_collection.id) if last_collection else None)
