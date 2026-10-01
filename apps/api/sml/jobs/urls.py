from django.urls import path

from . import sse, stream_views, views

urlpatterns = [
    path("jobs", views.JobListCreateView.as_view(), name="jobs"),
    path("jobs/quote", views.QuoteView.as_view(), name="jobs-quote"),
    path("jobs/cancel", views.JobBulkCancelView.as_view(), name="jobs-cancel"),
    path("detect", views.DetectView.as_view(), name="detect"),
    path("jobs/<uuid:pk>", views.JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:pk>/cancel", views.JobCancelView.as_view(), name="job-cancel"),
    path("jobs/<uuid:pk>/rerun", views.JobRerunView.as_view(), name="job-rerun"),
    path("jobs/<uuid:pk>/explain", views.ExplainView.as_view(), name="job-explain"),
    path("jobs/<uuid:pk>/artifacts/<uuid:artifact_id>/content", views.ArtifactContentView.as_view(),
         name="job-artifact-content"),
    path("events/stream", sse.user_event_stream, name="events-stream"),
    path("long-video/config", stream_views.StreamConfigView.as_view(), name="long-video-config"),
    path("long-video/sessions", stream_views.StreamSessionCreateView.as_view(), name="long-video-sessions"),
]
