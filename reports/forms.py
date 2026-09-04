from django import forms
from django.forms import inlineformset_factory

from .models import ActionItem, Answer, DirectReport, OllamaSettings, OneOnOne, Question


class BootstrapFormMixin:
    """Adds Bootstrap form-control/form-check classes to all fields automatically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.CheckboxInput,)):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                existing = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = (existing + " form-control").strip()


class DirectReportForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DirectReport
        fields = ["name", "title", "email", "start_date", "personal_notes", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "personal_notes": forms.Textarea(attrs={"rows": 4, "placeholder": "e.g. spouse's name, kids, hobbies, background..."}),
        }


class QuestionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Question
        fields = ["text", "order"]


class AnswerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Answer
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3}),
        }


class OneOnOneForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OneOnOne
        fields = ["date", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 8}),
        }


class BootstrapActionItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ActionItem
        fields = ["description", "is_done"]


ActionItemFormSet = inlineformset_factory(
    OneOnOne,
    ActionItem,
    form=BootstrapActionItemForm,
    extra=2,
    can_delete=True,
)


class OllamaSettingsForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OllamaSettings
        fields = ["host", "port"]
        widgets = {
            "host": forms.TextInput(attrs={"placeholder": "192.168.1.50"}),
        }
