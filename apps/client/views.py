# apps/client/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count
from datetime import datetime, time, timedelta
from .serializers import ClientBookingCardSerializer

from apps.worker.models import WorkerAvailability, WorkerJob
from apps.users.models import WorkerProfile

User = get_user_model()


# ========================================
# 1. POPULAR SERVICES (with worker count)
# ========================================
class PopularServicesView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        counts = WorkerProfile.objects.values('profession').annotate(
            count=Count('id')
        )
        count_dict = {item['profession']: item['count'] for item in counts}

        services = [
            {"profession": "handyman",  "label": "Handyman",    "worker_count": count_dict.get("handyman", 0)},
            {"profession": "cleaning",  "label": "Cleaning",   "worker_count": count_dict.get("cleaning", 0)},
            {"profession": "moving",    "label": "Moving",      "worker_count": count_dict.get("moving", 0)},
            {"profession": "homecare",  "label": "Home Care",   "worker_count": count_dict.get("homecare", 0)},
        ]

        return Response({
            "success": True,
            "services": services
        })


# ========================================
# 2. WORKERS BY PROFESSION (Directory)
# ========================================
class WorkersByProfessionView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        profession = self.request.query_params.get('profession')
        if not profession:
            return WorkerProfile.objects.none()

        return WorkerProfile.objects.filter(
            profession=profession,
            user__is_active=True
        ).select_related('user')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response({
                "success": True,
                "workers": [],
                "message": "No workers found in this category"
            })

        data = []
        for profile in queryset:
            user = profile.user
            data.append({
                "id": user.id,
                "full_name": user.full_name or "No Name",
                "photo": None,
                "profession": profile.get_profession_display(),
                "hourly_rate": str(profile.hourly_rate),
                "rating": float(profile.rating) if profile.rating else 0.0,
                "total_reviews": 0,
                "total_jobs": profile.total_jobs,
                "skills": profile.skills,
                "experience_years": profile.experience_years,
            })

        return Response({
            "success": True,
            "workers": data
        })


# ========================================
# 3. CONTRACTOR PROFILE DETAIL + CALENDAR
# ========================================
class ContractorProfileView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, worker_id):
        try:
            worker = User.objects.get(id=worker_id, user_type='worker', is_active=True)
            profile = worker.worker_profile
        except (User.DoesNotExist, WorkerProfile.DoesNotExist):
            return Response({
                "success": False,
                "message": "Worker not found or profile incomplete"
            }, status=404)

        today = timezone.now()
        availabilities = WorkerAvailability.objects.filter(
            worker=worker,
            date__year=today.year,
            date__month=today.month
        ).values('date', 'status')

        availability_list = [
            {"date": str(item['date']), "status": item['status']}
            for item in availabilities
        ]

        data = {
            "success": True,
            "worker": {
                "id": worker.id,
                "full_name": worker.full_name or "No Name Set",
                "photo": None,
                "profession": profile.get_profession_display(),
                "location": worker.phone[:3] if worker.phone else "Not Set",
                "hourly_rate": str(profile.hourly_rate),
                "total_jobs": profile.total_jobs,
                "experience_years": profile.experience_years,
                "rating": round(float(profile.rating), 1) if profile.rating and profile.rating > 0 else 0.0,
                "total_reviews": 0,
                "skills": profile.skills or [],
                "is_verified": False
            },
            "availability": {
                "year": today.year,
                "month": today.month,
                "month_name": today.strftime("%B"),
                "dates": availability_list
            },
            "reviews": []
        }
        return Response(data)


# ========================================
# 4. GET AVAILABLE DATES (for Select Date screen)
# ========================================
class WorkerBookingInfoView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, worker_id):
        try:
            worker = User.objects.get(id=worker_id, user_type='worker')
            profile = worker.worker_profile
        except:
            return Response({"success": False, "message": "Worker not found"}, status=404)

        today = timezone.now().date()
        future_date = today + timedelta(days=60)

        free_dates = WorkerAvailability.objects.filter(
            worker=worker,
            date__gte=today,
            date__lte=future_date,
            status='free'
        ).values_list('date', flat=True)

        free_dates_list = [d.strftime("%Y-%m-%d") for d in free_dates]

        return Response({
            "success": True,
            "worker": {
                "id": worker.id,
                "full_name": worker.full_name,
                "profession": profile.get_profession_display(),
                "location": "America",
                "hourly_rate": str(profile.hourly_rate)
            },
            "available_dates": free_dates_list
        })


