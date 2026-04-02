from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moderation", "0003_modmail_modmailmessage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="modaction",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("remove_post", "Remove Post"),
                    ("approve_post", "Approve Post"),
                    ("remove_comment", "Remove Comment"),
                    ("approve_comment", "Approve Comment"),
                    ("lock_post", "Lock Post"),
                    ("unlock_post", "Unlock Post"),
                    ("sticky_post", "Sticky Post"),
                    ("unsticky_post", "Unsticky Post"),
                    ("ban_user", "Ban User"),
                    ("unban_user", "Unban User"),
                    ("agent_flag", "Agent Flag"),
                    ("agent_remove", "Agent Remove"),
                    ("agent_warn", "Agent Warn"),
                ],
                max_length=30,
            ),
        ),
    ]
