from django.urls import path

from .views import search_quick_view, search_view

urlpatterns = [
    path("search/quick/", search_quick_view, name="search_quick"),
    path("search/", search_view, name="search"),
]
