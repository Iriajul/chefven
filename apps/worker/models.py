# apps/worker/models.py  ← FINAL VERSION (KEEP EVERYTHING YOU WANT)

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class WorkerAvailability(models.Model):
    STATUS_CHOICES = (
        ('free', 'Free'),
        ('booked', 'Booked'),     # worker manually blocked
        ('job', 'Has Job'),       # auto-set when booked
    )

    worker = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='availabilities',
        limit_choices_to={'user_type': 'worker'}
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='free')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('worker', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.worker.email} - {self.date} ({self.get_status_display()})"


class WorkerJob(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    worker = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='jobs',
        limit_choices_to={'user_type': 'worker'}
    )
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booked_jobs')

    service_name = models.CharField(max_length=100, default="Home Service")  # e.g. "Plumbing, Cleaning
    date = models.DateField()
    time = models.TimeField()  # e.g. 15:00:00 → 3:00 PM
    address = models.CharField(max_length=255)           # REQUIRED
    notes = models.TextField(blank=True, null=True)      # Optional instructions

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('worker', 'date', 'time')   # Prevents double booking
        ordering = ['-date', '-time']

    def __str__(self):
        return f"{self.worker.full_name} - {self.service_name} on {self.date} at {self.time}"

    def get_profession(self):
        return self.worker.worker_profile.get_profession_display()