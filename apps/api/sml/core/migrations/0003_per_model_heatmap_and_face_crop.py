# Face cropping for long-form scans is set per detector, not once for all of them.

from django.db import migrations, models


def keep_existing_choice(apps, schema_editor):  # type: ignore[no-untyped-def]
    """A global choice made earlier applies to the detector that was selected at the time."""
    PlatformSettings = apps.get_model("core", "PlatformSettings")
    for cfg in PlatformSettings.objects.exclude(long_video_face_crop=None).exclude(long_video_model=""):
        cfg.long_video_face_crops = {cfg.long_video_model: cfg.long_video_face_crop}
        cfg.save(update_fields=["long_video_face_crops"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_admin_chosen_detectors"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="long_video_face_crops",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Per long-form detector: crop to faces before scoring ({model_id: true|false}). "
                          "Missing = the detector's default.",
            ),
        ),
        migrations.RunPython(keep_existing_choice, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="platformsettings",
            name="long_video_face_crop",
        ),
    ]
