from django.urls import path

from . import views

urlpatterns = [
    path("catalog/models", views.ModelCatalogView.as_view(), name="catalog-models"),
    path("catalog/modules", views.ModuleCatalogView.as_view(), name="catalog-modules"),
    path("catalog/public-models", views.PublicModelCatalogView.as_view(), name="catalog-public-models"),
]
