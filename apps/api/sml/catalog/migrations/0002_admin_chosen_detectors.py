# Users no longer pick detectors: the admin chooses which run on images and on videos.

from django.db import migrations, models


def copy_default_selected(apps, schema_editor):  # type: ignore[no-untyped-def]
    """An admin's old "selected by default" override becomes "runs on every job" for both media."""
    ModelOverride = apps.get_model("catalog", "ModelOverride")
    for o in ModelOverride.objects.exclude(default_selected=None):
        o.run_on_image = o.run_on_video = o.default_selected
        o.save(update_fields=["run_on_image", "run_on_video"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeloverride",
            name="run_on_image",
            field=models.BooleanField(blank=True, help_text="Runs on every image job. Empty = models.yaml.", null=True),
        ),
        migrations.AddField(
            model_name="modeloverride",
            name="run_on_video",
            field=models.BooleanField(blank=True, help_text="Runs on every video job. Empty = models.yaml.", null=True),
        ),
        migrations.RunPython(copy_default_selected, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="modeloverride",
            name="default_selected",
        ),
    ]
