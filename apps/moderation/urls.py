from django.urls import path

from . import views

urlpatterns = [
    path("report/", views.report_content, name="report_content"),
    path("mod/<slug:community_slug>/queue/", views.mod_queue, name="mod_queue"),
    path("mod/<slug:community_slug>/log/", views.mod_log, name="mod_log"),
    path("mod/<slug:community_slug>/mail/", views.mod_mail_list, name="mod_mail_list"),
    path("mod/<slug:community_slug>/mail/new/", views.mod_mail_create, name="mod_mail_create"),
    path("mod/<slug:community_slug>/mail/<int:thread_id>/", views.mod_mail_thread, name="mod_mail_thread"),
    path("mod/<slug:community_slug>/removal-reasons/", views.removal_reasons_manage, name="removal_reasons_manage"),
    path("mod/<slug:community_slug>/action/", views.mod_action, name="mod_action"),
    path("mod/<slug:community_slug>/ban/", views.ban_user, name="ban_user"),
]
