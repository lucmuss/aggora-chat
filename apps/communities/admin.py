from django.contrib import admin

from .models import Community, CommunityMembership, CommunityRule, CommunityWikiPage, PostFlair, UserFlair


class CommunityRuleInline(admin.TabularInline):
    model = CommunityRule
    extra = 1


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "community_type", "subscriber_count", "created_at")
    search_fields = ("slug", "title", "name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CommunityRuleInline]


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("community__slug", "user__handle", "user__email")


admin.site.register(PostFlair)
admin.site.register(UserFlair)
admin.site.register(CommunityWikiPage)
