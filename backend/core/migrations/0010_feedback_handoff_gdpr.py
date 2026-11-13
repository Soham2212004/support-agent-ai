import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_analytics_and_widget"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicchatmessage",
            name="feedback",
            field=models.CharField(
                choices=[("none", "No feedback"), ("up", "Thumbs up"), ("down", "Thumbs down")],
                default="none",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="feedback",
            field=models.CharField(
                choices=[("none", "No feedback"), ("up", "Thumbs up"), ("down", "Thumbs down")],
                default="none",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="HandoffRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("resolved", "Resolved")], default="open", max_length=10
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="handoff_requests",
                        to="core.clientaccount",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="handoff_requests",
                        to="core.publicchatsession",
                    ),
                ),
            ],
            options={
                "verbose_name": "handoff request",
                "verbose_name_plural": "handoff requests",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="VisitorDataRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("kind", models.CharField(choices=[("export", "Export"), ("delete", "Delete")], max_length=10)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending verification"),
                            ("completed", "Completed"),
                            ("expired", "Expired"),
                        ],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
            ],
            options={
                "verbose_name": "visitor data request",
                "verbose_name_plural": "visitor data requests",
                "ordering": ["-created_at"],
            },
        ),
    ]