import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_botsettings_extra"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("model_name", models.CharField(max_length=100)),
                ("object_id", models.CharField(blank=True, default="", max_length=50)),
                ("object_repr", models.CharField(blank=True, default="", max_length=255)),
                (
                    "action",
                    models.CharField(
                        choices=[("view", "Viewed"), ("view_list", "Viewed list")], max_length=20
                    ),
                ),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "staff_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "admin audit log",
                "verbose_name_plural": "admin audit logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="IndexingLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("started", "Started"), ("succeeded", "Succeeded"), ("failed", "Failed")],
                        default="started",
                        max_length=10,
                    ),
                ),
                ("chunk_count", models.PositiveIntegerField(default=0)),
                ("error", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="indexing_logs",
                        to="core.clientdocument",
                    ),
                ),
            ],
            options={
                "verbose_name": "indexing log",
                "verbose_name_plural": "indexing logs",
                "ordering": ["-started_at"],
            },
        ),
        migrations.CreateModel(
            name="PurgeHeartbeat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_name", models.CharField(max_length=50, unique=True)),
                ("last_run_at", models.DateTimeField()),
                ("last_result", models.CharField(blank=True, default="", max_length=255)),
            ],
            options={
                "verbose_name": "purge heartbeat",
                "verbose_name_plural": "purge heartbeats",
            },
        ),
    ]