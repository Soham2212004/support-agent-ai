from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_pipeline_setting"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientaccount",
            name="token_version",
            field=models.PositiveIntegerField(default=1),
        ),
    ]