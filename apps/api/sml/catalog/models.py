from django.db import models


class ModelOverride(models.Model):
    """Admin overrides on top of config/models.yaml: enable/disable, weight, and which media each
    detector runs on. Users never choose detectors; every job runs the admin's set for its media type.
    """

    model_id = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(null=True, blank=True, help_text="Empty = use models.yaml value.")
    weight = models.FloatField(null=True, blank=True)
    run_on_image = models.BooleanField(null=True, blank=True, help_text="Runs on every image job. Empty = models.yaml.")
    run_on_video = models.BooleanField(null=True, blank=True, help_text="Runs on every video job. Empty = models.yaml.")
    trial = models.BooleanField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.model_id
