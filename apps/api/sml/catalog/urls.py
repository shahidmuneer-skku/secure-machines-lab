from django.urls import path

from . import views

# Detectors are an operator concern: users get modules and prices only (detector lists are
# under /api/v1/admin/models).
urlpatterns = [
    path("catalog/modules", views.ModuleCatalogView.as_view(), name="catalog-modules"),
]
