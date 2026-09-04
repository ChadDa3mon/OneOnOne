from django.contrib import admin

from .models import ActionItem, Answer, Contact, DirectReport, OllamaSettings, OneOnOne, Question, QuickNote, Resource

admin.site.register(DirectReport)
admin.site.register(Contact)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(OneOnOne)
admin.site.register(ActionItem)
admin.site.register(QuickNote)
admin.site.register(Resource)
admin.site.register(OllamaSettings)
