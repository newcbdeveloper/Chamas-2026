from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_http_methods
import logging

from .models import SupportTicket, SupportMessage
from .forms import CreateTicketForm, SendMessageForm
from .services import TicketService, NotificationService
from .permissions import can_view_ticket, ticket_owner_or_admin_required
from authentication.models import Profile
from notifications.models import UserNotificationHistory

from django.views.decorators.csrf import csrf_exempt
import json

from .permissions import admin_required
from .forms import AdminResponseForm, AssignTicketForm, UpdateTicketStatusForm, InternalNoteForm, TicketSearchForm

logger = logging.getLogger(__name__)


# ============================================
# USER-FACING VIEWS
# ============================================

@login_required(login_url='Login')
def my_tickets(request):
    """
    Display all tickets created by the current user
    With filtering and search
    """
    try:
        user_profile = Profile.objects.get(owner=request.user)
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect('user_dashboard:home')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    
    # Apply filters
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    if category_filter:
        tickets = tickets.filter(category=category_filter)
    
    if search_query:
        tickets = tickets.filter(
            Q(reference_number__icontains=search_query) |
            Q(subject__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(tickets, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts for each status
    status_counts = {
        'all': SupportTicket.objects.filter(user=request.user).count(),
        'open': SupportTicket.objects.filter(user=request.user, status='open').count(),
        'pending': SupportTicket.objects.filter(user=request.user, status='pending').count(),
        'resolved': SupportTicket.objects.filter(user=request.user, status='resolved').count(),
        'closed': SupportTicket.objects.filter(user=request.user, status='closed').count(),
    }
    
    context = {
        'user_profile': user_profile,
        'page_obj': page_obj,
        'status_counts': status_counts,
        'current_status': status_filter,
        'current_category': category_filter,
        'search_query': search_query,
        'categories': SupportTicket.CATEGORY_CHOICES,
    }
    
    return render(request, 'support/my_tickets.html', context)


@login_required(login_url='Login')
def create_ticket(request):
    """
    Create a new support ticket
    """
    try:
        user_profile = Profile.objects.get(owner=request.user)
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect('user_dashboard:home')
    
    if request.method == 'POST':
        form = CreateTicketForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Create the ticket
                ticket = TicketService.create_ticket(
                    user=request.user,
                    category=form.cleaned_data['category'],
                    subject=form.cleaned_data['subject'],
                    initial_message=form.cleaned_data['message'],
                    attachment=form.cleaned_data.get('attachment'),
                    request=request
                )
                
                messages.success(
                    request,
                    f'✅ Support ticket {ticket.reference_number} created successfully! '
                    f'Our team will respond as soon as possible.'
                )
                
                return redirect('support:ticket_detail', ticket_id=ticket.id)
                
            except Exception as e:
                logger.error(f"Error creating ticket: {str(e)}")
                messages.error(request, f"Error creating ticket: {str(e)}")
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CreateTicketForm()
    
    context = {
        'user_profile': user_profile,
        'form': form,
    }
    
    return render(request, 'support/create_ticket.html', context)


@login_required(login_url='Login')
def ticket_detail(request, ticket_id):
    """
    Display a single ticket with all messages (chat-style)
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    # Check permissions
    if not can_view_ticket(request.user, ticket):
        messages.error(request, "You don't have permission to view this ticket.")
        return redirect('support:my_tickets')
    
    try:
        user_profile = Profile.objects.get(owner=request.user)
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect('user_dashboard:home')
    
    # Get all messages (excluding internal notes)
    messages_list = ticket.messages.filter(is_internal=False).order_by('created_at')
    
    # Mark admin messages as read by user
    TicketService.mark_messages_as_read(ticket, user_type='user')
    
    # Form for sending new message
    if request.method == 'POST':
        form = SendMessageForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Add message
                TicketService.add_message(
                    ticket=ticket,
                    sender_user=request.user,
                    message_text=form.cleaned_data['message'],
                    attachment=form.cleaned_data.get('attachment'),
                    is_admin=False
                )
                
                messages.success(request, 'Message sent successfully!')
                return redirect('support:ticket_detail', ticket_id=ticket.id)
                
            except Exception as e:
                logger.error(f"Error sending message: {str(e)}")
                messages.error(request, f"Error sending message: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SendMessageForm()
    
    context = {
        'user_profile': user_profile,
        'ticket': ticket,
        'messages_list': messages_list,
        'form': form,
        'can_reopen': ticket.is_closed and (timezone.now() - ticket.closed_at).days <= 7 if ticket.closed_at else False,
    }
    
    return render(request, 'support/ticket_detail.html', context)


@login_required(login_url='Login')
@require_http_methods(["POST"])
def send_message(request, ticket_id):
    """
    Send a message to a ticket (POST endpoint)
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    # Check permissions
    if not can_view_ticket(request.user, ticket):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    form = SendMessageForm(request.POST, request.FILES)
    
    if form.is_valid():
        try:
            # Add message
            message = TicketService.add_message(
                ticket=ticket,
                sender_user=request.user,
                message_text=form.cleaned_data['message'],
                attachment=form.cleaned_data.get('attachment'),
                is_admin=False
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Message sent successfully',
                'message_id': str(message.id)
            })
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    else:
        errors = {field: error[0] for field, error in form.errors.items()}
        return JsonResponse({'success': False, 'errors': errors}, status=400)
    

# ADMIN VIEWS 

@login_required(login_url='Login')
@admin_required
def admin_tickets_list(request):
    """
    Admin dashboard showing all support tickets
    With advanced filtering and search
    """
    try:
        user_profile = Profile.objects.get(owner=request.user)
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect('user_dashboard:home')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    priority_filter = request.GET.get('priority', '')
    assigned_filter = request.GET.get('assigned_to', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    tickets = SupportTicket.objects.all().select_related('user', 'assigned_to').order_by('-created_at')
    
    # Apply filters
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    if category_filter:
        tickets = tickets.filter(category=category_filter)
    
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    
    if assigned_filter:
        if assigned_filter == 'unassigned':
            tickets = tickets.filter(assigned_to__isnull=True)
        elif assigned_filter == 'me':
            tickets = tickets.filter(assigned_to=request.user)
        else:
            tickets = tickets.filter(assigned_to_id=assigned_filter)
    
    if search_query:
        tickets = tickets.filter(
            Q(reference_number__icontains=search_query) |
            Q(subject__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(tickets, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    stats = {
        'total': SupportTicket.objects.count(),
        'open': SupportTicket.objects.filter(status='open').count(),
        'pending': SupportTicket.objects.filter(status='pending').count(),
        'resolved': SupportTicket.objects.filter(status='resolved').count(),
        'unassigned': SupportTicket.objects.filter(assigned_to__isnull=True, status__in=['open', 'pending']).count(),
        'my_tickets': SupportTicket.objects.filter(assigned_to=request.user, status__in=['open', 'pending']).count(),
    }
    
    # Get available admins for assignment
    from .permissions import get_available_assignees
    available_admins = get_available_assignees()
    
    context = {
        'user_profile': user_profile,
        'page_obj': page_obj,
        'stats': stats,
        'current_status': status_filter,
        'current_category': category_filter,
        'current_priority': priority_filter,
        'current_assigned': assigned_filter,
        'search_query': search_query,
        'categories': SupportTicket.CATEGORY_CHOICES,
        'priorities': SupportTicket.PRIORITY_CHOICES,
        'available_admins': available_admins,
    }
    
    return render(request, 'support/admin_tickets_list.html', context)


@login_required(login_url='Login')
@admin_required
def admin_ticket_detail(request, ticket_id):
    """
    Admin view of a single ticket
    Includes user context panel and admin actions
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    try:
        user_profile = Profile.objects.get(owner=request.user)
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect('user_dashboard:home')
    
    # Get all messages including internal notes
    messages_list = ticket.messages.order_by('created_at')
    
    # Mark user messages as read by admin
    TicketService.mark_messages_as_read(ticket, user_type='admin')
    
    # Get user context
    user_context = TicketService.get_user_context(ticket.user)
    
    # Get audit logs
    audit_logs = ticket.audit_logs.all()[:10]
    
    # Forms
    response_form = AdminResponseForm()
    assign_form = AssignTicketForm()
    status_form = UpdateTicketStatusForm(initial={'status': ticket.status})
    internal_note_form = InternalNoteForm()
    
    context = {
        'user_profile': user_profile,
        'ticket': ticket,
        'messages_list': messages_list,
        'user_context': user_context,
        'audit_logs': audit_logs,
        'response_form': response_form,
        'assign_form': assign_form,
        'status_form': status_form,
        'internal_note_form': internal_note_form,
    }
    
    return render(request, 'support/admin_ticket_detail.html', context)


@login_required(login_url='Login')
@admin_required
@require_http_methods(["POST"])
def assign_ticket(request, ticket_id):
    """
    Assign a ticket to an admin
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    form = AssignTicketForm(request.POST)
    
    if form.is_valid():
        try:
            TicketService.assign_ticket(
                ticket=ticket,
                assigned_to=form.cleaned_data['assigned_to'],
                assigned_by=request.user,
                notes=form.cleaned_data.get('notes', ''),
                request=request
            )
            
            messages.success(
                request,
                f'Ticket assigned to {form.cleaned_data["assigned_to"].get_full_name()} successfully!'
            )
            
        except Exception as e:
            logger.error(f"Error assigning ticket: {str(e)}")
            messages.error(request, f"Error assigning ticket: {str(e)}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    
    return redirect('support:admin_ticket_detail', ticket_id=ticket.id)


@login_required(login_url='Login')
@admin_required
@require_http_methods(["POST"])
def update_ticket_status(request, ticket_id):
    """
    Update ticket status
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    form = UpdateTicketStatusForm(request.POST)
    
    if form.is_valid():
        try:
            TicketService.update_status(
                ticket=ticket,
                new_status=form.cleaned_data['status'],
                admin_user=request.user,
                notes=form.cleaned_data.get('notes', ''),
                request=request
            )
            
            messages.success(request, 'Ticket status updated successfully!')
            
        except Exception as e:
            logger.error(f"Error updating status: {str(e)}")
            messages.error(request, f"Error updating status: {str(e)}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    
    return redirect('support:admin_ticket_detail', ticket_id=ticket.id)


@login_required(login_url='Login')
@admin_required
@require_http_methods(["POST"])
def admin_respond(request, ticket_id):
    """
    Admin responds to a ticket
    Can include status update and internal note
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    form = AdminResponseForm(request.POST, request.FILES)
    
    if form.is_valid():
        try:
            # Send response message
            TicketService.add_message(
                ticket=ticket,
                sender_user=request.user,
                message_text=form.cleaned_data['message'],
                attachment=form.cleaned_data.get('attachment'),
                is_admin=True,
                is_internal=False
            )
            
            # Add internal note if provided
            if form.cleaned_data.get('internal_note'):
                TicketService.add_message(
                    ticket=ticket,
                    sender_user=request.user,
                    message_text=form.cleaned_data['internal_note'],
                    is_admin=True,
                    is_internal=True
                )
            
            # Update status if requested
            if form.cleaned_data.get('update_status'):
                TicketService.update_status(
                    ticket=ticket,
                    new_status=form.cleaned_data['update_status'],
                    admin_user=request.user,
                    notes="Status updated with admin response",
                    request=request
                )
            
            messages.success(request, 'Response sent successfully!')
            
        except Exception as e:
            logger.error(f"Error sending admin response: {str(e)}")
            messages.error(request, f"Error sending response: {str(e)}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    
    return redirect('support:admin_ticket_detail', ticket_id=ticket.id)


@login_required(login_url='Login')
@admin_required
@require_http_methods(["POST"])
def add_internal_note(request, ticket_id):
    """
    Add an internal note to a ticket (admin only, not visible to user)
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    form = InternalNoteForm(request.POST)
    
    if form.is_valid():
        try:
            TicketService.add_message(
                ticket=ticket,
                sender_user=request.user,
                message_text=form.cleaned_data['note'],
                is_admin=True,
                is_internal=True
            )
            
            messages.success(request, 'Internal note added successfully!')
            
        except Exception as e:
            logger.error(f"Error adding internal note: {str(e)}")
            messages.error(request, f"Error adding note: {str(e)}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    
    return redirect('support:admin_ticket_detail', ticket_id=ticket.id)


# API ENDPOINTS

@login_required(login_url='Login')
@require_http_methods(["GET"])
def api_get_messages(request, ticket_id):
    """
    API endpoint to get messages for a ticket (AJAX)
    Used for auto-refresh
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    # Check permissions
    if not can_view_ticket(request.user, ticket):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    # Determine if user is admin
    is_admin = request.user.is_staff or request.user.is_superuser
    
    # Get messages (exclude internal notes for non-admins)
    if is_admin:
        messages_list = ticket.messages.order_by('created_at')
    else:
        messages_list = ticket.messages.filter(is_internal=False).order_by('created_at')
    
    # Serialize messages
    messages_data = []
    for msg in messages_list:
        messages_data.append({
            'id': str(msg.id),
            'sender_type': msg.sender_type,
            'sender_name': msg.sender.get_full_name() if msg.sender else 'System',
            'message': msg.message,
            'attachment': msg.attachment.url if msg.attachment else None,
            'attachment_filename': msg.attachment_filename,
            'is_internal': msg.is_internal,
            'created_at': msg.created_at.isoformat(),
            'created_at_display': msg.created_at.strftime('%b %d, %Y at %I:%M %p'),
        })
    
    return JsonResponse({
        'success': True,
        'messages': messages_data,
        'ticket': {
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'user_unread_count': ticket.user_unread_count,
            'admin_unread_count': ticket.admin_unread_count,
        }
    })


@login_required(login_url='Login')
@require_http_methods(["POST"])
def api_send_message(request):
    """
    API endpoint to send a message (AJAX)
    """
    try:
        ticket_id = request.POST.get('ticket_id')
        message_text = request.POST.get('message')
        
        if not ticket_id or not message_text:
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        
        # Check permissions
        if not can_view_ticket(request.user, ticket):
            return JsonResponse({
                'success': False,
                'error': 'Permission denied'
            }, status=403)
        
        # Determine if sender is admin
        is_admin = request.user.is_staff or request.user.is_superuser
        
        # Add message
        message = TicketService.add_message(
            ticket=ticket,
            sender_user=request.user,
            message_text=message_text,
            is_admin=is_admin
        )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': str(message.id),
                'sender_type': message.sender_type,
                'sender_name': message.sender.get_full_name(),
                'message': message.message,
                'created_at_display': message.created_at.strftime('%b %d, %Y at %I:%M %p'),
            }
        })
        
    except Exception as e:
        logger.error(f"Error in api_send_message: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='Login')
@require_http_methods(["POST"])
def api_mark_messages_read(request, ticket_id):
    """
    API endpoint to mark messages as read (AJAX)
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    # Check permissions
    if not can_view_ticket(request.user, ticket):
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)
    
    # Determine user type
    is_admin = request.user.is_staff or request.user.is_superuser
    user_type = 'admin' if is_admin else 'user'
    
    # Mark messages as read
    TicketService.mark_messages_as_read(ticket, user_type=user_type)
    
    return JsonResponse({
        'success': True,
        'user_unread_count': ticket.user_unread_count,
        'admin_unread_count': ticket.admin_unread_count,
    })