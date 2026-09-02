from .models import ActionItem, Question


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


def build_summary_prompt(report):
    who = report.name + (f", {report.title}" if report.title else "")
    lines = [
        f"You are helping an engineering manager get up to speed on their direct report, {who}.",
        "Below are the direct report's profile answers and their currently open action items from past 1:1s.",
        "Write a 1 to 3 paragraph summary covering what the manager most needs to know: this "
        "person's motivations, working style, growth areas, and anything currently outstanding. "
        "Synthesize the information rather than repeating it verbatim. Do not include a preamble "
        "or heading, just the summary.",
        "",
        "Profile Q&A:",
        *_qa_lines(report),
        "",
        "Open action items:",
        *_open_action_item_lines(report),
    ]
    return "\n".join(lines)


def build_talking_points_prompt(report):
    who = report.name + (f", {report.title}" if report.title else "")
    recent_meetings = list(report.one_on_ones.all()[:3])
    note_lines = [f"- {m.date}: {m.notes.strip()}" for m in recent_meetings if m.notes.strip()]

    lines = [
        f"You are helping an engineering manager prepare for their next 1:1 with {who}.",
        "Based on the context below, suggest 3 to 6 specific talking points or questions the "
        "manager should bring to the conversation. Return them as a short bulleted list with no "
        "preamble or heading.",
        "",
        "Profile Q&A:",
        *_qa_lines(report),
        "",
        "Open action items:",
        *_open_action_item_lines(report),
        "",
        "Notes from recent 1:1s (most recent first):",
        *(note_lines or ["(No 1:1 notes yet.)"]),
    ]
    return "\n".join(lines)
