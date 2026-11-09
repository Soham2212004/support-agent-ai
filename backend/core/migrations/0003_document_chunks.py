import django.db.models.deletion
import pgvector.django
from django.db import migrations, models
from pgvector.django import VectorExtension


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_clientdocument"),
    ]

    operations = [
        VectorExtension(),
        migrations.AddField(
            model_name="clientdocument",
            name="index_status",
            field=models.CharField(
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
        migrations.AddField(
            model_name="clientdocument",
            name="index_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="clientdocument",
            name="chunk_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="clientdocument",
            name="index_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="clientdocument",
            name="indexed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ordinal", models.PositiveIntegerField()),
                ("section_label", models.CharField(blank=True, max_length=200)),
                ("page_number", models.PositiveIntegerField(blank=True, null=True)),
                ("text", models.TextField()),
                ("char_count", models.PositiveIntegerField()),
                ("embedding", pgvector.django.VectorField(dimensions=None)),
                ("embedding_model", models.CharField(max_length=100)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="core.clientaccount",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="core.clientdocument",
                    ),
                ),
            ],
            options={
                "verbose_name": "document chunk",
                "verbose_name_plural": "document chunks",
            },
        ),
        migrations.AddConstraint(
            model_name="documentchunk",
            constraint=models.UniqueConstraint(fields=("document", "ordinal"), name="unique_chunk_ordinal"),
        ),
    ]