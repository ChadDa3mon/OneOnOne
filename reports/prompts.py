import re
from string import Template

from .models import ActionItem, Question
from .prompt_defaults import (
    DEFAULT_EXTRACT_ACTION_ITEMS_PROMPT,
    DEFAULT_SUMMARY_PROMPT,
    DEFAULT_TALKING_POINTS_PROMPT,
)

_LEADING_BULLET_RE = re.compile(r"^[\-\*•]\s*|^\d+[\.\)]\s*")


def _qa_lines(report):
    answers = report.answers_by_question()
    lines = []
    for question in Question.objects.all():
        answer = answers.get(question.id)
        if answer and answer.text.strip():
            lines.append(f"- Q: {question.text}\n  A: {answer.text.strip()}")
    return lines or ["(No profile questions answered yet.)"]


def _open_action_item_lines(report):
    items = ActionItem.objects.filter(one_on_one__report=report, is_done=False).select_related("one_on_one")
    lines = [f"- {item.description} (from 1:1 on {item.one_on_one.date})" for item in items]
    return lines or ["(No open action items.)"]


def _context(report):
    who = report.name + (f", {report.title}" if report.title else "")
    recent_meetings = list(report.one_on_ones.all()[:3])
    note_lines = [f"- {m.date}: {m.notes.strip()}" for m in recent_meetings if m.notes.strip()]
    return {
        "who": who,
        "qa": "\n".join(_qa_lines(report)),
        "action_items": "\n".join(_open_action_item_lines(report)),
        "notes": "\n".join(note_lines or ["(No 1:1 notes yet.)"]),
    }


def render_prompt(template_text, report):
    """Fill a user-editable $-placeholder template with this report's data.

    Uses safe_substitute so a malformed or unrecognized placeholder in a
    user-edited template is left as literal text instead of raising.
    """
    return Template(template_text).safe_substitute(_context(report))


def build_summary_prompt(report, template_text=None):
    return render_prompt(template_text or DEFAULT_SUMMARY_PROMPT, report)


def build_talking_points_prompt(report, template_text=None):
    return render_prompt(template_text or DEFAULT_TALKING_POINTS_PROMPT, report)


def build_extract_action_items_prompt(notes_text, template_text=None):
    template = template_text or DEFAULT_EXTRACT_ACTION_ITEMS_PROMPT
    return Template(template).safe_substitute({"notes": notes_text})


def parse_action_items(raw_text, limit=10):
    """Turn a model's line-per-item response into a clean list of item strings.

    Defensively strips bullet/numbering markers even though the prompt asks
    the model not to include them, since smaller local models don't always
    follow that instruction.
    """
    items = []
    for line in raw_text.splitlines():
        line = _LEADING_BULLET_RE.sub("", line.strip()).strip()
        if not line or line.upper() == "NONE":
            continue
        items.append(line)
        if len(items) >= limit:
            break
    return items
