from apps.feeds.views import community_feed
from django.urls import path

from . import views

urlpatterns = [
    path("create/", views.create_community, name="create_community"),
    path("", views.community_discovery, name="community_discovery"),
    path("<slug:slug>/landing/", views.community_landing, name="community_landing"),
    path("<slug:slug>/share-card/", views.community_share_card, name="community_share_card"),
    path("<slug:slug>/invite/<str:token>/", views.community_invite, name="community_invite"),
    path("<slug:slug>/challenges/<int:challenge_id>/join/", views.join_community_challenge, name="community_challenge_join"),
    path("<slug:slug>/wiki/edit/", views.wiki_edit, name="community_wiki_edit_home"),
    path("<slug:slug>/wiki/<slug:page_slug>/edit/", views.wiki_edit, name="community_wiki_edit"),
    path("<slug:slug>/wiki/", views.wiki_page, name="community_wiki_home"),
    path("<slug:slug>/wiki/<slug:page_slug>/", views.wiki_page, name="community_wiki_page"),
    path("<slug:slug>/settings/", views.community_settings, name="community_settings"),
    path("<slug:slug>/", community_feed, name="community_detail"),
    path("<slug:slug>/toggle-join/", views.toggle_membership, name="toggle_membership"),
]
