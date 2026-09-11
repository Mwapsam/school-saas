"""Fee collection generation: creating a collection materialises one FinanceFee
obligation per active batch student, priced from the category's active
particulars, and is idempotent on re-run."""
import uuid
import pytest
from decimal import Decimal
from datetime import date

from core.models import (
    Course, Batch, Student, BatchStudent, AcademicYear,
    FeeCategory, FeeParticular, BatchFeeCategory, FeeCollection, FinanceFee,
)
from core.services.fee_collection_service import FeeCollectionService
from core.services.student_service import StudentService
from core.services.exceptions import ValidationException, NotFoundException


@pytest.fixture
def prior_year(db, school):
    return AcademicYear.objects.create(
        name=f"2023-2024-{uuid.uuid4().hex[:4]}",
        start_date=date(2023, 9, 1),
        end_date=date(2024, 7, 31),
        is_active=True,
        tenant=school,
    )


@pytest.fixture
def current_year(db, school, prior_year):
    # Saving this active auto-deactivates prior_year (model.save() behaviour).
    return AcademicYear.objects.create(
        name=f"2024-2025-{uuid.uuid4().hex[:4]}",
        start_date=date(2024, 9, 1),
        end_date=date(2025, 7, 31),
        is_active=True,
        tenant=school,
    )


@pytest.fixture
def course(db, school):
    return Course.objects.create(
        course_name="Grade 1", code=f"G1{uuid.uuid4().hex[:5].upper()}", tenant=school
    )


@pytest.fixture
def batch(db, school, course, current_year):
    return Batch.objects.create(
        name=f"Grade 1A {uuid.uuid4().hex[:4]}",
        course=course,
        academic_year=current_year,
        start_date=date(2024, 9, 1),
        end_date=date(2025, 7, 31),
        tenant=school,
    )


@pytest.fixture
def other_batch(db, school, course, current_year):
    return Batch.objects.create(
        name=f"Grade 1B {uuid.uuid4().hex[:4]}",
        course=course,
        academic_year=current_year,
        start_date=date(2024, 9, 1),
        end_date=date(2025, 7, 31),
        tenant=school,
    )


@pytest.fixture
def student(db, school, batch):
    s = Student.objects.create(
        first_name="Pat", last_name="Learner",
        admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
        admission_date=date(2024, 9, 1),
        date_of_birth=date(2018, 1, 1),
        gender="male",
        tenant=school,
    )
    BatchStudent.objects.create(batch=batch, student=s, tenant=school)
    return s


@pytest.fixture
def fee_category(db, school, current_year):
    return FeeCategory.objects.create(
        name=f"Term 1 Fees {uuid.uuid4().hex[:4]}",
        academic_year=current_year, tenant=school,
    )


@pytest.fixture
def particulars(db, school, fee_category):
    return [
        FeeParticular.objects.create(
            name="Tuition Fee", fee_category=fee_category,
            amount=Decimal("5000.00"), is_active=True, tenant=school),
        FeeParticular.objects.create(
            name="Library Fee", fee_category=fee_category,
            amount=Decimal("300.00"), is_active=True, tenant=school),
        FeeParticular.objects.create(
            name="Old Levy", fee_category=fee_category,
            amount=Decimal("999.00"), is_active=False, tenant=school),
    ]


