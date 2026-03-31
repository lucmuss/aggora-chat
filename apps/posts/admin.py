from django.contrib import admin

from .models import Comment, Poll, PollOption, PollVote, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "community", "author", "post_type", "score", "comment_count", "created_at")
    list_filter = ("post_type", "is_removed", "community")
    search_fields = ("title", "body_md", "author__handle")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "score", "depth", "created_at")
    list_filter = ("is_removed",)
    search_fields = ("body_md", "author__handle")


admin.site.register(Poll)
admin.site.register(PollOption)
admin.site.register(PollVote)
