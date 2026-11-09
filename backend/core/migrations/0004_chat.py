import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_document_chunks"),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conversations",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "conversation",
                "verbose_name_plural": "conversations",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seq", models.PositiveIntegerField()),
                (
                    "role",
                    models.CharField(
                        choices=[("user", "User"), ("assistant", "Assistant")], max_length=10
                    ),
                ),
                ("content", models.TextField(blank=True)),
                ("citations", models.JSONField(blank=True, default=list)),
                ("is_fallback", models.BooleanField(default=False)),
                ("fallback_reason", models.CharField(blank=True, default="", max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[("complete", "Complete"), ("partial", "Partial")],
                        default="complete",
                        max_length=10,
                    ),
                ),
                ("provider", models.CharField(blank=True, default="", max_length=20)),
                ("llm_model", models.CharField(blank=True, default="", max_length=100)),
                ("tokens_in", models.PositiveIntegerField(default=0)),
                ("tokens_out", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="core.conversation",
                    ),
                ),
            ],
            options={
                "verbose_name": "message",
                "verbose_name_plural": "messages",
                "ordering": ["seq"],
            },
        ),
        migrations.CreateModel(
            name="ChatUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("day", models.DateField()),
                ("count", models.PositiveIntegerField(default=0)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_usage",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "chat usage",
                "verbose_name_plural": "chat usage",
            },
        ),
        migrations.AddConstraint(
            model_name="message",
            constraint=models.UniqueConstraint(fields=("conversation", "seq"), name="unique_message_seq"),
        ),
        migrations.AddConstraint(
            model_name="chatusage",
            constraint=models.UniqueConstraint(fields=("account", "day"), name="unique_chat_usage_day"),
        ),
    ]
