# engineering_office - Copy (2)/back-end/core/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, ChatMessage, CustomUser

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. استخراج رقم الغرفة والمستخدم
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.user = self.scope['user']

        # 2. التحقق من أن المستخدم مسجل دخوله
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        # 3. التحقق من أن المستخدم عضو في الغرفة المطلوبة
        is_participant = await self.is_user_participant(self.user, self.room_id)
        if not is_participant:
            await self.close() # ارفض الاتصال إذا لم يكن المستخدم عضواً
            return
            
        # 4. إذا نجحت كل التحققات، اقبل الاتصال
        self.room_group_name = f"chat_{self.room_id}"
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_content = text_data_json['message']

        # حفظ الرسالة في قاعدة البيانات
        new_message = await self.save_message(self.user, self.room_id, message_content)

        # إرسال الرسالة إلى مجموعة الغرفة
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'sender_id': self.user.id,
                'sender_name': self.user.get_full_name() or self.user.username,
                'timestamp': str(new_message.created_at)
            }
        )

    async def chat_message(self, event):
        # إرسال الرسالة إلى WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp': event['timestamp']
        }))

    @database_sync_to_async
    def is_user_participant(self, user, room_id):
        try:
            room = ChatRoom.objects.get(pk=room_id)
            return user in room.participants.all()
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, user, room_id, content):
        room = ChatRoom.objects.get(pk=room_id)
        return ChatMessage.objects.create(sender=user, room=room, content=content)