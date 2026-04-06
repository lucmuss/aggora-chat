from django.urls import path

from . import views

urlpatterns = [
    path("vote/", views.vote, name="vote"),
    path("award/", views.give_award, name="give_award"),
    path("save/<int:post_id>/", views.toggle_save, name="toggle_save"),
    path("save/<int:post_id>/status/", views.update_saved_post_status, name="update_saved_post_status"),
]
