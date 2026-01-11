from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from .forms import ContactForm
from .emails import send_contact_notification, send_auto_reply
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get the client's IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@require_http_methods(["GET", "POST"])
@csrf_protect
def contact_view(request):
    """
    Handle contact form submission.
    Supports both regular form submission and AJAX requests.
    """
    if request.method == 'POST':
        form = ContactForm(request.POST)
        
        if form.is_valid():
            try:
                # Save the contact message
                contact_message = form.save(commit=False)
                
                # Capture IP address
                contact_message.ip_address = get_client_ip(request)
                
                # Save to database
                contact_message.save()
                
                logger.info(f"New contact message saved: ID {contact_message.id} from {contact_message.email}")
                
                # Send notification email to team
                email_sent = send_contact_notification(contact_message)
                
                # Send auto-reply to submitter
                auto_reply_sent = send_auto_reply(contact_message)
                
                if not email_sent:
                    logger.warning(f"Failed to send notification for message ID: {contact_message.id}")
                
                # Check if this is an AJAX request
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Thank you! Your message has been sent. We\'ll get back to you soon.'
                    })
                else:
                    messages.success(
                        request, 
                        'Thank you! Your message has been sent. We\'ll get back to you soon.'
                    )
                    return redirect('contact:contact')
                    
            except Exception as e:
                logger.error(f"Error saving contact message: {str(e)}")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'An error occurred. Please try again later.'
                    }, status=500)
                else:
                    messages.error(
                        request,
                        'An error occurred. Please try again later.'
                    )
                    return redirect('contact:contact')
        else:
            # Form is invalid
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Please correct the errors in the form.',
                    'errors': form.errors
                }, status=400)
            else:
                messages.error(request, 'Please correct the errors below.')
    else:
        # GET request - show empty form
        form = ContactForm()
    
    context = {
        'form': form
    }
    
    return render(request, 'home/contact_us.html', context)