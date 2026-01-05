# user_dashboard/management/commands/create_kyc_profiles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from user_dashboard.models import KYCProfile
from authentication.models import Profile

class Command(BaseCommand):
    help = 'Create KYC profiles for existing users'

    def handle(self, *args, **options):
        created_count = 0
        
        for user in User.objects.all():
            if not hasattr(user, 'kyc_profile'):
                # Get declared ID from existing Profile
                try:
                    profile = Profile.objects.get(owner=user)
                    declared_id = profile.NIC_No
                except Profile.DoesNotExist:
                    declared_id = user.username
                
                KYCProfile.objects.create(
                    user=user,
                    declared_national_id=declared_id
                )
                created_count += 1
                self.stdout.write(f'Created KYC profile for {user.username}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} KYC profiles'
            )
        )