from django.urls import path

from . import views

urlpatterns = [
    path("c/<slug:community_slug>/submit/", views.create_post, name="create_post"),
    path("c/<slug:community_slug>/post/<int:post_id>/<slug:slug>/", views.post_detail, name="post_detail"),
    path("posts/<int:post_id>/comments/create/", views.create_comment, name="create_comment"),
    path("posts/<int:post_id>/poll-vote/", views.vote_poll, name="vote_poll"),
    path("posts/<int:post_id>/delete/", views.delete_post, name="delete_post"),
    path("posts/<int:post_id>/restore/", views.restore_deleted_post, name="restore_deleted_post"),
    path("comments/<int:comment_id>/delete/", views.delete_comment, name="delete_comment"),
    path("comments/<int:comment_id>/restore/", views.restore_deleted_comment, name="restore_deleted_comment"),
]
