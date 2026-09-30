from django.urls import path

from . import views

urlpatterns = [
    path("uploads", views.UploadView.as_view(), name="upload"),
    path("uploads/multipart", views.MultipartStartView.as_view(), name="upload-multipart"),
    path("uploads/<uuid:pk>/complete", views.MultipartCompleteView.as_view(), name="upload-complete"),
    path("media/<uuid:pk>", views.MediaDetailView.as_view(), name="media-detail"),
    path("media/<uuid:pk>/content", views.MediaContentView.as_view(), name="media-content"),
    path("media/<uuid:pk>/thumbnail", views.MediaThumbnailView.as_view(), name="media-thumbnail"),
]
