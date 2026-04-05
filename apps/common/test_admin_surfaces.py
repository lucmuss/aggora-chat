import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.communities.models import Community
from apps.posts.models import Post


User = get_user_model()


def make_superuser():
    user = User.objects.create_superuser(
        username="adminuser",
        email="admin@example.com",
        password="password123",
        handle="adminuser",
    )
    user.mfa_totp_enabled = True
    user.mfa_totp_secret = "TESTSECRET123456"
    user.save(update_fields=["mfa_totp_enabled", "mfa_totp_secret"])
    return user


@pytest.mark.django_db
class TestAdminSurfaces:
    def test_admin_changelist_add_and_change_pages_render(self):
        admin_user = make_superuser()
        client = Client()
        client.force_login(admin_user)
        community = Community.objects.create(
            name="Admin Community",
            slug="admin-community",
            title="Admin Community",
            description="Admin test",
            creator=admin_user,
        )
        post = Post.objects.create(
            community=community,
            author=admin_user,
            post_type=Post.PostType.TEXT,
            title="Admin Post",
            body_md="Body",
        )

        urls = [
            reverse("admin:accounts_user_changelist"),
            reverse("admin:accounts_user_add"),
            reverse("admin:accounts_user_change", args=[admin_user.pk]),
            reverse("admin:communities_community_changelist"),
            reverse("admin:communities_community_change", args=[community.pk]),
            reverse("admin:posts_post_changelist"),
            reverse("admin:posts_post_change", args=[post.pk]),
        ]

        for url in urls:
            response = client.get(url)
            assert response.status_code == 200

    def test_user_admin_actions_verify_and_revoke_agent(self):
        admin_user = make_superuser()
        agent = User.objects.create_user(
            username="agent-admin",
            email="agent-admin@example.com",
            password="password123",
            handle="agent_admin",
            is_agent=True,
            agent_verified=False,
        )
        client = Client()
        client.force_login(admin_user)

        verify_response = client.post(
            reverse("admin:accounts_user_changelist"),
            {
                "action": "verify_agent",
                "_selected_action": [agent.pk],
                "index": 0,
            },
        )
        agent.refresh_from_db()
        assert verify_response.status_code == 302
        assert agent.agent_verified is True

        revoke_response = client.post(
            reverse("admin:accounts_user_changelist"),
            {
                "action": "revoke_agent",
                "_selected_action": [agent.pk],
                "index": 0,
            },
        )
        agent.refresh_from_db()
        assert revoke_response.status_code == 302
        assert agent.agent_verified is False

    def test_admin_search_and_filters_render_for_registered_models(self):
        admin_user = make_superuser()
        client = Client()
        client.force_login(admin_user)
        community = Community.objects.create(
            name="Searchable Community",
            slug="searchable-community",
            title="Searchable Community",
            description="Admin search test",
            creator=admin_user,
        )
        Post.objects.create(
            community=community,
            author=admin_user,
            post_type=Post.PostType.TEXT,
            title="Searchable Post",
            body_md="Body",
            is_removed=False,
        )

        user_response = client.get(reverse("admin:accounts_user_changelist"), {"q": "adminuser"})
        community_response = client.get(reverse("admin:communities_community_changelist"), {"q": "searchable"})
        post_response = client.get(reverse("admin:posts_post_changelist"), {"q": "Searchable"})

        assert user_response.status_code == 200
        assert community_response.status_code == 200
        assert post_response.status_code == 200
        assert "adminuser" in user_response.content.decode()
        assert "Searchable Community" in community_response.content.decode()
        assert "Searchable Post" in post_response.content.decode()
