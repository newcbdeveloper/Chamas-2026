"""
Management command to cleanup expired sessions.
Run this periodically via cron or Celery.

Usage:
    python manage.py cleanup_expired_sessions
"""

from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
from django.utils import timezone


class Command(BaseCommand):
    help = 'Delete expired sessions from database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get expired sessions
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        count = expired_sessions.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'Would delete {count} expired sessions')
            )
        else:
            expired_sessions.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {count} expired sessions')
            )