from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_plans_and_public_pages"),
    ]

    operations = [
        migrations.AddField(
            model_name="botsettings",
            name="pipeline",
            field=models.CharField(
                choices=[
                    ("baseline", "Baseline (plain Python RAG)"),
                    ("enhanced", "Enhanced (LangGraph, reranker, injection guard)"),
                ],
                default="baseline",
                max_length=10,
            ),
        ),
    ]