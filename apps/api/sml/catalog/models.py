from django.db import models


class ModelOverride(models.Model):
    """Admin overrides on top of config/models.yaml (enable/disable, weight, drain)."""

    model_id = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(null=True, blank=True, help_text="Empty = use models.yaml value.")
    weight = models.FloatField(null=True, blank=True)
    default_selected = models.BooleanField(null=True, blank=True)
    trial = models.BooleanField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.model_id
