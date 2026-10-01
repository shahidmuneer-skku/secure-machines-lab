"""URL routing. Everything is under /api so the reverse proxy sends /api/* to Django."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from sml.core.views import HealthzView, ReadyzView
from sml.jobs.stream_views import StreamClaimView, StreamEventView

v1 = [
    path("", include("sml.accounts.urls")),
    path("", include("sml.apikeys.urls")),
    path("", include("sml.catalog.urls")),
    path("", include("sml.media.urls")),
    path("", include("sml.jobs.urls")),
    path("", include("sml.reports.urls")),
    path("", include("sml.news.urls")),
    path("", include("sml.studio.urls")),
    path("", include("sml.credits.urls")),
    path("", include("sml.billing.urls")),
    path("", include("sml.trial.urls")),
    path("", include("sml.dashboard.urls")),
    path("", include("sml.adminapi.urls")),
]

urlpatterns = [
    path("api/v1/", include(v1)),
    # django-allauth headless: /api/_allauth/browser/v1/auth/login, /auth/2fa/authenticate, ...
    path("api/_allauth/", include("allauth.headless.urls")),
    # Internal service-to-service endpoints (denied by nginx; authenticated with a shared key).
    path("api/internal/streams/<uuid:pk>/claim", StreamClaimView.as_view(), name="internal-stream-claim"),
    path("api/internal/streams/<uuid:pk>/events", StreamEventView.as_view(), name="internal-stream-events"),
    path("api/healthz", HealthzView.as_view(), name="healthz"),
    path("api/readyz", ReadyzView.as_view(), name="readyz"),
    path("api/openapi.json", SpectacularAPIView.as_view(custom_settings={
        "PREPROCESSING_HOOKS": ["sml.api_schema_hooks.exclude_admin_endpoints"]}), name="openapi-schema"),
    path("api/docs", SpectacularRedocView.as_view(url_name="openapi-schema"), name="api-docs"),
    path("api/docs/try", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="api-docs-swagger"),
    path("api/django-admin/", admin.site.urls),
]
