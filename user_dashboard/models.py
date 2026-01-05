
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid

class KYCProfile(models.Model):
    """
    KYC verification profile for users.
    Separates declared identity (from signup) from verified identity (from documents).
    """
    
    # Status choices
    STATUS_NOT_STARTED = 'not_started'
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_RESUBMISSION_REQUIRED = 'resubmission_required'
    
    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, 'Not Started'),
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_RESUBMISSION_REQUIRED, 'Resubmission Required'),
    ]
    
    # Document type choices
    DOC_TYPE_NATIONAL_ID = 'national_id'
    DOC_TYPE_PASSPORT = 'passport'
    
    DOC_TYPE_CHOICES = [
        (DOC_TYPE_NATIONAL_ID, 'National ID'),
        (DOC_TYPE_PASSPORT, 'Passport'),
    ]
    
    # Core fields
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='kyc_profile'
    )
    
    # Identity tracking (CRITICAL for integrity)
    declared_national_id = models.CharField(
        max_length=20,
        help_text="ID number provided at signup (may be unverified or incorrect)"
    )
    
    verified_national_id = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,  # Prevent duplicate verified IDs
        help_text="ID number extracted from verified documents (authoritative)"
    )
    
    # Document information
    document_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES,
        blank=True
    )
    
    # Document uploads (encrypted at rest by storage backend)
    id_front_image = models.ImageField(
        upload_to='kyc/documents/%Y/%m/',
        blank=True,
        null=True,
        help_text="Front of ID or passport bio page"
    )
    
    id_back_image = models.ImageField(
        upload_to='kyc/documents/%Y/%m/',
        blank=True,
        null=True,
        help_text="Back of ID (not required for passport)"
    )
    
    selfie_image = models.ImageField(
        upload_to='kyc/selfies/%Y/%m/',
        blank=True,
        null=True,
        help_text="Live selfie for facial verification"
    )
    
    # Verification status
    verification_status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_NOT_STARTED
    )
    
    # Admin review fields
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kyc_reviews'
    )
    
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    admin_notes = models.TextField(
        blank=True,
        help_text="Internal notes from admin reviewer"
    )
    
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason shown to user if rejected"
    )
    
    # Audit trail
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tracking for corrections
    id_correction_count = models.IntegerField(
        default=0,
        help_text="Number of times user corrected their declared ID"
    )
    
    resubmission_count = models.IntegerField(
        default=0,
        help_text="Number of times user resubmitted documents"
    )
    
    class Meta:
        verbose_name = "KYC Profile"
        verbose_name_plural = "KYC Profiles"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['verification_status']),
            models.Index(fields=['verified_national_id']),
            models.Index(fields=['submitted_at']),
        ]
    
    def __str__(self):
        return f"KYC Profile - {self.user.get_full_name()} ({self.verification_status})"
    
    def clean(self):
        """Validate data integrity"""
        # Don't allow duplicate verified IDs across different users
        if self.verified_national_id:
            existing = KYCProfile.objects.filter(
                verified_national_id=self.verified_national_id
            ).exclude(user=self.user).first()
            
            if existing:
                raise ValidationError(
                    f"This ID number is already verified for another user "
                    f"(User ID: {existing.user.id})"
                )
    
    def save(self, *args, **kwargs):
        """Override save to enforce business rules"""
        self.full_clean()  # Run validation
        super().save(*args, **kwargs)
    
    @property
    def is_verified(self):
        """Check if user is fully verified"""
        return self.verification_status == self.STATUS_APPROVED
    
    @property
    def can_submit(self):
        """Check if user can submit/resubmit KYC"""
        return self.verification_status in [
            self.STATUS_NOT_STARTED,
            self.STATUS_REJECTED,
            self.STATUS_RESUBMISSION_REQUIRED
        ]
    
    @property
    def needs_correction(self):
        """Check if declared ID differs from verified ID"""
        if not self.verified_national_id:
            return False
        return self.declared_national_id != self.verified_national_id
    
    def submit_for_review(self):
        """Mark KYC as submitted for admin review"""
        self.verification_status = self.STATUS_PENDING
        self.submitted_at = timezone.now()
        self.resubmission_count += 1
        self.save()
    
    def approve(self, admin_user, verified_id):
        """Approve KYC verification"""
        self.verification_status = self.STATUS_APPROVED
        self.verified_national_id = verified_id
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.approved_at = timezone.now()
        self.save()
        
        # Create audit log
        KYCAuditLog.objects.create(
            kyc_profile=self,
            action='approved',
            performed_by=admin_user,
            notes=f"Verified ID: {verified_id}"
        )
    
    def reject(self, admin_user, reason):
        """Reject KYC verification"""
        self.verification_status = self.STATUS_REJECTED
        self.rejection_reason = reason
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
        
        # Create audit log
        KYCAuditLog.objects.create(
            kyc_profile=self,
            action='rejected',
            performed_by=admin_user,
            notes=reason
        )
    
    def request_resubmission(self, admin_user, reason):
        """Request user to resubmit documents"""
        self.verification_status = self.STATUS_RESUBMISSION_REQUIRED
        self.rejection_reason = reason
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
        
        # Create audit log
        KYCAuditLog.objects.create(
            kyc_profile=self,
            action='resubmission_requested',
            performed_by=admin_user,
            notes=reason
        )


class KYCAuditLog(models.Model):
    """
    Audit trail for all KYC-related actions.
    Critical for compliance and debugging.
    """
    
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('resubmission_requested', 'Resubmission Requested'),
        ('id_corrected', 'ID Number Corrected'),
        ('documents_uploaded', 'Documents Uploaded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kyc_profile = models.ForeignKey(
        KYCProfile,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "KYC Audit Log"
        verbose_name_plural = "KYC Audit Logs"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action} - {self.kyc_profile.user.username} at {self.created_at}"


# Signal to create KYC profile for new users
from django.db.models.signals import post_save
from django.dispatch import receiver
from authentication.models import Profile

@receiver(post_save, sender=User)
def create_kyc_profile(sender, instance, created, **kwargs):
    """
    Automatically create KYC profile when user is created.
    Pulls declared_national_id from existing Profile model.
    """
    if created:
        try:
            # Get declared ID from Profile
            profile = Profile.objects.filter(owner=instance).first()
            declared_id = profile.NIC_No if profile else instance.username
            
            KYCProfile.objects.create(
                user=instance,
                declared_national_id=declared_id
            )
        except Exception as e:
            # Log error but don't break user creation
            print(f"Error creating KYC profile for user {instance.id}: {e}")