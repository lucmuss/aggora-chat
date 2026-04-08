from django.db import migrations, models

import apps.common.upload_paths


class Migration(migrations.Migration):
    dependencies = [
        ("communities", "0004_communitychallengeparticipation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="community",
            name="banner",
            field=models.ImageField(blank=True, upload_to=apps.common.upload_paths.HashedUploadTo("original/community_banners")),
        ),
        migrations.AlterField(
            model_name="community",
            name="icon",
            field=models.ImageField(blank=True, upload_to=apps.common.upload_paths.HashedUploadTo("original/community_icons")),
        ),
    ]
