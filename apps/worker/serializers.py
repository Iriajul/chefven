# apps/worker/serializers.py
from rest_framework import serializers
from .models import WorkerAvailability, WorkerJob
from django.utils import timezone
from datetime import datetime

class WorkerJobSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    time_display = serializers.SerializerMethodField()

    class Meta:
        model = WorkerJob
        fields = ['id', 'service_name', 'client_name', 'date', 'time', 'time_display', 'address']

    def get_time_display(self, obj):
        return obj.time.strftime("%I:%M %p")  # 2:00 PM


class WorkerAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerAvailability
        fields = ['date', 'status']


class UpdateAvailabilitySerializer(serializers.Serializer):
    dates = serializers.ListField(child=serializers.DateField())
    status = serializers.ChoiceField(choices=['free', 'booked'])