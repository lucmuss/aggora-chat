from django.urls import path

from .views import (
    handle_setup,
    notifications_view,
    profile_view,
    start_with_friends,
    toggle_block,
    toggle_follow,
    toggle_theme,
)

urlpatterns = [
    path("accounts/handle-setup/", handle_setup, name="handle_setup"),
    path("accounts/get-started/", start_with_friends, name="start_with_friends"),
    path("accounts/notifications/", notifications_view, name="notifications"),
    path("accounts/theme/toggle/", toggle_theme, name="toggle_theme"),
    path("u/<str:handle>/", profile_view, name="profile"),
    path("u/<str:handle>/follow/", toggle_follow, name="toggle_follow"),
    path("u/<str:handle>/block/", toggle_block, name="toggle_block"),
]
