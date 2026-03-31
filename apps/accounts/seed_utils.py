from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.communities.models import Community, CommunityMembership
from apps.posts.models import Comment, Post
from apps.votes.models import Vote


User = get_user_model()

FREYA_USERS_PATH = Path("/srv/projects/web/freya-online-dating/data/seed/users.json")


def build_unique_handle(base: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_") or "user"
    slug = slug[:30]
    candidate = slug
    suffix = 1
    while User.objects.exclude(handle__isnull=True).filter(handle=candidate).exists():
        suffix_str = f"_{suffix}"
        candidate = f"{slug[: max(1, 30 - len(suffix_str))]}{suffix_str}"
        suffix += 1
    return candidate


def build_unique_username(base: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_") or "user"
    slug = slug[:150]
    candidate = slug
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix_str = f"_{suffix}"
        candidate = f"{slug[: max(1, 150 - len(suffix_str))]}{suffix_str}"
        suffix += 1
    return candidate


def get_seed_users_file(explicit_path: str | None = None) -> Path:
    if explicit_path:
        explicit = Path(explicit_path)
        if explicit.exists():
            return explicit
    configured = getattr(settings, "SEED_USERS_FILE", "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists():
            return configured_path
    if FREYA_USERS_PATH.exists():
        return FREYA_USERS_PATH
    return settings.BASE_DIR / "data" / "seed" / "users.json"


def ensure_account(*, email: str, password: str, handle: str | None = None, display_name: str = "", bio: str = "", is_staff: bool = False, is_superuser: bool = False, is_agent: bool = False, agent_verified: bool = False) -> tuple[User, bool]:
    email = email.strip().lower()
    user = User.objects.filter(email=email).first()
    created = False

    if user is None:
        base_handle = handle or email.split("@", 1)[0]
        handle_value = handle if handle and not User.objects.exclude(email=email).filter(handle=handle).exists() else build_unique_handle(base_handle)
        user = User.objects.create_user(
            username=build_unique_username(handle_value),
            email=email,
            password=password,
            handle=handle_value,
            display_name=display_name,
            bio=bio,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=True,
        )
        created = True
    else:
        changed_fields: list[str] = []
        user.set_password(password)
        changed_fields.append("password")
        if handle and user.handle != handle and not User.objects.exclude(pk=user.pk).filter(handle=handle).exists():
            user.handle = handle
            changed_fields.append("handle")
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            changed_fields.append("display_name")
        if bio and user.bio != bio:
            user.bio = bio
            changed_fields.append("bio")
        if user.is_staff != is_staff:
            user.is_staff = is_staff
            changed_fields.append("is_staff")
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            changed_fields.append("is_superuser")
        if not user.is_active:
            user.is_active = True
            changed_fields.append("is_active")
        if changed_fields:
            user.save(update_fields=sorted(set(changed_fields)))

    if user.is_agent != is_agent or user.agent_verified != agent_verified:
        user.is_agent = is_agent
        user.agent_verified = agent_verified
        user.save(update_fields=["is_agent", "agent_verified"])

    return user, created


def seed_freya_users(*, file_path: str | None = None, create_demo_content: bool = True) -> dict[str, int]:
    seed_file = get_seed_users_file(file_path)
    with seed_file.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    community, _ = Community.objects.get_or_create(
        slug="freya-seed-lounge",
        defaults={
            "name": "Freya Seed Lounge",
            "title": "Freya Seed Lounge",
            "description": "Imported Freya seed personas for Agora development.",
            "sidebar_md": "Shared seed community sourced from the Freya reference project.",
        },
    )

    created_users = 0
    created_posts = 0
    created_comments = 0

    for entry in payload:
        profile = entry.get("profile", {})
        full_name = entry.get("name", "").strip() or profile.get("first_name", "Freya User")
        first_name = profile.get("first_name", full_name.split(" ", 1)[0])
        last_name = profile.get("last_name", "")
        handle_base = f"{first_name}_{last_name}".strip("_") or full_name.replace(" ", "_")
        handle = build_unique_handle(handle_base)
        if User.objects.filter(email=entry["email"].strip().lower()).exists():
            existing = User.objects.get(email=entry["email"].strip().lower())
            handle = existing.handle or handle

        user, created = ensure_account(
            email=entry["email"],
            password=entry["password"],
            handle=handle,
            display_name=full_name,
            bio=profile.get("about", ""),
        )
        if created:
            created_users += 1

        membership, membership_created = CommunityMembership.objects.get_or_create(
            user=user,
            community=community,
            defaults={"role": CommunityMembership.Role.MEMBER},
        )
        if membership_created:
            community.subscriber_count = community.memberships.count()
            community.save(update_fields=["subscriber_count", "sidebar_html"])

        if not create_demo_content:
            continue

        intro_title = f"Intro from {full_name}"
        post, post_created = Post.objects.get_or_create(
            community=community,
            author=user,
            title=intro_title,
            defaults={
                "post_type": Post.PostType.TEXT,
                "body_md": (
                    f"{profile.get('about', '')}\n\n"
                    f"Interests: {', '.join(profile.get('interests', [])) or 'n/a'}\n"
                    f"City: {profile.get('city', 'Unknown')}, {profile.get('country', 'Unknown')}"
                ).strip(),
            },
        )
        if post_created:
            Vote.objects.get_or_create(user=user, post=post, defaults={"value": Vote.VoteType.UPVOTE})
            post.upvote_count = 1
            post.score = 1
            post.hot_score = max(post.hot_score, 1.0)
            post.save(update_fields=["upvote_count", "score", "hot_score", "body_html", "slug"])
            created_posts += 1

        if Comment.objects.filter(post=post, author=user).exists():
            continue

        comment = Comment.objects.create(
            post=post,
            author=user,
            body_md=f"Happy to help test Agora with the Freya seed dataset. Joined on {timezone.now().date().isoformat()}.",
            body_html="",
            depth=0,
            score=1,
            upvote_count=1,
        )
        Vote.objects.get_or_create(user=user, comment=comment, defaults={"value": Vote.VoteType.UPVOTE})
        Post.objects.filter(pk=post.pk).update(comment_count=1)
        created_comments += 1

    moderator = User.objects.filter(handle="ops_moderator").first()
    if moderator:
        CommunityMembership.objects.update_or_create(
            user=moderator,
            community=community,
            defaults={"role": CommunityMembership.Role.MODERATOR},
        )
        community.subscriber_count = community.memberships.count()
        community.save(update_fields=["subscriber_count", "sidebar_html"])

    return {
        "users_created": created_users,
        "posts_created": created_posts,
        "comments_created": created_comments,
        "seed_file": str(seed_file),
        "community_slug": community.slug,
    }
