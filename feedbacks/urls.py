from django.urls import path

from .views import (
    FeedbackListView,
    FeedbackCreateView,
    FeedbackUpdateView,
    FeedbackDeleteView,
    ConversationDetailView,
    AIUsageView,
)

urlpatterns = [
    path('', FeedbackListView.as_view(), name='feedback_list'),
    path('create/', FeedbackCreateView.as_view(), name='feedback_create'),
    path('update/<int:pk>/', FeedbackUpdateView.as_view(), name='feedback_update'),
    path('delete/<int:pk>/', FeedbackDeleteView.as_view(), name='feedback_delete'),
    path('c/<int:pk>/', ConversationDetailView.as_view(), name='conversation_detail'),
    path('usage/', AIUsageView.as_view(), name='ai_usage'),
]
