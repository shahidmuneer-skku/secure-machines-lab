from django.urls import path

from . import views

urlpatterns = [
    path("jobs/<uuid:pk>/reports", views.JobReportsView.as_view(), name="job-reports"),
    path("reports", views.ReportListView.as_view(), name="reports"),
    path("reports/<uuid:pk>/download", views.ReportDownloadView.as_view(), name="report-download"),
]
