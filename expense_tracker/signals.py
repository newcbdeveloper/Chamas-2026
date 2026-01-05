# expense_tracker/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserPreferences


@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    """
    Automatically create UserPreferences when a new user is created.
    Ensures every user has preferences without manual setup.
    """
    if created:
        UserPreferences.objects.create(user=instance)