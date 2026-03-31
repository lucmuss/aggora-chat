from django.urls import path

from . import views

urlpatterns = [
    path("vote/", views.vote, name="vote"),
    path("save/<int:post_id>/", views.toggle_save, name="toggle_save"),
]
