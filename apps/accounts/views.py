from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.common.markdown import render_markdown
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

from .forms import AccountSettingsForm, HandleSetupForm, StartWithFriendsForm, TotpVerificationForm
from .growth import (
    award_onboarding_badges,
    first_week_missions_for_user,
    onboarding_progress_for_user,
    record_post_share,
    referral_summary_for_user,
)
from .models import User
from .security import build_totp_uri, generate_totp_secret, user_requires_mfa, verify_totp

try:
    from allauth.account.models import EmailAddress
    from allauth.socialaccount.models import SocialAccount
except ImportError:  # pragma: no cover - optional dependency wiring
    EmailAddress = None
    SocialAccount = None


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
    visibility_restricted = False
    if request.user != profile_user and (
        profile_user.profile_visibility == User.ProfileVisibility.PRIVATE
        or (
            profile_user.profile_visibility == User.ProfileVisibility.MEMBERS
            and not request.user.is_authenticated
        )
    ):
        visibility_restricted = True
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
    saved_entries = []
    comments = []
    comment_votes = {}
    if is_blocked or visibility_restricted:
        tab = "posts"
    elif tab == "posts":
        posts = list(Post.objects.visible().for_listing().filter(author=profile_user).order_by("-created_at")[:25])
    elif tab == "saved":
        saved_entries = [
            saved
            for saved in (
                SavedPost.objects.filter(user=profile_user)
                .select_related("post", "post__community", "post__author", "post__flair", "post__crosspost_parent")
                .order_by(
                    models.Case(
                        models.When(status=SavedPost.QueueStatus.UNREAD, then=0),
                        models.When(status=SavedPost.QueueStatus.READING, then=1),
                        default=2,
                        output_field=models.IntegerField(),
                    ),
                    "-saved_at",
                )[:40]
            )
            if saved.post and not saved.post.is_removed and not saved.post.author_deleted_at
        ]
        posts = [saved.post for saved in saved_entries]
    else:
        comments = list(
            Comment.objects.filter(author=profile_user, is_removed=False, author_deleted_at__isnull=True)
            .select_related("post", "post__community")
            .order_by("-created_at")[:25]
        )
        if request.user.is_authenticated and comments:
            from apps.votes.models import Vote

            comment_votes = dict(
                Vote.objects.filter(user=request.user, comment_id__in=[comment.id for comment in comments]).values_list(
                    "comment_id", "value"
                )
            )

    user_votes, saved_posts = annotate_posts_with_user_state(posts, request.user) if posts else ({}, set())
    joined_communities = list(
        Community.objects.filter(memberships__user=profile_user).order_by("-subscriber_count", "title")[:6]
    )
    recent_activity = {
        "posts": Post.objects.filter(author=profile_user, author_deleted_at__isnull=True).count(),
        "comments": Comment.objects.filter(author=profile_user, author_deleted_at__isnull=True).count(),
        "saved": SavedPost.objects.filter(user=profile_user).count(),
    }
    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": profile_user,
            "profile_bio_html": render_markdown(profile_user.bio) if profile_user.bio else "",
            "tab": tab,
            "posts": posts,
            "comments": comments,
            "user_votes": user_votes,
            "saved_posts": saved_posts,
            "saved_count": SavedPost.objects.filter(user=profile_user).count(),
            "saved_entries": saved_entries,
            "saved_statuses": SavedPost.QueueStatus,
            "comment_votes": comment_votes,
            "is_blocked": is_blocked,
            "visibility_restricted": visibility_restricted,
            "is_following": is_following,
            "follower_count": profile_user.followers.count(),
            "following_count": profile_user.followed_users.count(),
            "badges": list(profile_user.badges.all()[:8]),
            "joined_communities": joined_communities,
            "recent_activity": recent_activity,
            "referral_stats": referral_summary_for_user(profile_user) if request.user == profile_user else None,
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
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or reverse("home")
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
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        request.user.display_name = form.cleaned_data.get("display_name", "").strip()
        request.user.bio = form.cleaned_data.get("bio", "").strip()
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
        request.user.save(update_fields=["display_name", "bio", "onboarding_completed", "onboarding_completed_at"])
        award_onboarding_badges(request.user)

        if invite_community is not None and form.cleaned_data.get("first_contribution_type") == StartWithFriendsForm.FirstContributionType.COMMENT:
            starter_post = (
                Post.objects.visible()
                .for_listing()
                .filter(community=invite_community)
                .order_by("-comment_count", "-score", "-created_at")
                .first()
            )
            if starter_post is not None:
                return redirect(
                    f"{reverse('post_detail', kwargs={'community_slug': starter_post.community.slug, 'post_id': starter_post.id, 'slug': starter_post.slug})}?reply=1&welcome=1"
                )
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
            "progress": onboarding_progress_for_user(request.user),
            "user_bio_preview_html": render_markdown(request.user.bio) if request.user.bio else "",
        },
    )


