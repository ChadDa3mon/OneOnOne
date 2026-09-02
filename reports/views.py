import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ActionItemFormSet, DirectReportForm, OllamaSettingsForm, OneOnOneForm, QuestionForm
from .models import ActionItem, Answer, DirectReport, OllamaSettings, OneOnOne, Question
from .ollama import OllamaError, generate, list_models
from .prompts import build_summary_prompt, build_talking_points_prompt

logger = logging.getLogger(__name__)


def report_list(request):
    reports = DirectReport.objects.all()
    return render(request, "reports/report_list.html", {"reports": reports})


def report_add(request):
    if request.method == "POST":
        form = DirectReportForm(request.POST)
        if form.is_valid():
            report = form.save()
            messages.success(request, f"Added {report.name}.")
            return redirect("report-detail", pk=report.pk)
    else:
        form = DirectReportForm()
    return render(request, "reports/report_form.html", {"form": form, "title": "Add direct report"})


def report_edit(request, pk):
    report = get_object_or_404(DirectReport, pk=pk)
    if request.method == "POST":
        form = DirectReportForm(request.POST, instance=report)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {report.name}.")
            return redirect("report-detail", pk=report.pk)
    else:
        form = DirectReportForm(instance=report)
    return render(request, "reports/report_form.html", {"form": form, "title": f"Edit {report.name}"})


@require_POST
def report_delete(request, pk):
    report = get_object_or_404(DirectReport, pk=pk)
    name = report.name
    report.delete()
    messages.success(request, f"Removed {name}.")
    return redirect("report-list")


def report_detail(request, pk):
    report = get_object_or_404(DirectReport, pk=pk)
    questions = Question.objects.all()
    existing_answers = report.answers_by_question()
    answer_rows = [
        {"question": q, "answer": existing_answers.get(q.id)} for q in questions
    ]
    one_on_ones = report.one_on_ones.prefetch_related("action_items")
    ollama_settings = OllamaSettings.load()
    ai_configured = bool(ollama_settings.host and ollama_settings.selected_model)
    return render(
        request,
        "reports/report_detail.html",
        {
            "report": report,
            "answer_rows": answer_rows,
            "one_on_ones": one_on_ones,
            "ai_configured": ai_configured,
        },
    )


@require_POST
def report_ai_summary(request, pk):
    report = get_object_or_404(DirectReport, pk=pk)
    ollama_settings = OllamaSettings.load()
    configured = bool(ollama_settings.host and ollama_settings.selected_model)
    redirect_url = reverse("report-detail", args=[report.pk]) + "#ai-pane"

    if not configured:
        logger.warning(
            "AI generation requested for report %s but Ollama isn't configured (host=%r, model=%r)",
            report.pk, ollama_settings.host, ollama_settings.selected_model,
        )
        messages.error(request, "Ollama isn't configured — set a host and model first.")
        return redirect(redirect_url)

    if "generate_summary" in request.POST:
        logger.info("Generating AI summary for report %s (%s)", report.pk, report.name)
        try:
            report.ai_summary = generate(
                ollama_settings.base_url, ollama_settings.selected_model, build_summary_prompt(report)
            )
            report.ai_summary_generated_at = timezone.now()
            report.save(update_fields=["ai_summary", "ai_summary_generated_at"])
        except OllamaError as exc:
            logger.warning("AI summary generation failed for report %s: %s", report.pk, exc)
            messages.error(request, str(exc))
        except Exception:
            logger.exception("Unexpected error generating AI summary for report %s", report.pk)
            messages.error(request, "Unexpected error while generating the summary — check the server logs.")
        return redirect(redirect_url)

    if "generate_talking_points" in request.POST:
        logger.info("Generating AI talking points for report %s (%s)", report.pk, report.name)
        try:
            report.ai_talking_points = generate(
                ollama_settings.base_url, ollama_settings.selected_model, build_talking_points_prompt(report)
            )
            report.ai_talking_points_generated_at = timezone.now()
            report.save(update_fields=["ai_talking_points", "ai_talking_points_generated_at"])
        except OllamaError as exc:
            logger.warning("AI talking points generation failed for report %s: %s", report.pk, exc)
            messages.error(request, str(exc))
        except Exception:
            logger.exception("Unexpected error generating AI talking points for report %s", report.pk)
            messages.error(request, "Unexpected error while drafting talking points — check the server logs.")
        return redirect(redirect_url)

    return redirect(redirect_url)


