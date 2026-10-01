from django.db import models


class ModelOverride(models.Model):
    """Admin overrides on top of config/models.yaml: enable/disable, weight, result group (family),
    which media each detector runs on and whether users see its heatmap. Users never choose
    detectors; every job runs the admin's set for its media type.
    """

    class Family(models.TextChoices):
        DEEPFAKE = "deepfake", "Face swap (deepfake)"
        AI_GENERATED = "ai_generated", "AI-generated"

    model_id = models.CharField(max_length=64, unique=True)
    family = models.CharField(max_length=16, choices=Family.choices, blank=True, default="",
                              help_text="Result group the detector counts towards. Empty = models.yaml.")
    enabled = models.BooleanField(null=True, blank=True, help_text="Empty = use models.yaml value.")
    weight = models.FloatField(null=True, blank=True)
    run_on_image = models.BooleanField(null=True, blank=True, help_text="Runs on every image job. Empty = models.yaml.")
    run_on_video = models.BooleanField(null=True, blank=True, help_text="Runs on every video job. Empty = models.yaml.")
    trial = models.BooleanField(null=True, blank=True)
    show_heatmap = models.BooleanField(
        null=True, blank=True, help_text="Users see this detector's heatmap (one image). Empty = models.yaml.")
    authentic_boost = models.FloatField(
        null=True, blank=True, help_text="Weight multiplier when the detector says authentic. Empty = models.yaml.")
    authentic_counts_in_all = models.BooleanField(
        null=True, blank=True, help_text="An authentic answer also counts in the other analysis. Empty = models.yaml.")
    note = models.CharField(max_length=255, blank=True, default="")
    # Published figures the administrator enters for comparison (Admin → Models); never shown to users.
    benchmark_accuracy = models.FloatField(null=True, blank=True, help_text="0–1, e.g. from the paper.")
    benchmark_auc = models.FloatField(null=True, blank=True, help_text="0–1.")
    benchmark_dataset = models.CharField(max_length=120, blank=True, default="",
                                         help_text="Where the benchmark figures come from, e.g. Celeb-DF v2.")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.model_id
