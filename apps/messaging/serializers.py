from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Conversation, Message

UserAccount = get_user_model()

class ConversationSerializer(serializers.ModelSerializer):
    other_user_id = serializers.SerializerMethodField()
    conversation_name = serializers.SerializerMethodField()
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
            'other_user_avatar',
            'last_message',
            'last_message_sender',
            'last_message_is_me',
            'last_message_time',
            'unread_count'
        ]

    def get_other_user_id(self, obj):
        other_user = self.get_other_user(obj)
        return str(other_user.id) if other_user else None

    def get_other_user(self, obj):
        # cache the other participant for reuse
        if not hasattr(obj, '_cached_other_user'):
            user = self.context['request'].user
            other_participant = obj.participants.exclude(user=user).select_related('user').first()
            obj._cached_other_user = other_participant.user if other_participant else None
        return obj._cached_other_user

    def get_last_message_obj(self, obj):
        # cache the last message for reuse
        if not hasattr(obj, '_cached_last_message'):
            if hasattr(obj, 'latest_messages') and obj.latest_messages:
                obj._cached_last_message = obj.latest_messages[0]
            else:
                obj._cached_last_message = obj.messages.order_by('-created_at').first()
        return obj._cached_last_message

    def get_conversation_name(self, obj):
        other_user = self.get_other_user(obj)
        if other_user:
            full_name = f"{other_user.first_name} {other_user.last_name}".strip()
            return full_name or other_user.username
        return "Unknown"

    def get_other_user_avatar(self, obj):
        other_user = self.get_other_user(obj)
        if other_user and getattr(other_user, "profile_pic", None):
            avatar = other_user.profile_pic
            if hasattr(avatar, 'url'):
                return avatar.url
        return None

    def get_last_message(self, obj):
        last_msg = self.get_last_message_obj(obj)
        return last_msg.content if last_msg else ""

    def get_last_message_sender(self, obj):
        last_msg = self.get_last_message_obj(obj)
        if not last_msg:
            return ""
        user = self.context['request'].user
        return "Me" if last_msg.sender == user else f"{last_msg.sender.first_name} {last_msg.sender.last_name}".strip() or last_msg.sender.username

    def get_last_message_is_me(self, obj):
        last_msg = self.get_last_message_obj(obj)
        if not last_msg:
            return None
        return last_msg.sender == self.context['request'].user

    def get_last_message_time(self, obj):
        last_msg = self.get_last_message_obj(obj)
        return last_msg.created_at if last_msg else None

class ConversationDetailSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    is_send_by_me = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            'id',
            'sender',
            'content',
            'created_at',
            'is_read',
            'is_send_by_me',
        )

    def get_sender(self, obj):
        return obj.sender.first_name

    def get_is_send_by_me(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.sender_id == request.user.id
        return False
    
    def get_is_read(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
           return False
        if obj.sender_id == request.user.id:
           return True
        participant = obj.conversation.participants.filter(user=request.user).first()
        if not participant or not participant.last_read_at:
           return False
        return obj.created_at <= participant.last_read_at
