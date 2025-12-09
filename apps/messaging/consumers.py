# apps/messaging/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatThread, Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        self.room_group_name = f'chat_{self.thread_id}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data['message']

        thread = await database_sync_to_async(ChatThread.objects.get)(id=self.thread_id)

        # RULE: Worker cannot send first message
        if self.user == thread.worker:
            has_messages = await database_sync_to_async(
                Message.objects.filter(thread=thread).exists
            )()
            if not has_messages:
                await self.send(text_data=json.dumps({
                    'error': 'You cannot send the first message. Client must start.'
                }))
                return

        # Save message
        msg = await database_sync_to_async(Message.objects.create)(
            thread=thread,
            sender=self.user,
            text=message_text
        )

        await database_sync_to_async(thread.save)(update_fields=['last_message_at'])

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_text,
                'sender_id': self.user.id,
                'sender_name': self.user.full_name or self.user.email,
                'timestamp': msg.timestamp.isoformat()
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp': event['timestamp']
        }))