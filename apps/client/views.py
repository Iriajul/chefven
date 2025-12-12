# apps/client/views.py
from django.db import models
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import datetime, time, timedelta
from .serializers import ClientBookingCardSerializer
from decimal import Decimal
import random
import string
from apps.worker.models import WorkerAvailability, WorkerJob, Invoice, Review
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
        ).select_related('user').annotate(
            avg_rating=Avg('user__reviews_received__rating'),
            total_reviews=Count('user__reviews_received'),
            completed_jobs=Count('user__jobs', filter=models.Q(user__jobs__status='completed'))
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        if not queryset.exists():
            return Response({
                "success": True,
                "workers": [],
                "message": "No workers found in this category"
            })

        workers = []
        for profile in queryset:
            user = profile.user
            
            workers.append({
                "id": user.id,
                "full_name": user.full_name or "No Name",
                "photo": user.profile_pic.url if user.profile_pic else None, 
                "profession": profile.get_profession_display(),
                "location": user.location or "Not set",
                "experience_years": profile.experience_years,
                "rating": round(profile.avg_rating, 1) if profile.avg_rating else 0.0,
                "total_reviews": profile.total_reviews or 0,
                "hourly_rate": f"${profile.hourly_rate}",
                "total_jobs": profile.completed_jobs,
            })

        return Response({
            "success": True,
            "workers": workers
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
                "message": "Worker not found"
            }, status=404)

        # === AVAILABILITY ===
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

        # === TOTAL COMPLETED JOBS ONLY ===
        total_completed_jobs = WorkerJob.objects.filter(
            worker=worker,
            status='completed'
        ).count()

        # === REAL REVIEWS ===
        reviews = Review.objects.filter(
            reviewee=worker,
            job__status='completed'
        ).select_related('reviewer').order_by('-created_at')

        review_list = []
        for r in reviews:
            review_list.append({
                "client_name": r.reviewer.full_name or "Anonymous",
                "rating": r.rating,
                "comment": r.comment or "No comment",
                "date": r.created_at.strftime("%b %d, %Y"),
                "photos": r.get_photos()
            })

        return Response({
            "success": True,
            "worker": {
                "full_name": worker.full_name or "No Name",
                "profession": profile.get_profession_display(),
                "profile_pic": worker.profile_pic.url if worker.profile_pic else None,
                "location": "America",
                "hourly_rate": str(profile.hourly_rate),
                "total_jobs": total_completed_jobs,
                "experience_years": profile.experience_years,
                "skills": profile.skills or []
            },
            "availability": {
                "year": today.year,
                "month": today.month,
                "month_name": today.strftime("%B"),
                "dates": availability_list
            },
            "reviews": review_list
        })


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
                "profile_pic": worker.profile_pic.url if worker.profile_pic else None,
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
    

class ClientViewInvoiceView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        try:
            # CORRECT WAY — Q objects with keyword args, no positional args after
            job = WorkerJob.objects.get(
                Q(id=job_id) &
                Q(status='completed') &
                (Q(client=request.user) | Q(worker=request.user))
            )
            invoice = job.invoice
        except (WorkerJob.DoesNotExist, Invoice.DoesNotExist):
            return Response({
                "success": False,
                "message": "Invoice not found or access denied"
            }, status=404)

        # Calculate totals safely
        labor = invoice.hours_worked * invoice.hourly_rate
        materials_total = sum(Decimal(str(item.get('cost', 0))) for item in invoice.materials)
        total = labor + materials_total + invoice.service_charge

        return Response({
            "success": True,
            "invoice": {
                "invoice_number": f"INVB-{invoice.id}",
                "worker_name": job.worker.full_name,
                "profession": job.worker.worker_profile.get_profession_display(),
                "service": job.service_name,
                "date": job.date.strftime("%b %d, %Y"),
                "time": job.time.strftime("%I:%M %p"),
                "address": job.address,
                "notes": job.notes or "No notes",
                "materials": invoice.materials,
                "labor": f"{invoice.hours_worked} hrs × ${invoice.hourly_rate}/hr",
                "labor_cost": f"${labor:.2f}",
                "materials_total": f"${materials_total:.2f}",
                "service_charge": f"${invoice.service_charge:.2f}",
                "total": f"${total:.2f}"
            }
        })
    

class MarkAsPaidView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, job_id):
        try:
            job = WorkerJob.objects.get(
                id=job_id,
                client=request.user,
                status='completed',
                is_paid=False
            )
            invoice = job.invoice
        except (WorkerJob.DoesNotExist, Invoice.DoesNotExist):
            return Response({"success": False, "message": "Job not found or already paid"}, status=404)

        # Mark as paid
        job.is_paid = True
        job.paid_at = timezone.now()
        job.transaction_id = 'TXN-' + ''.join(random.choices(string.digits, k=10))
        job.save()

        return Response({
            "success": True,
            "message": "Your payment has been processed successfully!",
            "payment": {
                "transaction_id": job.transaction_id,
                "date": job.paid_at.strftime("%d %B, %Y"),
                "worker_name": job.worker.full_name,
                "service": job.service_name,
                "amount": f"${invoice.total:.2f}"
            }
        })
    

class ClientReviewWorkerView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, job_id):
        try:
            job = WorkerJob.objects.get(
                id=job_id,
                client=request.user,
                status='completed',
                is_paid=True
            )
        except WorkerJob.DoesNotExist:
            return Response({"success": False, "message": "Job not found or not paid"}, status=404)

        # Prevent duplicate review from same client
        if Review.objects.filter(reviewer=request.user, job=job).exists():
            return Response({"success": False, "message": "You already reviewed this worker"}, status=400)

        rating = request.data.get('rating')
        comment = request.data.get('comment', '')
        photo1 = request.FILES.get('photo1')
        photo2 = request.FILES.get('photo2')
        photo3 = request.FILES.get('photo3')
        photo4 = request.FILES.get('photo4')
        photo5 = request.FILES.get('photo5')

        try:
            rating = int(rating)
            if not 1 <= rating <= 5:
                raise ValueError
        except:
            return Response({"success": False, "message": "Rating must be 1-5"}, status=400)

        Review.objects.create(
            reviewer=request.user,
            reviewee=job.worker,
            job=job,
            rating=rating,
            comment=comment,
            photo1=photo1,
            photo2=photo2,
            photo3=photo3,
            photo4=photo4,
            photo5=photo5,
        )

        return Response({
            "success": True,
            "message": "Thank you! Your review has been submitted."
        })