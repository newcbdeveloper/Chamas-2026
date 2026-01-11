"""
Celery tasks for session management.
"""

from celery import shared_task
from django.contrib.sessions.models import Session
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(name='authentication.cleanup_expired_sessions')
def cleanup_expired_sessions():
    """
    Cleanup expired sessions from database.
    Runs daily at 3:00 AM via Celery Beat.
    """
    try:
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        count = expired_sessions.count()
        expired_sessions.delete()
        
        logger.info(f'Cleaned up {count} expired sessions')
        return f'Deleted {count} expired sessions'
    
    except Exception as e:
        logger.error(f'Error cleaning up sessions: {str(e)}')
        raise