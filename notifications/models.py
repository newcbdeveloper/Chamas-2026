from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserFcmTokens(models.Model):
    token = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)



class UserNotificationHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_title = models.TextField()
    notification_body = models.TextField()
    purpose = models.CharField(max_length=250,null=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=True)
    updated_at = models.DateTimeField(auto_now=True, editable=True)





class DismissedNotification(models.Model):
    """
    Track which system-generated notifications users have dismissed/deleted.
    This prevents them from reappearing on page refresh.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dismissed_notifications')
    notification_type = models.CharField(max_length=50)  # 'contribution', 'invitation', 'goal_reminder', 'low_balance'
    notification_id = models.CharField(max_length=100)  # The unique identifier (e.g., 'contribution_123')
    dismissed_at = models.DateTimeField(default=timezone.now)
    action = models.CharField(max_length=20, choices=[
        ('dismissed', 'Dismissed'),
        ('snoozed', 'Snoozed'),
        ('deleted', 'Deleted'),
    ], default='dismissed')
    snooze_until = models.DateTimeField(null=True, blank=True)  # For "remind later" feature
    
    class Meta:
        unique_together = ('user', 'notification_id')
        ordering = ['-dismissed_at']
        indexes = [
            models.Index(fields=['user', 'notification_type']),
            models.Index(fields=['user', 'snooze_until']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.notification_type} - {self.action}"
    
    @property
    def is_snoozed_active(self):
        """Check if snooze period is still active"""
        if self.action == 'snoozed' and self.snooze_until:
            return timezone.now() < self.snooze_until
        return False