@login_required
def notifications_view(request):
    notification_filter = request.GET.get("filter", "all")
    if notification_filter not in NOTIFICATION_FILTERS:
        notification_filter = "all"

    notifications_qs = request.user.notifications.select_related("actor", "community", "post", "comment")
    filter_types = NOTIFICATION_FILTERS[notification_filter]
    if filter_types:
        notifications_qs = notifications_qs.filter(notification_type__in=filter_types)
    notifications = list(notifications_qs[:50])
    counts = {
        "all": request.user.notifications.count(),
        "replies": request.user.notifications.filter(
            notification_type__in=NOTIFICATION_FILTERS["replies"]
        ).count(),
        "follows": request.user.notifications.filter(
            notification_type__in=NOTIFICATION_FILTERS["follows"]
        ).count(),
        "challenges": request.user.notifications.filter(
            notification_type__in=NOTIFICATION_FILTERS["challenges"]
        ).count(),
        "unread": request.user.notifications.filter(is_read=False).count(),
    }
    return render(
        request,
        "accounts/notifications.html",
        {
            "notifications": notifications,
            "notification_filter": notification_filter,
            "notification_counts": counts,
        },
    )


@login_required
def notification_toggle_read_view(request, notification_id):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    notification = get_object_or_404(request.user.notifications, pk=notification_id)
    notification.is_read = not notification.is_read
    notification.save(update_fields=["is_read"])
    next_url = request.POST.get("next") or reverse("notifications")
    return redirect(next_url)


@login_required
def notifications_mark_all_read_view(request):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    request.user.notifications.filter(is_read=False).update(is_read=True)
    next_url = request.POST.get("next") or reverse("notifications")
    return redirect(next_url)


@login_required
def referrals_view(request):
    summary = referral_summary_for_user(request.user)
    return render(
        request,
        "accounts/referrals.html",
        {
            "referral_cards": summary["cards"],
            "featured_referral_card": summary["featured_card"],
            "referral_stats": summary,
            "progress": onboarding_progress_for_user(request.user),
            "badges": list(request.user.badges.all()[:8]),
            "missions": first_week_missions_for_user(request.user),
        },
    )


@login_required
def record_share_view(request, post_id):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    post = get_object_or_404(Post.objects.visible().select_related("community"), pk=post_id)
    if not post.community_id:
        return HttpResponseForbidden("Invalid share target.")
    record_post_share(request.user)
    return JsonResponse({"status": "ok"})


@login_required
def account_settings_view(request):
    if request.method == "POST":
        form = AccountSettingsForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Account settings updated.")
            return redirect("account_settings")
    else:
        form = AccountSettingsForm(instance=request.user)

    connected_accounts = []
    email_addresses = []
    if SocialAccount is not None:
        connected_accounts = list(SocialAccount.objects.filter(user=request.user).order_by("provider"))
    if EmailAddress is not None:
        email_addresses = list(EmailAddress.objects.filter(user=request.user).order_by("-primary", "email"))

    password_url_name = "account_change_password" if request.user.has_usable_password() else "account_set_password"

    return render(
        request,
        "accounts/settings.html",
        {
            "form": form,
            "connected_accounts": connected_accounts,
            "email_addresses": email_addresses,
            "profile_bio_html": render_markdown(request.user.bio) if request.user.bio else "",
            "password_url_name": password_url_name,
            "has_usable_password": request.user.has_usable_password(),
            "requires_mfa": user_requires_mfa(request.user),
            "missions": first_week_missions_for_user(request.user),
        },
    )


@login_required
def mfa_setup_view(request):
    if not request.user.mfa_totp_secret:
        request.user.mfa_totp_secret = generate_totp_secret()
        request.user.save(update_fields=["mfa_totp_secret"])

    form = TotpVerificationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if verify_totp(request.user.mfa_totp_secret, form.cleaned_data["code"]):
            request.user.mfa_totp_enabled = True
            request.user.mfa_enabled_at = timezone.now()
            request.user.save(update_fields=["mfa_totp_enabled", "mfa_enabled_at"])
            messages.success(request, "Two-factor authentication is now active.")
            return redirect("account_settings")
        form.add_error("code", "That code does not match the current authenticator value.")

    return render(
        request,
        "accounts/mfa_setup.html",
        {
            "form": form,
            "totp_uri": build_totp_uri(request.user),
            "totp_secret": request.user.mfa_totp_secret,
            "mfa_enabled": request.user.mfa_totp_enabled,
            "required_for_admin": (request.GET.get("next") or "").startswith("/admin/"),
        },
    )


@login_required
def mfa_disable_view(request):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    form = TotpVerificationForm(request.POST)
    if not form.is_valid() or not verify_totp(request.user.mfa_totp_secret, form.cleaned_data["code"]):
        messages.error(request, "Use a valid authenticator code to disable 2FA.")
        return redirect("account_mfa_setup")
    request.user.mfa_totp_enabled = False
    request.user.mfa_totp_secret = generate_totp_secret()
    request.user.mfa_enabled_at = None
    request.user.save(update_fields=["mfa_totp_enabled", "mfa_totp_secret", "mfa_enabled_at"])
    messages.success(request, "Two-factor authentication has been disabled.")
    return redirect("account_settings")
NOTIFICATION_FILTERS = {
    "all": None,
    "replies": [
        "post_reply",
        "comment_reply",
    ],
    "follows": ["followed_user_joined"],
    "challenges": ["challenge_started"],
}
