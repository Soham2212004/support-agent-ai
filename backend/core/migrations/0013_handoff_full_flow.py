from django.db import migrations, models


def rename_open_to_waiting(apps, schema_editor):
    HandoffRequest = apps.get_model("core", "HandoffRequest")
    HandoffRequest.objects.filter(status="open").update(status="waiting")


def rename_waiting_to_open(apps, schema_editor):
    HandoffRequest = apps.get_model("core", "HandoffRequest")
    HandoffRequest.objects.filter(status="waiting").update(status="open")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_faq_and_document_versioning"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicchatsession",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active (bot answers)"),
                    ("waiting_human", "Waiting for a human"),
                    ("human_replied", "Human replied"),
                    ("closed", "Closed"),
                ],
                default="active",
                max_length=15,
            ),
        ),
        migrations.AlterField(
            model_name="publicchatmessage",
            name="role",
            field=models.CharField(
                choices=[
                    ("user", "User"),
                    ("assistant", "Assistant"),
                    ("human", "Human"),
                    ("system", "System"),
                ],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="handoffrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("waiting", "Waiting"),
                    ("replied", "Replied"),
                    ("resolved", "Resolved"),
                    ("expired", "Expired"),
                ],
                default="waiting",
                max_length=10,
            ),
        ),
        migrations.RunPython(rename_open_to_waiting, rename_waiting_to_open),
        migrations.AddField(
            model_name="handoffrequest",
            name="reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="handoffrequest",
            name="replied_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]