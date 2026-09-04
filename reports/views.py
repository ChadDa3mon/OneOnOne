import logging
import sqlite3
import tempfile

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ActionItemFormSet, ContactForm, DirectReportForm, OllamaSettingsForm, OneOnOneForm, QuestionForm
from .models import ActionItem, Answer, Contact, DirectReport, OllamaSettings, OneOnOne, ONE_ON_ONE_OVERDUE_DAYS, Question
from .ollama import OllamaError, generate, list_models
from .prompt_defaults import (
    DEFAULT_EXTRACT_ACTION_ITEMS_PROMPT,
    DEFAULT_SUMMARY_PROMPT,
    DEFAULT_TALKING_POINTS_PROMPT,
)
from .prompts import (
    build_extract_action_items_prompt,
    build_summary_prompt,
    build_talking_points_prompt,
    parse_action_items,
)

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


def contact_list(request):
    contacts = Contact.objects.all()
    return render(request, "reports/contact_list.html", {"contacts": contacts})


def contact_add(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            messages.success(request, f"Added {contact.name}.")
            return redirect("contact-list")
    else:
        form = ContactForm()
    return render(request, "reports/contact_form.html", {"form": form, "title": "Add contact"})


def contact_edit(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    if request.method == "POST":
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {contact.name}.")
            return redirect("contact-list")
    else:
        form = ContactForm(instance=contact)
    return render(request, "reports/contact_form.html", {"form": form, "title": f"Edit {contact.name}", "contact": contact})


@require_POST
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    name = contact.name
    contact.delete()
    messages.success(request, f"Removed {name}.")
    return redirect("contact-list")


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
                ollama_settings.base_url,
                ollama_settings.selected_model,
                build_summary_prompt(report, ollama_settings.summary_prompt),
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
                ollama_settings.base_url,
                ollama_settings.selected_model,
                build_talking_points_prompt(report, ollama_settings.talking_points_prompt),
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


def _suggest_action_items(request, one_on_one_instance):
    """Handle a 'suggest_action_items' submit: ask Ollama to find action items
    in the notes text and append them as new, unsaved rows onto the action
    item formset data. Nothing is saved here - the caller re-renders the form
    with these rows included so the user can edit/remove them before Save.
    """
    data = request.POST.copy()
    notes_text = data.get("notes", "")
    ollama_settings = OllamaSettings.load()

    if not (ollama_settings.host and ollama_settings.selected_model):
        messages.error(request, "Ollama isn't configured — set a host and model first.")
    elif not notes_text.strip():
        messages.error(request, "Add some notes first, then suggest action items from them.")
    else:
        try:
            raw = generate(
                ollama_settings.base_url,
                ollama_settings.selected_model,
                build_extract_action_items_prompt(notes_text, ollama_settings.extract_action_items_prompt),
            )
            suggested = parse_action_items(raw)
        except OllamaError as exc:
            logger.warning("Action item extraction failed: %s", exc)
            messages.error(request, str(exc))
        except Exception:
            logger.exception("Unexpected error extracting action items")
            messages.error(request, "Unexpected error while finding action items — check the server logs.")
        else:
            if suggested:
                prefix = ActionItemFormSet.get_default_prefix()
                total_key = f"{prefix}-TOTAL_FORMS"
                total = int(data.get(total_key, 0))
                for text in suggested:
                    data[f"{prefix}-{total}-description"] = text
                    data[f"{prefix}-{total}-id"] = ""
                    total += 1
                data[total_key] = str(total)
                messages.success(
                    request, f"Found {len(suggested)} possible action item(s) below — review, edit, or remove before saving."
                )
            else:
                messages.success(request, "No action items found in the notes.")

    form = OneOnOneForm(data, instance=one_on_one_instance)
    formset = ActionItemFormSet(data, instance=one_on_one_instance)
    return form, formset


def oneonone_add(request, pk):
    report = get_object_or_404(DirectReport, pk=pk)
    if request.method == "POST":
        if "suggest_action_items" in request.POST:
            form, formset = _suggest_action_items(request, None)
            return render(
                request,
                "reports/oneonone_form.html",
                {"form": form, "formset": formset, "report": report, "title": f"New 1:1 with {report.name}"},
            )

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
        if "suggest_action_items" in request.POST:
            form, formset = _suggest_action_items(request, one_on_one)
            return render(
                request,
                "reports/oneonone_form.html",
                {"form": form, "formset": formset, "report": report, "title": f"Edit 1:1 with {report.name}"},
            )

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

    if request.headers.get("HX-Request"):
        if request.POST.get("variant") == "dashboard":
            show_completed = request.POST.get("show_completed") == "1"
            if item.is_done and not show_completed:
                # Hidden-completed view: toggling an item done removes it
                # from view immediately rather than leaving a checked,
                # about-to-be-filtered-out row until the next full load.
                return HttpResponse("")
            return render(request, "reports/_action_item_dashboard.html", {"item": item, "show_completed": show_completed})
        return render(request, "reports/_action_item_plain.html", {"item": item})

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

    if request.method == "POST" and "save_summary_prompt" in request.POST:
        ollama_settings.summary_prompt = request.POST.get("summary_prompt", "").strip() or DEFAULT_SUMMARY_PROMPT
        ollama_settings.save(update_fields=["summary_prompt", "updated_at"])
        messages.success(request, "Summary prompt saved.")
        return redirect("ai-settings")

    if request.method == "POST" and "reset_summary_prompt" in request.POST:
        ollama_settings.summary_prompt = DEFAULT_SUMMARY_PROMPT
        ollama_settings.save(update_fields=["summary_prompt", "updated_at"])
        messages.success(request, "Summary prompt reset to default.")
        return redirect("ai-settings")

    if request.method == "POST" and "save_talking_points_prompt" in request.POST:
        ollama_settings.talking_points_prompt = (
            request.POST.get("talking_points_prompt", "").strip() or DEFAULT_TALKING_POINTS_PROMPT
        )
        ollama_settings.save(update_fields=["talking_points_prompt", "updated_at"])
        messages.success(request, "Talking points prompt saved.")
        return redirect("ai-settings")

    if request.method == "POST" and "reset_talking_points_prompt" in request.POST:
        ollama_settings.talking_points_prompt = DEFAULT_TALKING_POINTS_PROMPT
        ollama_settings.save(update_fields=["talking_points_prompt", "updated_at"])
        messages.success(request, "Talking points prompt reset to default.")
        return redirect("ai-settings")

    if request.method == "POST" and "save_extract_action_items_prompt" in request.POST:
        ollama_settings.extract_action_items_prompt = (
            request.POST.get("extract_action_items_prompt", "").strip() or DEFAULT_EXTRACT_ACTION_ITEMS_PROMPT
        )
        ollama_settings.save(update_fields=["extract_action_items_prompt", "updated_at"])
        messages.success(request, "Action item extraction prompt saved.")
        return redirect("ai-settings")

    if request.method == "POST" and "reset_extract_action_items_prompt" in request.POST:
        ollama_settings.extract_action_items_prompt = DEFAULT_EXTRACT_ACTION_ITEMS_PROMPT
        ollama_settings.save(update_fields=["extract_action_items_prompt", "updated_at"])
        messages.success(request, "Action item extraction prompt reset to default.")
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


def dashboard(request):
    show_completed = request.GET.get("show") == "all"
    items = ActionItem.objects.select_related("one_on_one", "one_on_one__report")
    if not show_completed:
        items = items.filter(is_done=False)
    items = items.order_by("one_on_one__date", "created_at")

    overdue_reports = [r for r in DirectReport.objects.filter(is_active=True) if r.is_overdue_for_one_on_one]
    overdue_reports.sort(key=lambda r: (r.last_one_on_one_date is not None, r.last_one_on_one_date))

    return render(
        request,
        "reports/dashboard.html",
        {
            "items": items,
            "show_completed": show_completed,
            "overdue_reports": overdue_reports,
            "overdue_days_threshold": ONE_ON_ONE_OVERDUE_DAYS,
        },
    )


def backup_download(request):
    db_settings = settings.DATABASES["default"]
    if db_settings["ENGINE"] != "django.db.backends.sqlite3":
        return HttpResponse("Backups are only supported for the SQLite database.", status=501)

    filename = f"manager-backup-{timezone.now().strftime('%Y-%m-%d_%H%M%S')}.sqlite3"

    # Use sqlite3's own backup API rather than reading the live file directly,
    # so a concurrent write can't hand back a torn/inconsistent copy.
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3")
    source_conn = sqlite3.connect(str(db_settings["NAME"]))
    dest_conn = sqlite3.connect(tmp.name)
    with dest_conn:
        source_conn.backup(dest_conn)
    source_conn.close()
    dest_conn.close()
    tmp.seek(0)

    logger.info("Backup downloaded: %s", filename)
    return FileResponse(tmp, as_attachment=True, filename=filename, content_type="application/x-sqlite3")
