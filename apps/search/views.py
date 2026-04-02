from django.db.models import Q
from django.shortcuts import render

from apps.accounts.models import User
from apps.communities.models import Community
from apps.communities.services import can_view_community
from apps.posts.services import annotate_posts_with_user_state

from .backends import get_discovery_backend, parse_search_query


def search_view(request):
    query = (request.GET.get("q") or "").strip()
    sort = request.GET.get("sort", "relevance")
    post_type = (request.GET.get("post_type") or "").strip()
    media = (request.GET.get("media") or "").strip()
    after = request.GET.get("after")
    query_text, _filters = parse_search_query(query) if query else ("", {})
    directory_query = query_text or query
    if post_type not in {"", "text", "link", "image", "poll", "crosspost"}:
        post_type = ""
    if media not in {"", "images", "links"}:
        media = ""
    result = (
        get_discovery_backend().search_posts(query, sort=sort, after=after, post_type=post_type, media=media)
        if query
        else None
    )
    posts = result.posts if result else []
    user_votes, saved_posts = annotate_posts_with_user_state(posts, request.user) if posts else ({}, set())
    communities = []
    users = []
    if directory_query:
        community_queryset = Community.objects.filter(
            Q(title__icontains=directory_query)
            | Q(name__icontains=directory_query)
            | Q(slug__icontains=directory_query)
            | Q(description__icontains=directory_query)
        ).order_by("-subscriber_count", "title")
        communities = [community for community in community_queryset[:12] if can_view_community(request.user, community)]
        users = list(
            User.objects.filter(handle__isnull=False)
            .filter(
                Q(handle__icontains=directory_query)
                | Q(display_name__icontains=directory_query)
                | Q(bio__icontains=directory_query)
            )
            .order_by("handle")[:12]
        )
    return render(
        request,
        "search/results.html",
        {
            "query": query,
            "sort": sort,
            "post_type": post_type,
            "media": media,
            "posts": posts,
            "communities": communities,
            "users": users,
            "next_cursor": result.next_cursor if result else None,
            "user_votes": user_votes,
            "saved_posts": saved_posts,
        },
    )
