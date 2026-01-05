# user_dashboard/kyc_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.conf import settings
from .models import KYCProfile, KYCAuditLog
from .kyc_utils import (
    get_kyc_profile, 
    get_kyc_status, 
    log_kyc_action, 
    get_client_ip,
    validate_id_number,
    check_duplicate_verified_id,
    get_verification_requirements,
    format_kyc_status_message
)
from authentication.models import Profile
import os


@login_required(login_url='Login')
def kyc_dashboard(request):
    """
    Main KYC dashboard - shows status and next steps.
    """
    kyc_profile = get_kyc_profile(request.user)
    status_info = get_kyc_status(request.user)
    requirements = get_verification_requirements()
    status_message = format_kyc_status_message(kyc_profile.verification_status)
    
    # Get user profile for additional info
    try:
        user_profile = Profile.objects.get(owner=request.user)
    except Profile.DoesNotExist:
        user_profile = None
    
    context = {
        'kyc_profile': kyc_profile,
        'status_info': status_info,
        'requirements': requirements,
        'status_message': status_message,
        'user_profile': user_profile,
        'can_resubmit': kyc_profile.can_submit,
    }
    
    return render(request, 'user_dashboard/kyc_dashboard.html', context)


@login_required(login_url='Login')
def kyc_start(request):
    """
    Start KYC verification process.
    """
    kyc_profile = get_kyc_profile(request.user)
    
    # Check if user can start/restart KYC
    if not kyc_profile.can_submit:
        messages.error(request, 'You cannot start KYC at this time.')
        return redirect('user_dashboard:kyc:dashboard')
    
    requirements = get_verification_requirements()
    
    context = {
        'kyc_profile': kyc_profile,
        'requirements': requirements,
    }
    
    return render(request, 'user_dashboard/kyc_start.html', context)


@login_required(login_url='Login')
def kyc_verify_identity(request):
    """
    Step 1: Verify/correct declared identity information.
    """
    kyc_profile = get_kyc_profile(request.user)
    
    if not kyc_profile.can_submit:
        messages.error(request, 'You cannot modify KYC at this time.')
        return redirect('user_dashboard:kyc:dashboard')
    
    if request.method == 'POST':
        declared_id = request.POST.get('declared_national_id', '').strip()
        document_type = request.POST.get('document_type')
        
        if not declared_id or not document_type:
            messages.error(request, 'All fields are required.')
            return redirect('user_dashboard:kyc:verify_identity')
        
        # Validate ID number format
        is_valid, error_msg = validate_id_number(declared_id, document_type)
        if not is_valid:
            messages.error(request, error_msg)
            return redirect('user_dashboard:kyc:verify_identity')
        
        # Track if ID was corrected
        if kyc_profile.declared_national_id != declared_id:
            kyc_profile.id_correction_count += 1
            log_kyc_action(
                kyc_profile,
                'id_corrected',
                request.user,
                f"Changed from {kyc_profile.declared_national_id} to {declared_id}",
                get_client_ip(request)
            )
        
        # Update KYC profile
        kyc_profile.declared_national_id = declared_id
        kyc_profile.document_type = document_type
        kyc_profile.save()
        
        messages.success(request, 'Identity information saved.')
        return redirect('user_dashboard:kyc:upload_documents')
    
    context = {
        'kyc_profile': kyc_profile,
    }
    
    return render(request, 'user_dashboard/kyc_verify_identity.html', context)


@login_required(login_url='Login')
def kyc_upload_documents(request):
    """
    Step 2: Upload ID documents (front and back).
    """
    kyc_profile = get_kyc_profile(request.user)
    
    if not kyc_profile.can_submit:
        messages.error(request, 'You cannot modify KYC at this time.')
        return redirect('user_dashboard:kyc:dashboard')
    
    if not kyc_profile.document_type:
        messages.warning(request, 'Please complete identity verification first.')
        return redirect('user_dashboard:kyc:verify_identity')
    
    if request.method == 'POST':
        id_front = request.FILES.get('id_front')
        id_back = request.FILES.get('id_back')
        
        # Validate uploads
        if not id_front:
            messages.error(request, 'Front of ID/Passport is required.')
            return redirect('user_dashboard:kyc:upload_documents')
        
        # Back is only required for National ID
        if kyc_profile.document_type == 'national_id' and not id_back:
            messages.error(request, 'Back of National ID is required.')
            return redirect('user_dashboard:kyc:upload_documents')
        
        # Validate file types
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if id_front.content_type not in allowed_types:
            messages.error(request, 'ID front must be JPG or PNG.')
            return redirect('user_dashboard:kyc:upload_documents')
        
        if id_back and id_back.content_type not in allowed_types:
            messages.error(request, 'ID back must be JPG or PNG.')
            return redirect('user_dashboard:kyc:upload_documents')
        
        # Validate file sizes (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if id_front.size > max_size:
            messages.error(request, 'ID front image too large (max 5MB).')
            return redirect('user_dashboard:kyc:upload_documents')
        
        if id_back and id_back.size > max_size:
            messages.error(request, 'ID back image too large (max 5MB).')
            return redirect('user_dashboard:kyc:upload_documents')
        
        # Delete old files if they exist
        if kyc_profile.id_front_image:
            kyc_profile.id_front_image.delete(save=False)
        if kyc_profile.id_back_image:
            kyc_profile.id_back_image.delete(save=False)
        
        # Save new files
        kyc_profile.id_front_image = id_front
        if id_back:
            kyc_profile.id_back_image = id_back
        kyc_profile.save()
        
        log_kyc_action(
            kyc_profile,
            'documents_uploaded',
            request.user,
            f"Uploaded {kyc_profile.document_type} documents",
            get_client_ip(request)
        )
        
        messages.success(request, 'Documents uploaded successfully.')
        return redirect('user_dashboard:kyc:upload_selfie')
    
    context = {
        'kyc_profile': kyc_profile,
    }
    
    return render(request, 'user_dashboard/kyc_upload_documents.html', context)


