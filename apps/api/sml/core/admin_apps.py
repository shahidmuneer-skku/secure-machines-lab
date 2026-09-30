"""Installs SecureAdminSite as the default admin site (kept free of model imports)."""

from django.contrib.admin.apps import AdminConfig


class SecureAdminConfig(AdminConfig):
    default_site = "sml.core.admin_site.SecureAdminSite"
