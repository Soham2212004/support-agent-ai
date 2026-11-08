import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_filename", models.CharField(max_length=255)),
                ("file_type", models.CharField(max_length=10)),
                ("size_bytes", models.PositiveIntegerField()),
                ("content_hash", models.CharField(max_length=64)),
                ("file_path", models.CharField(max_length=500)),
                ("extracted_text", models.TextField()),
                ("sections", models.JSONField(default=list)),
                ("page_count", models.PositiveIntegerField(blank=True, null=True)),
                ("word_count", models.PositiveIntegerField(default=0)),
                ("char_count", models.PositiveIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document",
                        to="core.clientaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "client document",
                "verbose_name_plural": "client documents",
                "ordering": ["-uploaded_at"],
            },
        ),
    ]