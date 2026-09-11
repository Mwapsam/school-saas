from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        (
            "core",
            "0075_rename_core_teache_tenant__examgr_idx_core_teache_tenant__7a5b6d_idx",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="SkillsTeacherComment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("comment", models.TextField(blank=True, default="")),
                ("signature_image", models.TextField(blank=True, default="")),
                (
                    "batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="skills_teacher_comments",
                        to="core.batch",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="skills_teacher_comments",
                        to="core.student",
                    ),
                ),
                (
                    "term",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="skills_teacher_comments",
                        to="core.term",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="skillsteachercomment_set",
                        to="core.school",
                    ),
                ),
            ],
            options={
                "unique_together": {("tenant", "student", "batch", "term")},
            },
        ),
        migrations.AddIndex(
            model_name="skillsteachercomment",
            index=models.Index(
                fields=["tenant", "batch", "term"],
                name="core_skills_tenant__batch__term_idx",
            ),
        ),
    ]
