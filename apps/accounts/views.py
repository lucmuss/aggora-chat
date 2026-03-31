from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.posts.models import Comment, Post
from apps.posts.services import annotate_posts_with_user_state
from apps.votes.models import SavedPost

from .forms import HandleSetupForm
from .models import User


@login_required
def handle_setup(request):
    if request.user.handle:
        return redirect("home")

    if request.method == "POST":
        form = HandleSetupForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("home")
    else:
        form = HandleSetupForm(instance=request.user)

    return render(request, "accounts/handle_setup.html", {"form": form})


def profile_view(request, handle):
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
