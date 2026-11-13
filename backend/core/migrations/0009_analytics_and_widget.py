from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_audit_indexing_purge"),
    ]

    operations = [
        migrations.AddField(
            model_name="botsettings",
            name="widget_mode",
            field=models.CharField(
                choices=[("default", "Default widget"), ("custom", "Custom integration")],
                default="default",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="publicchatmessage",
            name="is_fallback",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="publicchatmessage",
            name="fallback_reason",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]