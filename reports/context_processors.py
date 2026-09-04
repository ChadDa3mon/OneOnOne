from .models import Contact, DirectReport


def quick_note_targets(request):
    """Feeds the global quick-note modal (rendered in base.html on every
    page) the list of people to choose from."""
    return {
        "quick_note_reports": DirectReport.objects.filter(is_active=True).order_by("name"),
        "quick_note_contacts": Contact.objects.order_by("name"),
    }
