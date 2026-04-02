from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("communities", "0002_communitywikipage"),
        ("accounts", "0003_user_onboarding_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="community",
            name="best_of_html",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="community",
            name="best_of_md",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="community",
            name="faq_html",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="community",
            name="faq_md",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="community",
            name="landing_intro_html",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="community",
            name="landing_intro_md",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="community",
            name="seo_description",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.CreateModel(
            name="CommunityInvite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, max_length=32, unique=True)),
                ("usage_count", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("community", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invites", to="communities.community")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="community_invites", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="CommunityChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("prompt_md", models.TextField()),
                ("prompt_html", models.TextField(blank=True)),
                ("share_text", models.CharField(blank=True, max_length=200)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("is_featured", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("community", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="challenges", to="communities.community")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-starts_at", "-created_at"]},
        ),
    ]
