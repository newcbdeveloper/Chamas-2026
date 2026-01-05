# user_dashboard/management/commands/setup_kyc.py
"""
Management command to set up KYC system for ChamaSpace.
This command will:
1. Create KYC profiles for all existing users
2. Verify the setup
3. Report statistics
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from user_dashboard.models import KYCProfile
from authentication.models import Profile


class Command(BaseCommand):
    help = 'Set up KYC system for ChamaSpace'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without creating anything',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of KYC profiles (USE WITH CAUTION)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN MODE ==='))
        
        self.stdout.write(self.style.SUCCESS('\n📋 ChamaSpace KYC Setup\n'))
        
        # Step 1: Check existing setup
        self.stdout.write('Step 1: Checking existing setup...')
        total_users = User.objects.count()
        existing_kyc = KYCProfile.objects.count()
        
        self.stdout.write(f'  • Total users: {total_users}')
        self.stdout.write(f'  • Existing KYC profiles: {existing_kyc}')
        
        if existing_kyc > 0 and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  {existing_kyc} KYC profiles already exist. '
                    'Use --force to recreate (this will DELETE existing profiles).'
                )
            )
            if not dry_run:
                confirm = input('Continue creating profiles for remaining users? (yes/no): ')
                if confirm.lower() != 'yes':
                    self.stdout.write(self.style.WARNING('Setup cancelled.'))
                    return
        
        # Step 2: Create KYC profiles
        self.stdout.write('\nStep 2: Creating KYC profiles...')
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        users_to_process = User.objects.all()
        if force and not dry_run:
            # Delete existing profiles if force is enabled
            deleted_count = KYCProfile.objects.all().delete()[0]
            self.stdout.write(
                self.style.WARNING(f'  • Deleted {deleted_count} existing KYC profiles')
            )
        
        for user in users_to_process:
            try:
                # Check if KYC profile already exists
                if hasattr(user, 'kyc_profile') and not force:
                    skipped_count += 1
                    continue
                
                if dry_run:
                    # Just count what would be created
                    created_count += 1
                    continue
                
                # Get declared ID from existing Profile
                try:
                    profile = Profile.objects.get(owner=user)
                    declared_id = profile.NIC_No or user.username
                except Profile.DoesNotExist:
                    declared_id = user.username
                
                # Create KYC profile
                with transaction.atomic():
                    if force and hasattr(user, 'kyc_profile'):
                        user.kyc_profile.delete()
                    
                    KYCProfile.objects.create(
                        user=user,
                        declared_national_id=declared_id
                    )
                    created_count += 1
                    
                    if created_count % 100 == 0:
                        self.stdout.write(f'  • Created {created_count} profiles...')
            
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ Error creating KYC for user {user.id}: {str(e)}'
                    )
                )
        
        # Step 3: Verification
        self.stdout.write('\nStep 3: Verifying setup...')
        
        if not dry_run:
            final_count = KYCProfile.objects.count()
            users_without_kyc = User.objects.filter(kyc_profile__isnull=True).count()
            
            self.stdout.write(f'  • Total KYC profiles: {final_count}')
            self.stdout.write(f'  • Users without KYC: {users_without_kyc}')
            
            if users_without_kyc > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️  {users_without_kyc} users still without KYC profiles. '
                        'Check error messages above.'
                    )
                )
        
        # Step 4: Report statistics
        self.stdout.write('\n' + '='*50)
        self.stdout.write('📊 Summary:')
        self.stdout.write('='*50)
        self.stdout.write(f'  ✓ Created: {created_count}')
        self.stdout.write(f'  ⊘ Skipped: {skipped_count}')
        self.stdout.write(f'  ✗ Errors: {error_count}')
        
        if not dry_run and error_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✅ KYC setup completed successfully!'
                )
            )
            
            # Show status breakdown
            if KYCProfile.objects.exists():
                self.stdout.write('\nKYC Status Breakdown:')
                from django.db.models import Count
                statuses = KYCProfile.objects.values('verification_status').annotate(
                    count=Count('id')
                )
                for status in statuses:
                    self.stdout.write(
                        f"  • {status['verification_status']}: {status['count']}"
                    )
            
            # Next steps
            self.stdout.write('\n📝 Next Steps:')
            self.stdout.write('1. Check admin panel: /admin/user_dashboard/kycprofile/')
            self.stdout.write('2. Configure media storage for production')
            self.stdout.write('3. Test KYC flow with a test user')
            self.stdout.write('4. Train staff on KYC review process')
            self.stdout.write('5. Update settings page to show KYC status')
            
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n✓ Dry run complete. Run without --dry-run to apply changes.'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f'\n⚠️  Setup completed with {error_count} errors. '
                    'Review error messages above.'
                )
            )


# Alternative: Create individual KYC profile command
class Command2(BaseCommand):
    """Standalone command to create KYC profile for a single user"""
    help = 'Create KYC profile for a specific user'

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=int, help='User ID')

    def handle(self, *args, **options):
        user_id = options['user_id']
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise CommandError(f'User with ID {user_id} does not exist')
        
        if hasattr(user, 'kyc_profile'):
            self.stdout.write(
                self.style.WARNING(
                    f'User {user.username} already has a KYC profile'
                )
            )
            return
        
        try:
            profile = Profile.objects.get(owner=user)
            declared_id = profile.NIC_No or user.username
        except Profile.DoesNotExist:
            declared_id = user.username
        
        KYCProfile.objects.create(
            user=user,
            declared_national_id=declared_id
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Created KYC profile for {user.username}'
            )
        )