# apps/users/views.py
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Avg, Q
from django.utils import timezone
from .models import WorkerProfile
from apps.worker.models import WorkerJob, Review
from .serializers import WorkerStep1Serializer, WorkerStep2Serializer, LoginSerializer, ResetPasswordSerializer, ForgotPasswordSerializer, VerifyOtpSerializer, ClientSignupSerializer

User = get_user_model()


# ========================
# WORKER SIGNUP - STEP 1
# ========================
class WorkerSignUpStep1(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = WorkerStep1Serializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()  # This creates the User with user_type='worker'

        return Response({
            "message": "Step 1 completed successfully",
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email
        }, status=status.HTTP_201_CREATED)


# ========================
# WORKER SIGNUP - STEP 2
# ========================
class WorkerSignUpStep2(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = WorkerStep2Serializer

    def create(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id, user_type='worker')
        except User.DoesNotExist:
            return Response({"error": "Invalid user"}, status=status.HTTP_404_NOT_FOUND)

        if hasattr(user, 'worker_profile'):
            return Response({"error": "Profile already exists"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data, context={'user': user})
        serializer.is_valid(raise_exception=True)
        worker_profile = serializer.save()

        user.is_profile_complete = True
        user.save()

        # NO TOKENS HERE ANYMORE!
        return Response({
            "success": True,
            "message": "Account created successfully! Please sign in to continue.",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": "worker"
            }
        }, status=status.HTTP_201_CREATED)
    

# ========================
# GET PROFESSIONS LIST (Public)
# ========================
class ProfessionList(generics.ListAPIView):
    """
    Returns the full list of available professions for the dropdown
    Frontend will call this on signup page load
    """
    permission_classes = [AllowAny]
    
    def list(self, request, *args, **kwargs):
        professions = [
            {"value": key, "label": label}
            for key, label in WorkerProfile.PROFESSION_CHOICES
        ]
        return Response({
            "success": True,
            "professions": professions
        }, status=status.HTTP_200_OK)
    

class LoginAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        # Detect if worker has profile
        is_worker_complete = False
        worker_profile = None
        if user.user_type == 'worker' and hasattr(user, 'worker_profile'):
            is_worker_complete = user.is_profile_complete
            worker_profile = {
                "profession": user.worker_profile.get_profession_display(),
                "hourly_rate": str(user.worker_profile.hourly_rate),
                "skills": user.worker_profile.skills,
                "experience_years": user.worker_profile.experience_years,
            }

        return Response({
            "message": "Login successful",
            "tokens": {
                "access": str(access_token),
                "refresh": str(refresh)
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "is_profile_complete": user.is_profile_complete
            },
            "worker_profile": worker_profile if user.user_type == 'worker' else None
        }, status=status.HTTP_200_OK)   


# ========================
# 1. FORGOT PASSWORD → SEND OTP + TEMP TOKEN
# ========================
class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response({
                "success": True,
                "detail": "If your email is registered, an OTP has been sent."
            }, status=status.HTTP_200_OK)

        otp = user.set_otp(length=4, expiry_minutes=5)

        send_mail(
            subject="HireNearby – Your Password Reset Code",
            message=f"Your 6-digit verification code is:\n\n{otp}\n\nValid for 10 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        refresh = RefreshToken.for_user(user)
        refresh.set_exp(lifetime=timezone.timedelta(minutes=10))

        return Response({
            "success": True,
            "detail": "OTP sent to your email.",
            "temp_token": str(refresh.access_token),
        }, status=status.HTTP_200_OK)


# ========================
# 2. VERIFY OTP + TEMP TOKEN
# ========================
class VerifyOtpView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOtpSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        temp_token = serializer.validated_data["temp_token"]
        otp = serializer.validated_data["otp"]

        try:
            token = UntypedToken(temp_token)
            user_id = token["user_id"]
            user = User.objects.get(id=user_id)
        except Exception as e:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        if not user.verify_otp(otp):
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "success": True,
            "detail": "OTP verified successfully.",
            "temp_token": temp_token
        }, status=status.HTTP_200_OK)


# ========================
# 3. RESET PASSWORD (Only temp_token + passwords)
# ========================
class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        temp_token = serializer.validated_data["temp_token"]
        new_password = serializer.validated_data["new_password"]

        try:
            token = UntypedToken(temp_token)
            user_id = token["user_id"]
            user = User.objects.get(id=user_id)
        except Exception:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        if not user.otp:
            return Response({"detail": "Session expired. Please try again."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.clear_otp()
        user.save()

        return Response({
            "success": True,
            "detail": "Password changed successfully! You can now sign in."
        }, status=status.HTTP_200_OK)     



class ClientSignupView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = ClientSignupSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            "success": True,
            "message": "Client account created successfully! You can now sign in.",
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "user_type": "client"
            }
        }, status=status.HTTP_201_CREATED)
    

