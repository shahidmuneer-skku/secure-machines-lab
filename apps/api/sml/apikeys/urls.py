from django.urls import path

from . import views

urlpatterns = [
    path("api-keys", views.ApiKeyListCreateView.as_view(), name="api-keys"),
    path("api-keys/scopes", views.ScopeListView.as_view(), name="api-key-scopes"),
    path("api-keys/<uuid:pk>", views.ApiKeyDetailView.as_view(), name="api-key-detail"),
    path("api-keys/<uuid:pk>/rotate", views.ApiKeyRotateView.as_view(), name="api-key-rotate"),
    path("api-keys/<uuid:pk>/usage", views.ApiKeyUsageView.as_view(), name="api-key-usage"),
]
