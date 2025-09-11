# engineering_office/back-end/core/services.py

from django.contrib.contenttypes.models import ContentType
from .models import Notification
from django.conf import settings
import pusher
import logging

# إعداد logging لتتبع الأخطاء
logger = logging.getLogger(__name__)

def create_and_send_notification(user, message, event_type, link=None, related_object=None):
    """
    دالة مركزية لإنشاء إشعار وإرساله عبر Pusher.
    """
    print(f"--- بدء إنشاء إشعار للمستخدم: {user.username} ---")
    
    try:
        # 1. إنشاء الإشعار في قاعدة البيانات
        notification_data = {
            'user': user,
            'message': message,
            'event_type': event_type,
            'link': link,
        }
        if related_object:
            notification_data['content_type'] = ContentType.objects.get_for_model(related_object)
            notification_data['object_id'] = related_object.pk

        notification = Notification.objects.create(**notification_data)
        print(f"تم إنشاء الإشعار بنجاح في قاعدة البيانات (ID: {notification.id})")

        # 2. تهيئة Pusher
        pusher_client = pusher.Pusher(
            app_id=settings.PUSHER_APP_ID,
            key=settings.PUSHER_KEY,
            secret=settings.PUSHER_SECRET,
            cluster=settings.PUSHER_CLUSTER,
            ssl=True
        )

        # 3. تجهيز البيانات للإرسال
        from .serializers import NotificationSerializer
        serializer = NotificationSerializer(notification)
        channel_name = f'private-user-{user.id}'
        event_name = 'new_notification'
        
        print(f"سيتم إرسال الإشعار إلى القناة: {channel_name} بالحدث: {event_name}")
        print(f"بيانات الإشعار: {serializer.data}")

        # 4. إرسال الإشعار عبر Pusher
        pusher_client.trigger(channel_name, event_name, {'notification': serializer.data})
        
        print(f"--- اكتمل إرسال الإشعار بنجاح لـ {user.username} ---")
        return notification

    except Exception as e:
        # استخدام logging لتسجيل الأخطاء بشكل أفضل
        logger.error(f"حدث خطأ أثناء إنشاء أو إرسال الإشعار للمستخدم {user.username}: {e}", exc_info=True)
        print(f"!!! خطأ فادح أثناء إرسال الإشعار: {e} !!!")
        return None