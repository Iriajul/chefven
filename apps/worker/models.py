# apps/worker/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class WorkerAvailability(models.Model):
    STATUS_CHOICES = (
        ('free', 'Free'),
        ('booked', 'Booked'),
        ('job', 'Has Job'),
    )
    worker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='availabilities')
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
        ('pending', 'Pending'),       # New tab
        ('started', 'Started'),        # In Progress tab
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    worker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jobs')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booked_jobs')

    service_name = models.CharField(max_length=100, default="Home Service")
    date = models.DateField()
    time = models.TimeField()
    address = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['worker', 'date', 'time']),
        ]

    def __str__(self):
        return f"{self.worker.full_name} - {self.service_name} @ {self.date} {self.time}"

    def get_profession(self):
        return self.worker.worker_profile.get_profession_display()