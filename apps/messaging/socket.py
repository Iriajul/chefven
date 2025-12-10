# apps/messaging/socket.py

import socketio
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from channels.db import database_sync_to_async
from apps.messaging.models import Conversation, ConversationParticipant, Message
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

# Global tracking
connected_users = {}  # sid → user_id
user_sockets = {}     # user_id → sid

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")


# --- Database helpers ---
@database_sync_to_async
def get_user_by_id(user_id):
    return User.objects.get(id=user_id)


@database_sync_to_async
def get_conversation(sender, receiver):
    """
    Return existing conversation between two users if it exists.
    """
    return Conversation.objects.filter(
        is_group=False,
        participants__user=sender
    ).filter(
        participants__user=receiver
    ).first()


@database_sync_to_async
def create_conversation(sender, receiver):
    """
    Safely create a conversation and participants.
    """
    conversation = Conversation.objects.create(is_group=False)
    participants = [
        ConversationParticipant(user=sender, conversation=conversation),
        ConversationParticipant(user=receiver, conversation=conversation),
    ]
    ConversationParticipant.objects.bulk_create(participants, ignore_conflicts=True)
    return conversation


@database_sync_to_async
def save_message(conversation, sender, content):
    return Message.objects.create(
        conversation=conversation,
        sender=sender,
        content=content
    )


# NEW 🔥 — update conversation last message + time
@database_sync_to_async
def update_conversation_last_message(conversation, message):
    conversation.last_message = message.content
    conversation.last_message_time = message.created_at
    conversation.save(update_fields=["last_message", "last_message_time"])


# --- Socket.IO events ---
@sio.event
async def connect(sid, environ, auth):
    token = auth.get('token') if auth else None
    if not token:
        return False

    try:
        token = token.replace("Bearer ", "")
        payload = UntypedToken(token)
        user_id = int(payload['user_id'])
        user = await get_user_by_id(user_id)
    except Exception as e:
        print("Connection failed:", e)
        return False

    connected_users[sid] = str(user.id)
    user_sockets[str(user.id)] = sid
    await sio.save_session(sid, {'user': user})
    await sio.enter_room(sid, str(user.id))

    print(f"Connected: {user.get_full_name()} ({user.id})")
    return True


@sio.event
async def send_message(sid, data):
    user_id = connected_users.get(sid)
    if not user_id:
        return

    receiver_id = data.get('to_user')
    content = data.get('message', '').strip()

    if not receiver_id or not content:
        await sio.emit('error', {'error': 'Invalid data'}, to=sid)
        return

    try:
        sender = await get_user_by_id(user_id)
        receiver = await get_user_by_id(int(receiver_id))
    except Exception:
        await sio.emit('error', {'error': 'User not found'}, to=sid)
        return

    # Find or create conversation
    conversation = await get_conversation(sender, receiver)
    if not conversation:
        # Only clients can start conversations
        if sender.user_type == 'worker' and receiver.user_type == 'client':
            await sio.emit('error', {'error': 'Worker cannot send first message'}, to=sid)
            return
        conversation = await create_conversation(sender, receiver)

    # Save message
    message = await save_message(conversation, sender, content)

    # NEW 🔥 — update last_message + last_message_time so it goes to top in inbox
    await update_conversation_last_message(conversation, message)

    payload = {
        "id": message.id,
        "conversation_id": conversation.id,
        "sender_id": str(sender.id),
        "sender_name": sender.get_full_name() or sender.username,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "is_me": True
    }

    # Send to receiver if online
    receiver_sid = user_sockets.get(str(receiver.id))
    if receiver_sid:
        await sio.emit('new_message', payload, room=receiver_sid)

    # Send confirmation to sender
    await sio.emit('message_sent', payload, to=sid)


@sio.event
async def disconnect(sid):
    user_id = connected_users.pop(sid, None)
    if user_id and user_sockets.get(user_id) == sid:
        user_sockets.pop(user_id)
    print(f"Disconnected: {user_id}")