@pytest.mark.django_db
class TestCreateCollection:
    def test_creates_obligation_per_active_student(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        svc = FeeCollectionService(school)
        result = svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )
        assert result["obligations_created"] == 1
        assert len(result["collections"]) == 1
        fee = FinanceFee.objects.get(
            student=student, fee_collection=result["collections"][0]
        )
        # priced from ACTIVE particulars only: 5000 + 300
        assert fee.balance == Decimal("5300.00")
        assert fee.particular_total == Decimal("5300.00")
        assert fee.academic_year == current_year
        assert fee.batch == batch

    def test_rerun_is_idempotent(
        self, school, batch, student, fee_category, particulars
    ):
        svc = FeeCollectionService(school)
        kwargs = dict(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )
        svc.create_collection(**kwargs)
        result2 = svc.create_collection(**kwargs)
        assert result2["obligations_created"] == 0
        assert result2["students_skipped"] == 1
        assert FeeCollection.objects.filter(
            tenant=school, name="Term 1 Collection", batch=batch
        ).count() == 1
        assert FinanceFee.objects.filter(student=student).count() == 1

    def test_batch_assignment_without_particulars_raises(
        self, school, batch, student, fee_category
    ):
        # Even with batch assignment, collection fails if no particulars exist
        BatchFeeCategory.objects.create(
            fee_category=fee_category, batch=batch, tenant=school,
        )
        svc = FeeCollectionService(school)
        with pytest.raises(ValidationException):
            svc.create_collection(
                name="Term 1 Collection",
                fee_category_id=str(fee_category.id),
                batch_ids=[str(batch.id)],
                due_date=date(2025, 1, 20),
                start_date=date(2025, 1, 1),
                end_date=date(2025, 4, 30),
            )

    def test_no_pricing_at_all_raises(self, school, batch, student, fee_category):
        svc = FeeCollectionService(school)
        with pytest.raises(ValidationException):
            svc.create_collection(
                name="Term 1 Collection",
                fee_category_id=str(fee_category.id),
                batch_ids=[str(batch.id)],
                due_date=date(2025, 1, 20),
                start_date=date(2025, 1, 1),
                end_date=date(2025, 4, 30),
            )

    def test_soft_deleted_category_raises(
        self, school, batch, student, current_year
    ):
        deleted_category = FeeCategory.objects.create(
            name=f"Deleted Fees {uuid.uuid4().hex[:4]}",
            academic_year=current_year, tenant=school, is_deleted=True,
        )
        svc = FeeCollectionService(school)
        with pytest.raises(NotFoundException):
            svc.create_collection(
                name="Term 1 Collection",
                fee_category_id=str(deleted_category.id),
                batch_ids=[str(batch.id)],
                due_date=date(2025, 1, 20),
                start_date=date(2025, 1, 1),
                end_date=date(2025, 4, 30),
            )

    def test_unknown_category_raises(self, school, batch):
        svc = FeeCollectionService(school)
        with pytest.raises(NotFoundException):
            svc.create_collection(
                name="X", fee_category_id=str(uuid.uuid4()),
                batch_ids=[str(batch.id)],
                due_date=date(2025, 1, 20),
                start_date=date(2025, 1, 1), end_date=date(2025, 4, 30),
            )


@pytest.mark.django_db
class TestListCollections:
    def test_list_collections_annotations(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        svc = FeeCollectionService(school)
        svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )
        results = list(svc.list_collections(academic_year=current_year))
        assert len(results) == 1
        collection = results[0]
        assert collection.student_count == 1
        assert collection.total_amount == Decimal("5300.00")
        assert collection.outstanding_amount == Decimal("5300.00")


