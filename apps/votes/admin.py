from django.contrib import admin

from .models import SavedPost, Vote

admin.site.register(Vote)
admin.site.register(SavedPost)
