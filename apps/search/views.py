from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

from apps.accounts.regions import COUNTRY_CODE_BY_NAME
from apps.common.seo import (
    breadcrumb_schema,
    canonical_url_for_request,
    clean_description,
    collection_page_schema,
    item_list_schema,
    serialize_structured_data,
)
from apps.accounts.models import User
from apps.communities.models import Community
from apps.communities.services import can_view_community
from apps.posts.services import annotate_posts_with_user_state, enrich_posts_for_display

from .backends import get_discovery_backend, parse_search_query

RECENT_SEARCH_LIMIT = 5
QUICK_RESULT_LIMIT = 6


def _recent_searches(request):
    return list(request.session.get("recent_searches", []))


def _store_recent_search(request, query: str):
    query = query.strip()
    if len(query) < 2:
        return
    searches = [item for item in _recent_searches(request) if item.lower() != query.lower()]
    searches.insert(0, query)
    request.session["recent_searches"] = searches[:RECENT_SEARCH_LIMIT]
    request.session.modified = True


def _recent_communities_for_user(user, limit=4):
    if user is None or not user.is_authenticated:
        return []
    return list(
        Community.objects.filter(memberships__user=user)
        .distinct()
        .order_by("-memberships__joined_at", "title")[:limit]
    )


def _quick_actions_for_user(user):
    actions = [
        {"title": "Browse communities", "subtitle": "Jump into discovery", "url": reverse("community_discovery")},
        {"title": "Search everything", "subtitle": "Open the full search page", "url": reverse("search")},
    ]
    if user is not None and user.is_authenticated:
        profile_handle = user.handle or "me"
        actions = [
            {"title": "New community", "subtitle": "Create a fresh room", "url": reverse("create_community")},
            {"title": "Notifications", "subtitle": "Open your inbox", "url": reverse("notifications")},
            {"title": "Referral hub", "subtitle": "Invite people and track joins", "url": reverse("account_referrals")},
            {"title": "Saved posts", "subtitle": "Open your reading queue", "url": f"{reverse('profile', kwargs={'handle': profile_handle})}?tab=saved"},
            {"title": "Profile", "subtitle": "View your public profile", "url": reverse("profile", kwargs={"handle": profile_handle})},
            {"title": "Settings", "subtitle": "Edit profile, notifications, and security", "url": reverse("account_settings")},
        ] + actions
    return actions


def _search_best_match(query, posts, communities, users):
    normalized = query.strip().lower()
    for community in communities:
        if normalized in {community.slug.lower(), community.name.lower(), community.title.lower()}:
            return {
                "kind": "community",
                "title": community.title or community.name,
                "subtitle": f"c/{community.slug}",
                "description": community.description or "Open this community and jump into the conversation.",
                "url": reverse("community_detail", kwargs={"slug": community.slug}),
            }
    for user in users:
        if normalized in {
            (user.handle or "").lower(),
            (user.display_name or "").lower(),
        }:
            return {
                "kind": "person",
                "title": user.display_name or user.handle,
                "subtitle": f"u/{user.handle}",
                "description": user.bio or "Visit this profile and see what they are posting.",
                "url": reverse("profile", kwargs={"handle": user.handle}),
            }
    if posts:
        top_post = posts[0]
        return {
            "kind": "post",
            "title": top_post.title,
            "subtitle": f"c/{top_post.community.slug}",
            "description": (top_post.body_md or top_post.community.description or "").strip()[:120],
            "url": reverse(
                "post_detail",
                kwargs={
                    "community_slug": top_post.community.slug,
                    "post_id": top_post.id,
                    "slug": top_post.slug,
                },
            ),
        }
    return None


def _directory_matches(request, directory_query: str, limit=12):
    community_queryset = Community.objects.filter(
        Q(title__icontains=directory_query)
        | Q(name__icontains=directory_query)
        | Q(slug__icontains=directory_query)
        | Q(description__icontains=directory_query)
    ).order_by("-subscriber_count", "title")
    communities = [community for community in community_queryset[:limit] if can_view_community(request.user, community)]
    users = list(
        User.objects.filter(handle__isnull=False)
        .filter(
            Q(handle__icontains=directory_query)
            | Q(display_name__icontains=directory_query)
            | Q(bio__icontains=directory_query)
        )
        .order_by("handle")[:limit]
    )
    return communities, users