# ========================================
# 5. GET TIME SLOTS FOR SELECTED DATE
# ========================================
class AvailableTimeSlotsView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, worker_id):
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"success": False, "message": "Date required"}, status=400)

        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            return Response({"success": False, "message": "Invalid date"}, status=400)

        try:
            worker = User.objects.get(id=worker_id, user_type='worker')
        except:
            return Response({"success": False, "message": "Worker not found"}, status=404)

        if not WorkerAvailability.objects.filter(worker=worker, date=selected_date, status='free').exists():
            return Response({"success": False, "message": "Not available on this date"})

        booked = WorkerJob.objects.filter(worker=worker, date=selected_date).values_list('time', flat=True)

        slots = []
        for hour in range(8, 20):  # 8 AM to 7 PM
            t = time(hour, 0)
            display = t.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
            slots.append({
                "time": str(t),       # "15:00:00"
                "display": display,   # "3:00 PM"
                "available": str(t) not in [str(b) for b in booked]
            })

        return Response({
            "success": True,
            "date": date_str,
            "slots": slots
        })


# apps/client/views.py → FINAL CORRECT VERSION
class CreateBookingView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        worker_id = request.data.get('worker_id')
        date_str = request.data.get('date')
        time_str = request.data.get('time')
        address = request.data.get('address')
        notes = request.data.get('notes', '')

        if not all([worker_id, date_str, time_str, address]):
            return Response({"success": False, "message": "Missing required fields"}, status=400)

        try:
            worker = User.objects.get(id=worker_id, user_type='worker', is_active=True)
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            time = datetime.strptime(time_str, "%H:%M:%S").time()
        except User.DoesNotExist:
            return Response({"success": False, "message": "Worker not found"}, status=404)
        except ValueError:
            return Response({"success": False, "message": "Invalid date/time"}, status=400)

        # Calendar check
        if not WorkerAvailability.objects.filter(worker=worker, date=date, status='free').exists():
            return Response({"success": False, "message": "Date no longer available"}, status=400)

        # Block only ACTIVE (started) jobs
        if WorkerJob.objects.filter(worker=worker, date=date, time=time, status='started').exists():
            return Response({"success": False, "message": "Time slot in progress"}, status=400)

        # MAIN RULE: Only ONE pending OR upcoming job allowed per client-worker
        if WorkerJob.objects.filter(
            client=request.user,
            worker=worker,
            status__in=['pending', 'started']   # ← blocks both pending and active
        ).exists():
            return Response({
                "success": False,
                "message": "You already have an active or pending booking with this worker"
            }, status=400)

        # All good → create booking
        service_name = worker.worker_profile.get_profession_display()
        job = WorkerJob.objects.create(
            worker=worker,
            client=request.user,
            service_name=service_name,
            date=date,
            time=time,
            address=address,
            notes=notes,
            status='pending'
        )

        return Response({
            "success": True,
            "message": "Booking request sent! Waiting for worker to accept.",
            "booking_id": job.id,
            "booking": {
                "id": job.id,
                "worker_id": worker.id,
                "worker_name": worker.full_name,
                "profession": service_name,
                "date": date.strftime("%A, %B %d, %Y"),
                "time": time.strftime("%I:%M %p").lstrip("0"),
                "address": address,
                "status": "pending",
                "created_at": timezone.localtime(job.created_at).isoformat()
            }
        }, status=201)
    

class ClientMyBookingsView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        client = request.user

        pending = WorkerJob.objects.filter(client=client, status='pending') \
            .select_related('worker', 'worker__worker_profile')

        upcoming = WorkerJob.objects.filter(client=client, status='started') \
            .select_related('worker', 'worker__worker_profile')

        completed = WorkerJob.objects.filter(client=client, status='completed') \
            .select_related('worker', 'worker__worker_profile')

        return Response({
            "success": True,
            "pending": ClientBookingCardSerializer(pending, many=True).data,
            "upcoming": ClientBookingCardSerializer(upcoming, many=True).data,
            "completed": ClientBookingCardSerializer(completed, many=True).data,
        })