# apps/messaging/views.py
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .models import Conversation, Message, ConversationParticipant
from .serializers import ConversationSerializer, ConversationDetailSerializer

class InboxView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Conversation.objects.filter(participants__user=user)
            .prefetch_related("participants__user", "messages")
            .distinct()
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Add unread_count dynamically
        for conv in queryset:
            conv.unread_count = conv.messages.filter(
                is_read=False
            ).exclude(sender=request.user).count()

        serializer = self.get_serializer(queryset, many=True)
        return Response({"success": True, "inbox": serializer.data})


class ConversationDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationDetailSerializer

    def get(self, request, pk):
        # Get conversation
        try:
            conversation = Conversation.objects.get(id=pk)
        except Conversation.DoesNotExist:
            return Response({"success": False, "error": "Conversation not found"}, status=404)

        # Check if user is participant
        if not ConversationParticipant.objects.filter(
            conversation=conversation, 
            user=request.user
        ).exists():
            return Response({"success": False, "error": "Access denied"}, status=403)

        # Mark unread messages as read (except own messages)
        Message.objects.filter(
            conversation=conversation,
            is_read=False
        ).exclude(sender=request.user).update(is_read=True)

        # Update last_read_at
        ConversationParticipant.objects.filter(
            conversation=conversation,
            user=request.user
        ).update(last_read_at=timezone.now())

        # Get all messages
        messages = Message.objects.filter(conversation=conversation).order_by('created_at')

        # Serialize with is_read correctly calculated
        serializer = ConversationDetailSerializer(
            messages, 
            many=True, 
            context={"request": request}
        )

        return Response({
            "success": True,
            "conversation_id": conversation.id,
            "messages": serializer.data
        })

