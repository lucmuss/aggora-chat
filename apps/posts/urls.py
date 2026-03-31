from django.urls import path

from . import views

urlpatterns = [
    path("c/<slug:community_slug>/submit/", views.create_post, name="create_post"),
    path("c/<slug:community_slug>/post/<int:post_id>/<slug:slug>/", views.post_detail, name="post_detail"),
    path("posts/<int:post_id>/comments/create/", views.create_comment, name="create_comment"),
    path("posts/<int:post_id>/poll-vote/", views.vote_poll, name="vote_poll"),
]
