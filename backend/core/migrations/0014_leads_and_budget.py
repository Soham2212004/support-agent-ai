import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_handoff_full_flow"),
    ]

    operations = [
        migrations.CreateModel(
            name="Lead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("email", models.EmailField(max_length=254)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("conversation_count", models.PositiveIntegerField(default=1)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="leads", to="core.clientaccount"
                    ),
                ),
            ],
            options={"verbose_name": "lead", "verbose_name_plural": "leads", "ordering": ["-last_seen_at"]},
        ),
        migrations.AddConstraint(
            model_name="lead",
            constraint=models.UniqueConstraint(fields=("account", "email"), name="unique_lead_per_account_email"),
        ),
        migrations.CreateModel(
            name="LlmSpend",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("input_tokens", models.PositiveBigIntegerField(default=0)),
                ("output_tokens", models.PositiveBigIntegerField(default=0)),
                ("estimated_cost", models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ("budget_limit", models.DecimalField(decimal_places=2, default=5, max_digits=10)),
                ("paused", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "LLM daily spend",
                "verbose_name_plural": "LLM daily spend",
                "ordering": ["-date"],
            },
        ),
    ]