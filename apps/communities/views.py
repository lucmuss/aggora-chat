from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.common.seo import (
    absolute_url,
    breadcrumb_schema,
    canonical_url_for_request,
    clean_description,
    collection_page_schema,
    item_list_schema,
    serialize_structured_data,
)
from apps.moderation.permissions import ModPermission, has_mod_permission

from .forms import CommunityCreateForm, CommunitySettingsForm, CommunityWikiPageForm
from .models import Community, CommunityInvite, CommunityWikiPage
from .services import (
    active_challenge_for_community,
    best_posts_for_community,
    community_activity_snapshot,
    can_join_community,
    can_participate_in_community,
    can_view_community,
    community_leaderboard,
    community_owner_dashboard,
    community_topic_highlights,
    create_invite_for_community,
    enrich_challenges_for_user,
    join_challenge,
    redeem_invite,
    save_wiki_page,
    share_links_for_invite,
    share_links_for_challenge,
    submit_community,
    suggested_communities_for_user,
    top_challenge_entries,
    toggle_user_membership,
)


def _render_private_community_denied(request, community, *, primary_href=None, primary_label="Browse communities"):
    return render(
        request,
        "403.html",
        {
            "access_title": "This community is private",
            "access_copy": f"c/{community.slug} is only visible to members right now, including its wiki pages.",
            "access_hint": "Ask a moderator for an invite or explore a public community while you wait.",
            "access_primary_href": primary_href or reverse("community_discovery"),
            "access_primary_label": primary_label,
        },
        status=403,
    )


def _community_detail_url(community):
    return reverse("community_detail", kwargs={"slug": community.slug})


def _post_item_list(posts):
    return [
        {
            "name": post.title,
            "url": reverse(
                "post_detail",
                kwargs={"community_slug": post.community.slug, "post_id": post.id, "slug": post.slug},
            ),
        }
        for post in posts
    ]


@login_required
def create_community(request):
    if request.method == "POST":
        form = CommunityCreateForm(request.POST, request.FILES)
        if form.is_valid():
            community = submit_community(request.user, form)
            return redirect("community_detail", slug=community.slug)
    else:
        form = CommunityCreateForm()
    return render(request, "communities/create.html", {"form": form})


@login_required
def validate_community_field(request):
    field = (request.GET.get("field") or "").strip()
    value = (request.GET.get(field) or "").strip()

    if field not in {"name", "slug"}:
        return HttpResponse("", status=204)
    if not value:
        return HttpResponse("", status=204)

    lookup = {f"{field}__iexact": value}
    exists = Community.objects.filter(**lookup).exists()
    if exists:
        return HttpResponse(
            '<span class="text-xs text-red-600">Already taken. Try another one.</span>'
        )
    return HttpResponse(
        '<span class="text-xs text-green-700">Available.</span>'
    )


@login_required
def toggle_membership(request, slug):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")

    community = get_object_or_404(Community, slug=slug)
    if not can_join_community(request.user, community):
        return render(
            request,
            "403.html",
            {
                "access_title": "This community needs an invite",
                "access_copy": "Joining is limited right now because this community is restricted.",
                "access_hint": "Use an invite link from a member or ask a moderator for approval.",
                "access_primary_href": _community_detail_url(community),
                "access_primary_label": "Back to community",
            },
            status=403,
        )
    try:
        joined = toggle_user_membership(request.user, community)
    except ValueError as e:
        return render(
            request,
            "403.html",
            {
                "access_title": "You cannot join this community yet",
                "access_copy": str(e),
                "access_primary_href": reverse("community_discovery"),
                "access_primary_label": "Browse communities",
            },
            status=403,
        )

    return render(
        request,
        "communities/partials/join_button.html",
        {"community": community, "joined": joined},
    )


