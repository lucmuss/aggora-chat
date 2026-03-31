from apps.communities.models import CommunityMembership


class ModPermission:
    MANAGE_POSTS = "manage_posts"
    MANAGE_USERS = "manage_users"
    VIEW_MOD_LOG = "view_mod_log"
    VIEW_MOD_QUEUE = "view_mod_queue"
    MANAGE_SETTINGS = "manage_settings"
    MOD_MAIL = "mod_mail"


ROLE_PERMISSIONS = {
    CommunityMembership.Role.OWNER: {
        ModPermission.MANAGE_POSTS,
        ModPermission.MANAGE_USERS,
        ModPermission.VIEW_MOD_LOG,
        ModPermission.VIEW_MOD_QUEUE,
        ModPermission.MANAGE_SETTINGS,
        ModPermission.MOD_MAIL,
    },
    CommunityMembership.Role.MODERATOR: {
        ModPermission.MANAGE_POSTS,
        ModPermission.MANAGE_USERS,
        ModPermission.VIEW_MOD_LOG,
        ModPermission.VIEW_MOD_QUEUE,
        ModPermission.MANAGE_SETTINGS,
        ModPermission.MOD_MAIL,
    },
    CommunityMembership.Role.AGENT_MOD: {
        ModPermission.MANAGE_POSTS,
        ModPermission.VIEW_MOD_QUEUE,
    },
}


def has_mod_permission(user, community, permission):
    membership = CommunityMembership.objects.filter(user=user, community=community).first()
    if not membership:
        return False
    return permission in ROLE_PERMISSIONS.get(membership.role, set())
