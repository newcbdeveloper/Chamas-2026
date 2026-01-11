from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


def send_contact_notification(contact_message):
    """
    Send email notification to ChamaSpace team when a new contact message is submitted.
    
    Args:
        contact_message: ContactMessage instance
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Email subject
        subject = f"New Contact Form Submission: {contact_message.subject}"
        
        # Get recipients from settings
        recipients = getattr(
            settings, 
            'CONTACT_EMAIL_RECIPIENTS', 
            ['info@chamaspace.com']
        )
        
        # Prepare context for email template
        context = {
            'name': contact_message.name,
            'email': contact_message.email,
            'subject': contact_message.subject,
            'message': contact_message.message,
            'submitted_at': contact_message.created_at,
            'ip_address': contact_message.ip_address,
        }
        
        # Render HTML email
        html_message = render_to_string('contact/emails/contact_notification.html', context)
        
        # Create plain text version by stripping HTML tags
        text_message = strip_tags(html_message)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            reply_to=[contact_message.email]  # Allow direct reply to submitter
        )
        
        # Attach HTML version
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Contact notification sent for message ID: {contact_message.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send contact notification: {str(e)}")
        return False


def send_auto_reply(contact_message):
    """
    Send automatic confirmation email to the person who submitted the contact form.
    
    Args:
        contact_message: ContactMessage instance
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Email subject
        subject = "Thank you for contacting ChamaSpace"
        
        # Prepare context
        context = {
            'name': contact_message.name,
            'subject': contact_message.subject,
            'submitted_at': contact_message.created_at,
        }
        
        # Render HTML email
        html_message = render_to_string('contact/emails/auto_reply.html', context)
        
        # Create plain text version
        text_message = strip_tags(html_message)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[contact_message.email],
            reply_to=getattr(settings, 'CONTACT_EMAIL_RECIPIENTS', ['info@chamaspace.com'])
        )
        
        # Attach HTML version
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Auto-reply sent to: {contact_message.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send auto-reply: {str(e)}")
        return False