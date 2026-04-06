from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0012_alter_notification_notification_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="preferred_language",
            field=models.CharField(
                choices=[("en", "English")],
                default="en",
                max_length=8,
            ),
        ),
    ]
