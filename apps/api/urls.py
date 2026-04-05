from django.urls import path

from .views import (
    AgentModActionView,
    CommentCreateAPIView,
    CommunityFeedAPIView,
    CommunityOwnerDashboardAPIView,
    PollVoteAPIView,
    PopularFeedAPIView,
    PostCommentsAPIView,
    PostCreateAPIView,
    PostDetailAPIView,
    SearchAPIView,
    UserPostsAPIView,
    UserProfileAPIView,
    VoteAPIView,
)

urlpatterns = [
    path("v1/popular/", PopularFeedAPIView.as_view(), name="api_popular_feed"),
    path("v1/c/<slug:slug>/feed/", CommunityFeedAPIView.as_view(), name="api_community_feed"),
    path("v1/c/<slug:slug>/owner/", CommunityOwnerDashboardAPIView.as_view(), name="api_community_owner_dashboard"),
    path("v1/posts/<int:pk>/", PostDetailAPIView.as_view(), name="api_post_detail"),
    path("v1/posts/<int:pk>/comments/", PostCommentsAPIView.as_view(), name="api_post_comments"),
    path("v1/posts/<int:pk>/poll-vote/", PollVoteAPIView.as_view(), name="api_poll_vote"),
    path("v1/posts/", PostCreateAPIView.as_view(), name="api_post_create"),
    path("v1/comments/", CommentCreateAPIView.as_view(), name="api_comment_create"),
    path("v1/vote/", VoteAPIView.as_view(), name="api_vote"),
    path("v1/search/", SearchAPIView.as_view(), name="api_search"),
    path("v1/u/<str:handle>/", UserProfileAPIView.as_view(), name="api_user_profile"),
    path("v1/u/<str:handle>/posts/", UserPostsAPIView.as_view(), name="api_user_posts"),
    path("v1/mod/<slug:community_slug>/action/", AgentModActionView.as_view(), name="api_agent_mod_action"),
]
