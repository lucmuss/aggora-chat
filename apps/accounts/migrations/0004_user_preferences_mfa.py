from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_onboarding_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_notifications_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="mfa_enabled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="mfa_totp_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="mfa_totp_secret",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="user",
            name="notify_on_challenges",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="notify_on_follows",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="notify_on_replies",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="profile_visibility",
            field=models.CharField(
                choices=[("public", "Public"), ("members", "Signed-in members"), ("private", "Private")],
                default="public",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="push_notifications_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
