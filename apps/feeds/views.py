from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.communities.models import Community
from apps.communities.services import (
    active_challenge_for_community,
    can_view_community,
    community_leaderboard,
    create_invite_for_community,
    featured_challenges_for_user,
    share_links_for_invite,
    suggested_communities_for_user,
)
from apps.feeds.caching import (
    community_feed_cache_key,
    get_cached_feed,
    popular_feed_cache_key,
    set_cached_feed,
)
from apps.posts.services import annotate_posts_with_user_state
from apps.search.queries import community_feed_results, home_feed_results, popular_feed_results


def home(request):
    sort = request.GET.get("sort", "hot")
    after = request.GET.get("after")
    posts, next_cursor = home_feed_results(request.user, sort=sort, after=after)
    user_votes, saved_posts = annotate_posts_with_user_state(posts, request.user)
    communities = (
        Community.objects.annotate(rule_count=Count("rules"))
        .select_related("creator")
        .order_by("-created_at")[:12]
    )
    suggested = suggested_communities_for_user(request.user)
    return render(
        request,
        "feeds/home.html",
        {
            "posts": posts,
            "sort": sort,
            "next_cursor": next_cursor,
            "user_votes": user_votes,
            "saved_posts": saved_posts,
            "communities": communities,
            "suggested_communities": suggested,
            "featured_challenges": featured_challenges_for_user(request.user),
        },
    )


def community_feed(request, slug):
    community = get_object_or_404(Community.objects.prefetch_related("rules"), slug=slug)
    if not can_view_community(request.user, community):
        return HttpResponseForbidden("This private community is only visible to members.")
    sort = request.GET.get("sort", "hot")
    after = request.GET.get("after")
    cache_key = community_feed_cache_key(community.slug, sort)
    use_cache = not request.user.is_authenticated and not after
    posts = get_cached_feed(cache_key) if use_cache else None
    next_cursor = None
    if posts is None:
        posts, next_cursor = community_feed_results(request.user, community=community, sort=sort, after=after)
        if use_cache:
            set_cached_feed(cache_key, posts)
    user_votes, saved_posts = annotate_posts_with_user_state(posts, request.user)
    joined = False
    followed_member_count = 0
    if request.user.is_authenticated:
        joined = community.memberships.filter(user=request.user).exists()
        followed_member_count = community.memberships.filter(user__in=request.user.followed_users.all()).count()
    invite = create_invite_for_community(community, request.user if request.user.is_authenticated else None)
    return render(
        request,
        "communities/detail.html",
        {
            "community": community,
            "joined": joined,
            "member_count": community.memberships.count(),
            "recent_communities": Community.objects.order_by("-created_at")[:5],
            "posts": posts,
            "sort": sort,
            "next_cursor": next_cursor,
            "user_votes": user_votes,
            "saved_posts": saved_posts,
            "active_challenge": active_challenge_for_community(community),
            "leaderboard": community_leaderboard(community),
            "suggested_communities": suggested_communities_for_user(request.user),
            "followed_member_count": followed_member_count,
            "invite": invite,
            "share_links": share_links_for_invite(community, invite),
        },
    )


def popular(request):
    sort = request.GET.get("sort", "hot")
    after = request.GET.get("after")
    cache_key = popular_feed_cache_key(sort)
    use_cache = not request.user.is_authenticated and not after
    posts = get_cached_feed(cache_key) if use_cache else None
    next_cursor = None
    if posts is None:
        posts, next_cursor = popular_feed_results(sort=sort, user=request.user, after=after)
        if use_cache:
            set_cached_feed(cache_key, posts)
    user_votes, saved_posts = annotate_posts_with_user_state(posts, request.user)
    communities = Community.objects.order_by("-subscriber_count", "-created_at")[:8]
    return render(
        request,
        "feeds/popular.html",
        {
            "posts": posts,
            "sort": sort,
            "next_cursor": next_cursor,
            "user_votes": user_votes,
            "saved_posts": saved_posts,
            "communities": communities,
        },
    )
