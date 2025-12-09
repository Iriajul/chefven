# apps/worker/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
from .models import WorkerAvailability, WorkerJob, Invoice, Review
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


# 7. Get Job Info for Invoice
class JobDetailForInvoiceView(generics.RetrieveAPIView):
    permission_classes = [IsWorker]

    def get(self, request, job_id):
        job = get_object_or_404(
            WorkerJob,
            id=job_id,
            worker=request.user,
            status='started'
        )

        return Response({
            "success": True,
            "job": {
                "id": job.id,
                "client_name": job.client.full_name,
                "service_name": job.service_name,
                "date": job.date.strftime("%b %d, %Y"),
                "time": job.time.strftime("%I:%M %p"),
                "hourly_rate": str(job.worker.worker_profile.hourly_rate)
            }
        })


# 8. CREATE INVOICE + (Optional) WORKER REVIEW
class CreateInvoiceView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        job_id = request.data.get('job_id')
        hours_worked = request.data.get('hours_worked')
        materials = request.data.get('materials', [])
        worker_rating = request.data.get('worker_rating')
        worker_review = request.data.get('worker_review', '')
        photo1 = request.FILES.get('photo1')
        photo2 = request.FILES.get('photo2')
        photo3 = request.FILES.get('photo3')
        photo4 = request.FILES.get('photo4')
        photo5 = request.FILES.get('photo5')

        # Validate job
        try:
            job = WorkerJob.objects.get(id=job_id, worker=request.user, status='started')
        except WorkerJob.DoesNotExist:
            return Response({"success": False, "message": "Job not found or not in progress"}, status=404)

        # Convert hours_worked to Decimal safely
        try:
            hours_worked = Decimal(str(hours_worked))
        except:
            return Response({"success": False, "message": "Valid hours worked required"}, status=400)

        # Get hourly rate as Decimal
        hourly_rate = job.worker.worker_profile.hourly_rate  # already Decimal

        # Calculate everything as Decimal
        labor = hours_worked * hourly_rate
        materials_total = sum(Decimal(str(item.get('cost', 0))) for item in materials)
        service_charge = Decimal('10.00')
        total = labor + materials_total + service_charge

        # Create invoice
        invoice = Invoice.objects.create(
            job=job,
            hours_worked=hours_worked,
            hourly_rate=hourly_rate,
            materials=materials,
            total=total,
            sent_at=timezone.now()
        )

        # Save worker review about client (optional)
        if worker_rating:
            try:
                rating = int(worker_rating)
                if 1 <= rating <= 5:
                    Review.objects.create(
                        reviewer=request.user,
                        reviewee=job.client,
                        job=job,
                        rating=rating,
                        comment=worker_review or '',
                        photo1=photo1,
                        photo2=photo2,
                        photo3=photo3,
                        photo4=photo4,
                        photo5=photo5,
                    )
            except:
                pass

        # Mark job as completed
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save()

        return Response({
            "success": True,
            "message": "Invoice sent and job completed!",
            "invoice": {
                "id": invoice.id,
                "total": f"${total:.2f}",
                "labor": f"${labor:.2f}",
                "materials": f"${materials_total:.2f}",
                "service_charge": "$10.00",
                "earnings": f"${total - service_charge:.2f}"
            },
            "review_given": bool(worker_rating)
        }, status=201)