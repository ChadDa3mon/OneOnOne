from django.contrib import admin

from .models import ActionItem, Answer, DirectReport, OllamaSettings, OneOnOne, Question

admin.site.register(DirectReport)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(OneOnOne)
admin.site.register(ActionItem)
admin.site.register(OllamaSettings)
