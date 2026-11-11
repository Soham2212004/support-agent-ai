import uuid

import django.db.models.deletion
import django.utils.timezone
import pgvector.django
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_botsettings"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublishedBotVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("document_name", models.CharField(max_length=255)),
                ("document_hash", models.CharField(max_length=64)),
                ("document_text", models.TextField()),
                ("document_sections", models.JSONField(default=list)),
                ("document_metadata", models.JSONField(default=dict)),
                ("settings_snapshot", models.JSONField(default=dict)),
                ("embedding_model", models.CharField(max_length=100)),
                ("is_published", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="published_versions",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={"ordering": ["-version"]},
        ),
        migrations.AddConstraint(
            model_name="publishedbotversion",
            constraint=models.UniqueConstraint(fields=("account", "version"), name="unique_published_bot_version"),
        ),
        migrations.CreateModel(
            name="PublishedBotChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ordinal", models.PositiveIntegerField()),
                ("section_label", models.CharField(blank=True, max_length=200)),
                ("page_number", models.PositiveIntegerField(blank=True, null=True)),
                ("text", models.TextField()),
                ("embedding", pgvector.django.VectorField(dimensions=None)),
                ("embedding_model", models.CharField(max_length=100)),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="core.publishedbotversion",
                    ),
                ),
            ],
            options={"ordering": ["ordinal"]},
        ),
        migrations.AddConstraint(
            model_name="publishedbotchunk",
            constraint=models.UniqueConstraint(fields=("version", "ordinal"), name="unique_published_chunk_ordinal"),
        ),
        migrations.CreateModel(
            name="ClientApiKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key_hash", models.CharField(max_length=64, unique=True)),
                ("prefix", models.CharField(max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_keys",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AllowedWebsite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origin", models.CharField(max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="allowed_websites",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={"ordering": ["origin"]},
        ),
        migrations.AddConstraint(
            model_name="allowedwebsite",
            constraint=models.UniqueConstraint(fields=("account", "origin"), name="unique_allowed_website_origin"),
        ),
        migrations.CreateModel(
            name="PublicChatSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("visitor_name", models.CharField(max_length=150)),
                ("visitor_email", models.EmailField(max_length=254)),
                ("origin", models.CharField(max_length=300)),
                ("expires_at", models.DateTimeField()),
                ("is_generating", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="public_chat_sessions",
                        to="core.clientaccount",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="visitor_sessions",
                        to="core.publishedbotversion",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AddIndex(
            model_name="publicchatsession",
            index=models.Index(fields=["created_at"], name="public_session_created_idx"),
        ),
        migrations.CreateModel(
            name="PublicChatMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seq", models.PositiveIntegerField()),
                (
                    "role",
                    models.CharField(choices=[("user", "User"), ("assistant", "Assistant")], max_length=10),
                ),
                ("content", models.TextField(blank=True)),
                ("citations", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(default="complete", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="core.publicchatsession",
                    ),
                ),
            ],
            options={"ordering": ["seq"]},
        ),
        migrations.AddConstraint(
            model_name="publicchatmessage",
            constraint=models.UniqueConstraint(fields=("session", "seq"), name="unique_public_message_seq"),
        ),
        migrations.CreateModel(
            name="PublicMonthlyUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("month", models.DateField()),
                ("count", models.PositiveIntegerField(default=0)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="public_monthly_usage",
                        to="core.clientaccount",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="publicmonthlyusage",
            constraint=models.UniqueConstraint(fields=("account", "month"), name="unique_public_monthly_usage"),
        ),
        migrations.CreateModel(
            name="PublicRateLimitBucket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(max_length=30)),
                ("key", models.CharField(max_length=100)),
                ("minute", models.DateTimeField()),
                ("count", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.AddConstraint(
            model_name="publicratelimitbucket",
            constraint=models.UniqueConstraint(
                fields=("scope", "key", "minute"), name="unique_public_rate_bucket"
            ),
        ),
    ]
