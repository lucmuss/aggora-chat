from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.moderation.permissions import ModPermission, has_mod_permission

from .forms import CommunityCreateForm, CommunitySettingsForm, CommunityWikiPageForm
from .models import Community, CommunityWikiPage
from .services import save_wiki_page, submit_community, toggle_user_membership


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
def toggle_membership(request, slug):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")

    community = get_object_or_404(Community, slug=slug)
    try:
        joined = toggle_user_membership(request.user, community)
    except ValueError as e:
        return HttpResponseForbidden(str(e))

    return render(
        request,
        "communities/partials/join_button.html",
        {"community": community, "joined": joined},
    )


def community_discovery(request):
    query = (request.GET.get("q") or "").strip()
    communities = Community.objects.annotate(rule_count=Count("rules")).order_by("-subscriber_count", "-created_at")
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
        },
    )


@login_required
def community_settings(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if not has_mod_permission(request.user, community, ModPermission.MANAGE_SETTINGS):
        return HttpResponseForbidden("Moderator permissions required.")

    if request.method == "POST":
        form = CommunitySettingsForm(request.POST, request.FILES, instance=community)
        if form.is_valid():
            form.save()
            return redirect("community_detail", slug=community.slug)
    else:
        form = CommunitySettingsForm(instance=community)

    return render(request, "communities/settings.html", {"community": community, "form": form})


def wiki_page(request, slug, page_slug="home"):
    community = get_object_or_404(Community, slug=slug)
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
    if not has_mod_permission(request.user, community, ModPermission.MANAGE_SETTINGS):
        return HttpResponseForbidden("Moderator permissions required.")

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
