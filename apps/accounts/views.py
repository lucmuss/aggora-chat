from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.communities.models import Community
from apps.communities.services import (
    create_invite_for_community,
    redeem_pending_invite_token,
    send_friend_invites,
    suggested_communities_for_user,
)
from apps.posts.models import Comment, Post
from apps.posts.services import annotate_posts_with_user_state
from apps.votes.models import SavedPost

from .forms import HandleSetupForm, StartWithFriendsForm
from .models import User


@login_required
def handle_setup(request):
    if request.user.handle:
        return redirect("home" if request.user.onboarding_completed else "start_with_friends")

    if request.method == "POST":
        form = HandleSetupForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("start_with_friends")
    else:
        form = HandleSetupForm(instance=request.user)

    return render(request, "accounts/handle_setup.html", {"form": form})


def profile_view(request, handle):
    if handle == "me":
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not request.user.handle:
            return redirect("handle_setup")
        return redirect("profile", handle=request.user.handle)

    profile_user = get_object_or_404(User, handle=handle)
    is_blocked = False
    is_following = False
    if request.user.is_authenticated and request.user != profile_user:
        blocked_ids = set(request.user.blocked_users.values_list("id", flat=True))
        is_blocked = profile_user.id in blocked_ids or request.user.id in set(
            profile_user.blocked_users.values_list("id", flat=True)
        )
        is_following = request.user.followed_users.filter(pk=profile_user.pk).exists()
    tab = request.GET.get("tab", "posts")

    posts = []
    comments = []
    if is_blocked:
        tab = "posts"
    elif tab == "posts":
        posts = list(Post.objects.visible().for_listing().filter(author=profile_user).order_by("-created_at")[:25])
    elif tab == "saved":
        posts = list(
            Post.objects.visible()
            .for_listing()
            .filter(savedpost__user=profile_user)
            .order_by("-savedpost__saved_at")[:25]
        )
    else:
        comments = list(Comment.objects.filter(author=profile_user, is_removed=False).select_related("post")[:25])

    user_votes, saved_posts = annotate_posts_with_user_state(posts, request.user) if posts else ({}, set())
    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": profile_user,
            "tab": tab,
            "posts": posts,
            "comments": comments,
            "user_votes": user_votes,
            "saved_posts": saved_posts,
            "saved_count": SavedPost.objects.filter(user=profile_user).count(),
            "is_blocked": is_blocked,
            "is_following": is_following,
            "follower_count": profile_user.followers.count(),
            "following_count": profile_user.followed_users.count(),
        },
    )


@login_required
def toggle_follow(request, handle):
    if request.method != "POST":
        return redirect("profile", handle=handle)
    profile_user = get_object_or_404(User, handle=handle)
    if profile_user != request.user and not request.user.blocked_users.filter(pk=profile_user.pk).exists():
        if request.user.followed_users.filter(pk=profile_user.pk).exists():
            request.user.followed_users.remove(profile_user)
        else:
            request.user.followed_users.add(profile_user)
    return redirect("profile", handle=handle)


@login_required
def toggle_block(request, handle):
    if request.method != "POST":
        return redirect("profile", handle=handle)
    profile_user = get_object_or_404(User, handle=handle)
    if profile_user != request.user:
        if request.user.blocked_users.filter(pk=profile_user.pk).exists():
            request.user.blocked_users.remove(profile_user)
        else:
            request.user.blocked_users.add(profile_user)
            request.user.followed_users.remove(profile_user)
    return redirect("profile", handle=handle)


def toggle_theme(request):
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or "/"
    current_theme = request.COOKIES.get("agora_theme", "light")
    next_theme = "dark" if current_theme != "dark" else "light"
    response = redirect(next_url)
    response.set_cookie("agora_theme", next_theme, max_age=31536000, samesite="Lax")
    return response


@login_required
def start_with_friends(request):
    suggested = suggested_communities_for_user(request.user)
    joined = list(Community.objects.filter(memberships__user=request.user).distinct().order_by("title"))
    pending_token = request.session.get("pending_invite_token")
    if request.user.onboarding_completed and request.method == "GET" and not pending_token:
        return redirect("home")
    joined_for_form = joined if joined else suggested
    form = StartWithFriendsForm(
        request.POST or None,
        suggested_communities=suggested,
        joined_communities=joined_for_form,
    )

    if request.method == "POST" and form.is_valid():
        selected = list(form.cleaned_data["communities"])
        for community in selected:
            community.memberships.get_or_create(
                user=request.user,
                defaults={"role": community.memberships.model.Role.MEMBER},
            )
        for community in selected:
            community.subscriber_count = community.memberships.count()
            community.save(update_fields=["subscriber_count"])

        invite_community = form.cleaned_data.get("first_post_community") or (selected[0] if selected else None)
        if pending_token:
            redeemed_community = redeem_pending_invite_token(request.user, pending_token)
            request.session.pop("pending_invite_token", None)
            if redeemed_community and invite_community is None:
                invite_community = redeemed_community

        friend_emails = form.cleaned_data["friend_emails"]
        if friend_emails and invite_community is not None:
            invite = create_invite_for_community(invite_community, request.user)
            send_friend_invites(
                sender=request.user,
                community=invite_community,
                invite=invite,
                recipient_emails=friend_emails,
            )
            messages.success(request, f"Invites sent to {len(friend_emails)} friend(s).")

        request.user.onboarding_completed = True
        request.user.onboarding_completed_at = timezone.now()
        request.user.save(update_fields=["onboarding_completed", "onboarding_completed_at"])

        if invite_community is not None:
            return redirect("create_post", community_slug=invite_community.slug)
        return redirect("home")

    active_pending_community = None
    if pending_token:
        active_pending_community = Community.objects.filter(invites__token=pending_token, invites__is_active=True).first()

    return render(
        request,
        "accounts/onboarding.html",
        {
            "form": form,
            "suggested_communities": suggested,
            "joined_communities": joined,
            "pending_invite_community": active_pending_community,
        },
    )


@login_required
def notifications_view(request):
    notifications = list(request.user.notifications.select_related("actor", "community", "post")[:50])
    unread_ids = [notification.id for notification in notifications if not notification.is_read]
    if unread_ids:
        request.user.notifications.filter(id__in=unread_ids).update(is_read=True)
    return render(request, "accounts/notifications.html", {"notifications": notifications})
