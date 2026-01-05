# user_dashboard/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from .models import KYCProfile, KYCAuditLog
from .kyc_utils import log_kyc_action, check_duplicate_verified_id
from notifications.utils import send_notif


@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user_info',
        'status_badge',
        'document_type',
        'submitted_date',
        'reviewed_by',
        'action_buttons'
    ]
    
    list_filter = [
        'verification_status',
        'document_type',
        'submitted_at',
        'approved_at',
    ]
    
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email',
        'declared_national_id',
        'verified_national_id',
    ]
    
    readonly_fields = [
        'user',
        'created_at',
        'updated_at',
        'submitted_at',
        'approved_at',
        'reviewed_at',
        'id_correction_count',
        'resubmission_count',
        'document_preview',
        'audit_trail',
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'created_at', 'updated_at')
        }),
        ('Identity Information', {
            'fields': (
                'declared_national_id',
                'verified_national_id',
                'document_type',
                'id_correction_count',
            )
        }),
        ('Documents', {
            'fields': (
                'document_preview',
                'id_front_image',
                'id_back_image',
                'selfie_image',
            )
        }),
        ('Verification Status', {
            'fields': (
                'verification_status',
                'submitted_at',
                'reviewed_by',
                'reviewed_at',
                'approved_at',
                'resubmission_count',
            )
        }),
        ('Review Notes', {
            'fields': (
                'admin_notes',
                'rejection_reason',
            )
        }),
        ('Audit Trail', {
            'fields': ('audit_trail',),
            'classes': ('collapse',)
        })
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:kyc_id>/review/',
                self.admin_site.admin_view(self.review_kyc_view),
                name='kyc-review'
            ),
            path(
                '<int:kyc_id>/approve/',
                self.admin_site.admin_view(self.approve_kyc),
                name='kyc-approve'
            ),
            path(
                '<int:kyc_id>/reject/',
                self.admin_site.admin_view(self.reject_kyc),
                name='kyc-reject'
            ),
        ]
        return custom_urls + urls
    
    def user_info(self, obj):
        """Display user information with link"""
        return format_html(
            '<strong>{}</strong><br>'
            '<small>{}</small><br>'
            '<small>{}</small>',
            obj.user.get_full_name() or obj.user.username,
            obj.user.email,
            obj.user.username
        )
    user_info.short_description = 'User'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'not_started': 'gray',
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'resubmission_required': 'orange',
        }
        color = colors.get(obj.verification_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 4px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.get_verification_status_display()
        )
    status_badge.short_description = 'Status'
    
    def submitted_date(self, obj):
        """Display submitted date"""
        if obj.submitted_at:
            return obj.submitted_at.strftime('%Y-%m-%d %H:%M')
        return '-'
    submitted_date.short_description = 'Submitted'
    submitted_date.admin_order_field = 'submitted_at'
    
    def action_buttons(self, obj):
        """Display action buttons"""
        if obj.verification_status == KYCProfile.STATUS_PENDING:
            return format_html(
                '<a class="button" href="{}">Review</a>',
                reverse('admin:kyc-review', args=[obj.id])
            )
        return '-'
    action_buttons.short_description = 'Actions'
    
    def document_preview(self, obj):
        """Display document images in admin"""
        html_parts = []
        
        if obj.id_front_image:
            html_parts.append(format_html(
                '<div style="margin-bottom: 20px;">'
                '<h4>ID Front:</h4>'
                '<img src="{}" style="max-width: 400px; border: 1px solid #ddd; padding: 5px;"/>'
                '</div>',
                obj.id_front_image.url
            ))
        
        if obj.id_back_image:
            html_parts.append(format_html(
                '<div style="margin-bottom: 20px;">'
                '<h4>ID Back:</h4>'
                '<img src="{}" style="max-width: 400px; border: 1px solid #ddd; padding: 5px;"/>'
                '</div>',
                obj.id_back_image.url
            ))
        
        if obj.selfie_image:
            html_parts.append(format_html(
                '<div style="margin-bottom: 20px;">'
                '<h4>Selfie:</h4>'
                '<img src="{}" style="max-width: 400px; border: 1px solid #ddd; padding: 5px;"/>'
                '</div>',
                obj.selfie_image.url
            ))
        
        if html_parts:
            return format_html(''.join(html_parts))
        return 'No documents uploaded'
    
    document_preview.short_description = 'Document Preview'
    
    def audit_trail(self, obj):
        """Display audit trail"""
        logs = obj.audit_logs.all()[:20]
        if not logs:
            return 'No audit logs'
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f5f5f5;"><th>Date</th><th>Action</th><th>User</th><th>Notes</th></tr>'
        
        for log in logs:
            html += f'''
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 8px;">{log.created_at.strftime('%Y-%m-%d %H:%M')}</td>
                <td style="padding: 8px;">{log.get_action_display()}</td>
                <td style="padding: 8px;">{log.performed_by.username if log.performed_by else '-'}</td>
                <td style="padding: 8px;">{log.notes or '-'}</td>
            </tr>
            '''
        
        html += '</table>'
        return format_html(html)
    
    audit_trail.short_description = 'Audit Trail'
    
    def review_kyc_view(self, request, kyc_id):
        """Custom view for reviewing KYC submissions"""
        kyc_profile = KYCProfile.objects.get(id=kyc_id)
        
        context = {
            'kyc_profile': kyc_profile,
            'title': f'Review KYC - {kyc_profile.user.get_full_name()}',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/kyc_review.html', context)
    
    def approve_kyc(self, request, kyc_id):
        """Approve KYC verification"""
        kyc_profile = KYCProfile.objects.get(id=kyc_id)
        
        if request.method == 'POST':
            verified_id = request.POST.get('verified_id', '').strip()
            admin_notes = request.POST.get('admin_notes', '')
            
            if not verified_id:
                messages.error(request, 'Verified ID number is required')
                return redirect('admin:kyc-review', kyc_id=kyc_id)
            
            # Check for duplicate verified IDs
            is_duplicate, existing_user_id = check_duplicate_verified_id(
                verified_id,
                exclude_user_id=kyc_profile.user.id
            )
            
            if is_duplicate:
                messages.error(
                    request,
                    f'This ID number is already verified for User ID: {existing_user_id}'
                )
                return redirect('admin:kyc-review', kyc_id=kyc_id)
            
            # Approve the KYC
            kyc_profile.approve(request.user, verified_id)
            kyc_profile.admin_notes = admin_notes
            kyc_profile.save()
            
            # Send notification to user
            try:
                send_notif(
                    None, None, True, True,
                    "KYC Approved!",
                    "Congratulations! Your account has been verified. "
                    "You now have full access to all ChamaSpace features.",
                    None, False, kyc_profile.user
                )
            except Exception:
                pass
            
            messages.success(
                request,
                f'KYC approved for {kyc_profile.user.get_full_name()}'
            )
            return redirect('admin:user_dashboard_kycprofile_changelist')
        
        return redirect('admin:kyc-review', kyc_id=kyc_id)
    
    def reject_kyc(self, request, kyc_id):
        """Reject KYC verification"""
        kyc_profile = KYCProfile.objects.get(id=kyc_id)
        
        if request.method == 'POST':
            rejection_reason = request.POST.get('rejection_reason', '').strip()
            admin_notes = request.POST.get('admin_notes', '')
            require_resubmission = request.POST.get('require_resubmission') == 'on'
            
            if not rejection_reason:
                messages.error(request, 'Rejection reason is required')
                return redirect('admin:kyc-review', kyc_id=kyc_id)
            
            # Reject or request resubmission
            if require_resubmission:
                kyc_profile.request_resubmission(request.user, rejection_reason)
            else:
                kyc_profile.reject(request.user, rejection_reason)
            
            kyc_profile.admin_notes = admin_notes
            kyc_profile.save()
            
            # Send notification to user
            try:
                send_notif(
                    None, None, True, True,
                    "KYC Review Update",
                    f"Your KYC verification requires attention. "
                    f"Reason: {rejection_reason}",
                    None, False, kyc_profile.user
                )
            except Exception:
                pass
            
            action_word = 'Resubmission requested' if require_resubmission else 'Rejected'
            messages.success(
                request,
                f'{action_word} for {kyc_profile.user.get_full_name()}'
            )
            return redirect('admin:user_dashboard_kycprofile_changelist')
        
        return redirect('admin:kyc-review', kyc_id=kyc_id)


@admin.register(KYCAuditLog)
class KYCAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at',
        'kyc_user',
        'action',
        'performed_by',
        'ip_address',
    ]
    
    list_filter = [
        'action',
        'created_at',
    ]
    
    search_fields = [
        'kyc_profile__user__username',
        'kyc_profile__user__email',
        'performed_by__username',
        'notes',
    ]
    
    readonly_fields = [
        'id',
        'kyc_profile',
        'action',
        'performed_by',
        'notes',
        'ip_address',
        'created_at',
    ]
    
    def kyc_user(self, obj):
        return obj.kyc_profile.user.get_full_name() or obj.kyc_profile.user.username
    kyc_user.short_description = 'User'
    
    def has_add_permission(self, request):
        return False  # Audit logs are created automatically
    
    def has_delete_permission(self, request, obj=None):
        return False  # Don't allow deletion of audit logs