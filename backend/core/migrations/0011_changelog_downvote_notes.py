import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_feedback_handoff_gdpr"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChangelogEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("body", models.TextField()),
                ("published_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "changelog entry",
                "verbose_name_plural": "changelog entries",
                "ordering": ["-published_at"],
            },
        ),
        migrations.CreateModel(
            name="DownvoteNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key_hash", models.CharField(max_length=64)),
                ("question", models.TextField(blank=True, default="")),
                ("note", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Needs attention"), ("resolved", "Resolved")],
                        default="open",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="downvote_notes",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "downvote note",
                "verbose_name_plural": "downvote notes",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="downvotenote",
            constraint=models.UniqueConstraint(fields=("account", "key_hash"), name="unique_downvote_note"),
        ),
    ]