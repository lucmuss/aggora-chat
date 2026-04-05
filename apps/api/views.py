from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.communities.models import Community
from apps.communities.services import can_participate_in_community, can_view_community, community_owner_dashboard
from apps.moderation.models import CommunityAgentSettings, ModAction, ModQueueItem
from apps.moderation.permissions import ModPermission, has_mod_permission
from apps.moderation.utils import is_user_banned
from apps.posts.forms import PostCreateForm
from apps.posts.models import Comment, Poll, Post
from apps.posts.services import build_comment_tree, submit_comment, submit_poll_vote, submit_post
from apps.search.backends import get_discovery_backend, parse_search_query
from apps.search.queries import community_feed_results, popular_feed_results
from apps.search.tasks import index_post_task
from apps.votes.models import Vote
from apps.votes.tasks import recalculate_comment_vote_totals, recalculate_karma, recalculate_post_vote_totals

from .pagination import AgoraCursorPagination
from .serializers import (
    CommentSerializer,
    PostDetailSerializer,
    PostListSerializer,
    SearchCommunitySerializer,
    SearchUserSerializer,
    UserProfileSerializer,
)


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
        if not can_view_community(request.user, community):
            return Response({"error": "This private community is only visible to members."}, status=status.HTTP_403_FORBIDDEN)
        sort = request.query_params.get("sort", "hot")
        after = request.query_params.get("after")
        posts, next_cursor = community_feed_results(user=request.user, community=community, sort=sort, after=after)
        serializer = self.get_serializer(posts, many=True)
        return Response({"items": serializer.data, "after": next_cursor, "before": None, "count": len(serializer.data)})


class CommunityOwnerDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        community = get_object_or_404(Community, slug=slug)
        membership = community.memberships.filter(user=request.user).first()
        if not (request.user.is_staff or (membership and membership.role == membership.Role.OWNER)):
            return Response({"error": "Owner access required"}, status=status.HTTP_403_FORBIDDEN)
        dashboard = community_owner_dashboard(community)
        return Response(
            {
                "member_count": dashboard["member_count"],
                "recent_member_joins": dashboard["recent_member_joins"],
                "challenge_uptake": dashboard["challenge_uptake"],
                "invite_conversions": {
                    "active_links": dashboard["invite_conversions"]["active_links"],
                    "joins": dashboard["invite_conversions"]["joins"],
                },
                "queue_health": dashboard["queue_health"],
                "unanswered_threads": PostListSerializer(dashboard["unanswered_threads"], many=True).data,
                "active_posters": [
                    {
                        "handle": row["user"].handle if row["user"] else None,
                        "posts": row["posts"],
                    }
                    for row in dashboard["active_poster_rows"]
                ],
            }
        )


class PostDetailAPIView(generics.RetrieveAPIView):
    serializer_class = PostDetailSerializer
    permission_classes = [AllowAny]
    queryset = Post.objects.visible().for_listing()

    def retrieve(self, request, *args, **kwargs):
        post = self.get_object()
        if not can_view_community(request.user, post.community):
            return Response({"error": "This private community is only visible to members."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(post)
        return Response(serializer.data)


class PostCommentsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        post = get_object_or_404(Post.objects.visible(), pk=pk)
        if not can_view_community(request.user, post.community):
            return Response({"error": "This private community is only visible to members."}, status=status.HTTP_403_FORBIDDEN)
        comments = build_comment_tree(post, sort=request.GET.get("sort", "top"))
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)


class PostCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        community = get_object_or_404(Community, slug=request.data.get("community_slug"))
        if not can_participate_in_community(request.user, community):
            return Response({"error": "You need membership or an invite to post in this community."}, status=status.HTTP_403_FORBIDDEN)
        if is_user_banned(request.user, community):
            return Response({"error": "Banned from this community"}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data.copy()
        poll_options = payload.get("poll_options")
        if isinstance(poll_options, (list, tuple)):
            payload["poll_option_lines"] = "\n".join(str(option).strip() for option in poll_options if str(option).strip())
        elif poll_options is not None and "poll_option_lines" not in payload:
            payload["poll_option_lines"] = poll_options
        form = PostCreateForm(payload, request.FILES, community=community)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)

        crosspost_parent_id = request.data.get("crosspost_parent_id")
        if form.cleaned_data["post_type"] == Post.PostType.CROSSPOST and not crosspost_parent_id:
            return Response(
                {"errors": {"crosspost_parent_id": ["Crossposts require a source post."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        post = submit_post(
            user=request.user,
            community=community,
            post_data=form.cleaned_data,
            poll_lines=form.cleaned_data.get("poll_option_lines"),
            crosspost_source_id=crosspost_parent_id,
        )
        return Response(PostDetailSerializer(post).data, status=status.HTTP_201_CREATED)


class CommentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        post = get_object_or_404(Post.objects.visible(), pk=request.data.get("post_id"))
        if not can_participate_in_community(request.user, post.community):
            return Response({"error": "You need membership or an invite to comment in this community."}, status=status.HTTP_403_FORBIDDEN)
        if is_user_banned(request.user, post.community):
            return Response({"error": "Banned from this community"}, status=status.HTTP_403_FORBIDDEN)
        body_md = (request.data.get("body_md") or "").strip()
        if not body_md:
            return Response({"errors": {"body_md": ["Comment body is required."]}}, status=status.HTTP_400_BAD_REQUEST)
        try:
            comment = submit_comment(
                user=request.user,
                post=post,
                body_md=body_md,
                parent_id=request.data.get("parent_id"),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class PollVoteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(Post.objects.visible().select_related("community"), pk=pk, post_type=Post.PostType.POLL)
        if not can_participate_in_community(request.user, post.community):
            return Response({"error": "You need membership or an invite to vote in this community."}, status=status.HTTP_403_FORBIDDEN)
        if is_user_banned(request.user, post.community):
            return Response({"error": "Banned from this community"}, status=status.HTTP_403_FORBIDDEN)
        poll = get_object_or_404(Poll.objects.prefetch_related("options"), post=post)
        try:
            submit_poll_vote(request.user, poll, request.data.get("option_id"))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
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
        post_type = request.query_params.get("post_type", "")
        media = request.query_params.get("media", "")
        result = get_discovery_backend().search_posts(
            query,
            sort=sort,
            after=after,
            post_type=post_type,
            media=media,
        )
        post_serializer = self.get_serializer(result.posts, many=True)
        query_text, _filters = parse_search_query(query) if query else ("", {})
        directory_query = query_text or query
        communities = []
        users = []
        if directory_query:
            community_queryset = Community.objects.filter(
                Q(title__icontains=directory_query)
                | Q(name__icontains=directory_query)
                | Q(slug__icontains=directory_query)
                | Q(description__icontains=directory_query)
            ).order_by("-subscriber_count", "title")
            communities = [community for community in community_queryset[:12] if can_view_community(request.user, community)]
            users = list(
                User.objects.filter(handle__isnull=False)
                .filter(
                    Q(handle__icontains=directory_query)
                    | Q(display_name__icontains=directory_query)
                    | Q(bio__icontains=directory_query)
                )
                .order_by("handle")[:12]
            )
        return Response(
            {
                "items": post_serializer.data,
                "posts": post_serializer.data,
                "communities": SearchCommunitySerializer(communities, many=True).data,
                "users": SearchUserSerializer(users, many=True).data,
                "after": result.next_cursor,
                "before": None,
                "count": len(post_serializer.data),
            }
        )


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
