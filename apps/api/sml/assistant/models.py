"""Conversations with the assistant (owner, 2026-10-02).

A conversation belongs to one user. A user message may carry media: sending it starts a normal
detection job per file, at the normal price (chatting itself is free). Assistant messages are written
by the language model and filtered so they never describe how the analysis works
(sml.core.confidential); the model is only ever told the results as users see them.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from sml.core.models import TimeStampedModel


class Conversation(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"])]

    def __str__(self) -> str:
        return self.title or str(self.pk)


class Message(TimeStampedModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    class Status(models.TextChoices):
        COMPLETE = "complete", "Complete"
        STOPPED = "stopped", "Stopped by the user"
        FAILED = "failed", "Failed"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETE)
    content = models.TextField(blank=True, default="")
    # A user message's attachments and its analyses — new ones it started, or earlier results it brought
    # into the conversation ("Ask the assistant" on a result page); an assistant summary's analyses.
    media = models.ManyToManyField("media.MediaObject", blank=True, related_name="assistant_messages")
    jobs = models.ManyToManyField("jobs.Job", blank=True, related_name="assistant_messages")
    started_analyses = models.BooleanField(default=False)
    # For a user message whose files were analysed: the assistant's summary of the results, once written.
    results_reply = models.OneToOneField("self", null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="results_for")

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:40]}"