@require_POST
def save_answers(request, pk):
    report = get_object_or_404(DirectReport, pk=pk)
    for question in Question.objects.all():
        field_name = f"question_{question.id}"
        if field_name in request.POST:
            text = request.POST[field_name].strip()
            Answer.objects.update_or_create(
                report=report, question=question, defaults={"text": text}
            )
    messages.success(request, "Answers saved.")
    return redirect("report-detail", pk=report.pk)


def question_list(request):
    questions = Question.objects.all()
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Question added.")
            return redirect("question-list")
    else:
        form = QuestionForm(initial={"order": (questions.last().order + 1) if questions.exists() else 0})
    return render(request, "reports/question_list.html", {"questions": questions, "form": form})


def question_edit(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, "Question updated.")
            return redirect("question-list")
    else:
        form = QuestionForm(instance=question)
    return render(request, "reports/question_form.html", {"form": form, "question": question})


@require_POST
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk)
    question.delete()
    messages.success(request, "Question deleted (existing answers to it were removed too).")
    return redirect("question-list")


def oneonone_add(request, pk):
    report = get_object_or_404(DirectReport, pk=pk)
    if request.method == "POST":
        form = OneOnOneForm(request.POST)
        if form.is_valid():
            one_on_one = form.save(commit=False)
            one_on_one.report = report
            one_on_one.save()
            formset = ActionItemFormSet(request.POST, instance=one_on_one)
            if formset.is_valid():
                formset.save()
            messages.success(request, "1:1 note added.")
            return redirect("report-detail", pk=report.pk)
        formset = ActionItemFormSet(request.POST)
    else:
        form = OneOnOneForm()
        formset = ActionItemFormSet()
    return render(
        request,
        "reports/oneonone_form.html",
        {"form": form, "formset": formset, "report": report, "title": f"New 1:1 with {report.name}"},
    )


def oneonone_edit(request, pk):
    one_on_one = get_object_or_404(OneOnOne, pk=pk)
    report = one_on_one.report
    if request.method == "POST":
        form = OneOnOneForm(request.POST, instance=one_on_one)
        formset = ActionItemFormSet(request.POST, instance=one_on_one)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "1:1 note updated.")
            return redirect("report-detail", pk=report.pk)
    else:
        form = OneOnOneForm(instance=one_on_one)
        formset = ActionItemFormSet(instance=one_on_one)
    return render(
        request,
        "reports/oneonone_form.html",
        {"form": form, "formset": formset, "report": report, "title": f"Edit 1:1 with {report.name}"},
    )


@require_POST
def oneonone_delete(request, pk):
    one_on_one = get_object_or_404(OneOnOne, pk=pk)
    report_pk = one_on_one.report_id
    one_on_one.delete()
    messages.success(request, "1:1 note deleted.")
    return redirect("report-detail", pk=report_pk)


@require_POST
def action_item_toggle(request, pk):
    item = get_object_or_404(ActionItem, pk=pk)
    item.is_done = not item.is_done
    item.save(update_fields=["is_done"])
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("report-detail", pk=item.one_on_one.report_id)


def ai_settings(request):
    ollama_settings = OllamaSettings.load()

    if request.method == "POST" and "save_connection" in request.POST:
        form = OllamaSettingsForm(request.POST, instance=ollama_settings)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.selected_model = ""
            saved.save()
            messages.success(request, "Connection settings saved.")
        return redirect("ai-settings")

    if request.method == "POST" and "save_model" in request.POST:
        ollama_settings.selected_model = request.POST.get("selected_model", "")
        ollama_settings.save(update_fields=["selected_model", "updated_at"])
        messages.success(request, f"Now using model: {ollama_settings.selected_model}")
        return redirect("ai-settings")

    form = OllamaSettingsForm(instance=ollama_settings)
    models_available = []
    fetch_error = None
    if ollama_settings.host:
        try:
            models_available = list_models(ollama_settings.base_url)
            if not models_available:
                fetch_error = "Connected, but no models are installed on that Ollama instance."
        except OllamaError as exc:
            fetch_error = str(exc)

    return render(
        request,
        "reports/ai_settings.html",
        {
            "form": form,
            "settings": ollama_settings,
            "models_available": models_available,
            "fetch_error": fetch_error,
        },
    )


def todo_list(request):
    show_completed = request.GET.get("show") == "all"
    items = ActionItem.objects.select_related("one_on_one", "one_on_one__report")
    if not show_completed:
        items = items.filter(is_done=False)
    items = items.order_by("one_on_one__date", "created_at")
    return render(
        request,
        "reports/todo_list.html",
        {"items": items, "show_completed": show_completed},
    )
