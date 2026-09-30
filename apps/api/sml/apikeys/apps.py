from django.apps import AppConfig


class ApiKeysConfig(AppConfig):
    name = "sml.apikeys"
    label = "apikeys"
    verbose_name = "API keys"

    def ready(self) -> None:
        from . import schema  # noqa: F401  (registers the OpenAPI auth extension)
