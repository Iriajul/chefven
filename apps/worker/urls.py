# apps/worker/urls.py
from django.urls import path
from .views import (
    TodayJobView,
    MonthAvailabilityView,
    UpdateAvailabilityView,
)

urlpatterns = [
    path('today-job/', TodayJobView.as_view(), name='today-job'),
    path('availability/month/', MonthAvailabilityView.as_view(), name='month-availability'),
    path('availability/update/', UpdateAvailabilityView.as_view(), name='availability-update'),
]