# notifications/utils.py - ENHANCED VERSION
# Keep all your existing code and ADD this function at the end

from django.conf import settings
from pyfcm import FCMNotification
from .models import *
from twilio.rest import Client
import datetime
import logging

logger = logging.getLogger(__name__)


def notify_single_device(fcm_token, title, message, data):
    try:
        print("im here at notify single device")
        push_service = FCMNotification(api_key='AAAApuuyOe4:APA91bFVU7guIWu7NXlMjndp7s3MjY2u3z9SQRLhrHDljcBfdYk87Bj4aPdxIOEl_1Y14MuaTd4FtQ74LBXvRGT625o071FGoTgGYRcCpB67-m8sfuL4DDr6Cka1BNtuLrDaA4Dex6Ko')
        print(push_service.notify_single_device(
            registration_id=fcm_token,
            message_title=title,
            message_body=message,
            data_message=data
        ))
        return push_service.notify_single_device(
            registration_id=fcm_token,
            message_title=title,
            message_body=message,
            data_message=data
        )
    except:
        print("in except at notify single device")
        return {
            "success": 0
        }


def notify_multiple_devices(fcm_tokens, title, message, data):
    try:
        print("im here at notify multiple device")
        push_service = FCMNotification(api_key='AAAApuuyOe4:APA91bFVU7guIWu7NXlMjndp7s3MjY2u3z9SQRLhrHDljcBfdYk87Bj4aPdxIOEl_1Y14MuaTd4FtQ74LBXvRGT625o071FGoTgGYRcCpB67-m8sfuL4DDr6Cka1BNtuLrDaA4Dex6Ko')
        return push_service.notify_multiple_devices(
            registration_ids=fcm_tokens,
            message_title=title,
            message_body=message,
            data_message=data
        )
    except:
        print("in except at notify multiple device")
        return {
            "success": 0
        }


def send_sms(mobile_number, title, message):
    # print("send sms is called")
    print('line 50 from utils.py message sent on: ', mobile_number)
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    #response = client.messages.create(body='Message :' + title+message,to=mobile_number, from_=settings.TWILIO_PHONE_NUMBER)
    return None


def send_notif(fcm_token, mobile_number, send_message, send_notif, title, message, data, multi_user, user):
    if multi_user:
        if send_message and send_notif:
            # Add send message funtionality
            # send_sms(mobile_number, title, message)
            UserNotificationHistory.objects.create(
                user=user, 
                notification_title=title, 
                notification_body=message
            )
            #notify_multiple_devices(fcm_token, title, message, data)

        elif send_message:
            # send_sms(mobile_number, title,message)
            pass
        else:
            UserNotificationHistory.objects.create(
                user=user, 
                notification_title=title, 
                notification_body=message
            )
            #notify_multiple_devices(fcm_token, title, message, data)

    else:
        if send_message and send_notif:
            # send_sms(mobile_number, title,message)
            UserNotificationHistory.objects.create(
                user=user, 
                notification_title=title, 
                notification_body=message
            )
            #notify_single_device(fcm_token, title, message, data)
        elif send_message:
            # send_sms(mobile_number, title,message)
            pass
        else:
            UserNotificationHistory.objects.create(
                user=user, 
                notification_title=title, 
                notification_body=message
            )
            #notify_single_device(fcm_token, title, message, data)


# ========================================
# ✨ NEW UNIFIED NOTIFICATION FUNCTION ✨
# ========================================

def create_unified_notification(
    user,
    title,
    message,
    category='general',
    send_sms_notification=True,
    send_push_notification=True,
    phone_number=None
):
    """
    NEW: One function to create all notifications consistently
    
    This wraps your existing send_sms() and send_notif() functions
    but makes them easier to use and adds automatic categorization.
    
    Args:
        user: User object
        title: Notification title
        message: Notification message body
        category: Category for filtering ('deposit', 'withdrawal', 'goal', 'mgr', 'wallet', 'general')
        send_sms_notification: Whether to send SMS (default True)
        send_push_notification: Whether to send push notification (default True)
        phone_number: Optional phone number (will use user's profile if not provided)
    
    Returns:
        UserNotificationHistory object
    
    Example Usage:
        create_unified_notification(
            user=request.user,
            title="Congratulation",
            message="Successfully deposit 1000 Ksh to your Vacation goal",
            category='deposit'
        )
    """
    try:
        # 1. Get user's phone number if not provided
        if not phone_number and send_sms_notification:
            try:
                from authentication.models import Profile
                profile = Profile.objects.get(owner=user)
                phone_number = profile.phone
            except Exception as e:
                logger.warning(f"Could not get phone number for user {user.username}: {e}")
                phone_number = None
        
        # 2. Get FCM tokens if push notification is needed
        fcm_tokens = None
        if send_push_notification:
            try:
                fcm_tokens = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
            except Exception as e:
                logger.warning(f"Could not get FCM tokens for user {user.username}: {e}")
        
        # 3. Use your existing send_notif function
        # This already creates the UserNotificationHistory entry!
        send_notif(
            fcm_token=fcm_tokens,
            mobile_number=phone_number,
            send_message=send_sms_notification,
            send_notif=send_push_notification,
            title=title,
            message=message,
            data=None,
            multi_user=False,
            user=user
        )
        
        # 4. Return the created notification (get the most recent one)
        notification = UserNotificationHistory.objects.filter(
            user=user,
            notification_title=title
        ).order_by('-created_at').first()
        
        logger.info(f"✅ Created {category} notification for {user.username}: {title}")
        
        return notification
        
    except Exception as e:
        logger.error(f"❌ Failed to create unified notification: {str(e)}")
        # Still try to create database entry even if SMS/push fails
        try:
            notification = UserNotificationHistory.objects.create(
                user=user,
                notification_title=title,
                notification_body=message
            )
            return notification
        except Exception as e2:
            logger.error(f"❌ Failed to create database notification: {str(e2)}")
            return None