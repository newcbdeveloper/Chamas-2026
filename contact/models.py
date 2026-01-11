from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ContactMessage(models.Model):
    """
    Model to store contact form submissions from website visitors.
    """
    name = models.CharField(max_length=200, help_text="Name of the person submitting the message")
    email = models.EmailField(help_text="Email address for response")
    subject = models.CharField(max_length=300, help_text="Subject of the message")
    message = models.TextField(help_text="The actual message content")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the message was submitted")
    is_resolved = models.BooleanField(default=False, help_text="Whether this message has been handled")
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="When the message was marked as resolved")
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='resolved_messages',
        help_text="Admin who resolved this message"
    )
    
    # Optional security field
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of submitter")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_resolved']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.subject} ({self.created_at.strftime('%Y-%m-%d')})"
    
    def mark_as_resolved(self, user=None):
        """Mark this message as resolved."""
        from django.utils import timezone
        self.is_resolved = True
        self.resolved_at = timezone.now()
        if user:
            self.resolved_by = user
        self.save()