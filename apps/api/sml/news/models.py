from django.db import models

from sml.core.models import TimeStampedModel


class NewsCase(TimeStampedModel):
    """Inputs of a multimedia news verification case (mirrors the MV26 case JSON)."""

    job = models.OneToOneField("jobs.Job", on_delete=models.CASCADE, related_name="news_case")
    title = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, default="")
    category = models.CharField(max_length=100, blank=True, default="")
    violence_level = models.CharField(max_length=50, blank=True, default="")
    description = models.TextField(blank=True, default="")
    social_media_link = models.URLField(max_length=1000, blank=True, default="")
    media = models.ManyToManyField("media.MediaObject", blank=True, related_name="news_cases")

    def as_input(self) -> dict:
        return {"title": self.title, "location": self.location, "category": self.category,
                "violence level": self.violence_level, "description": self.description,
                "social media link": self.social_media_link}
