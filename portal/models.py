"""
Portal-owned persistence.

The only state the portal needs that core doesn't already model is the
teacher's draft/submit lifecycle for an exam's marks. We keep it here (rather
than adding columns to core.ExamScore) so the portal stays a self-contained
black box and reports/admin are unaffected — parents still only ever see marks
once an admin publishes the exam group.
"""
from django.conf import settings
from django.db import models

from core.models import TenantAwareModel


class MarkSubmission(TenantAwareModel):
    """Tracks whether a teacher has saved an exam's marks as a draft or
    submitted them for review. One row per exam."""

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
    ]

    exam = models.OneToOneField(
        "core.Exam",
        on_delete=models.CASCADE,
        related_name="portal_submission",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mark_submissions",
        db_constraint=False,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["exam"]),
        ]

    def __str__(self):
        return f"{self.exam_id} — {self.status}"


class SkillsSubmission(TenantAwareModel):
    """Tracks whether a class teacher has submitted (locked) a class's skill
    ratings and comments for a term. One row per (batch, term)."""

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
    ]

    batch = models.ForeignKey(
        "core.Batch",
        on_delete=models.CASCADE,
        related_name="skills_submissions",
    )
    term = models.ForeignKey(
        "core.Term",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="skills_submissions",
    )
    employee = models.ForeignKey(
        "core.Employee",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="skills_submissions",
        help_text="Null = whole-batch submission (legacy/staff). Set = this teacher's own subset only.",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="skills_submissions",
        db_constraint=False,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["batch", "term", "employee"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["batch", "term"]),
        ]

    def __str__(self):
        return f"{self.batch_id} — {self.term_id} — {self.status}"
