from __future__ import annotations

from apps.accounts.models import User

from .models import Community, CommunityMembership, CommunityWikiPage


def submit_community(creator: User, form) -> Community:
    """Service to create a new community and assign the owner role."""
    community = form.save(commit=False)
    community.creator = creator
    community.save()
    
    CommunityMembership.objects.create(
        user=creator,
        community=community,
        role=CommunityMembership.Role.OWNER,
    )
    community.subscriber_count = community.memberships.count()
    community.save(update_fields=["subscriber_count"])
    return community


def toggle_user_membership(user: User, community: Community) -> bool:
    """
    Toggles membership for a user in a community.
    Returns: bool - True if the user successfully joined, False if they successfully left.
    Raises: ValueError if the owner attempts to leave.
    """
    membership, created = CommunityMembership.objects.get_or_create(
        user=user,
        community=community,
        defaults={"role": CommunityMembership.Role.MEMBER},
    )
    if not created:
        if membership.role == CommunityMembership.Role.OWNER:
            raise ValueError("Owners cannot leave their own community.")
        membership.delete()
        joined = False
    else:
        joined = True

    community.subscriber_count = community.memberships.count()
    community.save(update_fields=["subscriber_count"])
    return joined


def save_wiki_page(user: User, community: Community, form) -> CommunityWikiPage:
    """Saves a community Wiki page and records the updater."""
    page = form.save(commit=False)
    page.community = community
    page.updated_by = user
    page.save()
    return page
