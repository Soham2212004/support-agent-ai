from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ClientAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("company_name", models.CharField(max_length=200)),
                ("role", models.CharField(max_length=150)),
                ("company_description", models.TextField()),
                ("website", models.URLField(max_length=300)),
                ("reason", models.TextField()),
                ("password", models.CharField(max_length=128)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("rejected_at", models.DateTimeField(blank=True, editable=False, null=True)),
            ],
            options={
                "verbose_name": "client request",
                "verbose_name_plural": "client requests",
                "ordering": ["-created_at"],
            },
        ),
    ]