def _quick_search_context(request, query: str, mode: str):
    query = query.strip()
    recent_searches = _recent_searches(request)
    recent_communities = _recent_communities_for_user(request.user)
    quick_actions = _quick_actions_for_user(request.user)

    if len(query) < 2:
        return {
            "mode": mode,
            "query": query,
            "posts": [],
            "communities": [],
            "users": [],
            "quick_actions": quick_actions,
            "recent_searches": recent_searches,
            "recent_communities": recent_communities,
            "show_empty_state": not (quick_actions or recent_searches or recent_communities),
        }

    result = get_discovery_backend().search_posts(query, sort="relevance", post_type="", media="")
    posts = result.posts[:QUICK_RESULT_LIMIT]
    query_text, _filters = parse_search_query(query)
    directory_query = query_text or query
    communities, users = _directory_matches(request, directory_query, limit=QUICK_RESULT_LIMIT)
    return {
        "mode": mode,
        "query": query,
        "posts": posts,
        "communities": communities,
        "users": users,
        "quick_actions": quick_actions,
        "recent_searches": recent_searches,
        "recent_communities": recent_communities,
        "show_empty_state": not (posts or communities or users),
    }


def search_view(request):
    query = (request.GET.get("q") or "").strip()
    sort = request.GET.get("sort", "relevance")
    post_type = (request.GET.get("post_type") or "").strip()
    media = (request.GET.get("media") or "").strip()
    country = (request.GET.get("country") or "").strip()
    result_type = (request.GET.get("type") or "all").strip()
    after = request.GET.get("after")
    query_text, parsed_filters = parse_search_query(query) if query else ("", {})
    directory_query = query_text or query
    if post_type not in {"", "text", "link", "image", "poll", "crosspost", "video"}:
        post_type = ""
    if media not in {"", "images", "links", "videos"}:
        media = ""
    if result_type not in {"all", "posts", "communities", "people"}:
        result_type = "all"
    country_name_by_code = {code.upper(): name for name, code in COUNTRY_CODE_BY_NAME.items() if code}
    country_options = sorted(
        [{"code": code, "name": name} for code, name in country_name_by_code.items()],
        key=lambda item: item["name"],
    )
    selected_country = country_name_by_code.get(country.upper(), country)
    effective_query = query
    if selected_country and "author__country__iexact" not in parsed_filters:
        effective_query = f"{query} country:{country}".strip()
    result = (
        get_discovery_backend().search_posts(effective_query, sort=sort, after=after, post_type=post_type, media=media)
        if effective_query
        else None
    )
    if query:
        _store_recent_search(request, query)
    posts = result.posts if result else []
    enrich_posts_for_display(posts, request.user)
    user_votes, saved_posts = annotate_posts_with_user_state(posts, request.user) if posts else ({}, set())
    communities = []
    users = []
    community_count = 0
    user_count = 0
    if directory_query:
        communities, users = _directory_matches(request, directory_query, limit=12)
        community_count = len(communities)
        user_count = len(users)
    best_match = _search_best_match(query, posts, communities, users) if query else None
    visible_posts = posts if result_type in {"all", "posts"} else []
    visible_communities = communities if result_type in {"all", "communities"} else []
    visible_users = users if result_type in {"all", "people"} else []
    return render(
        request,
        "search/results.html",
        {
            "query": query,
            "sort": sort,
            "post_type": post_type,
            "media": media,
            "country": country,
            "country_options": country_options,
            "result_type": result_type,
            "posts": visible_posts,
            "communities": visible_communities,
            "users": visible_users,
            "next_cursor": result.next_cursor if result else None,
            "user_votes": user_votes,
            "saved_posts": saved_posts,
            "best_match": best_match,
            "post_count": len(posts),
            "community_count": community_count,
            "user_count": user_count,
            "seo_title": f'Search results for "{query}" — Agora' if query else "Search — Agora",
            "seo_description": clean_description(
                f'Search Agora for "{query}" across posts, communities, and people.' if query else "Search posts, communities, and people across Agora."
            ),
            "meta_robots": "noindex,follow",
            "canonical_url": canonical_url_for_request(
                request,
                allowed_query_params=("q", "type", "sort", "post_type", "media", "country"),
            ),
            "structured_data": serialize_structured_data(
                breadcrumb_schema([("Home", reverse("home")), ("Search", reverse("search"))]),
                collection_page_schema(
                    name="Search",
                    description=clean_description(
                        f'Search Agora for "{query}" across posts, communities, and people.' if query else "Search posts, communities, and people across Agora."
                    ),
                    url=canonical_url_for_request(
                        request,
                        allowed_query_params=("q", "type", "sort", "post_type", "media", "country"),
                    ),
                ),
                item_list_schema(
                    "Search result posts",
                    [
                        {
                            "name": post.title,
                            "url": reverse(
                                "post_detail",
                                kwargs={"community_slug": post.community.slug, "post_id": post.id, "slug": post.slug},
                            ),
                        }
                        for post in posts[:10]
                    ],
                ) if posts else None,
            ),
        },
    )


def search_quick_view(request):
    mode = (request.GET.get("mode") or "dropdown").strip()
    if mode not in {"dropdown", "palette"}:
        mode = "dropdown"
    context = _quick_search_context(request, request.GET.get("q") or "", mode)
    return render(request, "search/partials/quick_results.html", context)
