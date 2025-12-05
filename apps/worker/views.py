# apps/worker/views.py  ← REPLACE the old WorkerDashboardView with these TWO

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.utils import timezone
from .models import WorkerAvailability, WorkerJob
from .serializers import WorkerJobSerializer, WorkerAvailabilitySerializer, UpdateAvailabilitySerializer


class IsWorker(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'worker'


# ================================
# 1. GET TODAY'S NEXT JOB
# ================================
class TodayJobView(generics.GenericAPIView):
    permission_classes = [IsWorker]

    def get(self, request):
        worker = request.user
        today = timezone.now().date()

        next_job = WorkerJob.objects.filter(
            worker=worker,
            date=today,
            status__in=['accepted', 'started']
        ).order_by('time').first()

        if not next_job:
            return Response({
                "success": True,
                "today_job": None,
                "message": "No jobs scheduled for today"
            })

        return Response({
            "success": True,
            "today_job": WorkerJobSerializer(next_job).data
        })


# ================================
# 2. GET CURRENT MONTH AVAILABILITY
# ================================
class MonthAvailabilityView(generics.GenericAPIView):
    permission_classes = [IsWorker]

    def get(self, request):
        worker = request.user
        today = timezone.now()
        year = today.year
        month = today.month

        availabilities = WorkerAvailability.objects.filter(
            worker=worker,
            date__year=year,
            date__month=month
        )

        return Response({
            "success": True,
            "current_month": {
                "year": year,
                "month": month,
                "month_name": today.strftime("%B"),
                "availabilities": WorkerAvailabilitySerializer(availabilities, many=True).data
            }
        })
    
class UpdateAvailabilityView(generics.GenericAPIView):
    permission_classes = [IsWorker]
    serializer_class = UpdateAvailabilitySerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dates = serializer.validated_data['dates']
        status_choice = serializer.validated_data['status']  # 'free' or 'booked'

        updated_dates = []
        for date in dates:
            obj, created = WorkerAvailability.objects.update_or_create(
                worker=request.user,
                date=date,
                defaults={'status': status_choice}
            )
            updated_dates.append(str(date))

        return Response({
            "success": True,
            "message": f"Availability updated for {len(dates)} dates",
            "updated_dates": updated_dates,
            "status": status_choice
        })    