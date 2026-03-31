from django.shortcuts import render

from apps.posts.services import annotate_posts_with_user_state

from .backends import get_discovery_backend


def search_view(request):
    query = (request.GET.get("q") or "").strip()
    sort = request.GET.get("sort", "relevance")
    after = request.GET.get("after")
    result = get_discovery_backend().search_posts(query, sort=sort, after=after) if query else None
    posts = result.posts if result else []
    user_votes, saved_posts = annotate_posts_with_user_state(posts, request.user) if posts else ({}, set())
    return render(
        request,
        "search/results.html",
        {
            "query": query,
            "sort": sort,
            "posts": posts,
            "next_cursor": result.next_cursor if result else None,
            "user_votes": user_votes,
            "saved_posts": saved_posts,
        },
    )
