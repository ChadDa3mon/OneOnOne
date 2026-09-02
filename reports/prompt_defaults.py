# Default prompt templates for the AI Summary and Talking Points features.
# Editable per-instance via the AI Settings page (stored on OllamaSettings);
# these are just the starting point for a fresh install.
#
# Available placeholders: $who, $qa, $action_items, $notes

DEFAULT_SUMMARY_PROMPT = """You are helping an engineering manager get up to speed on their direct report, $who.
Below are the direct report's profile answers and their currently open action items from past 1:1s.
Write a 1 to 3 paragraph summary covering what the manager most needs to know: this person's motivations, working style, growth areas, and anything currently outstanding. Synthesize the information rather than repeating it verbatim. Do not include a preamble or heading, just the summary.

Profile Q&A:
$qa

Open action items:
$action_items"""

DEFAULT_TALKING_POINTS_PROMPT = """You are helping an engineering manager prepare for their next 1:1 with $who.
Based on the context below, suggest 3 to 6 specific talking points or questions the manager should bring to the conversation. Return them as a short bulleted list with no preamble or heading.

Profile Q&A:
$qa

Open action items:
$action_items

Notes from recent 1:1s (most recent first):
$notes"""
