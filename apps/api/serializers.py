from rest_framework import serializers

from apps.accounts.models import User
from apps.posts.models import Comment, PollOption, Post


class PostListSerializer(serializers.ModelSerializer):
    community_slug = serializers.CharField(source="community.slug")
    author_handle = serializers.CharField(source="author.handle", default=None)
    flair_text = serializers.CharField(source="flair.text", default=None)

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "slug",
            "post_type",
            "url",
            "community_slug",
            "author_handle",
            "flair_text",
            "score",
            "comment_count",
            "created_at",
            "is_spoiler",
            "is_nsfw",
            "is_locked",
        ]


class PostDetailSerializer(PostListSerializer):
    body_html = serializers.CharField()
    image_url = serializers.SerializerMethodField()
    poll = serializers.SerializerMethodField()
    crosspost_parent_id = serializers.IntegerField(allow_null=True)

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ["body_html", "image_url", "poll", "crosspost_parent_id"]

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None

    def get_poll(self, obj):
        if not hasattr(obj, "poll"):
            return None
        options = obj.poll.options.order_by("position", "id")
        return {
            "id": obj.poll.id,
            "is_open": obj.poll.is_open(),
            "options": PollOptionSerializer(options, many=True).data,
        }


class PollOptionSerializer(serializers.ModelSerializer):
    vote_count = serializers.SerializerMethodField()

    class Meta:
        model = PollOption
        fields = ["id", "label", "position", "vote_count"]

    def get_vote_count(self, obj):
        return obj.votes.count()


class CommentSerializer(serializers.ModelSerializer):
    author_handle = serializers.CharField(source="author.handle", default=None)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "author_handle", "body_html", "score", "depth", "created_at", "replies"]

    def get_replies(self, obj):
        if hasattr(obj, "children"):
            return CommentSerializer(obj.children, many=True).data
        return []


class UserProfileSerializer(serializers.ModelSerializer):
    total_karma = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["handle", "display_name", "bio", "post_karma", "comment_karma", "total_karma", "is_agent"]

    def get_total_karma(self, obj):
        return obj.total_karma()
