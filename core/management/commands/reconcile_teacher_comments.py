"""
Fold stray teacher-comment rows into whichever table a batch's *current*
report-template layout actually routes to.

Before TeacherCommentService unified routing, the staff exam-group page wrote
skills batches' comments to ``TeacherComment`` (keyed by exam_group) while the
portal skills wizard wrote ``SkillsTeacherComment`` (keyed by batch+term) —
two rows for the same logical comment, papered over by per-field read
fallbacks. Routing now sends every surface of a batch to one table, chosen by
the batch's live report-template layout — but that layout can change (an
admin flips the default template), and when it does, existing rows in the
*old* table become invisible to the new route. This command folds rows in
both directions so it stays correct regardless of which way a batch flips:

- SKILLS-layout batches: fold stray ``TeacherComment`` (exam_group-keyed)
  rows into the canonical ``SkillsTeacherComment`` (batch+term-keyed) row.
- Non-SKILLS-layout batches: fold stray ``SkillsTeacherComment`` rows into
  the canonical ``TeacherComment`` row, keyed to the batch's latest exam
  group (the same exam group ``current_route_for_batch`` would resolve).

Per field (comment, signature), a non-empty value beats an empty one and the
most recently updated row wins a genuine conflict; the ``class_teacher`` stamp
travels with whichever comment text wins. The stray row is then deleted,
leaving one source of truth. Idempotent: after a successful run there are no
stray rows left for any scanned batch.

Usage:
    # Dry run
    python manage.py reconcile_teacher_comments --tenant=<schema>

    # Apply
    python manage.py reconcile_teacher_comments --tenant=<schema> --execute

    # Restrict to one batch
    python manage.py reconcile_teacher_comments --tenant=<schema> --batch=<uuid>
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

# The value-bearing fields a fold can move. `class_teacher` is deliberately not
# here: it is a stamp that follows the comment rather than a field that competes
# on its own recency (see _fold_field). Same set as migration 0117's _FOLD_FIELDS.
_FOLD_FIELDS = ("comment", "signature_image")


class Command(BaseCommand):
    help = "Fold stray teacher-comment rows into whichever table a batch's current report layout routes to (both directions)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--execute", action="store_true", default=False)
        parser.add_argument("--batch", default=None, help="Restrict to one batch id")

    def handle(self, *args, **options):
        schema = options["tenant"]
        execute = options["execute"]

        if not execute:
            self.stdout.write(self.style.WARNING("DRY RUN — pass --execute to apply\n"))

        with schema_context(schema):
            self._reconcile(execute, options["batch"])

    def _reconcile(self, execute: bool, batch_id):
        from core.models import Batch, ReportTemplate

        batches = Batch.objects.all().select_related("course")
        if batch_id:
            batches = batches.filter(id=batch_id)

        created = []      # (row, term) — no skills row existed, values moved over
        merged = []        # (row, target, fields_changed) — folded into existing skills row
        no_term = []        # (row,) — no term resolvable; folded into the term=None row
        created_rev = []   # (row, exam_group) — reverse direction: no TeacherComment row existed
        merged_rev = []     # (row, target, fields_changed) — reverse direction fold
        no_exam_group = []  # (row,) — batch has no exam group to fold into; skipped
        skills_batches = 0
        non_skills_batches = 0

        for batch in batches:
            layout = self._current_layout(batch)
            if layout == ReportTemplate.LAYOUT_SKILLS:
                skills_batches += 1
                self._fold_into_skills(batch, execute, created, merged, no_term)
            else:
                non_skills_batches += 1
                self._fold_into_non_skills(batch, execute, created_rev, merged_rev, no_exam_group)

        self.stdout.write(f"SKILLS-layout batches scanned:     {skills_batches}")
        self.stdout.write(f"  Moved to new skills row:         {len(created)}")
        self.stdout.write(f"  Folded into existing skills row: {len(merged)}")
        self.stdout.write(f"  Keyed to term=None (no term):    {len(no_term)}")
        self.stdout.write(f"Non-SKILLS-layout batches scanned: {non_skills_batches}")
        self.stdout.write(f"  Moved to new exam-group row:     {len(created_rev)}")
        self.stdout.write(f"  Folded into existing exam row:   {len(merged_rev)}")
        self.stdout.write(f"  Skipped (no exam group to fold into): {len(no_exam_group)}")

        if created:
            self.stdout.write("\nSample moves, TeacherComment -> SkillsTeacherComment (first 10):")
            for row, term in created[:10]:
                self.stdout.write(
                    f"  student={row.student_id} exam_group={row.exam_group_id} "
                    f"-> term={getattr(term, 'id', None)} "
                    f"comment_len={len(row.comment)} has_signature={bool(row.signature_image)}"
                )

        if merged:
            self.stdout.write("\nSample folds, TeacherComment -> SkillsTeacherComment (first 10):")
            for row, target, changed in merged[:10]:
                self.stdout.write(
                    f"  student={row.student_id} exam_group={row.exam_group_id} "
                    f"-> skills(pk={target.pk}, term={target.term_id}) "
                    f"fields_updated={changed or 'none'}"
                )

        if no_term:
            self.stdout.write(self.style.WARNING(
                "\nRows keyed to term=None because no term resolved (first 10):"
            ))
            for row in no_term[:10]:
                self.stdout.write(
                    f"  student={row.student_id} exam_group={row.exam_group_id} (pk={row.pk})"
                )

        if created_rev:
            self.stdout.write("\nSample moves, SkillsTeacherComment -> TeacherComment (first 10):")
            for row, exam_group in created_rev[:10]:
                self.stdout.write(
                    f"  student={row.student_id} batch={row.batch_id} term={row.term_id} "
                    f"-> exam_group={exam_group.id} "
                    f"comment_len={len(row.comment)} has_signature={bool(row.signature_image)}"
                )

        if merged_rev:
            self.stdout.write("\nSample folds, SkillsTeacherComment -> TeacherComment (first 10):")
            for row, target, changed in merged_rev[:10]:
                self.stdout.write(
                    f"  student={row.student_id} batch={row.batch_id} term={row.term_id} "
                    f"-> exam_group_comment(pk={target.pk}, exam_group={target.exam_group_id}) "
                    f"fields_updated={changed or 'none'}"
                )

        if no_exam_group:
            self.stdout.write(self.style.WARNING(
                "\nRows skipped — batch has no exam group to fold into (first 10):"
            ))
            for row in no_exam_group[:10]:
                self.stdout.write(
                    f"  student={row.student_id} batch={row.batch_id} term={row.term_id} (pk={row.pk})"
                )

        if not execute:
            self.stdout.write(self.style.WARNING("\nDry run complete. Pass --execute to apply."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Moved {len(created) + len(created_rev)} row(s), "
            f"folded {len(merged) + len(merged_rev)} row(s)."
        ))

    @staticmethod
    def _current_layout(batch):
        from core.grading_utils import infer_report_layout
        from core.services.teacher_comment_service import TeacherCommentService

        template = TeacherCommentService.resolve_template_for_batch(batch.tenant, batch)
        if template is not None:
            return template.layout_type
        layout, _scale = infer_report_layout(batch)
        return layout

    @staticmethod
    def _fold_field(row, target, changed, provenance):
        """`provenance[field]` is the updated_at of the row whose value the
        target currently carries: its own pre-run timestamp to start with (never
        `target.updated_at`, which `save()` bumps via auto_now and which would
        then beat every remaining stray), then each stray that wins the field.

        Ranking every stray against one *fixed* baseline is wrong. Strays are
        folded newest-first, so as soon as a newer stray writes a field, an older
        stray still clears a stale baseline and overwrites it — and the newer
        text is then deleted along with its row.
        """
        for field in _FOLD_FIELDS:
            src = getattr(row, field) or ""
            dst = getattr(target, field) or ""
            if not src or src == dst:
                continue
            # Non-empty beats empty; a genuine conflict goes to the most
            # recently updated row that has spoken so far.
            if not dst or row.updated_at > provenance[field]:
                setattr(target, field, src)
                provenance[field] = row.updated_at
                changed.append(field)
                # The stamp follows the comment text it belongs to — same rule
                # as migration 0117's _fold_group, so the command and the
                # migration reach the same final state. Guarded on truthiness:
                # a NULL stamp means "unknown", not "nobody", and must not
                # erase one the target already has.
                if field == "comment" and row.class_teacher_id:
                    target.class_teacher_id = row.class_teacher_id
                    changed.append("class_teacher")
        return changed

    @staticmethod
    def _newest_first(rows):
        return sorted(rows, key=lambda r: r.updated_at, reverse=True)

    def _fold_bucket(self, strays, target, baseline, execute):
        """Fold every stray that resolves to `target` in a single pass.

        Several strays routinely converge on one target — every exam group of
        a batch resolves to the same (student, term) skills row — so they must
        be folded together against one `baseline` and saved once. Folding them
        one at a time re-read the target's bumped updated_at, so every stray
        after the first lost the recency tie-break and was deleted with its
        content still in it.

        Newest-first, so when several strays could fill the same blank field
        the freshest one wins. Returns [(stray, changed_fields), ...].
        """
        results, changed_all = [], []
        # One provenance map for the whole bucket: each field starts out owned
        # by whatever the target already carried, then changes hands as strays
        # win it. See _fold_field.
        provenance = dict.fromkeys(_FOLD_FIELDS, baseline)
        for stray in self._newest_first(strays):
            changed = self._fold_field(stray, target, [], provenance)
            changed_all.extend(changed)
            results.append((stray, changed))

        if execute:
            if changed_all:
                # dict.fromkeys: dedupe while keeping order.
                target.save(update_fields=list(dict.fromkeys(changed_all)) + ["updated_at"])
            for stray, _changed in results:
                stray.delete()
        return results

    def _fold_into_skills(self, batch, execute, created, merged, no_term):
        from core.models import SkillsTeacherComment, TeacherComment
        from core.services.teacher_comment_service import TeacherCommentService

        svc = TeacherCommentService(tenant=batch.tenant)
        rows = list(
            TeacherComment.objects.filter(
                tenant=batch.tenant, exam_group__batch=batch
            ).select_related("exam_group")
        )
        if not rows:
            return

        # Bucket by the identity of the row each stray folds into — several
        # exam groups of one batch resolve to the same (student, term), so
        # they share a target and have to be folded as a group.
        buckets = {}
        for row in rows:
            term = svc.resolve_skills_term(batch, exam_group=row.exam_group)
            if term is None:
                no_term.append(row)
            key = (str(row.student_id), getattr(term, "id", None))
            buckets.setdefault(key, (term, []))[1].append(row)

        with transaction.atomic():
            for (student_id, _term_id), (term, strays) in buckets.items():
                # Matched on row identity only — class_teacher is a stamp, not
                # part of the key, so including it here would fold the stray
                # row into a *second* row for the same student.
                target = SkillsTeacherComment.objects.filter(
                    tenant=batch.tenant, student_id=student_id,
                    batch=batch, term=term,
                ).first()
                baseline = target.updated_at if target is not None else None

                if target is None:
                    # No target yet: the newest stray becomes it, and the rest
                    # fold in against *its* timestamp — a freshly created row
                    # would carry `now`, outranking every remaining stray.
                    seed, *strays = self._newest_first(strays)
                    baseline = seed.updated_at
                    fields = dict(
                        tenant=batch.tenant, student_id=student_id,
                        batch=batch, term=term,
                        comment=seed.comment,
                        signature_image=seed.signature_image,
                        class_teacher=seed.class_teacher,
                    )
                    if execute:
                        target = SkillsTeacherComment.objects.create(**fields)
                        seed.delete()
                    else:
                        target = SkillsTeacherComment(**fields)
                    created.append((seed, term))

                for stray, changed in self._fold_bucket(strays, target, baseline, execute):
                    merged.append((stray, target, changed))

    def _fold_into_non_skills(self, batch, execute, created_rev, merged_rev, no_exam_group):
        from core.models import ExamGroup, SkillsTeacherComment, TeacherComment

        rows = list(SkillsTeacherComment.objects.filter(tenant=batch.tenant, batch=batch))
        if not rows:
            return

        exam_group = ExamGroup.objects.filter(
            tenant=batch.tenant, batch=batch
        ).order_by("-exam_date").first()
        if exam_group is None:
            no_exam_group.extend(rows)
            return

        # One exam group for the whole batch, so the target identity is just
        # the student — a student's rows across several terms all converge.
        buckets = {}
        for row in rows:
            buckets.setdefault(str(row.student_id), []).append(row)

        with transaction.atomic():
            for student_id, strays in buckets.items():
                # Identity only — see the note in _fold_into_skills.
                target = TeacherComment.objects.filter(
                    tenant=batch.tenant, student_id=student_id,
                    exam_group=exam_group,
                ).first()
                baseline = target.updated_at if target is not None else None

                if target is None:
                    seed, *strays = self._newest_first(strays)
                    baseline = seed.updated_at
                    fields = dict(
                        tenant=batch.tenant, student_id=student_id,
                        exam_group=exam_group,
                        comment=seed.comment,
                        signature_image=seed.signature_image,
                        class_teacher=seed.class_teacher,
                    )
                    if execute:
                        target = TeacherComment.objects.create(**fields)
                        seed.delete()
                    else:
                        target = TeacherComment(**fields)
                    created_rev.append((seed, exam_group))

                for stray, changed in self._fold_bucket(strays, target, baseline, execute):
                    merged_rev.append((stray, target, changed))
