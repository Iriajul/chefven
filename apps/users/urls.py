# apps/users/urls.py
from django.urls import path
from .views import (
    WorkerSignUpStep1,
    WorkerSignUpStep2,
    ProfessionList,
    LoginAPIView,
    ForgotPasswordView,
    VerifyOtpView,
    ResetPasswordView,
    ClientSignupView,
    UserProfileView

)
urlpatterns = [
    path('worker/signup/step1/', WorkerSignUpStep1.as_view(), name='worker-signup-step1'),
    path('worker/signup/step2/', WorkerSignUpStep2.as_view(), name='worker-signup-step2'),
    path('client/signup/', ClientSignupView.as_view(), name='client-signup'),
    path('professions/', ProfessionList.as_view(), name='profession-list'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('password/forgot/', ForgotPasswordView.as_view(), name='password-forgot'),
    path('password/verify-otp/', VerifyOtpView.as_view(), name='password-verify-otp'),
    path('password/reset/', ResetPasswordView.as_view(), name='password-reset'),
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),
    
]