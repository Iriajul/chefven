# apps/client/serializers.py  ← NEW FILE

from rest_framework import serializers
from apps.worker.models import WorkerJob

class ClientBookingCardSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)
    worker_photo = serializers.SerializerMethodField()
    profession = serializers.CharField(source='worker.worker_profile.get_profession_display', read_only=True)
    date_display = serializers.SerializerMethodField()
    time_display = serializers.SerializerMethodField()
    is_paid = serializers.BooleanField(read_only=True)

    class Meta:
        model = WorkerJob
        fields = [
            'id',
            'service_name',
            'status',
            'profession',
            'worker_name',
            'worker_photo',
            'date_display',
            'time_display',
            'address',
            'notes',
            'is_paid'
        ]

    def get_worker_photo(self, obj):
        if obj.worker.profile_pic:
            return obj.worker.profile_pic.url
        return None

    def get_date_display(self, obj):
        return obj.date.strftime("%b %d")

    def get_time_display(self, obj):
        return obj.time.strftime("%I:%M %p").lstrip("0")