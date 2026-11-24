from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_token_revocation"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientdocument",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="faqentry",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]