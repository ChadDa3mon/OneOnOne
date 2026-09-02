from django.db import models
from django.urls import reverse


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
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("report-detail", args=[self.pk])

    def answers_by_question(self):
        """Map of question_id -> Answer for quick template lookups."""
        return {a.question_id: a for a in self.answers.select_related("question")}


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
