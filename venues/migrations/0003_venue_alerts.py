# Hand-written: a unique field with a random default needs three steps, or
# every existing venue would be given the same topic (Django evaluates a
# callable default once per AddField).

from django.db import migrations, models

import venues.models


def fill_topics(apps, schema_editor):
    Venue = apps.get_model("venues", "Venue")
    for venue in Venue.objects.filter(ntfy_topic__isnull=True):
        venue.ntfy_topic = venues.models.new_ntfy_topic()
        venue.save(update_fields=["ntfy_topic"])


class Migration(migrations.Migration):
    dependencies = [
        ("venues", "0002_venue_allow_political_ads"),
    ]

    operations = [
        migrations.AddField(
            model_name="venue",
            name="notify_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="venue",
            name="email_alerts",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="venue",
            name="push_alerts",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="venue",
            name="ntfy_topic",
            field=models.CharField(editable=False, max_length=64, null=True),
        ),
        migrations.RunPython(fill_topics, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="venue",
            name="ntfy_topic",
            field=models.CharField(
                default=venues.models.new_ntfy_topic, editable=False, max_length=64, unique=True
            ),
        ),
    ]
