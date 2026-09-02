from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ActionItemFormSet, DirectReportForm, OneOnOneForm, QuestionForm
from .models import ActionItem, Answer, DirectReport, OneOnOne, Question


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
    return render(
        request,
        "reports/report_detail.html",
        {
            "report": report,
            "answer_rows": answer_rows,
            "one_on_ones": one_on_ones,
        },
    )


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
