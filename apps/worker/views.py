# apps/worker/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from .models import WorkerAvailability, WorkerJob
from .serializers import (
    WorkerJobSerializer,
    WorkerAvailabilitySerializer,
    UpdateAvailabilitySerializer,
    WorkerJobCardSerializer
)


class IsWorker(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.is_authenticated
            and request.user.user_type == 'worker'   # ← FIXED: added .user_type
        )


# 1. Today's Job
class TodayJobView(generics.GenericAPIView):
    permission_classes = [IsWorker]

    def get(self, request):
        worker = request.user
        today = timezone.now().date()
        job = WorkerJob.objects.filter(
            worker=worker,
            date=today,
            status__in=['started', 'pending']
        ).order_by('time').first()

        if not job:
            return Response({"success": True, "today_job": None})

        return Response({
            "success": True,
            "today_job": WorkerJobSerializer(job).data
        })


# 2. Month Calendar
class MonthAvailabilityView(generics.GenericAPIView):
    permission_classes = [IsWorker]

    def get(self, request):
        worker = request.user
        today = timezone.now()
        avail = WorkerAvailability.objects.filter(
            worker=worker,
            date__year=today.year,
            date__month=today.month
        )
        return Response({
            "success": True,
            "current_month": {
                "year": today.year,
                "month": today.month,
                "month_name": today.strftime("%B"),
                "availabilities": WorkerAvailabilitySerializer(avail, many=True).data
            }
        })


# 3. Update Availability
class UpdateAvailabilityView(generics.GenericAPIView):
    permission_classes = [IsWorker]
    serializer_class = UpdateAvailabilitySerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dates = serializer.validated_data['dates']
        status_choice = serializer.validated_data['status']

        updated = []
        for d in dates:
            obj, _ = WorkerAvailability.objects.update_or_create(
                worker=request.user, date=d, defaults={'status': status_choice}
            )
            updated.append(str(d))

        return Response({
            "success": True,
            "message": f"Updated {len(dates)} dates",
            "updated_dates": updated,
            "status": status_choice
        })


# 4. My Jobs — New / In Progress / Completed
class MyJobsView(generics.GenericAPIView):
    permission_classes = [IsWorker]

    def get(self, request):
        worker = request.user

        new_jobs = WorkerJob.objects.filter(worker=worker, status='pending')
        in_progress_jobs = WorkerJob.objects.filter(worker=worker, status='started')
        completed_jobs = WorkerJob.objects.filter(worker=worker, status='completed')

        return Response({
            "success": True,
            "new": WorkerJobCardSerializer(new_jobs, many=True).data,
            "in_progress": WorkerJobCardSerializer(in_progress_jobs, many=True).data,
            "completed": WorkerJobCardSerializer(completed_jobs, many=True).data,
        })


# 5. Start Job
@api_view(['POST'])
@permission_classes([IsWorker])
def start_job(request, job_id):
    """
    Worker accepts the booking request → job becomes confirmed
    Calendar turns orange (status='job')
    """
    try:
        job = WorkerJob.objects.get(
            id=job_id,
            worker=request.user,
            status='pending'
        )
    except WorkerJob.DoesNotExist:
        return Response({
            "success": False,
            "message": "Job not found or already processed"
        }, status=status.HTTP_404_NOT_FOUND)

    # Update job status
    job.status = 'started'
    job.started_at = timezone.now()
    job.save()

    # NOW mark the date as confirmed (orange in calendar)
    WorkerAvailability.objects.filter(
        worker=job.worker,
        date=job.date
    ).update(status='job')

    return Response({
        "success": True,
        "message": "Booking confirmed! Job moved to In Progress.",
        "job_id": job.id,
        "date": job.date.strftime("%Y-%m-%d"),
        "time": job.time.strftime("%I:%M %p")
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsWorker])
def reject_job(request, job_id):
    """
    Worker rejects the booking → client sees rejected
    Calendar goes back to green (free)
    """
    try:
        job = WorkerJob.objects.get(
            id=job_id,
            worker=request.user,
            status='pending'
        )
    except WorkerJob.DoesNotExist:
        return Response({
            "success": False,
            "message": "Job not found or already processed"
        }, status=status.HTTP_404_NOT_FOUND)

    # Cancel the job
    job.status = 'cancelled'
    job.save()

    # Free up the date again
    WorkerAvailability.objects.filter(
        worker=job.worker,
        date=job.date
    ).update(status='free')

    return Response({
        "success": True,
        "message": "Booking request rejected. Date is now available again.",
        "job_id": job.id,
        "date": job.date.strftime("%Y-%m-%d")
    }, status=status.HTTP_200_OK)