# apps/messaging/views.py
from rest_framework import generics, permissions
from rest_framework.response import Response
from django.db.models import Q
from .models import ChatThread, Message

class InboxView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        threads = ChatThread.objects.filter(
            Q(client=request.user) | Q(worker=request.user)
        ).select_related('client', 'worker')

        data = []
        for thread in threads:
            other = thread.worker if request.user == thread.client else thread.client
            last_msg = thread.messages.last()
            data.append({
                "thread_id": thread.id,
                "other_user_id": other.id,
                "other_user_name": other.full_name or other.email,
                "last_message": last_msg.text if last_msg else "No messages",
                "last_message_time": last_msg.timestamp.isoformat() if last_msg else thread.created_at.isoformat(),
                "unread_count": thread.messages.filter(is_read=False, sender=other).count()
            })
        return Response({"success": True, "inbox": data})