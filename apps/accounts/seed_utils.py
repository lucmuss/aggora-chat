from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.communities.models import Community, CommunityChallenge, CommunityMembership, CommunityRule, CommunityWikiPage, PostFlair
from apps.posts.models import Comment, Poll, PollOption, Post
from apps.votes.models import SavedPost, Vote


User = get_user_model()


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
    return settings.BASE_DIR / "data" / "seed" / "users.json"


def get_seed_admins_file(explicit_path: str | None = None) -> Path:
    if explicit_path:
        explicit = Path(explicit_path)
        if explicit.exists():
            return explicit
    configured = getattr(settings, "SEED_ADMINS_FILE", "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists():
            return configured_path
    return settings.BASE_DIR / "data" / "seed" / "admins.json"


def get_seed_communities_file(explicit_path: str | None = None) -> Path:
    if explicit_path:
        explicit = Path(explicit_path)
        if explicit.exists():
            return explicit
    configured = getattr(settings, "SEED_COMMUNITIES_FILE", "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists():
            return configured_path
    return settings.BASE_DIR / "data" / "seed" / "communities.json"


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


def _load_seed_payload(seed_file: Path) -> list[dict]:
    with seed_file.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _ensure_seed_community(owner: User | None = None) -> Community:
    community, _ = Community.objects.get_or_create(
        slug="freya-seed-lounge",
        defaults={
            "name": "Freya Seed Lounge",
            "title": "Freya Seed Lounge",
            "description": "Curated seed community for Agora development, QA, and screenshots.",
            "sidebar_md": "A seeded Agora community with demo users, admins, and starter content.",
            "landing_intro_md": "Welcome to the seeded demo community used for local development and onboarding tests.",
            "faq_md": "## FAQ\n\n### What is this?\nA safe demo space for local testing.\n\n### Can I post here?\nYes, this community is intended for local smoke tests and screenshots.",
            "best_of_md": "- Demo onboarding threads\n- Example invite flows\n- Suggested communities and challenge previews",
        },
    )
    if owner and community.creator_id != owner.pk:
        community.creator = owner
        community.save(update_fields=["creator", "sidebar_html", "landing_intro_html", "faq_html", "best_of_html"])
    return community


def _get_user_by_email(users_by_email: dict[str, User], email: str | None) -> User | None:
    if not email:
        return None
    return users_by_email.get(email.strip().lower())


def _sync_community_metadata(community: Community, entry: dict, creator: User | None):
    updates = {
        "name": entry.get("name", community.name),
        "title": entry.get("title", community.title),
        "description": entry.get("description", community.description),
        "seo_description": entry.get("seo_description", community.seo_description),
        "sidebar_md": entry.get("sidebar_md", community.sidebar_md),
        "landing_intro_md": entry.get("landing_intro_md", community.landing_intro_md),
        "faq_md": entry.get("faq_md", community.faq_md),
        "best_of_md": entry.get("best_of_md", community.best_of_md),
        "community_type": entry.get("community_type", community.community_type),
        "allow_text_posts": bool(entry.get("allow_text_posts", community.allow_text_posts)),
        "allow_link_posts": bool(entry.get("allow_link_posts", community.allow_link_posts)),
        "allow_image_posts": bool(entry.get("allow_image_posts", community.allow_image_posts)),
        "allow_polls": bool(entry.get("allow_polls", community.allow_polls)),
        "creator": creator or community.creator,
    }
    changed = False
    for field, value in updates.items():
        if getattr(community, field) != value:
            setattr(community, field, value)
            changed = True
    if changed:
        community.save()


def _sync_rules(community: Community, rules: list[dict]):
    seen_titles: set[str] = set()
    for rule in rules:
        title = rule.get("title", "").strip()
        if not title:
            continue
        seen_titles.add(title)
        CommunityRule.objects.update_or_create(
            community=community,
            title=title,
            defaults={
                "order": int(rule.get("order", 0)),
                "description": rule.get("description", "").strip(),
            },
        )


def _sync_flairs(community: Community, flairs: list[dict]):
    for flair in flairs:
        text = flair.get("text", "").strip()
        if not text:
            continue
        PostFlair.objects.update_or_create(
            community=community,
            text=text,
            defaults={
                "css_class": flair.get("css_class", "").strip(),
                "bg_color": flair.get("bg_color", "#6B7280").strip() or "#6B7280",
            },
        )


def _sync_wiki_pages(community: Community, pages: list[dict], updated_by: User | None):
    for page in pages:
        slug = page.get("slug", "").strip()
        if not slug:
            continue
        CommunityWikiPage.objects.update_or_create(
            community=community,
            slug=slug,
            defaults={
                "title": page.get("title", slug.replace("-", " ").title()).strip(),
                "body_md": page.get("body_md", "").strip(),
                "updated_by": updated_by,
            },
        )


def _sync_challenge(community: Community, challenge_entry: dict | None, created_by: User | None):
    if not challenge_entry:
        return
    now = timezone.now()
    starts_at = now - timezone.timedelta(days=1)
    ends_at = now + timezone.timedelta(days=14)
    CommunityChallenge.objects.update_or_create(
        community=community,
        title=challenge_entry.get("title", "Seed Challenge").strip(),
        defaults={
            "created_by": created_by,
            "prompt_md": challenge_entry.get("prompt_md", "").strip(),
            "share_text": challenge_entry.get("share_text", "").strip(),
            "starts_at": starts_at,
            "ends_at": ends_at,
            "is_featured": True,
        },
    )


def _apply_post_votes(post: Post, users_by_email: dict[str, User], upvoters: list[str], downvoters: list[str] | None = None):
    upvote_count = 0
    downvote_count = 0
    for email in upvoters or []:
        voter = _get_user_by_email(users_by_email, email)
        if not voter:
            continue
        Vote.objects.update_or_create(
            user=voter,
            post=post,
            defaults={"value": Vote.VoteType.UPVOTE},
        )
        upvote_count += 1
    for email in downvoters or []:
        voter = _get_user_by_email(users_by_email, email)
        if not voter:
            continue
        Vote.objects.update_or_create(
            user=voter,
            post=post,
            defaults={"value": Vote.VoteType.DOWNVOTE},
        )
        downvote_count += 1
    score = upvote_count - downvote_count
    hot_score = max(float(score), 0.0)
    Post.objects.filter(pk=post.pk).update(
        upvote_count=upvote_count,
        downvote_count=downvote_count,
        score=score,
        hot_score=hot_score,
    )


def _apply_comment_votes(comment: Comment, users_by_email: dict[str, User], upvoters: list[str] | None = None):
    upvote_count = 0
    for email in upvoters or []:
        voter = _get_user_by_email(users_by_email, email)
        if not voter:
            continue
        Vote.objects.update_or_create(
            user=voter,
            comment=comment,
            defaults={"value": Vote.VoteType.UPVOTE},
        )
        upvote_count += 1
    Comment.objects.filter(pk=comment.pk).update(
        upvote_count=upvote_count,
        downvote_count=0,
        score=upvote_count,
    )


def _create_or_update_post(*, community: Community, users_by_email: dict[str, User], post_entry: dict) -> tuple[Post | None, bool]:
    author = _get_user_by_email(users_by_email, post_entry.get("author_email"))
    if not author:
        return None, False

    flair = None
    flair_text = post_entry.get("flair", "").strip()
    if flair_text:
        flair = PostFlair.objects.filter(community=community, text=flair_text).first()

    defaults = {
        "post_type": post_entry.get("post_type", Post.PostType.TEXT),
        "body_md": post_entry.get("body_md", "").strip(),
        "url": post_entry.get("url", "").strip(),
        "author": author,
        "flair": flair,
        "is_spoiler": bool(post_entry.get("is_spoiler", False)),
        "is_nsfw": bool(post_entry.get("is_nsfw", False)),
    }
    post, created = Post.objects.get_or_create(
        community=community,
        author=author,
        title=post_entry.get("title", "").strip(),
        defaults=defaults,
    )
    changed_fields: list[str] = []
    for field, value in defaults.items():
        if getattr(post, field) != value:
            setattr(post, field, value)
            changed_fields.append(field)
    if changed_fields:
        post.save(update_fields=changed_fields + ["body_html"])

    poll_entry = post_entry.get("poll") or {}
    if post.post_type == Post.PostType.POLL and poll_entry:
        poll, _ = Poll.objects.get_or_create(
            post=post,
            defaults={
                "multiple_choice": bool(poll_entry.get("multiple_choice", False)),
                "closes_at": timezone.now() + timezone.timedelta(days=7),
            },
        )
        if poll.multiple_choice != bool(poll_entry.get("multiple_choice", False)):
            poll.multiple_choice = bool(poll_entry.get("multiple_choice", False))
            poll.save(update_fields=["multiple_choice"])
        for position, label in enumerate(poll_entry.get("options", []), start=1):
            PollOption.objects.get_or_create(
                poll=poll,
                label=label.strip(),
                defaults={"position": position},
            )

    comment_count = 0
    for comment_entry in post_entry.get("comments", []):
        comment_author = _get_user_by_email(users_by_email, comment_entry.get("author_email"))
        if not comment_author:
            continue
        comment, _ = Comment.objects.get_or_create(
            post=post,
            author=comment_author,
            body_md=comment_entry.get("body_md", "").strip(),
            defaults={
                "body_html": "",
                "depth": 0,
            },
        )
        _apply_comment_votes(comment, users_by_email, comment_entry.get("upvoters", []))
        comment_count += 1
    Post.objects.filter(pk=post.pk).update(comment_count=comment_count)

    _apply_post_votes(
        post,
        users_by_email,
        post_entry.get("upvoters", []),
        post_entry.get("downvoters", []),
    )

    for email in post_entry.get("saved_by", []):
        saver = _get_user_by_email(users_by_email, email)
        if saver:
            SavedPost.objects.get_or_create(user=saver, post=post)

    return post, created


def seed_demo_accounts(
    *,
    users_file_path: str | None = None,
    admins_file_path: str | None = None,
    communities_file_path: str | None = None,
    create_demo_content: bool = True,
) -> dict[str, int | str]:
    user_seed_file = get_seed_users_file(users_file_path)
    admin_seed_file = get_seed_admins_file(admins_file_path)
    communities_seed_file = get_seed_communities_file(communities_file_path)
    user_payload = _load_seed_payload(user_seed_file)
    admin_payload = _load_seed_payload(admin_seed_file) if admin_seed_file.exists() else []
    communities_payload = _load_seed_payload(communities_seed_file) if communities_seed_file.exists() else []

    created_users = 0
    created_admins = 0
    created_posts = 0
    created_comments = 0
    created_communities = 0

    admin_users: list[tuple[User, dict]] = []
    users_by_email: dict[str, User] = {}
    for entry in admin_payload:
        user, created = ensure_account(
            email=entry["email"],
            password=entry["password"],
            handle=entry.get("handle"),
            display_name=entry.get("display_name", ""),
            bio=entry.get("bio", ""),
            is_staff=bool(entry.get("is_staff", False)),
            is_superuser=bool(entry.get("is_superuser", False)),
        )
        admin_users.append((user, entry))
        users_by_email[user.email] = user
        if created:
            created_admins += 1

    owner_user = next((user for user, entry in admin_users if entry.get("community_role") == CommunityMembership.Role.OWNER), None)

    for entry in user_payload:
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
        users_by_email[user.email] = user

    if not communities_payload:
        communities_payload = [
            {
                "slug": "freya-seed-lounge",
                "name": "Freya Seed Lounge",
                "title": "Freya Seed Lounge",
            }
        ]

    primary_slug = communities_payload[0].get("slug", "freya-seed-lounge")
    for community_index, community_entry in enumerate(communities_payload):
        slug = community_entry.get("slug", "").strip()
        if not slug:
            continue
        community, community_created = Community.objects.get_or_create(
            slug=slug,
            defaults={
                "name": community_entry.get("name", slug.replace("-", " ").title()),
                "title": community_entry.get("title", slug.replace("-", " ").title()),
                "description": community_entry.get("description", ""),
                "creator": owner_user,
            },
        )
        if community_created:
            created_communities += 1

        if community_index == 0 and community.slug == "freya-seed-lounge":
            seeded = _ensure_seed_community(owner_user)
            if seeded.pk != community.pk:
                community = seeded

        _sync_community_metadata(community, community_entry, owner_user)

        for user, entry in admin_users:
            community_role = entry.get("community_role")
            if community_role in {
                CommunityMembership.Role.OWNER,
                CommunityMembership.Role.MODERATOR,
                CommunityMembership.Role.MEMBER,
                CommunityMembership.Role.AGENT_MOD,
            }:
                CommunityMembership.objects.update_or_create(
                    user=user,
                    community=community,
                    defaults={"role": community_role},
                )

        for email, user in users_by_email.items():
            if user.is_staff:
                continue
            CommunityMembership.objects.get_or_create(
                user=user,
                community=community,
                defaults={"role": CommunityMembership.Role.MEMBER},
            )

        _sync_rules(community, community_entry.get("rules", []))
        _sync_flairs(community, community_entry.get("flairs", []))
        _sync_wiki_pages(community, community_entry.get("wiki_pages", []), owner_user)
        _sync_challenge(community, community_entry.get("challenge"), owner_user)

        if not create_demo_content:
            continue

        for post_entry in community_entry.get("posts", []):
            _, post_created = _create_or_update_post(
                community=community,
                users_by_email=users_by_email,
                post_entry=post_entry,
            )
            if post_created:
                created_posts += 1
            created_comments += len(post_entry.get("comments", []))

        for email, user in users_by_email.items():
            if user.is_staff:
                continue
            profile = {
                "about": user.bio,
                "city": community_entry.get("title", community.title),
                "country": "Seeded",
                "interests": ["Agora", "Community building", "QA"],
            }
            intro_title = f"Intro from {user.display_name or user.handle or email.split('@', 1)[0]}"
            intro_post, intro_created = Post.objects.get_or_create(
                community=community,
                author=user,
                title=intro_title,
                defaults={
                    "post_type": Post.PostType.TEXT,
                    "body_md": (
                        f"{profile.get('about', '')}\n\n"
                        f"Interests: {', '.join(profile.get('interests', [])) or 'n/a'}\n"
                        f"Context: testing {community.title}"
                    ).strip(),
                },
            )
            if intro_created:
                created_posts += 1
                Vote.objects.get_or_create(user=user, post=intro_post, defaults={"value": Vote.VoteType.UPVOTE})
                Post.objects.filter(pk=intro_post.pk).update(
                    upvote_count=1,
                    score=1,
                    hot_score=1.0,
                )
            comment, comment_created = Comment.objects.get_or_create(
                post=intro_post,
                author=user,
                body_md=f"Happy to help test Agora with the richer seed dataset on {timezone.now().date().isoformat()}.",
                defaults={"body_html": "", "depth": 0},
            )
            if comment_created:
                Vote.objects.get_or_create(user=user, comment=comment, defaults={"value": Vote.VoteType.UPVOTE})
                Comment.objects.filter(pk=comment.pk).update(score=1, upvote_count=1)
                Post.objects.filter(pk=intro_post.pk).update(comment_count=intro_post.comments.count())
                created_comments += 1

        community.subscriber_count = community.memberships.count()
        community.save(update_fields=["subscriber_count", "sidebar_html", "landing_intro_html", "faq_html", "best_of_html"])

    return {
        "users_created": created_users,
        "admins_created": created_admins,
        "posts_created": created_posts,
        "comments_created": created_comments,
        "communities_created": created_communities,
        "seed_file": str(user_seed_file),
        "admins_file": str(admin_seed_file),
        "communities_file": str(communities_seed_file),
        "community_slug": primary_slug,
    }
