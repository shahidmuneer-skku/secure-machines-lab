from django.urls import path

from . import views

urlpatterns = [
    path("config", views.PublicConfigView.as_view(), name="public-config"),
    path("me", views.MeView.as_view(), name="me"),
    path("me/consent", views.ConsentView.as_view(), name="me-consent"),
    path("me/export", views.DataExportView.as_view(), name="me-export"),
    path("me/delete", views.DeleteAccountView.as_view(), name="me-delete"),
]
