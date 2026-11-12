from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_publishing_public_chat"),
    ]

    operations = [
        migrations.AddField(
            model_name="botsettings",
            name="similarity_threshold",
            field=models.FloatField(default=0.75),
        ),
        migrations.AddField(
            model_name="botsettings",
            name="show_citations",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="botsettings",
            name="max_answer_length",
            field=models.CharField(
                choices=[("short", "Short"), ("standard", "Standard"), ("detailed", "Detailed")],
                default="standard",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="botsettings",
            name="starter_questions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="botsettings",
            name="escalation_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="botsettings",
            name="avatar_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]