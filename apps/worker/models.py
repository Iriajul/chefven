# apps/worker/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from cloudinary.models import CloudinaryField
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator

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
    is_paid = models.BooleanField(default=False) 
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=50, blank=True, null=True)
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
    

class Invoice(models.Model):
    job = models.OneToOneField(WorkerJob, on_delete=models.CASCADE, related_name='invoice')
    materials = models.JSONField(default=list) 
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)
    
    # THIS IS THE ONLY CHANGE YOU NEED
    service_charge = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('10.00')   # ← Decimal, not float!
    )
    
    total = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        labor = self.hours_worked * self.hourly_rate
        materials_total = sum(Decimal(str(item.get('cost', 0))) for item in self.materials)
        self.total = labor + materials_total + self.service_charge  # ← Now 100% safe
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice for Job #{self.job.id}"


class Review(models.Model):
    reviewer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reviews_given'
    )
    reviewee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reviews_received'
    )
    # ← CHANGED TO ForeignKey (allows multiple reviews per job)
    job = models.ForeignKey(
        WorkerJob, on_delete=models.CASCADE, related_name='reviews'
    )

    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    
    photo1 = CloudinaryField('image', blank=True, null=True)
    photo2 = CloudinaryField('image', blank=True, null=True)
    photo3 = CloudinaryField('image', blank=True, null=True)
    photo4 = CloudinaryField('image', blank=True, null=True)
    photo5 = CloudinaryField('image', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # One person can only review once per job
        unique_together = ('reviewer', 'job')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reviewer} → {self.reviewee} ({self.rating} stars)"

    def get_photos(self):
        photos = []
        for i in range(1, 6):
            field = getattr(self, f'photo{i}', None)
            if field:
                photos.append(field.url)
        return photos