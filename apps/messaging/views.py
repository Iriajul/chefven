# apps/messaging/views.py
from rest_framework import generics, permissions
from rest_framework.response import Response
from django.db.models import Q
from .models import Conversation, Message, ConversationParticipant

class InboxView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Get all conversations where the user is a participant
        conversations = Conversation.objects.filter(
            participants__user=request.user
        ).distinct()

        data = []
        for conv in conversations:
            # Get the other participants (exclude self)
            other_participants = conv.participants.exclude(user=request.user)
            other_user = other_participants.first().user if other_participants.exists() else request.user

            last_msg = conv.messages.order_by('-created_at').first()
            unread_count = conv.messages.filter(is_read=False).exclude(sender=request.user).count()

            data.append({
                "conversation_id": conv.id,
                "other_user_id": other_user.id,
                "other_user_name": other_user.get_full_name() or other_user.username,
                "last_message": last_msg.content if last_msg else "No messages",
                "last_message_time": last_msg.created_at.isoformat() if last_msg else None,
                "unread_count": unread_count
            })

        return Response({"success": True, "inbox": data})


class ConversationDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            conversation = Conversation.objects.get(id=pk)
        except Conversation.DoesNotExist:
            return Response({"success": False, "error": "Conversation not found"}, status=404)

        # Ensure the user is a participant
        if not ConversationParticipant.objects.filter(conversation=conversation, user=request.user).exists():
            return Response({"success": False, "error": "Access denied"}, status=403)

        messages = Message.objects.filter(conversation=conversation).order_by("created_at")
        data = [
            {
                "id": msg.id,
                "sender_id": msg.sender.id,
                "sender_name": msg.sender.get_full_name() or msg.sender.username,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            } 
            for msg in messages
        ]
        return Response({"success": True, "conversation_id": conversation.id, "messages": data})