from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_userbadge"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="first_post_share_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
