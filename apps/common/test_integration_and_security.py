import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.communities.models import Community, CommunityMembership
from apps.moderation.models import ModAction, ModQueueItem
from apps.posts.models import Post
from apps.votes.models import SavedPost, Vote
from apps.common.markdown import render_markdown

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "integration_user"),
        "email": overrides.pop("email", "integration_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "integration_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


@pytest.mark.django_db
class TestIntegrationAndSecurity:
    def test_content_workflow_create_post_comment_vote_and_save(self, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        user = make_user(username="workflow", email="workflow@example.com", handle="workflow")
        voter = make_user(username="workflowvoter", email="workflowvoter@example.com", handle="workflowvoter")
        client = Client()
        client.force_login(user)

        create_community_response = client.post(
            reverse("create_community"),
            {
                "name": "Workflow Community",
                "slug": "workflow-community",
                "title": "Workflow Community",
                "description": "Created in workflow test",
                "sidebar_md": "Welcome",
                "community_type": Community.CommunityType.PUBLIC,
            },
        )
        community = Community.objects.get(slug="workflow-community")

        create_post_response = client.post(
            reverse("create_post", kwargs={"community_slug": community.slug}),
            {
                "post_type": Post.PostType.TEXT,
                "title": "Workflow Post",
                "body_md": "Hello **world**",
            },
        )
        post = Post.objects.get(title="Workflow Post")

        comment_response = client.post(
            reverse("create_comment", kwargs={"post_id": post.id}),
            {"body_md": "First reply"},
        )
        save_response = client.post(reverse("toggle_save", kwargs={"post_id": post.id}))
        voter_client = Client()
        voter_client.force_login(voter)
        vote_response = voter_client.post(reverse("vote"), {"post_id": post.id, "value": Vote.VoteType.UPVOTE})

        assert create_community_response.status_code == 302
        assert create_post_response.status_code == 302
        assert comment_response.status_code == 302
        assert vote_response.status_code == 200
        assert save_response.status_code == 200
        assert SavedPost.objects.filter(user=user, post=post).exists() is True
        assert Vote.objects.filter(user=voter, post=post).count() == 1

    def test_moderation_workflow_report_then_remove_updates_queue_and_log(self):
        owner = make_user(username="ownerflow", email="ownerflow@example.com", handle="ownerflow")
        owner.mfa_totp_enabled = True
        owner.save(update_fields=["mfa_totp_enabled"])
        member = make_user(username="memberflow", email="memberflow@example.com", handle="memberflow")
        reporter = make_user(username="reporterflow", email="reporterflow@example.com", handle="reporterflow")
        community = Community.objects.create(
            name="Moderation Workflow",
            slug="moderation-workflow",
            title="Moderation Workflow",
            description="Moderation flow tests",
            creator=owner,
        )
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        CommunityMembership.objects.create(user=member, community=community, role=CommunityMembership.Role.MEMBER)
        post = Post.objects.create(
            community=community,
            author=member,
            post_type=Post.PostType.TEXT,
            title="Flag this",
            body_md="Needs review",
        )
        reporter_client = Client()
        reporter_client.force_login(reporter)
        report_response = reporter_client.post(reverse("report_content"), {"post_id": post.id, "reason": "spam"})
        owner_client = Client()
        owner_client.force_login(owner)
        queue_response = owner_client.get(reverse("mod_queue", kwargs={"community_slug": community.slug}))
        action_response = owner_client.post(
            reverse("mod_action", kwargs={"community_slug": community.slug}),
            {
                "post_id": post.id,
                "action_type": ModAction.ActionType.REMOVE_POST,
                "reason_code": "spam",
                "reason_text": "Confirmed spam",
            },
        )
        log_response = owner_client.get(reverse("mod_log", kwargs={"community_slug": community.slug}))

        post.refresh_from_db()
        queue_item = ModQueueItem.objects.get(post=post)
        assert report_response.status_code == 302
        assert queue_response.status_code == 200
        assert action_response.status_code == 302
        assert log_response.status_code == 200
        assert post.is_removed is True
        assert queue_item.status == ModQueueItem.Status.REMOVED
        assert ModAction.objects.filter(target_post=post, action_type=ModAction.ActionType.REMOVE_POST).exists()

    def test_start_with_friends_redirects_to_first_post_destination(self):
        user = make_user(username="starter", email="starter@example.com", handle="starter")
        community = Community.objects.create(
            name="Starter Community",
            slug="starter-community",
            title="Starter Community",
            description="Onboarding target",
            creator=user,
        )
        client = Client()
        client.force_login(user)

        response = client.post(
            reverse("start_with_friends"),
            {
                "display_name": "Starter",
                "bio": "Ready to post",
                "communities": [community.pk],
                "first_post_community": community.pk,
                "friend_emails": "",
                "first_contribution_type": "post",
            },
        )

        user.refresh_from_db()
        assert response.status_code == 302
        assert reverse("create_post", kwargs={"community_slug": community.slug}) in response.url
        assert user.onboarding_completed is True

    def test_private_community_blocks_outsider_access_and_save_attempts(self):
        owner = make_user(username="privateowner", email="privateowner@example.com", handle="privateowner")
        outsider = make_user(username="outsidersec", email="outsidersec@example.com", handle="outsidersec")
        community = Community.objects.create(
            name="Private Community",
            slug="private-community",
            title="Private Community",
            description="Private tests",
            creator=owner,
            community_type=Community.CommunityType.PRIVATE,
        )
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        post = Post.objects.create(
            community=community,
            author=owner,
            post_type=Post.PostType.TEXT,
            title="Private Post",
            body_md="Hidden",
        )
        client = Client()
        client.force_login(outsider)

        detail_response = client.get(reverse("community_detail", kwargs={"slug": community.slug}))
        save_response = client.post(reverse("toggle_save", kwargs={"post_id": post.id}))

        assert detail_response.status_code == 403
        assert save_response.status_code == 403
        assert SavedPost.objects.filter(user=outsider, post=post).exists() is False

    def test_post_creation_sanitizes_markdown_xss_payload(self):
        user = make_user(username="xssuser", email="xssuser@example.com", handle="xssuser")
        community = Community.objects.create(
            name="XSS Community",
            slug="xss-community",
            title="XSS Community",
            description="XSS tests",
            creator=user,
        )
        client = Client()
        client.force_login(user)

        response = client.post(
            reverse("create_post", kwargs={"community_slug": community.slug}),
            {
                "post_type": Post.PostType.TEXT,
                "title": "Unsafe markdown",
                "body_md": "<script>alert(1)</script> **safe**",
            },
        )
        post = Post.objects.get(title="Unsafe markdown")

        assert response.status_code == 302
        assert "<script>" not in post.body_html
        assert "<strong>safe</strong>" in post.body_html

    def test_render_markdown_linkifies_existing_user_mentions(self):
        mentioned = make_user(username="ariane", email="ariane@example.com", handle="ariane")

        html = render_markdown("Hello @ariane and `@ariane`")

        assert f'href="/u/{mentioned.handle}/"' in html
        assert "<code>@ariane</code>" in html

    def test_post_create_requires_csrf_token_when_csrf_checks_enabled(self):
        user = make_user(username="csrfuser", email="csrfuser@example.com", handle="csrfuser")
        community = Community.objects.create(
            name="CSRF Community",
            slug="csrf-community",
            title="CSRF Community",
            description="CSRF tests",
            creator=user,
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        response = client.post(
            reverse("create_post", kwargs={"community_slug": community.slug}),
            {
                "post_type": Post.PostType.TEXT,
                "title": "Blocked by CSRF",
                "body_md": "Missing token",
            },
        )

        assert response.status_code == 403
