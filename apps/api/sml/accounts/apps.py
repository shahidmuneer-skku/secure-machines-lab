from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "sml.accounts"
    label = "accounts"
    verbose_name = "Accounts & access control"

    def ready(self) -> None:
        from . import signals  # noqa: F401
