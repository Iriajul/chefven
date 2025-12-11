# apps/messaging/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('conversations/', views.InboxView.as_view(), name='chat-list'),
    path('conversation/<int:pk>/', views.ConversationDetailView.as_view(), name='chat-detail'),
    path('conversation/<int:pk>/mark-read/', views.MarkAsReadView.as_view(), name='mark-read'),
]