@pytest.mark.django_db
class TestRosterSync:
    def test_new_enrollment_after_collection_created_is_billed(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        svc = FeeCollectionService(school)
        svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )

        late_joiner = Student.objects.create(
            first_name="Sam", last_name="Newcomer",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date(2024, 9, 1),
            date_of_birth=date(2018, 1, 1),
            gender="male",
            tenant=school,
        )
        # Creating this BatchStudent fires the post_save signal that syncs
        # obligations against already-open collections for the batch.
        BatchStudent.objects.create(batch=batch, student=late_joiner, tenant=school)

        assert FinanceFee.objects.filter(student=late_joiner).count() == 1
        results = list(svc.list_collections(academic_year=current_year))
        assert results[0].student_count == 2
        assert results[0].total_amount == Decimal("10600.00")

    def test_bulk_created_enrollment_is_billed(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        """StudentService.bulk_create_students() enrolls students into a
        batch via individual BatchStudent.create() calls (not bulk_create),
        so the post_save signal still fires and open collections stay in
        sync — matching every other enrollment path.
        """
        svc = FeeCollectionService(school)
        svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )

        created = StudentService(school).bulk_create_students(
            students_data=[{
                "first_name": "Bulk", "last_name": "Enrollee",
                "admission_no": f"ADM{uuid.uuid4().hex[:6].upper()}",
                "admission_date": date(2024, 9, 1),
                "date_of_birth": date(2018, 1, 1),
                "gender": "male",
            }],
            batch_id=str(batch.id),
        )

        assert FinanceFee.objects.filter(student=created[0]).count() == 1
        results = list(svc.list_collections(academic_year=current_year))
        assert results[0].student_count == 2
        assert results[0].total_amount == Decimal("10600.00")

    def test_transferred_out_unpaid_student_excluded_from_reality(
        self, school, batch, other_batch, student, fee_category, particulars, current_year
    ):
        svc = FeeCollectionService(school)
        svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )

        StudentService(school).transfer_batch(
            student_id=str(student.id),
            from_batch_id=str(batch.id),
            to_batch_id=str(other_batch.id),
        )

        results = list(svc.list_collections(academic_year=current_year))
        collection = results[0]
        assert collection.student_count == 0
        assert collection.total_amount is None
        assert collection.outstanding_amount is None

        summary = svc.get_collection_summary(str(collection.id))
        assert summary["totals"]["students"] == 0
        assert summary["rows"] == []

    def test_transferred_out_student_with_payment_still_counted(
        self, school, batch, other_batch, student, fee_category, particulars, current_year
    ):
        svc = FeeCollectionService(school)
        result = svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )
        collection = result["collections"][0]
        fee = FinanceFee.objects.get(fee_collection=collection)
        fee.balance = Decimal("4300.00")  # 1000 already paid
        fee.save(update_fields=["balance"])

        StudentService(school).transfer_batch(
            student_id=str(student.id),
            from_batch_id=str(batch.id),
            to_batch_id=str(other_batch.id),
        )

        results = list(svc.list_collections(academic_year=current_year))
        assert results[0].student_count == 1
        assert results[0].outstanding_amount == Decimal("4300.00")

        summary = svc.get_collection_summary(str(collection.id))
        assert summary["totals"]["students"] == 1
        assert summary["rows"][0]["student"] == student


