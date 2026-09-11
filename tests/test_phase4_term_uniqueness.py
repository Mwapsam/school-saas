"""Tests for Phase 4 Term uniqueness constraint — (tenant, academic_year, name)."""

import pytest
from django.db import IntegrityError

from core.models import Term


@pytest.mark.django_db
class TestTermUniquenessPhase4:
    """Phase 4: Term is uniquely identified by (tenant, academic_year, name)."""

    def test_term_unique_together_tenant_year_name(self, school, academic_year):
        """Creating two Terms with same (tenant, academic_year, name) raises IntegrityError."""
        term1 = Term.objects.create(
            tenant=school,
            academic_year=academic_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-03-31",
            order=1,
        )
        assert term1.id is not None

        # Attempt to create duplicate: same tenant, year, name
        with pytest.raises(IntegrityError):
            Term.objects.create(
                tenant=school,
                academic_year=academic_year,
                name="Term 1",  # Duplicate name in same year
                start_date="2025-01-15",  # Different dates don't matter
                end_date="2025-04-15",
                order=1,
            )

    def test_term_allows_same_name_different_years(self, school, academic_year, db):
        """Same Term name is allowed in different academic years."""
        ay2 = pytest.importorskip("core.models").AcademicYear.objects.create(
            tenant=school,
            name="2026",
            start_date="2026-01-01",
            end_date="2026-12-31",
        )

        term1 = Term.objects.create(
            tenant=school,
            academic_year=academic_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-03-31",
            order=1,
        )

        term2 = Term.objects.create(
            tenant=school,
            academic_year=ay2,
            name="Term 1",  # Same name, different year ✓
            start_date="2026-01-01",
            end_date="2026-03-31",
            order=1,
        )

        assert term1.academic_year != term2.academic_year

    def test_term_requires_academic_year(self, school):
        """academic_year is non-nullable; Term creation fails without it."""
        with pytest.raises((IntegrityError, ValueError)):
            Term.objects.create(
                tenant=school,
                # academic_year=None,  # Omitted
                name="Term 1",
                start_date="2025-01-01",
                end_date="2025-03-31",
            )

    def test_term_no_exam_group_field(self, school, academic_year):
        """Phase 4: exam_group field is removed entirely."""
        term = Term.objects.create(
            tenant=school,
            academic_year=academic_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-03-31",
        )

        # Should not have exam_group attribute
        assert not hasattr(term, 'exam_group') or term._meta.get_field('exam_group') is None

    def test_term_str_uses_academic_year(self, school, academic_year):
        """Term.__str__ includes academic_year, not exam_group."""
        term = Term.objects.create(
            tenant=school,
            academic_year=academic_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-03-31",
        )

        # Should include academic_year name in string representation
        str_repr = str(term)
        assert academic_year.name in str_repr
        assert term.name in str_repr
