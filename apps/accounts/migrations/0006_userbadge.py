from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_rename_accounts_not_user_id_97fcb7_idx_accounts_no_user_id_b29cd4_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserBadge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "code",
                    models.CharField(
                        choices=[
                            ("profile_ready", "Profile Ready"),
                            ("first_steps", "First Steps"),
                            ("first_post", "First Post"),
                            ("first_comment", "First Comment"),
                            ("first_referral", "First Referral"),
                            ("crew_builder", "Crew Builder"),
                        ],
                        max_length=32,
                    ),
                ),
                ("title", models.CharField(max_length=80)),
                ("description", models.CharField(blank=True, max_length=160)),
                ("icon", models.CharField(default="★", max_length=8)),
                ("awarded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="badges", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-awarded_at"]},
        ),
        migrations.AddConstraint(
            model_name="userbadge",
            constraint=models.UniqueConstraint(fields=("user", "code"), name="accounts_unique_user_badge_code"),
        ),
    ]
