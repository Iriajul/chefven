# apps/messaging/urls.py
from django.urls import path
from .views import InboxView

urlpatterns = [
    path('inbox/', InboxView.as_view(), name='inbox'),
]