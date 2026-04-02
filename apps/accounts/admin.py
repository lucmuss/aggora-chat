from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AgentIdentityProvider, Notification, User, UserBadge


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Agora Profile",
            {
                "fields": (
                    "handle",
                    "display_name",
                    "bio",
                    "avatar",
                    "post_karma",
                    "comment_karma",
                    "is_agent",
                    "agent_verified",
                    "agent_provider_issuer",
                    "onboarding_completed",
                    "onboarding_completed_at",
                )
            },
        ),
    )
    list_display = ("email", "username", "handle", "is_agent", "agent_verified", "is_staff")
    list_filter = ("is_agent", "agent_verified", "is_staff", "is_superuser")
    search_fields = ("email", "username", "handle")
    actions = ("verify_agent", "revoke_agent")

    @admin.action(description="Verify selected agent accounts")
    def verify_agent(self, request, queryset):
        queryset.filter(is_agent=True).update(agent_verified=True)

    @admin.action(description="Revoke verification from selected agent accounts")
    def revoke_agent(self, request, queryset):
        queryset.filter(is_agent=True).update(agent_verified=False)


@admin.register(AgentIdentityProvider)
class AgentIdentityProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "issuer_url", "status", "owner_organization", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "issuer_url", "owner_organization")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "notification_type", "community", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")
    search_fields = ("user__email", "user__handle", "message")


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "title", "awarded_at")
    list_filter = ("code",)
    search_fields = ("user__email", "user__handle", "title")
