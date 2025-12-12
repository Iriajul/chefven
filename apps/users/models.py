# apps/users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import random
from cloudinary.models import CloudinaryField

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('client', 'Client'),
        ('worker', 'Worker'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='client')
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_profile_complete = models.BooleanField(default=False)
    profile_pic = CloudinaryField('image', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    otp = models.CharField(max_length=6, blank=True, null=True) 
    otp_created_at = models.DateTimeField(blank=True, null=True)  
    created_at = models.DateTimeField(auto_now_add=True)

    def set_otp(self, length=6, expiry_minutes=10):
        """Generate and save a new OTP"""
        self.otp = ''.join([str(random.randint(0, 9)) for _ in range(length)])
        self.otp_created_at = timezone.now() + timezone.timedelta(minutes=expiry_minutes)
        self.save(update_fields=['otp', 'otp_created_at'])
        return self.otp

    def verify_otp(self, otp):
        """Check if OTP is valid and not expired"""
        if not self.otp or not self.otp_created_at:
            return False
        if timezone.now() > self.otp_created_at:
            self.clear_otp()
            return False
        if self.otp != otp:
            return False
        return True

    def clear_otp(self):
        """Clear OTP after use or expiry"""
        self.otp = None
        self.otp_created_at = None
        self.save(update_fields=['otp', 'otp_created_at'])

    def __str__(self):
        return self.email


class WorkerProfile(models.Model):
    PROFESSION_CHOICES = (
        ('handyman', 'Handyman'),
        ('cleaning', 'Cleaning'),
        ('moving', 'Moving'),
        ('homecare', 'Home Care'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='worker_profile')
    profession = models.CharField(max_length=20, choices=PROFESSION_CHOICES)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)
    skills = models.JSONField(default=list)
    experience_years = models.PositiveIntegerField()
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_jobs = models.PositiveIntegerField(default=0)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.full_name} - {self.get_profession_display()}"