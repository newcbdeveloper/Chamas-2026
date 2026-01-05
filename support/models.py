from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
import os


def ticket_attachment_path(instance, filename):
    """Generate upload path for ticket attachments"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('support/attachments', str(instance.ticket.id), filename)


class SupportTicket(models.Model):
    """
    Main support ticket model
    Tracks user issues and communication with support team
    """
    
    # Category choices
    CATEGORY_WALLET = 'wallet'
    CATEGORY_DEPOSITS = 'deposits'
    CATEGORY_WITHDRAWALS = 'withdrawals'
    CATEGORY_KYC = 'kyc'
    CATEGORY_MGR = 'mgr'
    CATEGORY_GOALS = 'goals'
    CATEGORY_SUSPICIOUS = 'suspicious'
    CATEGORY_BOOKKEEPING = 'bookkeeping'
    CATEGORY_GENERAL = 'general'
    
    CATEGORY_CHOICES = [
        (CATEGORY_WALLET, 'Wallet Issues'),
        (CATEGORY_DEPOSITS, 'Deposits / M-Pesa'),
        (CATEGORY_WITHDRAWALS, 'Withdrawals'),
        (CATEGORY_KYC, 'KYC Verification'),
        (CATEGORY_MGR, 'Merry-Go-Round / Chamas'),
        (CATEGORY_GOALS, 'Goals & Savings'),
        (CATEGORY_BOOKKEEPING, 'Chamas records '),
        (CATEGORY_SUSPICIOUS, 'Suspicious Activity'),
        (CATEGORY_GENERAL, 'General Inquiry'),
    ]
    
    # Status choices
    STATUS_OPEN = 'open'
    STATUS_PENDING = 'pending'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'
    
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_PENDING, 'Pending User Response'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CLOSED, 'Closed'),
    ]
    
    # Priority choices
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'
    
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]
    
    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(max_length=50, unique=True, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='support_tickets'
    )
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_by = models.CharField(max_length=10, default='user')
    user_unread_count = models.IntegerField(default=0)
    admin_unread_count = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Support Ticket"
        verbose_name_plural = "Support Tickets"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.reference_number} - {self.subject[:50]}"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            from django.db.models import Max
            year = timezone.now().year
            prefix = f"SUPP-{year}-"
            
            last_ticket = SupportTicket.objects.filter(
                reference_number__startswith=prefix
            ).aggregate(Max('reference_number'))
            
            if last_ticket['reference_number__max']:
                last_num = int(last_ticket['reference_number__max'].split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.reference_number = f"{prefix}{str(new_num).zfill(6)}"
        
        super().save(*args, **kwargs)
    
    @property
    def is_open(self):
        return self.status in [self.STATUS_OPEN, self.STATUS_PENDING]
    
    @property
    def is_resolved(self):
        return self.status == self.STATUS_RESOLVED
    
    @property
    def is_closed(self):
        return self.status == self.STATUS_CLOSED
    
    def mark_resolved(self, admin_user=None):
        self.status = self.STATUS_RESOLVED
        self.resolved_at = timezone.now()
        self.save()
        
        if admin_user:
            TicketAuditLog.objects.create(
                ticket=self,
                action='resolved',
                performed_by=admin_user,
                notes=f"Ticket marked as resolved by {admin_user.get_full_name()}"
            )
    
    def mark_closed(self, admin_user=None):
        self.status = self.STATUS_CLOSED
        self.closed_at = timezone.now()
        self.save()
        
        if admin_user:
            TicketAuditLog.objects.create(
                ticket=self,
                action='closed',
                performed_by=admin_user,
                notes=f"Ticket closed by {admin_user.get_full_name()}"
            )


class SupportMessage(models.Model):
    SENDER_TYPE_USER = 'user'
    SENDER_TYPE_ADMIN = 'admin'
    
    SENDER_TYPE_CHOICES = [
        (SENDER_TYPE_USER, 'User'),
        (SENDER_TYPE_ADMIN, 'Admin'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPE_CHOICES)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='support_messages')
    
    message = models.TextField()
    attachment = models.FileField(upload_to=ticket_attachment_path, null=True, blank=True, max_length=500)
    
    is_internal = models.BooleanField(default=False)
    read_by_user = models.BooleanField(default=False)
    read_by_admin = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Support Message"
        verbose_name_plural = "Support Messages"
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.ticket.reference_number} - {self.sender_type} message"
    
    def clean(self):
        blocked_keywords = ['pin', 'otp', 'password', 'cvv', 'secret']
        message_lower = self.message.lower()
        
        for keyword in blocked_keywords:
            if keyword in message_lower:
                raise ValidationError(f"Please do not share sensitive information like {keyword.upper()}.")
        
        if self.attachment and self.attachment.size > 5242880:
            raise ValidationError("File size must be under 5MB")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        
        self.ticket.last_message_at = timezone.now()
        self.ticket.last_message_by = self.sender_type
        
        if self.sender_type == 'user':
            self.ticket.admin_unread_count += 1
            self.read_by_user = True
        else:
            self.ticket.user_unread_count += 1
            self.read_by_admin = True
        
        self.ticket.save()
        super().save(*args, **kwargs)


class TicketAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='assignments')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ticket_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assignments_made')
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Ticket Assignment"
        verbose_name_plural = "Ticket Assignments"
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f"{self.ticket.reference_number} assigned to {self.assigned_to.get_full_name()}"


class TicketAuditLog(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('assigned', 'Assigned'),
        ('status_changed', 'Status Changed'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('reopened', 'Reopened'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Ticket Audit Log"
        verbose_name_plural = "Ticket Audit Logs"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.ticket.reference_number} - {self.action}"