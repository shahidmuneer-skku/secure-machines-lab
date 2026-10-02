"""The assistant's API: conversations, and messages answered as Server-Sent Events (POST responses)."""

from __future__ import annotations

from typing import Any, cast

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml.accounts.models import User
from sml.core.pagination import DefaultCursorPagination
from sml.core.permissions import require
from sml.core.throttling import ScopedPrincipalThrottle

from . import services
from .models import Conversation, Message
from .serializers import ConversationDetailSerializer, ConversationSerializer, MessageSerializer, SendMessageSerializer

TAG = ["assistant"]
STREAM = {(200, "text/event-stream"): OpenApiResponse(OpenApiTypes.STR, description=(
    "Server-Sent Events: `meta` (the stored user message and any analyses it started), `delta` "
    "(reply text, sentence by sentence), then `done` (the stored reply) or `error`."))}


class AssistantThrottle(ScopedPrincipalThrottle):
    scope = "assistant"


class ConversationPagination(DefaultCursorPagination):
    ordering = "-updated_at"  # the conversation used last first


def _locale(request: Request, data: dict[str, Any]) -> str:
    return data.get("locale") or getattr(request.user, "locale", "") or "en"


def _stream(turn: services.Turn, meta: dict[str, Any], request: Request) -> StreamingHttpResponse:
    def serialize(message: Message) -> dict[str, Any]:
        return MessageSerializer(message, context={"request": request}).data

    resp = StreamingHttpResponse(services.stream_reply(turn, meta, serialize), content_type="text/event-stream")
    # no-transform: proxies (Next's rewrite, nginx) must not compress it — gzip holds the events back
    # until the reply ends. X-Accel-Buffering: nginx passes the stream through as it is written.
    resp["Cache-Control"] = "no-cache, no-transform"
    resp["X-Accel-Buffering"] = "no"
    return resp


class Base(APIView):
    permission_classes = [IsAuthenticated, require("use_assistant")]

    def conversation(self, request: Request, pk: Any) -> Conversation:
        return get_object_or_404(Conversation, pk=pk, user=request.user)


class StreamBase(Base):
    """Replies are event streams. Browsers ask for `text/event-stream`, which no DRF renderer offers, so
    negotiation falls back to JSON instead of refusing (406): problems found before the stream starts
    (no credits, unknown files) are answered as JSON problem details."""

    throttle_classes = [AssistantThrottle]

    def perform_content_negotiation(self, request: Request, force: bool = False) -> Any:
        return super().perform_content_negotiation(request, force=True)  # type: ignore[misc]


class ConversationListView(Base, generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    pagination_class = ConversationPagination

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return services.conversations_for(self.request.user)

    @extend_schema(tags=TAG, summary="My conversations (newest first)")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=TAG, summary="Start a conversation (listed once it has a message)")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        ser = ConversationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        conv = Conversation.objects.create(user=cast(User, request.user),
                                           title=ser.validated_data.get("title", "")[:120])
        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED)


class ConversationDetailView(Base):
    @extend_schema(tags=TAG, responses=ConversationDetailSerializer, summary="A conversation with its messages")
    def get(self, request: Request, pk: Any) -> Response:
        conv = self.conversation(request, pk)
        return Response(ConversationDetailSerializer(conv, context={"request": request}).data)

    @extend_schema(tags=TAG, request=ConversationSerializer, responses=ConversationSerializer, summary="Rename")
    def patch(self, request: Request, pk: Any) -> Response:
        conv = self.conversation(request, pk)
        ser = ConversationSerializer(conv, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    @extend_schema(tags=TAG, responses={204: None}, summary="Delete (the analyses stay in Results)")
    def delete(self, request: Request, pk: Any) -> Response:
        self.conversation(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageCreateView(StreamBase):
    """Sends a message to the assistant. Attached files are analysed at the normal price per file; the
    reply arrives as Server-Sent Events. Errors before the reply starts are JSON problem details."""


    @extend_schema(tags=TAG, request=SendMessageSerializer, responses=STREAM, summary=(
        "Send a message. Attached files are analysed at the normal price per file; the reply streams."))
    def post(self, request: Request, pk: Any) -> StreamingHttpResponse:
        conv = self.conversation(request, pk)
        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        turn = services.send(request.user, conv, data["content"], [str(i) for i in data["media_ids"]],
                             _locale(request, data), job_ids=[str(i) for i in data["job_ids"]])
        meta = {"conversation": ConversationSerializer(turn.conversation).data,
                "user_message": MessageSerializer(turn.user_message, context={"request": request}).data}
        return _stream(turn, meta, request)


class ResultsReplyView(StreamBase):
    """Once every analysis a message started has finished, the assistant explains the results (once per
    message), as Server-Sent Events."""


    @extend_schema(tags=TAG, request=None, responses=STREAM, summary=(
        "Have the assistant explain the results once every analysis a message started has finished."))
    def post(self, request: Request, pk: Any, message_id: Any) -> StreamingHttpResponse:
        conv = self.conversation(request, pk)
        message = get_object_or_404(Message, pk=message_id, conversation=conv)
        body = request.data if isinstance(request.data, dict) else {}
        turn = services.prepare_results(request.user, conv, message, _locale(request, body))
        meta = {"conversation": ConversationSerializer(conv).data, "results_for": str(message.pk)}
        return _stream(turn, meta, request)
