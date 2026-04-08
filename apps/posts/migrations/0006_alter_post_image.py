from django.db import migrations, models

import apps.common.upload_paths


class Migration(migrations.Migration):
    dependencies = [
        ("posts", "0005_comment_award_count_post_award_count"),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="image",
            field=models.ImageField(blank=True, upload_to=apps.common.upload_paths.HashedUploadTo("original/post_images")),
        ),
    ]
