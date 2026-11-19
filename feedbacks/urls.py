from django.urls import path

from .views import (
    FeedbackListView,
    FeedbackCreateView,
    FeedbackUpdateView,
    FeedbackDeleteView,
    ConversationDetailView,
    AIUsageView,
    ExpertQueueView,
    RequestExpertView,
    ClaimConversationView,
    ReleaseConversationView,
    CloseConversationView,
)

urlpatterns = [
    path('', FeedbackListView.as_view(), name='feedback_list'),
    path('create/', FeedbackCreateView.as_view(), name='feedback_create'),
    path('update/<int:pk>/', FeedbackUpdateView.as_view(), name='feedback_update'),
    path('delete/<int:pk>/', FeedbackDeleteView.as_view(), name='feedback_delete'),
    path('c/<int:pk>/', ConversationDetailView.as_view(), name='conversation_detail'),
    path('usage/', AIUsageView.as_view(), name='ai_usage'),
    path('expert/', ExpertQueueView.as_view(), name='expert_queue'),
    path('c/<int:pk>/request-expert/', RequestExpertView.as_view(), name='conversation_request_expert'),
    path('c/<int:pk>/claim/', ClaimConversationView.as_view(), name='conversation_claim'),
    path('c/<int:pk>/release/', ReleaseConversationView.as_view(), name='conversation_release'),
    path('c/<int:pk>/close/', CloseConversationView.as_view(), name='conversation_close'),
]
