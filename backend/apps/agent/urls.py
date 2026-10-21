from django.urls import path

from apps.agent import views as v

urlpatterns = [
    path("assistant/conversations/", v.ConversationListView.as_view(), name="assistant-conversations"),
    path("assistant/conversations/<uuid:pk>/", v.ConversationDetailView.as_view(), name="assistant-conversation"),
    path("assistant/conversations/<uuid:pk>/messages/", v.ConversationMessageView.as_view(), name="assistant-message"),
]
