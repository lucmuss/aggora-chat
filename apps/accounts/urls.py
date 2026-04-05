from django.urls import path

from .views import (
    account_settings_view,
    handle_setup,
    mfa_disable_view,
    mfa_setup_view,
    notifications_view,
    notifications_mark_all_read_view,
    notification_toggle_read_view,
    profile_view,
    record_share_view,
    referrals_view,
    start_with_friends,
    toggle_block,
    toggle_follow,
    toggle_theme,
)

urlpatterns = [
    path("accounts/handle-setup/", handle_setup, name="handle_setup"),
    path("accounts/get-started/", start_with_friends, name="start_with_friends"),
    path("accounts/settings/", account_settings_view, name="account_settings"),
    path("accounts/referrals/", referrals_view, name="account_referrals"),
    path("accounts/share/posts/<int:post_id>/record/", record_share_view, name="record_post_share"),
    path("accounts/mfa/", mfa_setup_view, name="account_mfa_setup"),
    path("accounts/mfa/disable/", mfa_disable_view, name="account_mfa_disable"),
    path("accounts/notifications/", notifications_view, name="notifications"),
    path(
        "accounts/notifications/mark-all-read/",
        notifications_mark_all_read_view,
        name="notifications_mark_all_read",
    ),
    path(
        "accounts/notifications/<int:notification_id>/toggle-read/",
        notification_toggle_read_view,
        name="notification_toggle_read",
    ),
    path("accounts/theme/toggle/", toggle_theme, name="toggle_theme"),
    path("u/<str:handle>/", profile_view, name="profile"),
    path("u/<str:handle>/follow/", toggle_follow, name="toggle_follow"),
    path("u/<str:handle>/block/", toggle_block, name="toggle_block"),
]
