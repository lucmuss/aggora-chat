from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.communities.models import Community
from apps.communities.services import can_participate_in_community, can_view_community
from apps.moderation.utils import is_user_banned
from apps.votes.models import Vote

from .forms import PostCreateForm
from .models import Poll, PollVote, Post
from .services import (
    annotate_posts_with_user_state,
    build_comment_tree,
    share_links_for_post,
    submit_comment,
    submit_poll_vote,
    submit_post,
)


@login_required
@require_http_methods(["GET", "POST"])
def create_post(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
    if not can_participate_in_community(request.user, community):
        return HttpResponseForbidden("You need membership or an invite to post in this community.")
    if is_user_banned(request.user, community):
        return HttpResponseForbidden("You are banned from posting in this community.")
    crosspost_source = None
    crosspost_source_id = request.GET.get("crosspost")
    if crosspost_source_id:
        crosspost_source = get_object_or_404(
            Post.objects.visible().select_related("community", "author"),
            pk=crosspost_source_id,
        )

    if request.method == "POST":
        form = PostCreateForm(request.POST, request.FILES, community=community)
        if form.is_valid():
            if form.cleaned_data.get("post_type") == Post.PostType.CROSSPOST and not request.POST.get("crosspost_parent_id"):
                return HttpResponseBadRequest("Crossposts require a source post.")

            post = submit_post(
                user=request.user,
                community=community,
                post_data=form.cleaned_data,
                poll_lines=form.cleaned_data.get("poll_option_lines"),
                crosspost_source_id=request.POST.get("crosspost_parent_id"),
            )
            return redirect("post_detail", community_slug=community.slug, post_id=post.id, slug=post.slug)
    else:
        initial = {}
        if crosspost_source is not None:
            initial = {
                "post_type": Post.PostType.CROSSPOST,
                "title": crosspost_source.title,
                "body_md": f"Crossposted from c/{crosspost_source.community.slug}.",
            }
        form = PostCreateForm(community=community, initial=initial)

    return render(
        request,
        "posts/create.html",
        {
            "form": form,
            "community": community,
            "crosspost_source": crosspost_source,
        },
    )


def post_detail(request, community_slug, post_id, slug=None):
    post = get_object_or_404(
        Post.objects.for_listing().select_related(
            "crosspost_parent",
            "crosspost_parent__community",
            "crosspost_parent__author",
        ),
        pk=post_id,
        community__slug=community_slug,
    )
    if not can_view_community(request.user, post.community):
        return HttpResponseForbidden("This private community is only visible to members.")
    sort = request.GET.get("sort", "top")
    comments = build_comment_tree(post, sort=sort, user=request.user)
    post_votes, saved_posts = annotate_posts_with_user_state([post], request.user)
    poll_vote = None
    if request.user.is_authenticated and hasattr(post, "poll"):
        poll_vote = PollVote.objects.filter(poll=post.poll, user=request.user).select_related("option").first()
    comment_votes = {}
    if request.user.is_authenticated and comments:
        visible_ids = []

        def flatten(items):
            for item in items:
                visible_ids.append(item.id)
                flatten(getattr(item, "children", []))

        flatten(comments)
        comment_votes = dict(
            Vote.objects.filter(user=request.user, comment_id__in=visible_ids).values_list("comment_id", "value")
        )

    return render(
        request,
        "posts/detail.html",
        {
            "post": post,
            "comments": comments,
            "sort": sort,
            "post_user_vote": post_votes.get(post.id, 0),
            "is_saved": post.id in saved_posts,
            "comment_votes": comment_votes,
            "poll_vote": poll_vote,
            "joined": request.user.is_authenticated and post.community.memberships.filter(user=request.user).exists(),
            "share_links": share_links_for_post(post),
            "onboarding_reply_prompt": request.GET.get("reply") == "1",
            "welcome_prompt": request.GET.get("welcome") == "1",
        },
    )


@login_required
@require_http_methods(["POST"])
def create_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id, is_locked=False, is_removed=False)
    if not can_participate_in_community(request.user, post.community):
        return HttpResponseForbidden("You need membership or an invite to comment in this community.")
    if is_user_banned(request.user, post.community):
        return HttpResponseForbidden("You are banned from commenting in this community.")

    body = (request.POST.get("body_md") or "").strip()
    if not body:
        return HttpResponseBadRequest("Comment body is required.")

    try:
        comment = submit_comment(
            user=request.user,
            post=post,
            body_md=body,
            parent_id=request.POST.get("parent_id"),
        )
    except ValueError as e:
        return HttpResponseForbidden(str(e))

    if request.htmx:
        return render(request, "posts/partials/comment.html", {"comment": comment, "comment_votes": {comment.id: 1}})
    return redirect("post_detail", community_slug=post.community.slug, post_id=post.id, slug=post.slug)


@login_required
@require_http_methods(["POST"])
def vote_poll(request, post_id):
    post = get_object_or_404(Post.objects.select_related("community"), pk=post_id, post_type=Post.PostType.POLL)
    if not can_participate_in_community(request.user, post.community):
        return HttpResponseForbidden("You need membership or an invite to vote in this community.")
    if is_user_banned(request.user, post.community):
        return HttpResponseForbidden("You are banned from voting in this community.")

    poll = get_object_or_404(Poll.objects.prefetch_related("options"), post=post)
    try:
        submit_poll_vote(request.user, poll, request.POST.get("option_id"))
    except ValueError as e:
        return HttpResponseForbidden(str(e))

    return redirect("post_detail", community_slug=post.community.slug, post_id=post.id, slug=post.slug)
