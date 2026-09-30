"""OpenAPI description of API-key authentication (drf-spectacular extension)."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "sml.apikeys.authentication.ApiKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):  # type: ignore[no-untyped-def]
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "sml_live_<prefix>_<secret>",
            "description": "Personal API key created at /app/api-keys. Send as `Authorization: Bearer <key>`.",
        }
