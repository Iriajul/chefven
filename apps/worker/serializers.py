# apps/worker/serializers.py
from rest_framework import serializers
from .models import WorkerAvailability, WorkerJob


# For TodayJobView and older parts
class WorkerJobSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    time_display = serializers.TimeField(format="%I:%M %p")

    class Meta:
        model = WorkerJob
        fields = ['id', 'service_name', 'client_name', 'date', 'time', 'address']


# For My Jobs (New / In Progress / Completed) — the card you see
class WorkerJobCardSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    client_photo = serializers.SerializerMethodField()
    date_display = serializers.SerializerMethodField()
    time_display = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    class Meta:
        model = WorkerJob
        fields = [
            'id', 'service_name', 'status', 'client_name', 'client_photo',
            'date_display', 'time_display', 'address', 'notes', 'location'
        ]

    def get_client_photo(self, obj):
        if obj.client.profile_pic:
            return obj.client.profile_pic.url
        return None
    
    def get_date_display(self, obj):
        return obj.date.strftime("%b %d")

    def get_time_display(self, obj):
        return obj.time.strftime("%I:%M %p").lstrip("0")

    def get_location(self, obj):
        return "America"  # or add real location later


class WorkerAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerAvailability
        fields = ['date', 'status']


class UpdateAvailabilitySerializer(serializers.Serializer):
    dates = serializers.ListField(child=serializers.DateField())
    status = serializers.ChoiceField(choices=['free', 'booked'])