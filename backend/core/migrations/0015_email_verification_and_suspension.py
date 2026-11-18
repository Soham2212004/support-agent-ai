from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_leads_and_budget"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientaccount",
            name="status",
            field=models.CharField(
                choices=[
                    ("unverified", "Unverified"),
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("suspended", "Suspended"),
                ],
                default="unverified",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="clientaccount",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="clientaccount",
            name="suspended_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="clientaccount",
            name="suspension_reason",
            field=models.TextField(blank=True, default=""),
        ),
    ]