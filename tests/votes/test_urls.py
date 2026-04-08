from django.urls import resolve, reverse

from apps.votes import views


def test_vote_urls_reverse_and_resolve_correctly():
    cases = [
        ("vote", {}, views.vote),
        ("give_award", {}, views.give_award),
        ("toggle_save", {"post_id": 7}, views.toggle_save),
    ]

    for name, kwargs, expected_view in cases:
        path = reverse(name, kwargs=kwargs)
        match = resolve(path)
        assert match.func == expected_view