def community_discovery(request):
    query = (request.GET.get("q") or "").strip()
    communities = Community.objects.annotate(rule_count=Count("rules"))
    if not request.user.is_authenticated:
        communities = communities.exclude(community_type=Community.CommunityType.PRIVATE)
    else:
        communities = communities.filter(
            Q(community_type__in=[Community.CommunityType.PUBLIC, Community.CommunityType.RESTRICTED])
            | Q(memberships__user=request.user)
        ).distinct()
    communities = communities.order_by("-subscriber_count", "-created_at")
    if query:
        communities = communities.filter(
            Q(title__icontains=query) | Q(slug__icontains=query) | Q(description__icontains=query)
        )
    return render(
        request,
        "communities/discover.html",
        {
            "query": query,
            "communities": communities[:50],
            "suggested_communities": suggested_communities_for_user(request.user),
            "seo_title": "Communities — Agora",
            "seo_description": clean_description(
                "Browse public and invite-friendly Agora communities by topic, momentum, and recent activity."
            ),
            "canonical_url": canonical_url_for_request(request, allowed_query_params=("q",)),
            "structured_data": serialize_structured_data(
                breadcrumb_schema([("Home", reverse("home")), ("Communities", reverse("community_discovery"))]),
                collection_page_schema(
                    name="Communities",
                    description=clean_description(
                        "Browse public and invite-friendly Agora communities by topic, momentum, and recent activity."
                    ),
                    url=canonical_url_for_request(request, allowed_query_params=("q",)),
                ),
            ),
        },
    )


