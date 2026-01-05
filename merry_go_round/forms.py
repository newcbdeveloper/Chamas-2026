from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Round, RoundMembership, Contribution, Invitation, RoundMessage, UserProfile
from django import forms
from django.core.exceptions import ValidationError
from authentication.models import Profile
import re



class RoundCreationForm(forms.ModelForm):
    """Form for creating new savings rounds"""
    
    # Additional fields not in model
    start_immediately = forms.BooleanField(
        required=False,
        initial=False,
        label="Start round immediately when full",
        help_text="Round will start automatically when max members is reached"
    )
    
    class Meta:
        model = Round
        fields = [
            'name', 'description', 'round_type', 'payout_model',
            'contribution_amount', 'frequency', 'max_members',
            'min_trust_score', 'interest_rate'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., January 2025 Savings Circle',
                'maxlength': '200'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe the purpose of this round...',
                'rows': 4
            }),
            'round_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'round-type-select'
            }),
            'payout_model': forms.Select(attrs={
                'class': 'form-control',
                'id': 'payout-model-select'
            }),
            'contribution_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter amount (min: 100)',
                'min': '100',
                'step': '50'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'max_members': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of members (2-100)',
                'min': '2',
                'max': '100'
            }),
            'min_trust_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Minimum trust score (0-100)',
                'min': '0',
                'max': '100'
            }),
            'interest_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Annual interest rate %',
                'step': '0.01',
                'readonly': 'readonly'
            })
        }
        labels = {
            'name': 'Round Name',
            'description': 'Description (Optional)',
            'round_type': 'Privacy Setting',
            'payout_model': 'Payout Model',
            'contribution_amount': 'Contribution Amount (KES)',
            'frequency': 'Contribution Frequency',
            'max_members': 'Maximum Members',
            'min_trust_score': 'Minimum Trust Score',
            'interest_rate': 'Interest Rate (% per year)'
        }
        help_texts = {
            'round_type': 'Public rounds are open to all users. Private rounds require invitations.',
            'payout_model': 'Marathon: everyone paid at end. Rotational: turn-based payouts (private only).',
            'contribution_amount': 'Amount each member contributes per cycle. You only need this amount to join, not the full commitment.',
            'frequency': 'How often members contribute',
            'max_members': 'Total number of members allowed in this round',
            'min_trust_score': 'Minimum trust score required to join (recommended: 30+)',
            'interest_rate': 'Set by admin - funds earn this rate while in escrow'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set interest rate from constance
        from constance import config
        self.fields['interest_rate'].initial = config.MGR_DEFAULT_INTEREST_RATE
        self.fields['interest_rate'].widget.attrs['value'] = str(config.MGR_DEFAULT_INTEREST_RATE)
        
        # Check if rotational model is enabled
        if not config.ROTATIONAL_MODEL_ENABLED:
            # Remove rotational option from choices
            self.fields['payout_model'].choices = [
                choice for choice in self.fields['payout_model'].choices 
                if choice[0] != 'rotational'
            ]
    
    def clean(self):
        cleaned_data = super().clean()
        round_type = cleaned_data.get('round_type')
        payout_model = cleaned_data.get('payout_model')
        
        # Validate: Public rounds can only use marathon model
        if round_type == 'public' and payout_model != 'marathon':
            raise ValidationError(
                "Public rounds must use the Marathon payout model for security. "
                "Create a private round to use the Rotational model."
            )
        
        # Validate: Rotational model must be enabled
        from constance import config
        if payout_model == 'rotational' and not config.ROTATIONAL_MODEL_ENABLED:
            raise ValidationError(
                "The Rotational model is currently disabled by the administrator. "
                "Please use the Marathon model or contact support."
            )
        
        return cleaned_data
    
    def clean_contribution_amount(self):
        amount = self.cleaned_data.get('contribution_amount')
        if amount and amount < Decimal('100.00'):
            raise ValidationError("Contribution amount must be at least KES 100.")
        return amount
    
    def clean_max_members(self):
        max_members = self.cleaned_data.get('max_members')
        if max_members and (max_members < 2 or max_members > 100):
            raise ValidationError("Number of members must be between 2 and 100.")
        return max_members
    
    def clean_min_trust_score(self):
        score = self.cleaned_data.get('min_trust_score')
        if score and (score < 0 or score > 100):
            raise ValidationError("Trust score must be between 0 and 100.")
        return score


class JoinRoundForm(forms.Form):
    """Form for joining a public round"""
    
    round_id = forms.UUIDField(widget=forms.HiddenInput())
    agree_to_terms = forms.BooleanField(
        required=True,
        label="I agree to contribute on time and understand the round rules",
        error_messages={
            'required': 'You must agree to the terms before joining.'
        }
    )
    
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_round_id(self):
        round_id = self.cleaned_data.get('round_id')
        
        try:
            round_obj = Round.objects.get(id=round_id)
        except Round.DoesNotExist:
            raise ValidationError("This round does not exist.")
        
        # Check if round is open for joining
        if round_obj.status not in ['draft', 'open']:
            raise ValidationError("This round is no longer open for new members.")
        
        # Check if round is full
        if round_obj.is_full():
            raise ValidationError("This round is full.")
        
        # Check if user already joined
        if self.user and RoundMembership.objects.filter(round=round_obj, user=self.user).exists():
            raise ValidationError("You are already a member of this round.")
        
        # Check trust score requirement
        if self.user:
            try:
                profile = self.user.mgr_profile
                if profile.trust_score < round_obj.min_trust_score:
                    raise ValidationError(
                        f"Your trust score ({profile.trust_score}) is below the minimum "
                        f"required ({round_obj.min_trust_score}) to join this round."
                    )
            except UserProfile.DoesNotExist:
                raise ValidationError("User profile not found. Please contact support.")
        
        return round_id


class InvitationForm(forms.ModelForm):
    """Form for sending invitations to private rounds"""
    
    invitee_type = forms.ChoiceField(
        choices=[
            ('email', 'Email Address'),
            ('phone', 'Phone Number'),
        ],
        widget=forms.RadioSelect,
        label="Invitation Method"
    )
    
    class Meta:
        model = Invitation
        fields = ['invitee_email', 'invitee_phone', 'message']
        widgets = {
            'invitee_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'invitee_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+254700000000'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Add a personal message (optional)...',
                'rows': 3
            })
        }
        labels = {
            'invitee_email': 'Email Address',
            'invitee_phone': 'Phone Number',
            'message': 'Personal Message (Optional)'
        }
    
    def __init__(self, *args, round_obj=None, inviter=None, **kwargs):
        self.round_obj = round_obj
        self.inviter = inviter
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        invitee_type = cleaned_data.get('invitee_type')
        invitee_email = cleaned_data.get('invitee_email')
        invitee_phone = cleaned_data.get('invitee_phone')
        
        # Validate that appropriate field is filled
        if invitee_type == 'email' and not invitee_email:
            raise ValidationError({'invitee_email': 'Email address is required.'})
        
        if invitee_type == 'phone' and not invitee_phone:
            raise ValidationError({'invitee_phone': 'Phone number is required.'})
        
        # Clear the field that's not being used
        if invitee_type == 'email':
            cleaned_data['invitee_phone'] = ''
        else:
            cleaned_data['invitee_email'] = ''
        
        # Check if round is full
        if self.round_obj and self.round_obj.is_full():
            raise ValidationError("This round is full and cannot accept more invitations.")
        
        return cleaned_data
    
    def clean_invitee_phone(self):
        phone = self.cleaned_data.get('invitee_phone')
        if phone:
            # Basic phone validation (Kenyan format)
            phone = phone.strip().replace(' ', '').replace('-', '')
            if not phone.startswith('+254') and not phone.startswith('0'):
                raise ValidationError("Please enter a valid Kenyan phone number (e.g., +254700000000 or 0700000000)")
            
            # Normalize to +254 format
            if phone.startswith('0'):
                phone = '+254' + phone[1:]
            
            return phone
        return phone


