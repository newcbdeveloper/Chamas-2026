from django import forms
from django.core.exceptions import ValidationError
from .models import SupportTicket, SupportMessage
from .utils import sanitize_message, validate_file_upload
from .permissions import get_available_assignees


class CreateTicketForm(forms.Form):
    """
    Form for creating a new support ticket
    """
    category = forms.ChoiceField(
        choices=SupportTicket.CATEGORY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Brief description of your issue',
            'required': True
        })
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Please describe your issue in detail...',
            'required': True
        })
    )
    
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.jpg,.jpeg,.png,.pdf,.txt,.doc,.docx'
        })
    )
    
    def clean_message(self):
        """Validate and sanitize message"""
        message = self.cleaned_data.get('message')
        
        if not message or len(message.strip()) < 10:
            raise ValidationError("Please provide more details about your issue (at least 10 characters).")
        
        try:
            sanitize_message(message)
        except ValidationError as e:
            raise e
        
        return message
    
    def clean_attachment(self):
        """Validate file upload"""
        attachment = self.cleaned_data.get('attachment')
        
        if attachment:
            try:
                validate_file_upload(attachment)
            except ValidationError as e:
                raise e
        
        return attachment
    
    def clean_subject(self):
        """Validate subject"""
        subject = self.cleaned_data.get('subject')
        
        if not subject or len(subject.strip()) < 5:
            raise ValidationError("Subject must be at least 5 characters long.")
        
        return subject


class SendMessageForm(forms.Form):
    """
    Form for sending a message in an existing ticket
    """
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Type your message...',
            'required': True
        })
    )
    
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.jpg,.jpeg,.png,.pdf,.txt,.doc,.docx'
        })
    )
    
    def clean_message(self):
        """Validate and sanitize message"""
        message = self.cleaned_data.get('message')
        
        if not message or len(message.strip()) < 1:
            raise ValidationError("Message cannot be empty.")
        
        try:
            sanitize_message(message)
        except ValidationError as e:
            raise e
        
        return message
    
    def clean_attachment(self):
        """Validate file upload"""
        attachment = self.cleaned_data.get('attachment')
        
        if attachment:
            try:
                validate_file_upload(attachment)
            except ValidationError as e:
                raise e
        
        return attachment


class AdminResponseForm(forms.Form):
    """
    Form for admin to respond to tickets
    Includes options for status update and internal notes
    """
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Type your response to the user...',
            'required': True
        }),
        label='Response to User'
    )
    
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.jpg,.jpeg,.png,.pdf,.txt,.doc,.docx'
        })
    )
    
    update_status = forms.ChoiceField(
        choices=[
            ('', 'Keep Current Status'),
            ('open', 'Open'),
            ('pending', 'Pending User Response'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Update Status'
    )
    
    internal_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Internal notes (not visible to user)...'
        }),
        label='Internal Note (Admin Only)'
    )
    
    def clean_message(self):
        """Validate message"""
        message = self.cleaned_data.get('message')
        
        if not message or len(message.strip()) < 1:
            raise ValidationError("Response message cannot be empty.")
        
        return message
    
    def clean_attachment(self):
        """Validate file upload"""
        attachment = self.cleaned_data.get('attachment')
        
        if attachment:
            try:
                validate_file_upload(attachment)
            except ValidationError as e:
                raise e
        
        return attachment


class AssignTicketForm(forms.Form):
    """
    Form for assigning tickets to admins
    """
    assigned_to = forms.ModelChoiceField(
        queryset=get_available_assignees(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        label='Assign To',
        empty_label='Select Admin...'
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Assignment notes (optional)...'
        }),
        label='Notes'
    )
    
    def clean_assigned_to(self):
        """Validate assignee"""
        assigned_to = self.cleaned_data.get('assigned_to')
        
        if not assigned_to:
            raise ValidationError("Please select an admin to assign the ticket to.")
        
        if not assigned_to.is_staff:
            raise ValidationError("Selected user is not a staff member.")
        
        return assigned_to


class UpdateTicketStatusForm(forms.Form):
    """
    Simple form for updating ticket status
    """
    status = forms.ChoiceField(
        choices=SupportTicket.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Status change notes (optional)...'
        })
    )


class InternalNoteForm(forms.Form):
    """
    Form for adding internal notes (admin only)
    """
    note = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Internal note (not visible to user)...',
            'required': True
        }),
        label='Internal Note'
    )
    
    def clean_note(self):
        """Validate note"""
        note = self.cleaned_data.get('note')
        
        if not note or len(note.strip()) < 1:
            raise ValidationError("Note cannot be empty.")
        
        return note


class TicketSearchForm(forms.Form):
    """
    Form for searching and filtering tickets
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by reference, subject, or user...'
        })
    )
    
    category = forms.ChoiceField(
        required=False,
        choices=[('', 'All Categories')] + list(SupportTicket.CATEGORY_CHOICES),
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + list(SupportTicket.STATUS_CHOICES),
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'All Priorities')] + list(SupportTicket.PRIORITY_CHOICES),
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=get_available_assignees(),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        empty_label='All Admins'
    )