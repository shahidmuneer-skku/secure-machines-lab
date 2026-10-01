from django.urls import path

from . import views

urlpatterns = [
    path("studio/config", views.StudioConfigView.as_view(), name="studio-config"),
    path("studio/jobs", views.StudioJobListCreateView.as_view(), name="studio-jobs"),
    path("studio/jobs/<uuid:pk>", views.StudioJobDetailView.as_view(), name="studio-job-detail"),
    path("admin/studio", views.StudioAdminView.as_view(), name="admin-studio"),
]
