from django.contrib import admin

from .models import Ban, CommunityAgentSettings, ModAction, ModMail, ModMailMessage, ModQueueItem, RemovalReason, Report


admin.site.register(ModQueueItem)
admin.site.register(Report)
admin.site.register(ModAction)
admin.site.register(RemovalReason)
admin.site.register(Ban)
admin.site.register(CommunityAgentSettings)
admin.site.register(ModMail)
admin.site.register(ModMailMessage)
