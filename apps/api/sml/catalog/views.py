from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.credits.pricing import price_table

from . import access
from .registry import registry


def _lang(request: Request) -> str:
    lang = request.query_params.get("lang") or getattr(request.user, "locale", None) or "en"
    return lang if lang in ("en", "ko", "de") else "en"


def _model_payload(spec, lang: str, allowed: bool | None = None) -> dict:  # type: ignore[no-untyped-def]
    data = {
        "id": spec.id, "name": spec.name(lang), "description": spec.description.get(lang)
        or spec.description.get("en", ""), "family": spec.family, "media": sorted(spec.media),
        "face_required": spec.face_required, "xai": spec.xai, "default_selected": spec.default_selected,
        "variant_of": spec.variant_of, "enabled": spec.enabled,
    }
    if allowed is not None:
        data["allowed"] = allowed
    return data


class ModelCatalogView(APIView):
    @extend_schema(tags=["catalog"], parameters=[
        OpenApiParameter("media", str, enum=["image", "video"], required=False),
        OpenApiParameter("lang", str, enum=["en", "ko", "de"], required=False)],
        responses=schemas.ModelCatalogSerializer, summary="Detection models available to the caller")
    def get(self, request: Request) -> Response:
        lang = _lang(request)
        media = request.query_params.get("media")
        api_key = getattr(request, "auth", None)
        reg = registry()
        out = []
        for spec in reg.models.values():
            if not spec.enabled or (media and not spec.supports(media)):
                continue
            out.append(_model_payload(spec, lang, access.model_allowed(request.user, spec, api_key)))
        long_video = [
            {"id": m.id, "name": m.name(lang), "description": m.description.get(lang) or m.description.get("en", ""),
             "default_selected": m.default_selected}
            for m in reg.long_video_models.values()
        ]
        steps = access.allowed_audit_steps(request.user)
        audit = [
            {"id": s.id, "name": s.name(lang), "description": s.description.get(lang) or s.description.get("en", ""),
             "always_on": s.builtin, "allowed": s.builtin or s.id in steps}
            for s in reg.audit_steps.values()
        ]
        return Response({"models": out, "long_video_models": long_video, "audit_steps": audit})


class ModuleCatalogView(APIView):
    @extend_schema(tags=["catalog"], responses=schemas.ModuleInfoSerializer(many=True),
                   summary="Modules (detect / long-form video / news) and whether you can use them")
    def get(self, request: Request) -> Response:
        prices = price_table()
        return Response([
            {"id": "detect", "allowed": access.module_allowed(request.user, "detect"),
             "price": {"image": prices["image"], "video_base": prices["video_base"],
                       "video_base_seconds": prices["video_base_seconds"],
                       "video_per_extra_minute": prices["video_per_extra_minute"]}},
            {"id": "long_video", "allowed": access.module_allowed(request.user, "long_video"),
             "price": {"per_minute": prices["long_video_per_minute"]}},
            {"id": "news", "allowed": access.module_allowed(request.user, "news"),
             "price": {"per_case": prices["news_case"]}},
        ])


class PublicModelCatalogView(APIView):
    """Public model list for marketing/docs pages."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["catalog"], responses=schemas.ModelInfoSerializer(many=True), summary="Public model catalog")
    def get(self, request: Request) -> Response:
        lang = _lang(request)
        return Response([_model_payload(s, lang) for s in registry().models.values() if s.enabled])
