from django.urls import path

from . import views

urlpatterns = [
    path("", views.report_list, name="report-list"),
    path("reports/add/", views.report_add, name="report-add"),
    path("reports/<int:pk>/", views.report_detail, name="report-detail"),
    path("reports/<int:pk>/edit/", views.report_edit, name="report-edit"),
    path("reports/<int:pk>/delete/", views.report_delete, name="report-delete"),
    path("reports/<int:pk>/answers/", views.save_answers, name="save-answers"),
    path("reports/<int:pk>/ai-summary/", views.report_ai_summary, name="report-ai-summary"),
    path("reports/<int:pk>/one-on-ones/add/", views.oneonone_add, name="oneonone-add"),
    path("one-on-ones/<int:pk>/edit/", views.oneonone_edit, name="oneonone-edit"),
    path("one-on-ones/<int:pk>/delete/", views.oneonone_delete, name="oneonone-delete"),
    path("action-items/<int:pk>/toggle/", views.action_item_toggle, name="action-item-toggle"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("ai-settings/", views.ai_settings, name="ai-settings"),
    path("questions/", views.question_list, name="question-list"),
    path("questions/<int:pk>/edit/", views.question_edit, name="question-edit"),
    path("questions/<int:pk>/delete/", views.question_delete, name="question-delete"),
]
