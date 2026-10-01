"""Uploads and ownership-checked media delivery.

User uploads are never served as active content from the app origin: with
object storage we redirect to a short-lived signed URL on the storage host;
with local storage we stream with a sandboxing CSP and nosniff.
"""

from __future__ import annotations

import base64
import binascii

from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.apikeys.permissions import require_scope
from sml.core.exceptions import ApiError
from sml.core.permissions import has_capability

from . import services, storage
from .models import MediaObject


def serve_object(key: str, *, content_type: str, filename: str, inline: bool = True) -> HttpResponse:
    if storage.uses_s3():
        return HttpResponseRedirect(storage.presigned_get(key, filename=filename, inline=inline))
    resp = FileResponse(storage.open_file(key), content_type=content_type, as_attachment=not inline,
                        filename=filename)
    resp["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'; media-src 'self'"
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Cache-Control"] = "private, max-age=300"
    return resp


def visible_media(request: Request):  # type: ignore[no-untyped-def]
    qs = MediaObject.objects.exclude(status=MediaObject.Status.DELETED)
    if has_capability(request.user, "view_all_media"):
        return qs
    return qs.filter(owner=request.user)


class MediaSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaObject
        fields = ["id", "status", "media_type", "original_name", "content_type", "size_bytes", "sha256", "width",
                  "height", "duration_seconds", "fps", "frame_count", "codec", "expires_at", "thumbnail_url",
                  "created_at"]

    def get_thumbnail_url(self, obj: MediaObject) -> str | None:
        return f"/api/v1/media/{obj.pk}/thumbnail" if obj.thumbnail_key else None


class UploadView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated, require_scope("detect:write")]

    @extend_schema(
        tags=["uploads"], summary="Upload an image or video (multipart field `file`)",
        request={"multipart/form-data": {"type": "object", "properties": {"file": {"type": "string",
                                                                                   "format": "binary"}}}},
        responses={201: MediaSerializer},
    )
    def post(self, request: Request) -> Response:
        upload = request.FILES.get("file")
        if upload is None:
            raise ApiError("Send the file in a multipart field named 'file'.")
        media = services.ingest_file(upload, original_name=upload.name, owner=request.user)
        return Response(MediaSerializer(media).data, status=status.HTTP_201_CREATED)


class MultipartStartSerializer(serializers.Serializer):
    file_name = serializers.CharField(max_length=255)
    size_bytes = serializers.IntegerField(min_value=1)
    head_base64 = serializers.CharField(help_text="Base64 of the file's first 4096 bytes (for type sniffing).")


class MultipartStartView(APIView):
    permission_classes = [IsAuthenticated, require_scope("detect:write")]

    @extend_schema(tags=["uploads"], request=MultipartStartSerializer,
                   responses={201: schemas.MultipartStartResponseSerializer},
                   summary="Start a resumable multipart upload for a large video")
    def post(self, request: Request) -> Response:
        ser = MultipartStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            head = base64.b64decode(ser.validated_data["head_base64"], validate=True)[:8192]
        except (binascii.Error, ValueError) as exc:
            raise ApiError("head_base64 is not valid base64.") from exc
        media, urls = services.start_multipart(owner=request.user, original_name=ser.validated_data["file_name"],
                                               size_bytes=ser.validated_data["size_bytes"], head=head)
        return Response({"media_id": str(media.pk), "part_size": storage.PART_SIZE, "part_urls": urls},
                        status=status.HTTP_201_CREATED)


class PartSerializer(serializers.Serializer):
    part_number = serializers.IntegerField(min_value=1, max_value=10000)
    etag = serializers.CharField(max_length=200)


class MultipartCompleteSerializer(serializers.Serializer):
    parts = PartSerializer(many=True)


class MultipartCompleteView(APIView):
    permission_classes = [IsAuthenticated, require_scope("detect:write")]

    @extend_schema(tags=["uploads"], request=MultipartCompleteSerializer, responses=MediaSerializer,
                   summary="Complete a multipart upload (the server verifies the file)")
    def post(self, request: Request, pk: str) -> Response:
        media = get_object_or_404(MediaObject, pk=pk, owner=request.user)
        ser = MultipartCompleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        media = services.complete_multipart(media, ser.validated_data["parts"])
        return Response(MediaSerializer(media).data)

    @extend_schema(tags=["uploads"], responses={204: None}, summary="Abort an unfinished multipart upload")
    def delete(self, request: Request, pk: str) -> Response:
        media = get_object_or_404(MediaObject, pk=pk, owner=request.user, status=MediaObject.Status.UPLOADING)
        storage.multipart_abort(media.storage_key, media.s3_multipart_upload_id)
        media.status = MediaObject.Status.DELETED
        media.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class MediaDetailView(APIView):
    permission_classes = [IsAuthenticated, require_scope("jobs:read")]

    @extend_schema(tags=["uploads"], responses=MediaSerializer, summary="Get upload metadata")
    def get(self, request: Request, pk: str) -> Response:
        return Response(MediaSerializer(get_object_or_404(visible_media(request), pk=pk)).data)


class MediaContentView(APIView):
    permission_classes = [IsAuthenticated, require_scope("jobs:read")]

    @extend_schema(tags=["uploads"], responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
                   parameters=[OpenApiParameter("download", bool, description="Save as a file instead of showing it")],
                   summary="Download the original file")
    def get(self, request: Request, pk: str) -> HttpResponse:
        media = get_object_or_404(visible_media(request), pk=pk, status=MediaObject.Status.READY)
        return serve_object(media.storage_key, content_type=media.content_type, filename=media.original_name,
                            inline=request.query_params.get("download") not in ("1", "true"))


class MediaThumbnailView(APIView):
    permission_classes = [IsAuthenticated, require_scope("jobs:read")]

    @extend_schema(tags=["uploads"], responses={(200, "image/jpeg"): OpenApiTypes.BINARY},
                   summary="Metadata-stripped JPEG thumbnail")
    def get(self, request: Request, pk: str) -> HttpResponse:
        media = get_object_or_404(visible_media(request), pk=pk)
        if not media.thumbnail_key:
            raise ApiError("No thumbnail available.")
        return serve_object(media.thumbnail_key, content_type="image/jpeg", filename=f"{media.pk}.jpg")
