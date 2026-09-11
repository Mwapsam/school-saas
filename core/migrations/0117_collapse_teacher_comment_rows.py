"""Collapse teacher-comment rows to one per (student, route).

Rows used to be keyed by (student, period, class_teacher), so a reassignment
started a *new* row rather than restamping the existing one. Reads then had to
guess which of several rows was "the" comment, and every heuristic tried so far
has had a failure mode — the latest being that an explicit clear by the newly
assigned teacher could never outrank the previous teacher's stale row.

`class_teacher` is now a display/grouping stamp only, not part of row identity.
This migration folds each student's duplicate rows into a single survivor before
tightening `unique_together`, which cannot be applied while duplicates exist.

Grouping is done in Python rather than by the database on purpose: Postgres
never enforced the old constraint across a NULL `term` or NULL `class_teacher`,
so duplicates exist that the old constraint did not catch.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Count

_FOLD_FIELDS = ("comment", "signature_image")

_STAMP_HELP_TEXT = (
    "Teacher resolved as responsible for this student when the row was last "
    "saved — stamped by TeacherCommentService, never edited directly. A "
    "display/grouping stamp only: it is NOT part of the row's identity, so a "
    "reassignment restamps this row rather than starting a new one."
)


def _fold_group(rows):
    """Fold a student's duplicate rows into one survivor.

    The most recently updated row survives. Per field, a non-empty value beats
    an empty one — same rule as the reconcile_teacher_comments command. Because
    the survivor is by definition the newest, a loser can only ever fill in a
    field the survivor left blank, never overwrite a newer value.

    Returns (survivor, losers).
    """
    survivor = max(rows, key=lambda r: r.updated_at)
    losers = [r for r in rows if r.pk != survivor.pk]

    # Newest-first, so the freshest loser wins when several could fill a blank.
    for loser in sorted(losers, key=lambda r: r.updated_at, reverse=True):
        for field in _FOLD_FIELDS:
            src = getattr(loser, field) or ""
            if src and not (getattr(survivor, field) or ""):
                setattr(survivor, field, src)
                # The stamp follows the comment text it belongs to — but only
                # when the loser has one. A NULL stamp means "we don't know who
                # was responsible", not "nobody", so copying it over would erase
                # a valid stamp on the survivor and, with it, the class-teacher
                # signature the report card prints.
                if field == "comment" and loser.class_teacher_id:
                    survivor.class_teacher_id = loser.class_teacher_id
    return survivor, losers


def _duplicate_keys(model, key_fields):
    """The `key_fields` values that more than one row shares.

    An aggregate, so it never loads a row — comment and signature_image hold
    base64 blobs and a schema can have many thousands of rows. GROUP BY treats
    NULLs as equal, so this finds the NULL-term duplicates the old unique
    constraint could not see, which are the whole reason this runs.
    """
    return (
        model.objects.values(*key_fields)
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )


def _collapse(model, key_fields):
    """Collapse duplicates in `model`, grouping rows by `key_fields`.

    Only rows belonging to a duplicated key are ever loaded; a schema with no
    duplicates costs one aggregate query and nothing else.
    """
    collapsed = 0
    # Materialised up front — the loop body deletes rows the aggregate counted.
    for key in list(_duplicate_keys(model, key_fields)):
        key.pop("n")
        rows = list(model.objects.filter(**key))
        if len(rows) < 2:  # raced away between the two queries
            continue
        survivor, losers = _fold_group(rows)
        survivor.save()
        model.objects.filter(pk__in=[r.pk for r in losers]).delete()
        collapsed += len(losers)
    return collapsed


def collapse_rows(apps, schema_editor):
    _collapse(
        apps.get_model("core", "TeacherComment"),
        ("tenant_id", "student_id", "exam_group_id"),
    )
    _collapse(
        apps.get_model("core", "SkillsTeacherComment"),
        ("tenant_id", "student_id", "batch_id", "term_id"),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0116_remove_school_signature_fields"),
    ]

    operations = [
        migrations.RunPython(collapse_rows, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="teachercomment",
            unique_together={("tenant", "student", "exam_group")},
        ),
        migrations.AlterUniqueTogether(
            name="skillsteachercomment",
            unique_together={("tenant", "student", "batch", "term")},
        ),
        migrations.AddConstraint(
            model_name="skillsteachercomment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("term__isnull", True)),
                fields=("tenant", "student", "batch"),
                name="uniq_skills_comment_null_term",
            ),
        ),
        migrations.AlterField(
            model_name="teachercomment",
            name="class_teacher",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="core.employee",
                help_text=_STAMP_HELP_TEXT,
            ),
        ),
        migrations.AlterField(
            model_name="skillsteachercomment",
            name="class_teacher",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="core.employee",
                help_text=_STAMP_HELP_TEXT,
            ),
        ),
    ]
