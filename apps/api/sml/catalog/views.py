from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.credits.pricing import price_table

from . import access


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
