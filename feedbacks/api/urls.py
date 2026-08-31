from django.urls import path

from .views import FeedbackListAPIView


urlpatterns = [
    path(
        'feedbacks/',
        FeedbackListAPIView.as_view(),
        name='api-feedback-list'
    ),
]