from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.celery import dispatch_task
from apps.accounts.models import User
from apps.communities.models import Community
from apps.moderation.models import CommunityAgentSettings, ModAction, ModQueueItem
from apps.moderation.permissions import ModPermission, has_mod_permission
from apps.moderation.utils import is_user_banned
from apps.posts.forms import PostCreateForm
from apps.posts.models import Comment, Poll, PollOption, PollVote, Post
from apps.posts.services import build_comment_tree, hot_score
from apps.search.backends import get_discovery_backend
from apps.search.queries import community_feed_results, popular_feed_results
from apps.search.tasks import index_post_task
from apps.votes.models import Vote
from apps.votes.tasks import recalculate_comment_vote_totals, recalculate_karma, recalculate_post_vote_totals

from .pagination import AgoraCursorPagination
from .serializers import CommentSerializer, PostDetailSerializer, PostListSerializer, UserProfileSerializer


class AgentModActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, community_slug):
        user = request.user
        if not (user.is_agent and user.agent_verified):
            return Response({"error": "Not a verified agent"}, status=status.HTTP_403_FORBIDDEN)

        community = get_object_or_404(Community, slug=community_slug)
        if not has_mod_permission(user, community, ModPermission.MANAGE_POSTS):
            return Response({"error": "No permission"}, status=status.HTTP_403_FORBIDDEN)

        action = request.data.get("action")
        confidence = float(request.data.get("confidence", 0.0))
        reason_code = request.data.get("reason_code")
        explanation = request.data.get("explanation")
        post_id = request.data.get("post_id")
        comment_id = request.data.get("comment_id")

        if action not in {"flag", "remove", "warn"}:
            return Response({"error": "Unsupported action"}, status=status.HTTP_400_BAD_REQUEST)
        if not explanation or not reason_code:
            return Response(
                {"error": "explanation and reason_code required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not post_id and not comment_id:
            return Response({"error": "post_id or comment_id required"}, status=status.HTTP_400_BAD_REQUEST)

        settings_obj, _ = CommunityAgentSettings.objects.get_or_create(community=community)
        target_post = None
        target_comment = None
        queue_item = None

        if post_id:
            target_post = get_object_or_404(Post, pk=post_id, community=community)
        if comment_id:
            target_comment = get_object_or_404(Comment, pk=comment_id, post__community=community)

        should_queue = action == "flag" or action == "warn" or confidence < settings_obj.auto_remove_threshold
        if should_queue:
            queue_item, _ = ModQueueItem.objects.get_or_create(
                community=community,
                post=target_post,
                comment=target_comment,
                defaults={
                    "status": ModQueueItem.Status.NEEDS_REVIEW,
                    "content_type": ModQueueItem.ContentType.POST if target_post else ModQueueItem.ContentType.COMMENT,
                },
            )
        elif action == "remove":
            if target_post:
                target_post.is_removed = True
                target_post.removed_reason = explanation
                target_post.save(update_fields=["is_removed", "removed_reason", "body_html"])
                index_post_task(target_post.pk)
            if target_comment:
                target_comment.is_removed = True
                target_comment.save(update_fields=["is_removed", "body_html"])

        mod_action = ModAction.objects.create(
            community=community,
            moderator=user,
            is_agent_action=True,
            action_type=f"agent_{action}",
            target_post=target_post,
            target_comment=target_comment,
            reason_code=reason_code,
            reason_text=explanation,
            confidence_score=confidence,
            details_json={"queued": should_queue},
        )

        return Response(
            {
                "status": "ok",
                "queued": should_queue,
                "queue_item_id": queue_item.id if queue_item else None,
                "action_id": mod_action.id,
            }
        )


class PopularFeedAPIView(generics.ListAPIView):
    serializer_class = PostListSerializer
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        sort = request.query_params.get("sort", "hot")
        after = request.query_params.get("after")
        posts, next_cursor = popular_feed_results(sort=sort, user=request.user, after=after)
        serializer = self.get_serializer(posts, many=True)
        return Response({"items": serializer.data, "after": next_cursor, "before": None, "count": len(serializer.data)})


class CommunityFeedAPIView(generics.ListAPIView):
    serializer_class = PostListSerializer
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        community = get_object_or_404(Community, slug=self.kwargs["slug"])
        sort = request.query_params.get("sort", "hot")
        after = request.query_params.get("after")
        posts, next_cursor = community_feed_results(user=request.user, community=community, sort=sort, after=after)
        serializer = self.get_serializer(posts, many=True)
        return Response({"items": serializer.data, "after": next_cursor, "before": None, "count": len(serializer.data)})


class PostDetailAPIView(generics.RetrieveAPIView):
    serializer_class = PostDetailSerializer
    permission_classes = [AllowAny]
    queryset = Post.objects.visible().for_listing()


class PostCommentsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        post = get_object_or_404(Post.objects.visible(), pk=pk)
        comments = build_comment_tree(post, sort=request.GET.get("sort", "top"))
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)


class PostCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        community = get_object_or_404(Community, slug=request.data.get("community_slug"))
        if is_user_banned(request.user, community):
            return Response({"error": "Banned from this community"}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data.copy()
        poll_options = payload.get("poll_options")
        if isinstance(poll_options, (list, tuple)):
            payload["poll_options"] = "\n".join(str(option).strip() for option in poll_options if str(option).strip())
        form = PostCreateForm(payload, request.FILES, community=community)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)

        post = form.save(commit=False)
        post.community = community
        post.author = request.user
        if post.post_type == Post.PostType.CROSSPOST:
            source_id = request.data.get("crosspost_parent_id")
            if not source_id:
                return Response({"errors": {"crosspost_parent_id": ["Crossposts require a source post."]}}, status=status.HTTP_400_BAD_REQUEST)
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
        return Response(PostDetailSerializer(post).data, status=status.HTTP_201_CREATED)


class CommentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        post = get_object_or_404(Post.objects.visible(), pk=request.data.get("post_id"))
        if is_user_banned(request.user, post.community):
            return Response({"error": "Banned from this community"}, status=status.HTTP_403_FORBIDDEN)
        body_md = (request.data.get("body_md") or "").strip()
        if not body_md:
            return Response({"errors": {"body_md": ["Comment body is required."]}}, status=status.HTTP_400_BAD_REQUEST)
        parent = None
        parent_id = request.data.get("parent_id")
        depth = 0
        if parent_id:
            parent = get_object_or_404(Comment, pk=parent_id, post=post)
            depth = parent.depth + 1
            if depth > 10:
                return Response({"error": "Maximum nesting depth reached."}, status=status.HTTP_403_FORBIDDEN)
        comment = Comment.objects.create(
            post=post,
            parent=parent,
            author=request.user,
            body_md=body_md,
            depth=depth,
        )
        Vote.objects.create(user=request.user, comment=comment, value=Vote.VoteType.UPVOTE)
        comment.upvote_count = 1
        comment.score = 1
        comment.save(update_fields=["upvote_count", "score", "body_html"])
        Post.objects.filter(pk=post.pk).update(comment_count=models.F("comment_count") + 1)
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class PollVoteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(Post.objects.visible().select_related("community"), pk=pk, post_type=Post.PostType.POLL)
        if is_user_banned(request.user, post.community):
            return Response({"error": "Banned from this community"}, status=status.HTTP_403_FORBIDDEN)
        poll = get_object_or_404(Poll.objects.prefetch_related("options"), post=post)
        if not poll.is_open():
            return Response({"error": "This poll is closed."}, status=status.HTTP_403_FORBIDDEN)
        option = get_object_or_404(PollOption, poll=poll, pk=request.data.get("option_id"))
        PollVote.objects.update_or_create(
            poll=poll,
            user=request.user,
            defaults={"option": option},
        )
        post.refresh_from_db()
        return Response(PostDetailSerializer(post).data)


class VoteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        post_id = request.data.get("post_id")
        comment_id = request.data.get("comment_id")
        value = int(request.data.get("value", 0))
        if post_id:
            target = get_object_or_404(Post, pk=post_id)
            existing = Vote.objects.filter(user=request.user, post=target).first()
        else:
            target = get_object_or_404(Comment, pk=comment_id)
            existing = Vote.objects.filter(user=request.user, comment=target).first()

        if existing:
            if existing.value == value:
                existing.delete()
            else:
                existing.value = value
                existing.save(update_fields=["value"])
        else:
            Vote.objects.create(user=request.user, post_id=post_id, comment_id=comment_id, value=value)

        if post_id:
            recalculate_post_vote_totals(post_id)
            if target.author_id:
                recalculate_karma(target.author_id)
            target.refresh_from_db()
            return Response(PostDetailSerializer(target).data)
        recalculate_comment_vote_totals(comment_id)
        if target.author_id:
            recalculate_karma(target.author_id)
        target.refresh_from_db()
        return Response(CommentSerializer(target).data)


class SearchAPIView(generics.ListAPIView):
    serializer_class = PostListSerializer
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        query = request.query_params.get("q", "")
        sort = request.query_params.get("sort", "relevance")
        after = request.query_params.get("after")
        result = get_discovery_backend().search_posts(query, sort=sort, after=after)
        serializer = self.get_serializer(result.posts, many=True)
        return Response({"items": serializer.data, "after": result.next_cursor, "before": None, "count": len(serializer.data)})


class UserProfileAPIView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = "handle"
    queryset = User.objects.all()


class UserPostsAPIView(generics.ListAPIView):
    serializer_class = PostListSerializer
    pagination_class = AgoraCursorPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Post.objects.visible().for_listing().filter(author__handle=self.kwargs["handle"]).order_by("-created_at")