class UserProfileView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        user = request.user

        # BASE DATA — NOW USING REAL FIELDS
        profile_data = {
            "full_name": user.full_name or user.username,
            "email": user.email,
            "phone": user.phone or "",
            "location": user.location or "Not set",
            "profile_pic": user.profile_pic.url if user.profile_pic else None, 
            "user_type": user.user_type,
        }

        if user.user_type == 'client':
            completed_jobs = WorkerJob.objects.filter(client=user, status='completed')
            hired_count = completed_jobs.count()
            unique_workers = completed_jobs.values('worker').distinct().count()

            reviews_received = Review.objects.filter(
                reviewee=user,
                job__status='completed'
            ).select_related('reviewer').order_by('-created_at')

            avg_rating = reviews_received.aggregate(avg=Avg('rating'))['avg']
            avg_rating = round(avg_rating or 0, 1)

            profile_data.update({
                "rating": avg_rating,
                "total_reviews": reviews_received.count(),
                "hired_count": hired_count,
                "unique_workers": unique_workers,
                "reviews": [
                    {
                        "reviewer_name": r.reviewer.get_full_name() or r.reviewer.username,
                        "rating": r.rating,
                        "comment": r.comment or "No comment",
                        "date": r.created_at.strftime("%b %d, %Y"),
                        "photos": r.get_photos()
                    }
                    for r in reviews_received[:10]
                ]
            })

        else:  # worker
            profile = user.worker_profile
            completed_jobs_count = WorkerJob.objects.filter(worker=user, status='completed').count()

            reviews_received = Review.objects.filter(
                reviewee=user,
                job__status='completed'
            ).select_related('reviewer').order_by('-created_at')

            avg_rating = reviews_received.aggregate(avg=Avg('rating'))['avg']
            avg_rating = round(avg_rating or 0, 1)

            profile_data.update({
                "profession": profile.get_profession_display(),
                "hourly_rate": f"${profile.hourly_rate}",
                "experience_years": profile.experience_years,
                "total_jobs": completed_jobs_count,
                "rating": avg_rating,
                "total_reviews": reviews_received.count(),
                "reviews": [
                    {
                        "client_name": r.reviewer.get_full_name() or r.reviewer.username,
                        "rating": r.rating,
                        "comment": r.comment or "No comment",
                        "date": r.created_at.strftime("%b %d, %Y"),
                        "photos": r.get_photos()
                    }
                    for r in reviews_received[:10]
                ]
            })

        return Response({
            "success": True,
            "profile": profile_data
        })


class EditProfileView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        user = request.user

        full_name = request.data.get('full_name')
        phone = request.data.get('phone')
        location = request.data.get('location')
        profile_pic = request.FILES.get('profile_pic')

        if full_name is not None:
            user.full_name = full_name.strip() or user.full_name
        if phone is not None:
            user.phone = phone.strip() or user.phone  # ← NOW UPDATES PHONE
        if location is not None:
            user.location = location.strip() or user.location
        if profile_pic:
            user.profile_pic = profile_pic

        user.save()

        return Response({
            "success": True,
            "message": "Profile updated successfully",
            "profile": {
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone or "",
                "location": user.location or "Not set",
                "profile_pic": user.profile_pic.url if user.profile_pic else None
            }
        })