@login_required
def community_settings(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if not has_mod_permission(request.user, community, ModPermission.MANAGE_SETTINGS):
        return render(
            request,
            "403.html",
            {
                "access_title": "Moderator permissions required",
                "access_copy": f"You need community settings access for c/{community.slug} to change posting rules or privacy.",
                "access_hint": "If you should have access, ask an owner to update your moderator role.",
                "access_primary_href": _community_detail_url(community),
                "access_primary_label": "Back to community",
            },
            status=403,
        )

    if request.method == "POST":
        form = CommunitySettingsForm(request.POST, request.FILES, instance=community)
        if form.is_valid():
            form.save()
            return redirect("community_detail", slug=community.slug)
    else:
        form = CommunitySettingsForm(instance=community)

    return render(request, "communities/settings.html", {"community": community, "form": form})


def community_landing(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if not can_view_community(request.user, community):
        raise PermissionDenied
    invite = create_invite_for_community(community, request.user if request.user.is_authenticated else None)
    share_links = share_links_for_invite(community, invite)
    leaderboard = community_leaderboard(community)
    best_posts = best_posts_for_community(community)
    challenge = active_challenge_for_community(community)
    if challenge:
        challenge = enrich_challenges_for_user([challenge], request.user)[0]
    return render(
        request,
        "communities/landing.html",
        {
            "community": community,
            "invite": invite,
            "share_links": share_links,
            "leaderboard": leaderboard,
            "best_posts": best_posts,
            "challenge": challenge,
            "topic_highlights": community_topic_highlights(community),
            "activity_snapshot": community_activity_snapshot(community),
            "can_join_directly": request.user.is_authenticated and can_join_community(request.user, community),
            "challenge_entries": top_challenge_entries(challenge, limit=6) if challenge else [],
            "challenge_share_links": share_links_for_challenge(challenge) if challenge else None,
            "seo_title": f"{community.title} — Join c/{community.slug} on Agora",
            "seo_description": clean_description(
                community.seo_description or community.description or f"Join c/{community.slug} and explore its best threads, challenge entries, and contributors."
            ),
            "canonical_url": canonical_url_for_request(request),
            "og_image_url": absolute_url(community.banner_optimized_url) if community.banner else None,
            "structured_data": serialize_structured_data(
                breadcrumb_schema(
                    [
                        ("Home", reverse("home")),
                        ("Communities", reverse("community_discovery")),
                        (f"c/{community.slug}", reverse("community_detail", kwargs={"slug": community.slug})),
                        ("Landing", reverse("community_landing", kwargs={"slug": community.slug})),
                    ]
                ),
                collection_page_schema(
                    name=community.title,
                    description=clean_description(
                        community.seo_description or community.description or f"Join c/{community.slug} on Agora."
                    ),
                    url=canonical_url_for_request(request),
                ),
                item_list_schema(f"Best posts in c/{community.slug}", _post_item_list(best_posts[:10])),
            ),
        },
    )


def community_share_card(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if not can_view_community(request.user, community):
        raise PermissionDenied
    invite = create_invite_for_community(community, request.user if request.user.is_authenticated else None)
    challenge = active_challenge_for_community(community)
    best_posts = best_posts_for_community(community, limit=3)
    return render(
        request,
        "communities/share_card.html",
        {
            "community": community,
            "invite": invite,
            "challenge": challenge,
            "best_posts": best_posts,
        },
    )


@login_required
def community_owner_dashboard_view(request, slug):
    community = get_object_or_404(Community, slug=slug)
    membership = community.memberships.filter(user=request.user).first()
    if not (request.user.is_staff or (membership and membership.role == membership.Role.OWNER)):
        return render(
            request,
            "403.html",
            {
                "access_title": "Owner access required",
                "access_copy": f"The owner dashboard for c/{community.slug} is reserved for community owners.",
                "access_hint": "Moderators can still use the queue, log, and settings tools linked from the community page.",
                "access_primary_href": reverse("community_detail", kwargs={"slug": community.slug}),
                "access_primary_label": "Back to community",
            },
            status=403,
        )
    dashboard = community_owner_dashboard(community)
    return render(
        request,
        "communities/owner_dashboard.html",
        {
            "community": community,
            "dashboard": dashboard,
        },
    )


def community_invite(request, slug, token):
    invite = get_object_or_404(CommunityInvite.objects.select_related("community", "created_by"), token=token, community__slug=slug, is_active=True)
    if request.user.is_authenticated and request.method == "POST":
        community = redeem_invite(request.user, invite)
        messages.success(request, f"You joined c/{community.slug}. Start your first post.")
        return redirect("create_post", community_slug=community.slug)

    if not request.user.is_authenticated:
        request.session["pending_invite_token"] = invite.token

    return render(
        request,
        "communities/invite_landing.html",
        {
            "community": invite.community,
            "invite": invite,
            "share_links": share_links_for_invite(invite.community, invite),
            "challenge": active_challenge_for_community(invite.community),
            "leaderboard": community_leaderboard(invite.community),
        },
    )


@login_required
def join_community_challenge(request, slug, challenge_id):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")

    community = get_object_or_404(Community, slug=slug)
    if not can_participate_in_community(request.user, community):
        return render(
            request,
            "403.html",
            {
                "access_title": "Join the community first",
                "access_copy": f"You need access to c/{community.slug} before joining its challenge.",
                "access_primary_href": _community_detail_url(community),
                "access_primary_label": "Back to community",
            },
            status=403,
        )

    challenge = get_object_or_404(community.challenges, pk=challenge_id)
    _, created = join_challenge(request.user, challenge)
    if created:
        messages.success(request, f"You're in for {challenge.title}.")
    else:
        messages.info(request, f"You're already part of {challenge.title}.")

    next_url = request.POST.get("next") or reverse("community_detail", kwargs={"slug": community.slug})
    return redirect(next_url)


def wiki_page(request, slug, page_slug="home"):
    community = get_object_or_404(Community, slug=slug)
    if not can_view_community(request.user, community):
        return _render_private_community_denied(request, community)
    pages = community.wiki_pages.all()
    page = pages.filter(slug=page_slug).first()
    can_edit = request.user.is_authenticated and has_mod_permission(
        request.user,
        community,
        ModPermission.MANAGE_SETTINGS,
    )
    return render(
        request,
        "communities/wiki_page.html",
        {
            "community": community,
            "page": page,
            "pages": pages,
            "can_edit": can_edit,
            "page_slug": page_slug,
        },
    )


@login_required
def wiki_edit(request, slug, page_slug="home"):
    community = get_object_or_404(Community, slug=slug)
    if not can_view_community(request.user, community):
        return _render_private_community_denied(
            request,
            community,
            primary_href=reverse("community_discovery"),
            primary_label="Browse communities",
        )
    if not has_mod_permission(request.user, community, ModPermission.MANAGE_SETTINGS):
        return render(
            request,
            "403.html",
            {
                "access_title": "Moderator permissions required",
                "access_copy": f"You need wiki access for c/{community.slug} to edit community docs.",
                "access_primary_href": reverse("community_wiki_home", kwargs={"slug": community.slug}),
                "access_primary_label": "View wiki",
            },
            status=403,
        )

    page = CommunityWikiPage.objects.filter(community=community, slug=page_slug).first()
    if request.method == "POST":
        form = CommunityWikiPageForm(request.POST, instance=page)
        if form.is_valid():
            page = save_wiki_page(request.user, community, form)
            return redirect("community_wiki_page", slug=community.slug, page_slug=page.slug)
    else:
        initial = {"slug": page_slug, "title": page_slug.replace("-", " ").title()}
        form = CommunityWikiPageForm(instance=page, initial=initial)

    return render(
        request,
        "communities/wiki_edit.html",
        {
            "community": community,
            "page": page,
            "form": form,
        },
    )
