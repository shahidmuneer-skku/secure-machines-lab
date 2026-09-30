from django.urls import path

from . import views

urlpatterns = [
    path("news/cases", views.NewsCaseListCreateView.as_view(), name="news-cases"),
    path("news/cases/<uuid:pk>", views.NewsCaseDetailView.as_view(), name="news-case-detail"),
]