@pytest.mark.django_db
class TestBackfillDriftedEnrollment:
    """sync_fee_collection_enrollment reconciles enrollments that bypassed the
    post_save signal entirely (raw SQL inserts like the Fedena migration, or
    the historical bulk_create() bug) and so never got billed against an
    already-open collection."""

    def test_command_backfills_signal_bypassed_enrollment(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        from io import StringIO
        from django.core.management import call_command
        from django.db.models.signals import post_save
        from core.signals import create_student_fees_on_batch_enrollment

        svc = FeeCollectionService(school)
        svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )

        drifted = Student.objects.create(
            first_name="Drifted", last_name="Enrollee",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date(2024, 9, 1),
            date_of_birth=date(2018, 1, 1),
            gender="male",
            tenant=school,
        )
        # Simulate an enrollment path that bypasses the ORM's post_save
        # signal (raw SQL / bulk_create) — the drifted student is enrolled
        # but never billed.
        post_save.disconnect(create_student_fees_on_batch_enrollment, sender=BatchStudent)
        try:
            BatchStudent.objects.create(batch=batch, student=drifted, tenant=school)
        finally:
            post_save.connect(create_student_fees_on_batch_enrollment, sender=BatchStudent)

        assert FinanceFee.objects.filter(student=drifted).count() == 0
        results = list(svc.list_collections(academic_year=current_year))
        assert results[0].student_count == 1  # only the original `student`

        out = StringIO()
        call_command("sync_fee_collection_enrollment", "--tenant-id", str(school.id), stdout=out)

        assert FinanceFee.objects.filter(student=drifted).count() == 1
        results = list(svc.list_collections(academic_year=current_year))
        assert results[0].student_count == 2

    def test_dry_run_reports_without_writing(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        from io import StringIO
        from django.core.management import call_command
        from django.db.models.signals import post_save
        from core.signals import create_student_fees_on_batch_enrollment

        svc = FeeCollectionService(school)
        svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )

        drifted = Student.objects.create(
            first_name="Drifted", last_name="Enrollee",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date(2024, 9, 1),
            date_of_birth=date(2018, 1, 1),
            gender="male",
            tenant=school,
        )
        post_save.disconnect(create_student_fees_on_batch_enrollment, sender=BatchStudent)
        try:
            BatchStudent.objects.create(batch=batch, student=drifted, tenant=school)
        finally:
            post_save.connect(create_student_fees_on_batch_enrollment, sender=BatchStudent)

        out = StringIO()
        call_command(
            "sync_fee_collection_enrollment", "--tenant-id", str(school.id),
            "--dry-run", stdout=out,
        )

        assert FinanceFee.objects.filter(student=drifted).count() == 0
        assert "Would create 1" in out.getvalue()

    def test_stale_prior_year_enrollment_is_not_counted(
        self, school, course, batch, student, fee_category, particulars, current_year, prior_year
    ):
        """A student with a leftover is_active=True BatchStudent row in a
        PRIOR year (the promote_students.py residue bug) must not inflate
        this command's enrollment count or get synced against this year's
        collections — only batch__academic_year=<active year> counts.
        """
        from io import StringIO
        from django.core.management import call_command

        old_batch = Batch.objects.create(
            name=f"Old Section {uuid.uuid4().hex[:4]}", course=course, academic_year=prior_year,
            start_date=date(2023, 9, 1), end_date=date(2024, 7, 31), tenant=school,
        )
        stale_student = Student.objects.create(
            first_name="Stale", last_name="Leftover",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date(2023, 9, 1), date_of_birth=date(2017, 1, 1),
            gender="male", tenant=school,
        )
        BatchStudent.objects.create(batch=old_batch, student=stale_student, tenant=school)

        svc = FeeCollectionService(school)
        svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )

        out = StringIO()
        call_command("sync_fee_collection_enrollment", "--tenant-id", str(school.id), stdout=out)

        assert "checked 1 enrollment" in out.getvalue()
        assert FinanceFee.objects.filter(student=stale_student).count() == 0


@pytest.mark.django_db
class TestCollectionSummary:
    def test_summary_totals_and_status(
        self, school, batch, student, fee_category, particulars
    ):
        svc = FeeCollectionService(school)
        result = svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )
        collection = result["collections"][0]
        summary = svc.get_collection_summary(str(collection.id))
        assert summary["totals"]["students"] == 1
        assert summary["totals"]["total"] == Decimal("5300.00")
        assert summary["totals"]["collected"] == Decimal("0.00")
        assert summary["totals"]["outstanding"] == Decimal("5300.00")
        row = summary["rows"][0]
        assert row["student"] == student
        assert row["status"] == "unpaid"

    def test_partial_payment_status(
        self, school, batch, student, fee_category, particulars
    ):
        svc = FeeCollectionService(school)
        result = svc.create_collection(
            name="Term 1 Collection",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 1, 20),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 30),
        )
        collection = result["collections"][0]
        fee = FinanceFee.objects.get(fee_collection=collection)
        fee.balance = Decimal("4300.00")  # 1000 paid
        fee.save(update_fields=["balance"])
        summary = svc.get_collection_summary(str(collection.id))
        assert summary["rows"][0]["status"] == "partial"
        assert summary["rows"][0]["paid"] == Decimal("1000.00")
        assert summary["totals"]["collected"] == Decimal("1000.00")
