from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import requests
import json


def send_email(subject, recipient_list, template_path, context):
    """
    Send email with rendered HTML template.

    Args:
        subject (str): Subject of the email.
        recipient_list (list): List of recipient email addresses.
        template_path (str): Path to the email template.
        context (dict): Context data to render the template.

    Returns:
        bool: True if email is sent successfully, False otherwise.
    """
    try:
        # Render HTML template
        html_message = render_to_string(template_path, context)

        # Strip HTML tags for plain text email
        plain_message = strip_tags(html_message)

        # Send email
        send_mail(
            subject,
            plain_message,
            'sender@example.com',  # Change to your email address
            recipient_list,
            html_message=html_message,
        )
        return True
    except Exception as e:
        # Handle exception (e.g., logging)
        print(f"Failed to send email: {str(e)}")
        return False

#send sms
def send_sms(recipient, message, profile_code, external_id=None, dlr_callback_url=None, message_type=1, req_type=1, api_key='your-api-key'):
    """
    Send SMS using MuruTech API.

    Args:
        recipient (str): Recipient phone number in international format (e.g., "+254792XXXXXX").
        message (str): Message content.
        profile_code (str): Profile code for the SMS service.
        external_id (str, optional): Unique external ID for tracking purposes. Defaults to None.
        dlr_callback_url (str, optional): URL for delivery report callback. Defaults to None.
        message_type (int, optional): Type of message. Defaults to 1.
        req_type (int, optional): Request type. Defaults to 1.
        api_key (str, optional): API key for authentication. Defaults to 'your-api-key'.

    Returns:
        dict: Response from the API.
    """
    url = "https://sms.murutechinc.com:2780/api/outbox/create"

    payload = {
        "profile_code": profile_code,
        "messages": [
            {
                "recipient": recipient,
                "message": message,
                "message_type": message_type,
                "req_type": req_type,
                "external_id": external_id
            }
        ],
        "dlr_callback_url": dlr_callback_url
    }

    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an error if request was not successful
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending SMS: {e}")
        return None

# Example usage:
# response = send_sms("+254792XXXXXX", "Test message", "12345", external_id="Your unique external_id", dlr_callback_url="https://posthere.io/")
# print(response)
