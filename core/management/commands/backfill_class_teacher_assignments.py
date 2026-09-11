from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import schema_context

from core.models import School, Batch, BatchStudent, ClassTeacherAssignment, TeacherComment, SkillsTeacherComment
from core.services.class_teacher_assignment_service import ClassTeacherAssignmentService
from core.services.teacher_comment_service import TeacherCommentService


class Command(BaseCommand):
    help = (
        "Backfill ClassTeacherAssignment rows for existing students in multi-teacher batches. "
        "Mirrors the reconcile_teacher_comments pattern: dry-run by default, --execute to apply."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            required=True,
            help="Schema name of the tenant to backfill",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually write changes; omit to dry-run",
        )
        parser.add_argument(
            "--batch",
            type=str,
            default=None,
            help="Backfill only this batch (UUID); omit for all",
        )
        parser.add_argument(
            "--rollback",
            action="store_true",
            help="Delete only rows tagged reason__startswith='backfill:'; never touches admin rows",
        )

    def handle(self, *args, **options):
        tenant_name = options["tenant"]
        execute = options["execute"]
        batch_id = options["batch"]
        rollback = options["rollback"]

        try:
            tenant = School.objects.get(schema_name=tenant_name)
        except School.DoesNotExist:
            raise CommandError(f"Tenant {tenant_name} not found")

        with schema_context(tenant_name):
            if rollback:
                return self._do_rollback(tenant, execute)
            return self._do_backfill(tenant, batch_id, execute)

    def _do_backfill(self, tenant, batch_id, execute):
        svc = ClassTeacherAssignmentService(tenant)
        tc_svc = TeacherCommentService(tenant)

        query = Batch.objects.filter(tenant=tenant)
        if batch_id:
            query = query.filter(id=batch_id)

        total_students = 0
        assigned_auto = 0
        assigned_needs_review = 0
        skipped_empty_pool = 0
        skipped_existing = 0
        comments_stamped = 0
        signatures_migrated = 0

        for batch in query.select_related("employee").prefetch_related("class_teachers"):
            # Get the pool of teachers, ordered by ID for consistent selection
            pool = list(batch.class_teachers.all().order_by('id')) or ([batch.employee] if batch.employee else [])

            if not pool:
                # No teachers → skip this batch
                active_students = BatchStudent.objects.filter(
                    batch=batch, tenant=tenant, is_active=True
                ).count()
                skipped_empty_pool += active_students
                self.stdout.write(
                    f"  Batch {batch.name}: {active_students} students, no teachers — skipping"
                )
                continue

            is_single_teacher = len(pool) == 1
            assigned_teacher = pool[0]
            reason = "backfill:auto" if is_single_teacher else "backfill:needs_review"

            # Backfill assignment rows
            active_students = BatchStudent.objects.filter(
                batch=batch, tenant=tenant, is_active=True
            ).select_related("student")

            for bs in active_students:
                total_students += 1
                existing = ClassTeacherAssignment.objects.filter(
                    student=bs.student,
                    batch=batch,
                    is_active=True,
                    tenant=tenant,
                ).exists()

                if existing:
                    skipped_existing += 1
                    continue

                if execute:
                    svc.assign(
                        str(bs.student.id),
                        str(batch.id),
                        str(assigned_teacher.id),
                        reason=reason,
                    )

                if is_single_teacher:
                    assigned_auto += 1
                else:
                    assigned_needs_review += 1

            # Stamp existing comments with class_teacher if not already stamped
            for comment in TeacherComment.objects.filter(
                exam_group__batch=batch, tenant=tenant, class_teacher__isnull=True
            ):
                teacher = svc.get_assigned_employee(str(comment.student.id), batch)
                if teacher and execute:
                    comment.class_teacher = teacher
                    comment.save(update_fields=["class_teacher"])
                    comments_stamped += 1

            for comment in SkillsTeacherComment.objects.filter(
                batch=batch, tenant=tenant, class_teacher__isnull=True
            ):
                teacher = svc.get_assigned_employee(str(comment.student.id), batch)
                if teacher and execute:
                    comment.class_teacher = teacher
                    comment.save(update_fields=["class_teacher"])
                    comments_stamped += 1

            # Migrate signature_image from comments up to Employee
            for employee in pool:
                # Get signatures from both TeacherComment and SkillsTeacherComment
                tc_sigs = TeacherComment.objects.filter(
                    exam_group__batch=batch,
                    tenant=tenant,
                    signature_image__gt="",
                ).values_list("signature_image", flat=True)
                sc_sigs = SkillsTeacherComment.objects.filter(
                    batch=batch,
                    tenant=tenant,
                    signature_image__gt="",
                ).values_list("signature_image", flat=True)

                first_sig = next(iter(list(tc_sigs) + list(sc_sigs)), None)
                if first_sig and not employee.signature_image and execute:
                    employee.signature_image = first_sig
                    employee.save(update_fields=["signature_image"])
                    signatures_migrated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nBackfill complete ({'EXECUTED' if execute else 'DRY-RUN'}):\n"
                f"  Total students considered: {total_students}\n"
                f"  Assigned (auto, single-teacher): {assigned_auto}\n"
                f"  Assigned (needs_review, multi-teacher): {assigned_needs_review}\n"
                f"  Skipped (already assigned): {skipped_existing}\n"
                f"  Skipped (empty teacher pool): {skipped_empty_pool}\n"
                f"  Comments stamped with class_teacher: {comments_stamped}\n"
                f"  Signatures migrated to Employee: {signatures_migrated}"
            )
        )

    def _do_rollback(self, tenant, execute):
        deleted, _ = ClassTeacherAssignment.objects.filter(
            tenant=tenant,
            reason__startswith="backfill:",
        ).delete() if execute else (0, {})

        action = "DELETED" if execute else "WOULD DELETE"
        self.stdout.write(
            self.style.WARNING(
                f"Rollback ({'EXECUTED' if execute else 'DRY-RUN'}): "
                f"{action} {deleted} backfill-tagged rows"
            )
        )
