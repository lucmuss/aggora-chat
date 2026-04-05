from __future__ import annotations

import json
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags


def absolute_url(path_or_url: str) -> str:
    if not path_or_url:
        return settings.APP_PUBLIC_URL.rstrip("/")
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    base = settings.APP_PUBLIC_URL.rstrip("/") + "/"
    return urljoin(base, path_or_url.lstrip("/"))


def canonical_url_for_request(request, *, allowed_query_params: tuple[str, ...] = ()) -> str:
    pairs: list[tuple[str, str]] = []
    for key in allowed_query_params:
        for value in request.GET.getlist(key):
            if value:
                pairs.append((key, value))
    query_string = urlencode(pairs, doseq=True)
    suffix = f"{request.path}?{query_string}" if query_string else request.path
    return absolute_url(suffix)


def clean_description(text: str | None, *, limit: int = 160) -> str:
    cleaned = " ".join(strip_tags(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}…"


def organization_schema() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": settings.APP_NAME,
        "url": absolute_url("/"),
        "description": settings.APP_TAGLINE,
        "potentialAction": {
            "@type": "SearchAction",
            "target": absolute_url(f"{reverse('search')}?q={{search_term_string}}"),
            "query-input": "required name=search_term_string",
        },
    }


def breadcrumb_schema(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                "item": absolute_url(url),
            }
            for index, (name, url) in enumerate(items, start=1)
        ],
    }


def item_list_schema(name: str, items: list[dict]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": name,
        "itemListOrder": "https://schema.org/ItemListOrderDescending",
        "numberOfItems": len(items),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "url": absolute_url(item["url"]),
                "name": item["name"],
            }
            for index, item in enumerate(items, start=1)
        ],
    }


def collection_page_schema(*, name: str, description: str, url: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": name,
        "description": description,
        "url": absolute_url(url),
        "isPartOf": {
            "@type": "WebSite",
            "name": settings.APP_NAME,
            "url": absolute_url("/"),
        },
    }


def profile_page_schema(*, name: str, description: str, url: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "name": name,
        "description": description,
        "url": absolute_url(url),
    }


def discussion_forum_posting_schema(post, *, comments: list | None = None) -> dict:
    author_name = "Deleted user"
    author_url = None
    if post.author and post.author.handle:
        author_name = post.author.display_name or post.author.handle
        author_url = absolute_url(reverse("profile", kwargs={"handle": post.author.handle}))

    schema = {
        "@context": "https://schema.org",
        "@type": "DiscussionForumPosting",
        "headline": post.title,
        "description": clean_description(post.body_html or post.body_md or post.community.description or post.title),
        "articleBody": clean_description(post.body_html or post.body_md, limit=5000),
        "url": absolute_url(
            reverse(
                "post_detail",
                kwargs={"community_slug": post.community.slug, "post_id": post.id, "slug": post.slug},
            )
        ),
        "datePublished": post.created_at.isoformat(),
        "dateModified": (post.edited_at or post.created_at).isoformat(),
        "author": {"@type": "Person", "name": author_name},
        "isPartOf": {
            "@type": "CollectionPage",
            "name": post.community.title,
            "url": absolute_url(reverse("community_detail", kwargs={"slug": post.community.slug})),
        },
        "commentCount": post.comment_count,
        "interactionStatistic": {
            "@type": "InteractionCounter",
            "interactionType": {"@type": "LikeAction"},
            "userInteractionCount": max(post.score, 0),
        },
    }
    if author_url:
        schema["author"]["url"] = author_url
    if post.image:
        schema["image"] = absolute_url(post.image.url)
    if comments:
        schema["comment"] = [
            {
                "@type": "Comment",
                "text": clean_description(comment.body_html or comment.body_md, limit=1000),
                "dateCreated": comment.created_at.isoformat(),
                "author": {
                    "@type": "Person",
                    "name": (
                        (comment.author.display_name or comment.author.handle)
                        if getattr(comment, "author", None) and getattr(comment.author, "handle", None)
                        else "Deleted user"
                    ),
                },
            }
            for comment in comments[:5]
        ]
    return schema


def serialize_structured_data(*nodes: dict | None) -> str:
    payload = [node for node in nodes if node]
    return json.dumps(payload, ensure_ascii=False)


def default_og_image_url() -> str:
    return absolute_url(static("icons/agora-logo.svg"))
