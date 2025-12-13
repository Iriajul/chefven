# apps/messaging/serializers.py → FINAL VERSION (FULL NAME + EMAIL)

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Conversation, Message

User = get_user_model()

class ConversationSerializer(serializers.ModelSerializer):
    other_user_id = serializers.SerializerMethodField()
    conversation_name = serializers.SerializerMethodField()  # ← Shows full_name if exists
    conversation_email = serializers.SerializerMethodField()  # ← Always shows email
    last_message = serializers.SerializerMethodField()
    last_message_sender = serializers.SerializerMethodField()
    last_message_is_me = serializers.SerializerMethodField()
    last_message_time = serializers.SerializerMethodField()
    other_user_avatar = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Conversation
        fields = [
            'id',
            'other_user_id',
            'conversation_name',
            'conversation_email',
            'other_user_avatar',
            'last_message',
            'last_message_sender',
            'last_message_is_me',
            'last_message_time',
            'unread_count'
        ]

    def get_other_user(self, obj):
        if not hasattr(obj, '_cached_other_user'):
            user = self.context['request'].user
            other_participant = obj.participants.exclude(user=user).select_related('user').first()
            obj._cached_other_user = other_participant.user if other_participant else None
        return obj._cached_other_user

    def get_other_user_id(self, obj):
        other = self.get_other_user(obj)
        return str(other.id) if other else None

    def get_conversation_name(self, obj):
        other = self.get_other_user(obj)
        if other:
            full_name = other.full_name.strip()  # ← Use full_name field
            return full_name or other.email or other.username
        return "Unknown"

    def get_conversation_email(self, obj):
        other = self.get_other_user(obj)
        return other.email if other else None

    def get_other_user_avatar(self, obj):
        other = self.get_other_user(obj)
        if other and other.profile_pic:
            return other.profile_pic.url
        return None

    def get_last_message(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        return msg.content if msg else ""

    def get_last_message_sender(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        if not msg:
            return ""
        user = self.context['request'].user
        if msg.sender == user:
            return "Me"
        full_name = msg.sender.full_name.strip()
        return full_name or msg.sender.email

    def get_last_message_is_me(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        return msg.sender == self.context['request'].user if msg else False

    def get_last_message_time(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        return msg.created_at.isoformat() if msg else None


class ConversationDetailSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()      # ← Real full_name
    sender_email = serializers.SerializerMethodField()
    sender_profile_pic = serializers.SerializerMethodField()
    my_profile_pic = serializers.SerializerMethodField()
    is_send_by_me = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            'id',
            'sender_name',
            'sender_email',
            'sender_profile_pic',
            'content',
            'created_at',
            'is_read',
            'is_send_by_me',
            'my_profile_pic',
        )

    def get_sender_name(self, obj):
        # Use your custom full_name field first
        full_name = obj.sender.full_name.strip()
        return full_name or obj.sender.email or obj.sender.username

    def get_sender_email(self, obj):
        return obj.sender.email

    def get_sender_profile_pic(self, obj):
        if obj.sender.profile_pic:
            return obj.sender.profile_pic.url
        return None

    def get_my_profile_pic(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.profile_pic:
            return request.user.profile_pic.url
        return None

    def get_is_send_by_me(self, obj):
        request = self.context.get("request")
        return obj.sender == request.user if request else False

    def get_is_read(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if obj.sender == request.user:
            return True
        participant = obj.conversation.participants.filter(user=request.user).first()
        if not participant or not participant.last_read_at:
            return False
        return obj.created_at <= participant.last_read_at