from django.db import models
from django.urls import reverse
from django.utils import timezone

from .prompt_defaults import (
    DEFAULT_EXTRACT_ACTION_ITEMS_PROMPT,
    DEFAULT_SUMMARY_PROMPT,
    DEFAULT_TALKING_POINTS_PROMPT,
)

ONE_ON_ONE_OVERDUE_DAYS = 21


class Question(models.Model):
    """A profile question asked of every direct report (flat, shared list)."""

    text = models.CharField(max_length=500)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.text


class DirectReport(models.Model):
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    personal_notes = models.TextField(
        blank=True,
        help_text="Family, interests, background — anything worth remembering that isn't a 1:1 topic.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ai_summary = models.TextField(blank=True)
    ai_summary_generated_at = models.DateTimeField(null=True, blank=True)
    ai_talking_points = models.TextField(blank=True)
    ai_talking_points_generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("report-detail", args=[self.pk])

    def answers_by_question(self):
        """Map of question_id -> Answer for quick template lookups."""
        return {a.question_id: a for a in self.answers.select_related("question")}

    @property
    def last_one_on_one_date(self):
        latest = self.one_on_ones.first()  # OneOnOne.Meta.ordering is -date
        return latest.date if latest else None

    @property
    def days_since_last_one_on_one(self):
        last = self.last_one_on_one_date
        return (timezone.now().date() - last).days if last else None

    @property
    def is_overdue_for_one_on_one(self):
        days = self.days_since_last_one_on_one
        return days is None or days >= ONE_ON_ONE_OVERDUE_DAYS


class Contact(models.Model):
    """A coworker who isn't a direct report - manager, peer, skip-level, etc."""

    RELATIONSHIP_CHOICES = [
        ("manager", "My manager"),
        ("peer", "Peer"),
        ("skip", "Skip-level"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, default="peer")
    title = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(
        blank=True,
        help_text="Anything worth remembering — family, projects, background, how you know them.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class QuickNote(models.Model):
    """A short timestamped note captured from the global quick-note box,
    for jotting something down before it's forgotten - distinct from a
    formal 1:1 record, and usable for either a direct report or a contact.
    """

    report = models.ForeignKey(DirectReport, null=True, blank=True, related_name="quick_notes", on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, null=True, blank=True, related_name="quick_notes", on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(report__isnull=False, contact__isnull=True)
                    | models.Q(report__isnull=True, contact__isnull=False)
                ),
                name="quicknote_exactly_one_target",
            )
        ]

    def __str__(self):
        return self.text[:50]

    @property
    def target(self):
        return self.report or self.contact


class Resource(models.Model):
    """A saved reference note - an article link, a technique, a quote -
    written in Markdown, for building up a personal management playbook."""

    title = models.CharField(max_length=200)
    tag = models.CharField(max_length=100, blank=True, help_text="A topic label, e.g. 'Servant Leadership' or 'Difficult Conversations'.")
    url = models.URLField(blank=True, help_text="Link to the original source, if any.")
    body = models.TextField(blank=True, help_text="Markdown supported.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("resource-detail", args=[self.pk])


class Answer(models.Model):
    report = models.ForeignKey(DirectReport, related_name="answers", on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name="answers", on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["report", "question"], name="unique_answer_per_report_question")
        ]

    def __str__(self):
        return f"{self.report} / {self.question}"


class OneOnOne(models.Model):
    report = models.ForeignKey(DirectReport, related_name="one_on_ones", on_delete=models.CASCADE)
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.report} - {self.date}"


class ActionItem(models.Model):
    one_on_one = models.ForeignKey(OneOnOne, related_name="action_items", on_delete=models.CASCADE)
    description = models.CharField(max_length=500)
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_done", "created_at"]

    def __str__(self):
        return self.description


class OllamaSettings(models.Model):
    """Single shared record of how to reach the user's Ollama instance."""

    host = models.CharField(max_length=255, blank=True, help_text="Hostname or IP, e.g. 192.168.1.50")
    port = models.PositiveIntegerField(default=11434)
    selected_model = models.CharField(max_length=200, blank=True)
    summary_prompt = models.TextField(default=DEFAULT_SUMMARY_PROMPT)
    talking_points_prompt = models.TextField(default=DEFAULT_TALKING_POINTS_PROMPT)
    extract_action_items_prompt = models.TextField(default=DEFAULT_EXTRACT_ACTION_ITEMS_PROMPT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ollama settings"
        verbose_name_plural = "Ollama settings"

    def __str__(self):
        return f"Ollama @ {self.host}:{self.port}" if self.host else "Ollama (not configured)"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def base_url(self):
        return f"http://{self.host}:{self.port}"
