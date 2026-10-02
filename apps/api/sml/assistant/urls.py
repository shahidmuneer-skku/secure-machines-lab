from django.urls import path

from . import views

urlpatterns = [
    path("assistant/conversations", views.ConversationListView.as_view(), name="assistant-conversations"),
    path("assistant/conversations/<uuid:pk>", views.ConversationDetailView.as_view(), name="assistant-conversation"),
    path("assistant/conversations/<uuid:pk>/messages", views.MessageCreateView.as_view(), name="assistant-messages"),
    path("assistant/conversations/<uuid:pk>/messages/<uuid:message_id>/results", views.ResultsReplyView.as_view(),
         name="assistant-results"),
]
