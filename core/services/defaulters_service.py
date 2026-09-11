"""Defaulters list — students with overdue fee balances.

Black box: given a school (tenant), return the set of students who still owe
money on a fee collection whose ``due_date`` has passed. The list is always
computed live from ``FinanceFee`` balances vs ``FeeCollection.due_date``;
nothing is stored.

Manual pre-due-date generation: pass ``include_upcoming=True`` to drop the
due-date filter so an admin can preview who *would* default on collections that
are not yet due.

Three views of the same data:
  * ``rows``          — one ``DefaulterRow`` per outstanding fee-collection line.
  * ``student_rows``  — one ``DefaulterStudent`` per student, aggregating their
                        lines (this is what the screen's selectable table and the
                        bulk payment-agreement action work off).
  * ``batch_rows``    — one ``DefaulterBatch`` per batch, grouping the students
                        above (the screen's "Batch-wise" tab).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import Q

from core.models import AcademicYear, Batch, FinanceFee


@dataclass
class DefaulterRow:
    student: object
    student_name: str
    admission_no: str
    batch_name: str
    fee_collection: object
    collection_name: str
    due_date: Optional[date]
    days_overdue: int
    outstanding: Decimal


@dataclass
class DefaulterStudent:
    student: object
    student_name: str
    admission_no: str
    batch_name: str
    outstanding: Decimal
    oldest_due_date: Optional[date]
    max_days_overdue: int
    lines: list


@dataclass
class DefaulterBatch:
    batch_name: str
    outstanding: Decimal
    student_count: int
    students: list


class DefaultersService:
    """One method: :meth:`list_defaulters`. Reads only."""

    def __init__(self, tenant):
        self.tenant = tenant

    def list_defaulters(
        self,
        academic_year: Optional[AcademicYear] = None,
        batch: Optional[Batch] = None,
        as_of: Optional[date] = None,
        include_upcoming: bool = False,
    ) -> dict:
        """Return ``{'rows', 'total', 'as_of', 'include_upcoming',
        'student_count'}``.

        A row exists for every ``FinanceFee`` line that (a) belongs to a fee
        collection, (b) has an outstanding ``balance > 0`` and (c) — unless
        ``include_upcoming`` — sits on a collection whose ``due_date`` is
        strictly before ``as_of`` (defaults to today).
        """
        as_of = as_of or date.today()

        qs = FinanceFee.objects.filter(
            tenant=self.tenant,
            balance__gt=0,
            fee_collection__isnull=False,
        ).select_related(
            "student", "batch", "fee_collection", "fee_collection__batch",
        )
        if academic_year is not None:
            qs = qs.filter(academic_year=academic_year)
        if batch is not None:
            qs = qs.filter(Q(batch=batch) | Q(fee_collection__batch=batch))
        if not include_upcoming:
            qs = qs.filter(fee_collection__due_date__lt=as_of)

        qs = qs.order_by(
            "student__first_name", "student__last_name",
            "fee_collection__due_date",
        )

        rows = []
        total = Decimal("0.00")
        for fee in qs:
            collection = fee.fee_collection
            due = collection.due_date
            days_overdue = (as_of - due).days if due and due < as_of else 0
            row_batch = fee.batch or collection.batch
            name = f"{fee.student.first_name} {fee.student.last_name}".strip()
            rows.append(DefaulterRow(
                student=fee.student,
                student_name=name,
                admission_no=fee.student.admission_no or "",
                batch_name=row_batch.name if row_batch else "—",
                fee_collection=collection,
                collection_name=collection.name,
                due_date=due,
                days_overdue=days_overdue,
                outstanding=fee.balance,
            ))
            total += fee.balance

        # Aggregate the lines by student (preserves first-seen order, which is
        # already student-name sorted from the queryset above).
        by_student: "dict" = {}
        for row in rows:
            bucket = by_student.get(row.student.id)
            if bucket is None:
                bucket = DefaulterStudent(
                    student=row.student,
                    student_name=row.student_name,
                    admission_no=row.admission_no,
                    batch_name=row.batch_name,
                    outstanding=Decimal("0.00"),
                    oldest_due_date=row.due_date,
                    max_days_overdue=0,
                    lines=[],
                )
                by_student[row.student.id] = bucket
            bucket.outstanding += row.outstanding
            bucket.lines.append(row)
            bucket.max_days_overdue = max(bucket.max_days_overdue, row.days_overdue)
            if row.due_date and (bucket.oldest_due_date is None or row.due_date < bucket.oldest_due_date):
                bucket.oldest_due_date = row.due_date

        student_rows = list(by_student.values())

        # Group the students by batch for the "Batch-wise" tab.
        by_batch: "dict" = {}
        for s in student_rows:
            group = by_batch.get(s.batch_name)
            if group is None:
                group = DefaulterBatch(
                    batch_name=s.batch_name,
                    outstanding=Decimal("0.00"),
                    student_count=0,
                    students=[],
                )
                by_batch[s.batch_name] = group
            group.students.append(s)
            group.student_count += 1
            group.outstanding += s.outstanding
        batch_rows = sorted(by_batch.values(), key=lambda g: g.batch_name)

        return {
            "rows": rows,
            "student_rows": student_rows,
            "batch_rows": batch_rows,
            "total": total,
            "as_of": as_of,
            "include_upcoming": include_upcoming,
            "student_count": len(by_student),
        }
