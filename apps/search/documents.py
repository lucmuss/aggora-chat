from django.conf import settings

if settings.SEARCH_BACKEND == "elasticsearch" and settings.SEARCH_INDEX_ENABLED:
    from django_elasticsearch_dsl import Document, Index, fields
    from django_elasticsearch_dsl.registries import registry

    from apps.posts.models import Post

    POSTS_INDEX = Index("agora_posts")
    POSTS_INDEX.settings(number_of_shards=1, number_of_replicas=0, refresh_interval="1s")

    @registry.register_document
    class PostDocument(Document):
        community_slug = fields.KeywordField(attr="community.slug")
        community_name = fields.TextField(attr="community.name")
        author_handle = fields.KeywordField(attr="author.handle")
        flair_text = fields.KeywordField(attr="flair.text")
        body_text = fields.TextField(attr="body_md")

        class Index:
            name = "agora_posts"

        class Django:
            model = Post
            fields = [
                "id",
                "title",
                "slug",
                "post_type",
                "url",
                "score",
                "hot_score",
                "upvote_count",
                "downvote_count",
                "comment_count",
                "created_at",
                "is_removed",
            ]
else:
    PostDocument = None
