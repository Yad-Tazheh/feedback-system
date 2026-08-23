from django.urls import path
from .views import request_list, request_create, request_update, request_delete

urlpatterns = [
    path('', request_list, name='request_list'),
    path('create/', request_create, name='request_create'),
    path('update/<int:pk>/', request_update, name='request_update'),
    path('delete/<int:pk>/', request_delete, name='request_delete'),
]

