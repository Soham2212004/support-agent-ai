import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_chat"),
    ]

    operations = [
        migrations.CreateModel(
            name="BotSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, default="", max_length=100)),
                (
                    "greeting",
                    models.TextField(blank=True, default="Hello! How can I help you today?"),
                ),
                (
                    "tone",
                    models.CharField(
                        choices=[("friendly", "Friendly"), ("professional", "Professional"), ("concise", "Concise")],
                        default="friendly",
                        max_length=20,
                    ),
                ),
                ("custom_instructions", models.TextField(blank=True, default="")),
                (
                    "fallback_message",
                    models.TextField(
                        blank=True,
                        default="I couldn't find the answer to that in your document. Try rephrasing your question, or ask about something the document covers.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bot_settings",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "bot settings",
                "verbose_name_plural": "bot settings",
            },
        ),
    ]
