from django.urls import path

from sml.jobs import sse

from . import views

urlpatterns = [
    path("trial/status", views.TrialStatusView.as_view(), name="trial-status"),
    path("trial/detect", views.TrialDetectView.as_view(), name="trial-detect"),
    path("trial/jobs/<uuid:pk>", views.TrialJobView.as_view(), name="trial-job"),
    path("trial/jobs/<uuid:pk>/stream", sse.trial_job_event_stream, name="trial-job-stream"),
    path("trial/jobs/<uuid:pk>/artifacts/<uuid:artifact_id>/content", views.TrialArtifactView.as_view(),
         name="trial-artifact"),
    path("trial/media/<uuid:pk>/thumbnail", views.TrialMediaThumbnailView.as_view(), name="trial-thumbnail"),
]
