# apps/client/urls.py
from django.urls import path
from .views import PopularServicesView, WorkersByProfessionView, ContractorProfileView, WorkerBookingInfoView, AvailableTimeSlotsView, CreateBookingView, ClientMyBookingsView, ClientViewInvoiceView, MarkAsPaidView, ClientReviewWorkerView  

urlpatterns = [
    path('services/popular/', PopularServicesView.as_view(), name='popular-services'),
    path('workers/', WorkersByProfessionView.as_view(), name='workers-by-profession'),
    path('worker/<int:worker_id>/', ContractorProfileView.as_view(), name='contractor-profile'),
    path('worker/<int:worker_id>/booking-info/', WorkerBookingInfoView.as_view(), name='booking-info'),
    path('worker/<int:worker_id>/time-slots/', AvailableTimeSlotsView.as_view(), name='time-slots'),
    path('booking/create/', CreateBookingView.as_view(), name='create-booking'),
    path('my-bookings/', ClientMyBookingsView.as_view(), name='my-bookings'),
    path('job/<int:job_id>/invoice/', ClientViewInvoiceView.as_view(), name='client-view-invoice'),
    path('job/<int:job_id>/mark-paid/', MarkAsPaidView.as_view(), name='mark-paid'),
    path('job/<int:job_id>/review-worker/', ClientReviewWorkerView.as_view(), name='review-worker'),
]