from django.db import migrations, models

import apps.common.upload_paths


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_user_preferred_language"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="avatar",
            field=models.ImageField(blank=True, upload_to=apps.common.upload_paths.HashedUploadTo("original/avatars")),
        ),
        migrations.AlterField(
            model_name="user",
            name="banner",
            field=models.ImageField(blank=True, upload_to=apps.common.upload_paths.HashedUploadTo("original/profile_banners")),
        ),
    ]