class ContributionConfirmForm(forms.Form):
    """Form for confirming contribution payment"""
    
    membership_id = forms.UUIDField(widget=forms.HiddenInput())
    cycle_number = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.HiddenInput()
    )
    payment_method = forms.ChoiceField(
        choices=[
            ('mpesa', 'M-Pesa'),
            ('bank', 'Bank Transfer'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='mpesa',
        label="Payment Method"
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+254700000000 or 0700000000'
        }),
        label="M-Pesa Phone Number",
        help_text="Required for M-Pesa payments"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        phone_number = cleaned_data.get('phone_number')
        
        # Validate phone number for M-Pesa
        if payment_method == 'mpesa' and not phone_number:
            raise ValidationError({'phone_number': 'Phone number is required for M-Pesa payments.'})
        
        return cleaned_data
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            phone = phone.strip().replace(' ', '').replace('-', '')
            if not phone.startswith('+254') and not phone.startswith('0'):
                raise ValidationError("Please enter a valid Kenyan phone number")
            
            if phone.startswith('0'):
                phone = '+254' + phone[1:]
            
            return phone
        return phone


class RoundMessageForm(forms.ModelForm):
    """Form for posting messages in a round"""
    
    class Meta:
        model = RoundMessage
        fields = ['subject', 'content']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Message subject (optional)',
                'maxlength': '200'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Write your message...',
                'rows': 4,
                'required': 'required'
            })
        }
        labels = {
            'subject': 'Subject (Optional)',
            'content': 'Message'
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content and len(content.strip()) < 5:
            raise ValidationError("Message must be at least 5 characters long.")
        return content


class RoundFilterForm(forms.Form):
    """Form for filtering rounds on the join page"""
    
    AMOUNT_CHOICES = [
        ('', 'Any Amount'),
        ('0-500', 'KES 100 - 500'),
        ('500-1000', 'KES 500 - 1,000'),
        ('1000-5000', 'KES 1,000 - 5,000'),
        ('5000-10000', 'KES 5,000 - 10,000'),
        ('10000+', 'KES 10,000+'),
    ]
    
    FREQUENCY_CHOICES = [
        ('', 'Any Frequency'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ]
    
    TRUST_SCORE_CHOICES = [
        ('', 'Any Trust Score'),
        ('0-30', '0 - 30'),
        ('30-50', '30 - 50'),
        ('50-70', '50 - 70'),
        ('70-100', '70 - 100'),
    ]
    
    STATUS_CHOICES = [
        ('', 'All Status'),
        ('open', 'Open for Joining'),
        ('active', 'Active'),
    ]
    
    contribution_amount = forms.ChoiceField(
        choices=AMOUNT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Contribution Amount"
    )
    
    frequency = forms.ChoiceField(
        choices=FREQUENCY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Frequency"
    )
    
    min_trust_score = forms.ChoiceField(
        choices=TRUST_SCORE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Trust Score Requirement"
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Status"
    )
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name...'
        }),
        label="Search"
    )


