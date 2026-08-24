from django.urls import path

from .views import (
    feedback_list,
    feedback_create,
    feedback_update,
    feedback_delete,
)
urlpatterns = [
    path('', feedback_list, name='feedback_list'),
    path('create/', feedback_create, name='feedback_create'),
    path('update/<int:pk>/', feedback_update, name='feedback_update'),
    path('delete/<int:pk>/', feedback_delete, name='feedback_delete'),
]

