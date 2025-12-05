# apps/client/urls.py
from django.urls import path
from .views import PopularServicesView, WorkersByProfessionView, ContractorProfileView, WorkerBookingInfoView, AvailableTimeSlotsView, CreateBookingView  

urlpatterns = [
    path('services/popular/', PopularServicesView.as_view(), name='popular-services'),
    path('workers/', WorkersByProfessionView.as_view(), name='workers-by-profession'),
    path('worker/<int:worker_id>/', ContractorProfileView.as_view(), name='contractor-profile'),
    path('worker/<int:worker_id>/booking-info/', WorkerBookingInfoView.as_view(), name='booking-info'),
    path('worker/<int:worker_id>/time-slots/', AvailableTimeSlotsView.as_view(), name='time-slots'),
    path('booking/create/', CreateBookingView.as_view(), name='create-booking'),
]