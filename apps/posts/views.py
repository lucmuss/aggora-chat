from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.common.celery import dispatch_task
from apps.communities.models import Community
from apps.moderation.utils import is_user_banned
from apps.search.tasks import index_post_task
from apps.votes.models import Vote
from apps.votes.tasks import recalculate_post_vote_totals

from .forms import PostCreateForm
from .models import Comment, Poll, PollOption, PollVote, Post
from .services import annotate_posts_with_user_state, build_comment_tree, hot_score


@login_required
@require_http_methods(["GET", "POST"])
def create_post(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
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
            post = form.save(commit=False)
            post.author = request.user
            post.community = community
            if post.post_type == Post.PostType.CROSSPOST:
                source_id = request.POST.get("crosspost_parent_id")
                if not source_id:
                    return HttpResponseBadRequest("Crossposts require a source post.")
                post.crosspost_parent = get_object_or_404(Post.objects.visible(), pk=source_id)
            post.save()
            if post.post_type == Post.PostType.POLL:
                poll = Poll.objects.create(post=post)
                for index, label in enumerate(form.cleaned_data["poll_option_lines"], start=1):
                    PollOption.objects.create(poll=poll, label=label, position=index)
            Vote.objects.create(user=request.user, post=post, value=Vote.VoteType.UPVOTE)
            post.upvote_count = 1
            post.score = 1
            post.hot_score = hot_score(1, 0, post.created_at)
            post.save(update_fields=["upvote_count", "score", "hot_score", "body_html"])
            dispatch_task(index_post_task, post.pk)
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
        },
    )


@login_required
@require_http_methods(["POST"])
def create_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id, is_locked=False, is_removed=False)
    if is_user_banned(request.user, post.community):
        return HttpResponseForbidden("You are banned from commenting in this community.")
    body = (request.POST.get("body_md") or "").strip()
    parent_id = request.POST.get("parent_id")

    if not body:
        return HttpResponseBadRequest("Comment body is required.")

    parent = None
    depth = 0
    if parent_id:
        parent = get_object_or_404(Comment, pk=parent_id, post=post)
        depth = parent.depth + 1
        if depth > 10:
            return HttpResponseForbidden("Maximum nesting depth reached.")

    comment = Comment.objects.create(post=post, parent=parent, author=request.user, body_md=body, depth=depth)
    Vote.objects.create(user=request.user, comment=comment, value=Vote.VoteType.UPVOTE)
    comment.upvote_count = 1
    comment.score = 1
    comment.save(update_fields=["upvote_count", "score", "body_html"])
    Post.objects.filter(pk=post.pk).update(comment_count=models.F("comment_count") + 1)
    dispatch_task(recalculate_post_vote_totals, post.id)

    if request.htmx:
        return render(request, "posts/partials/comment.html", {"comment": comment, "comment_votes": {comment.id: 1}})
    return redirect("post_detail", community_slug=post.community.slug, post_id=post.id, slug=post.slug)


@login_required
@require_http_methods(["POST"])
def vote_poll(request, post_id):
    post = get_object_or_404(Post.objects.select_related("community"), pk=post_id, post_type=Post.PostType.POLL)
    if is_user_banned(request.user, post.community):
        return HttpResponseForbidden("You are banned from voting in this community.")
    poll = get_object_or_404(Poll.objects.prefetch_related("options"), post=post)
    if not poll.is_open():
        return HttpResponseForbidden("This poll is closed.")
    option = get_object_or_404(PollOption, poll=poll, pk=request.POST.get("option_id"))
    PollVote.objects.update_or_create(
        poll=poll,
        user=request.user,
        defaults={"option": option},
    )
    return redirect("post_detail", community_slug=post.community.slug, post_id=post.id, slug=post.slug)
