from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AgentIdentityProvider, User


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
