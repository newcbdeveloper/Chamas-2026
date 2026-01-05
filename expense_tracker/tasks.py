
from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, name='expense_tracker.process_recurring_transactions')
def process_recurring_transactions(self):
    """
    Scheduled task: process all pending recurring transactions.
    Runs daily at 8:00 AM via Celery Beat.
    """
    try:
        logger.info(f"🕗 Starting recurring transaction processing at {timezone.now()}")
        call_command('process_recurring')
        logger.info("✅ Recurring transaction processing completed.")
    except Exception as exc:
        logger.error(f"❌ Failed to process recurring transactions: {exc}", exc_info=True)
        # Retry with exponential backoff (60s, 120s, 240s)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))