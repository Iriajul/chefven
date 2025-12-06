# apps/worker/urls.py
from django.urls import path
from .views import (
    TodayJobView,
    MonthAvailabilityView,
    UpdateAvailabilityView,
    MyJobsView,
    start_job,
    reject_job,
)

urlpatterns = [
    path('today-job/', TodayJobView.as_view(), name='today-job'),
    path('availability/month/', MonthAvailabilityView.as_view(), name='month-availability'),
    path('availability/update/', UpdateAvailabilityView.as_view(), name='availability-update'),
    
    path('my-jobs/', MyJobsView.as_view(), name='my-jobs'),
    path('job/<int:job_id>/start/', start_job, name='start-job'),
    path('job/<int:job_id>/reject/', reject_job, name='reject-job'),
]