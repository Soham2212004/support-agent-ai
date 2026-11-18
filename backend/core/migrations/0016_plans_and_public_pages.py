import django.db.models.deletion
from django.db import migrations, models


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("core", "Plan")
    ClientAccount = apps.get_model("core", "ClientAccount")

    free, _ = Plan.objects.get_or_create(
        key="free",
        defaults={
            "name": "Free",
            "monthly_messages": 200,
            "daily_test_messages": 50,
            "max_documents": 1,
            "max_faq_entries": 50,
        },
    )
    Plan.objects.get_or_create(
        key="pro",
        defaults={
            "name": "Pro",
            "monthly_messages": 5000,
            "daily_test_messages": 50,
            "max_documents": 1,
            "max_faq_entries": 200,
        },
    )
    Plan.objects.get_or_create(
        key="internal",
        defaults={
            "name": "Internal",
            "monthly_messages": 3000,
            "daily_test_messages": 50,
            "max_documents": 1,
            "max_faq_entries": 200,
        },
    )
    ClientAccount.objects.filter(plan__isnull=True).update(plan=free)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_email_verification_and_suspension"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(choices=[("free", "Free"), ("pro", "Pro"), ("internal", "Internal")], max_length=10, unique=True)),
                ("name", models.CharField(max_length=50)),
                ("monthly_messages", models.PositiveIntegerField()),
                ("daily_test_messages", models.PositiveIntegerField(default=50)),
                ("max_documents", models.PositiveIntegerField(default=1)),
                ("max_faq_entries", models.PositiveIntegerField(default=50)),
            ],
            options={"verbose_name": "plan", "verbose_name_plural": "plans", "ordering": ["monthly_messages"]},
        ),
        migrations.AddField(
            model_name="clientaccount",
            name="plan",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="accounts", to="core.plan",
            ),
        ),
        migrations.CreateModel(
            name="UpgradeRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("open", "Open"), ("done", "Done"), ("declined", "Declined")], default="open", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("handled_at", models.DateTimeField(blank=True, null=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="upgrade_requests", to="core.clientaccount")),
                ("requested_plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="upgrade_requests", to="core.plan")),
            ],
            options={"verbose_name": "upgrade request", "verbose_name_plural": "upgrade requests", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ContactMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("email", models.EmailField(max_length=254)),
                ("message", models.TextField(max_length=2000)),
                ("handled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "contact message", "verbose_name_plural": "contact messages", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="UsageWarningLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("month", models.DateField()),
                ("level", models.PositiveIntegerField()),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="usage_warnings", to="core.clientaccount")),
            ],
        ),
        migrations.AddConstraint(
            model_name="usagewarninglog",
            constraint=models.UniqueConstraint(fields=("account", "month", "level"), name="unique_usage_warning"),
        ),
        migrations.RunPython(seed_plans, noop),
    ]