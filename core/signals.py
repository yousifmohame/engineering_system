from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import pusher
from .models import Task, Notification

# تهيئة عميل Pusher
pusher_client = pusher.Pusher(
  app_id=settings.PUSHER_APP_ID,
  key=settings.PUSHER_KEY,
  secret=settings.PUSHER_SECRET,
  cluster=settings.PUSHER_CLUSTER,
  ssl=True
)

@receiver(post_save, sender=Task)
def create_task_notification(sender, instance, created, **kwargs):
    # تحقق مما إذا كانت المهمة جديدة ولديها موظف مُسند إليها
    if created and instance.assigned_to:
        user_to_notify = instance.assigned_to
        message = f"تم إسناد مهمة جديدة لك: '{instance.title}'"
        link = f"/tasks/{instance.id}" # رابط المهمة

        # 1. حفظ الإشعار في قاعدة البيانات
        notification = Notification.objects.create(
            user=user_to_notify,
            message=message,
            link=link
        )

        # 2. إرسال الإشعار الفوري عبر Pusher
        channel_name = f'private-user-{user_to_notify.id}'
        event_name = 'new_notification'
        
        pusher_client.trigger(
            channel_name, 
            event_name, 
            {
                'id': notification.id,
                'message': message,
                'link': link
            }
        )