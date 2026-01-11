from django import forms
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    """
    Form for website visitors to submit contact messages.
    Includes validation and spam prevention.
    """
    
    # Honeypot field - hidden from users, but bots will fill it
    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
        label='Leave this field empty'
    )
    
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Name',
                'maxlength': '200'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your.email@example.com',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'What is this about?',
                'maxlength': '300'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Tell us more...',
                'rows': 5,
                'maxlength': '5000'
            }),
        }
        labels = {
            'name': 'Name',
            'email': 'Email',
            'subject': 'Subject',
            'message': 'Message',
        }
    
    def clean_honeypot(self):
        """Check honeypot field - if filled, it's likely a bot."""
        honeypot = self.cleaned_data.get('honeypot')
        if honeypot:
            raise forms.ValidationError('Bot detected. Submission rejected.')
        return honeypot
    
    def clean_name(self):
        """Validate name field."""
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 2:
            raise forms.ValidationError('Please enter a valid name (at least 2 characters).')
        return name
    
    def clean_subject(self):
        """Validate subject field."""
        subject = self.cleaned_data.get('subject', '').strip()
        if len(subject) < 3:
            raise forms.ValidationError('Please enter a subject (at least 3 characters).')
        return subject
    
    def clean_message(self):
        """Validate message field."""
        message = self.cleaned_data.get('message', '').strip()
        if len(message) < 10:
            raise forms.ValidationError('Please enter a message (at least 10 characters).')
        
        # Optional: Check for spam keywords
        spam_keywords = SPAM_KEYWORDS = [
                # Pharma
                'viagra', 'cialis', 'levitra', 'buy pills',

                # Gambling
                'casino', 'online casino', 'lottery', 'jackpot', 'prize money',

                # Crypto scams
                'guaranteed returns', 'double your money', 'crypto giveaway',
                'send btc', 'send usdt',

                # SEO spam
                'seo services', 'backlinks', 'guest post', 'link building',

                # Adult
                'escort', 'porn', 'xxx',

                # Generic scams
                'click here', 'limited offer', 'act now',
                'congratulations you won', 'urgent response'
            ]

        message_lower = message.lower()
        for keyword in spam_keywords:
            if keyword in message_lower:
                raise forms.ValidationError('Your message contains prohibited content.')
        
        return message