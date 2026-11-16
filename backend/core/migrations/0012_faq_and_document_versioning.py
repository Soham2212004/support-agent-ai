import django.db.models.deletion
import pgvector.django
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_changelog_downvote_notes"),
    ]

    operations = [
        migrations.CreateModel(
            name="FAQEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.CharField(max_length=300)),
                ("answer", models.TextField(max_length=2000)),
                ("embedding", pgvector.django.VectorField(blank=True, dimensions=None, null=True)),
                ("embedding_model", models.CharField(blank=True, default="", max_length=100)),
                (
                    "index_status",
                    models.CharField(
                        choices=[
                            ("pending", "Not indexed"),
                            ("processing", "Processing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=12,
                    ),
                ),
                ("index_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="faq_entries",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "FAQ entry",
                "verbose_name_plural": "FAQ entries",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="DocumentArchive",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_filename", models.CharField(max_length=255)),
                ("file_type", models.CharField(max_length=10)),
                ("size_bytes", models.PositiveIntegerField()),
                ("word_count", models.PositiveIntegerField(default=0)),
                ("chunk_count", models.PositiveIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField()),
                ("archived_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_archive",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "document version (archived)",
                "verbose_name_plural": "document versions (archived)",
                "ordering": ["-archived_at"],
            },
        ),
    ]