@login_required(login_url='Login')
def kyc_upload_selfie(request):
    """
    Step 3: Upload live selfie.
    """
    kyc_profile = get_kyc_profile(request.user)
    
    if not kyc_profile.can_submit:
        messages.error(request, 'You cannot modify KYC at this time.')
        return redirect('user_dashboard:kyc:dashboard')
    
    if not kyc_profile.id_front_image:
        messages.warning(request, 'Please upload your ID documents first.')
        return redirect('user_dashboard:kyc:upload_documents')
    
    if request.method == 'POST':
        selfie = request.FILES.get('selfie')
        
        if not selfie:
            messages.error(request, 'Selfie is required.')
            return redirect('user_dashboard:kyc:upload_selfie')
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if selfie.content_type not in allowed_types:
            messages.error(request, 'Selfie must be JPG or PNG.')
            return redirect('user_dashboard:kyc:upload_selfie')
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024
        if selfie.size > max_size:
            messages.error(request, 'Selfie image too large (max 5MB).')
            return redirect('user_dashboard:kyc:upload_selfie')
        
        # Delete old selfie if exists
        if kyc_profile.selfie_image:
            kyc_profile.selfie_image.delete(save=False)
        
        # Save new selfie
        kyc_profile.selfie_image = selfie
        kyc_profile.save()
        
        log_kyc_action(
            kyc_profile,
            'documents_uploaded',
            request.user,
            "Uploaded selfie",
            get_client_ip(request)
        )
        
        messages.success(request, 'Selfie uploaded successfully.')
        return redirect('user_dashboard:kyc:review_submit')
    
    context = {
        'kyc_profile': kyc_profile,
    }
    
    return render(request, 'user_dashboard/kyc_upload_selfie.html', context)


@login_required(login_url='Login')
def kyc_review_submit(request):
    """
    Step 4: Review all information and submit for approval.
    """
    kyc_profile = get_kyc_profile(request.user)
    
    if not kyc_profile.can_submit:
        messages.error(request, 'You cannot submit KYC at this time.')
        return redirect('user_dashboard:kyc:dashboard')
    
    # Check all requirements are met
    if not all([
        kyc_profile.declared_national_id,
        kyc_profile.document_type,
        kyc_profile.id_front_image,
        kyc_profile.selfie_image
    ]):
        messages.error(request, 'Please complete all steps before submitting.')
        return redirect('user_dashboard:kyc:start')
    
    # Check back image for national ID
    if kyc_profile.document_type == 'national_id' and not kyc_profile.id_back_image:
        messages.error(request, 'Please upload the back of your National ID.')
        return redirect('user_dashboard:kyc:upload_documents')
    
    if request.method == 'POST':
        # Submit for review
        kyc_profile.submit_for_review()
        
        log_kyc_action(
            kyc_profile,
            'submitted',
            request.user,
            "KYC submitted for admin review",
            get_client_ip(request)
        )
        
        # Send notification to user
        from notifications.utils import send_notif
        try:
            send_notif(
                None, None, True, True,
                "KYC Submitted",
                "Your verification documents have been submitted for review. "
                "We'll notify you once the review is complete (usually 1-2 business days).",
                None, False, request.user
            )
        except Exception:
            pass
        
        messages.success(
            request,
            'KYC verification submitted successfully! '
            'We will review your documents and notify you within 1-2 business days.'
        )
        return redirect('user_dashboard:kyc:dashboard')
    
    context = {
        'kyc_profile': kyc_profile,
    }
    
    return render(request, 'user_dashboard/kyc_review_submit.html', context)


@login_required(login_url='Login')
@require_http_methods(["POST"])
def kyc_delete_document(request):
    """
    AJAX endpoint to delete uploaded documents.
    """
    kyc_profile = get_kyc_profile(request.user)
    
    if not kyc_profile.can_submit:
        return JsonResponse({
            'success': False,
            'error': 'Cannot modify KYC at this time'
        }, status=403)
    
    document_type = request.POST.get('document_type')
    
    try:
        if document_type == 'id_front' and kyc_profile.id_front_image:
            kyc_profile.id_front_image.delete()
            kyc_profile.id_front_image = None
            kyc_profile.save()
        elif document_type == 'id_back' and kyc_profile.id_back_image:
            kyc_profile.id_back_image.delete()
            kyc_profile.id_back_image = None
            kyc_profile.save()
        elif document_type == 'selfie' and kyc_profile.selfie_image:
            kyc_profile.selfie_image.delete()
            kyc_profile.selfie_image = None
            kyc_profile.save()
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid document type'
            }, status=400)
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)