# apps/messaging/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class ChatThread(models.Model):
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_chats')
    worker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='worker_chats')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('client', 'worker')
        ordering = ['-last_message_at']

    def __str__(self):
        return f"{self.client} ↔ {self.worker}"


class Message(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender}: {self.text[:30]}"