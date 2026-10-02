from __future__ import annotations

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from sml.core.confidential import scrub
from sml.jobs.serializers import JobListSerializer
from sml.media.models import MediaObject

from .models import Conversation, Message


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AttachmentSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="original_name")
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaObject
        fields = ["id", "name", "media_type", "thumbnail_url"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_thumbnail_url(self, obj: MediaObject) -> str | None:
        ready = obj.thumbnail_key and obj.status == MediaObject.Status.READY
        return f"/api/v1/media/{obj.pk}/thumbnail" if ready else None


class MessageSerializer(serializers.ModelSerializer):
    content = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(source="media", many=True, read_only=True)
    jobs = JobListSerializer(many=True, read_only=True)
    results_reply: serializers.PrimaryKeyRelatedField[Message] = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "role", "status", "content", "created_at", "attachments", "jobs", "started_analyses",
                  "results_reply"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_content(self, obj: Message) -> str:
        # The model's words are filtered again on the way out (sml.core.confidential).
        return obj.content if obj.role == Message.Role.USER else scrub(obj.content)


class ConversationDetailSerializer(ConversationSerializer):
    messages = serializers.SerializerMethodField()

    class Meta(ConversationSerializer.Meta):
        fields = [*ConversationSerializer.Meta.fields, "messages"]

    @extend_schema_field(MessageSerializer(many=True))
    def get_messages(self, obj: Conversation) -> Any:
        qs = obj.messages.prefetch_related("media", "jobs", "jobs__media", "jobs__artifacts").order_by("created_at")
        return MessageSerializer(qs, many=True, context=self.context).data


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(required=False, allow_blank=True, default="", max_length=4000)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list, max_length=10)
    job_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list, max_length=10,
                                    help_text="Your earlier results to discuss; nothing is analysed again.")
    locale = serializers.ChoiceField(choices=["en", "ko", "de"], required=False)
