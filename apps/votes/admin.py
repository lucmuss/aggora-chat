from django.contrib import admin

from .models import ContentAward, SavedPost, Vote

admin.site.register(Vote)
admin.site.register(SavedPost)
admin.site.register(ContentAward)