class PayoutPositionForm(forms.Form):
    """Form for selecting payout position in rotational rounds"""
    
    position = forms.IntegerField(
        min_value=1,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Select Your Payout Position"
    )
    
    def __init__(self, *args, available_positions=None, **kwargs):
        super().__init__(*args, **kwargs)
        if available_positions:
            self.fields['position'].widget.choices = [
                (pos, f"Position {pos}") for pos in available_positions
            ]


class UserProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile information"""
    
    class Meta:
        model = UserProfile
        fields = ['phone_number']
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+254700000000'
            })
        }
        labels = {
            'phone_number': 'Phone Number'
        }
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            phone = phone.strip().replace(' ', '').replace('-', '')
            if not phone.startswith('+254') and not phone.startswith('0'):
                raise ValidationError("Please enter a valid Kenyan phone number")
            
            if phone.startswith('0'):
                phone = '+254' + phone[1:]
            
            return phone
        return phone


class RoundUpdateForm(forms.ModelForm):
    """Form for updating round details (creator only)"""
    
    class Meta:
        model = Round
        fields = ['name', 'description', 'start_date']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '200'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            })
        }
        labels = {
            'name': 'Round Name',
            'description': 'Description',
            'start_date': 'Start Date'
        }
    
    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date and start_date < timezone.now().date():
            raise ValidationError("Start date cannot be in the past.")
        return start_date


class BulkInvitationForm(forms.Form):
    """Form for sending multiple invitations at once"""
    
    INVITATION_TYPE_CHOICES = [
        ('email', 'Email Addresses'),
        ('phone', 'Phone Numbers'),
    ]
    
    invitation_type = forms.ChoiceField(
        choices=INVITATION_TYPE_CHOICES,
        widget=forms.RadioSelect,
        label="Invitation Method"
    )
    
    contacts = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter one email/phone per line\nExample:\nemail@example.com\nanother@example.com',
            'rows': 6
        }),
        label="Contacts",
        help_text="Enter one email address or phone number per line"
    )
    
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Add a personal message (optional)...',
            'rows': 3
        }),
        label="Personal Message (Optional)"
    )
    
    def clean_contacts(self):
        contacts = self.cleaned_data.get('contacts')
        if contacts:
            # Split by newlines and clean up
            contact_list = [c.strip() for c in contacts.split('\n') if c.strip()]
            
            if len(contact_list) == 0:
                raise ValidationError("Please enter at least one contact.")
            
            if len(contact_list) > 50:
                raise ValidationError("You can only send up to 50 invitations at once.")
            
            return contact_list
        return []
    
   # Sending an invitation

class NationalIDInvitationForm(forms.Form):
    """Form for sending invitations by National ID - aligned with OTPService signup/login logic."""
    
    national_ids = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': 'Enter National IDs (one per line)\nExample:\n12345678\n0012345678' # Example shows potential raw input
        }),
        label="National ID Numbers",
        help_text="Enter one National ID number per line, as used during signup."
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        label="Personal Message (Optional)"
    )

    def clean_national_ids(self):
        ids_text = self.cleaned_data.get('national_ids')
        # Split and clean the input lines
        id_list_raw = [id.strip() for id in ids_text.split('\n') if id.strip()]

        if len(id_list_raw) == 0:
            raise ValidationError("Please enter at least one National ID.")

        if len(id_list_raw) > 20: # Or your chosen limit
            raise ValidationError("Maximum 20 invitations at once.")

        # Basic format validation (digits only, length)
        validated_ids = []
        for raw_id in id_list_raw:
            if not re.fullmatch(r'\d{6,10}', raw_id): # Adjust length as needed for Kenyan IDs
                raise ValidationError(f"Invalid National ID format: '{raw_id}'. Must be 6-10 digits.")
            validated_ids.append(raw_id) # Store the raw ID as entered

        # Remove duplicates while preserving order (using raw input)
        unique_raw_ids = list(dict.fromkeys(validated_ids))

        return unique_raw_ids # Return the list of *raw* IDs as entered by the user


    def clean(self):
        cleaned_data = super().clean()
        raw_ids = cleaned_data.get('national_ids', []) # Get the raw IDs from clean_national_ids

        if raw_ids:
            # 4. Query the database using the *raw* IDs against Profile.NIC_No
            # This matches the logic in OTPService.get_profile_by_nic
            existing_profiles = Profile.objects.filter(
                NIC_No__in=raw_ids
            ).values_list('NIC_No', flat=True)

            existing_ids_set = set(existing_profiles) # Use a set for faster lookup
            invalid_ids = [rid for rid in raw_ids if rid not in existing_ids_set]

            if invalid_ids:
                # Show the raw ID that failed lookup
                raise ValidationError(f"The following National IDs do not exist in the system: {', '.join(sorted(invalid_ids))}")

        return cleaned_data

class InvitationReviewForm(forms.Form):
    """
    NEW: Form for reviewing and accepting/declining invitations
    """
    action = forms.ChoiceField(
        choices=[
            ('accept', 'Accept Invitation'),
            ('decline', 'Decline Invitation'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        }),
        label="Your Decision"
    )
    
    agree_to_terms = forms.BooleanField(
        required=False,
        label="I agree to contribute on time and understand the round rules",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        agree_to_terms = cleaned_data.get('agree_to_terms')
        
        # If accepting, must agree to terms
        if action == 'accept' and not agree_to_terms:
            raise ValidationError({
                'agree_to_terms': 'You must agree to the terms before accepting the invitation.'
            })
        
        return cleaned_data

class EnhancedInvitationForm(forms.Form):
    """
    NEW: Enhanced form for member lookup and batch invitations
    """
    lookup_type = forms.ChoiceField(
        choices=[
            ('national_id', 'National ID'),
            ('phone', 'Phone Number'),
        ],
        widget=forms.RadioSelect,
        initial='national_id'
    )
    
    lookup_value = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter National ID or Phone Number'
        })
    )
    
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add a personal message (optional)...'
        }),
        label='Personal Message (Optional)'
    )
    
    def clean_lookup_value(self):
        value = self.cleaned_data.get('lookup_value', '').strip()
        lookup_type = self.data.get('lookup_type')
        
        if not value:
            return value
        
        if lookup_type == 'national_id':
            # Validate National ID format (6-10 digits)
            if not re.fullmatch(r'\d{6,10}', value):
                raise ValidationError('Invalid National ID format. Must be 6-10 digits.')
        
        elif lookup_type == 'phone':
            # Validate phone format
            value = value.replace(' ', '').replace('-', '')
            if not value.startswith('+254') and not value.startswith('0'):
                raise ValidationError('Please enter a valid Kenyan phone number')
            
            if value.startswith('0'):
                value = '+254' + value[1:]
        
        return value

class BatchInvitationForm(forms.Form):
    """
    NEW: Form for sending batch invitations from invitation list
    """
    invitation_data = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3
        })
    )
    
    def clean_invitation_data(self):
        import json
        data = self.cleaned_data.get('invitation_data')
        
        try:
            invitation_list = json.loads(data)
            
            if not isinstance(invitation_list, list):
                raise ValidationError('Invalid invitation data format')
            
            if len(invitation_list) == 0:
                raise ValidationError('Invitation list is empty')
            
            if len(invitation_list) > 20:
                raise ValidationError('Maximum 20 invitations at once')
            
            return invitation_list
            
        except json.JSONDecodeError:
            raise ValidationError('Invalid JSON data')