from django.db import models


class TrialUsage(models.Model):
    """Daily guest-trial counters per device cookie and per (hashed, truncated) IP."""

    class Kind(models.TextChoices):
        DEVICE = "device", "Device"
        IP = "ip", "IP"

    kind = models.CharField(max_length=8, choices=Kind.choices)
    identifier = models.CharField(max_length=64)
    date = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kind", "identifier", "date"], name="uniq_trial_usage")]
