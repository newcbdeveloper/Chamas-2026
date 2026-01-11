# Goals/management/commands/populate_categories.py

from django.core.management.base import BaseCommand
from Goals.models import GoalCategory


class Command(BaseCommand):
    help = 'Populate GoalCategory table with predefined categories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing categories before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted_count = GoalCategory.objects.all().count()
            GoalCategory.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'Deleted {deleted_count} existing categories')
            )

        categories = [
            {
                'key': 'emergency',
                'display_name': 'Emergency Fund',
                'default_image': 'emergency.jpg',
                'default_icon': 'shield-check',
                'theme_color': '#166534'
            },
            {
                'key': 'education',
                'display_name': 'Education / School Fees',
                'default_image': 'education.jpg',
                'default_icon': 'graduation-cap',
                'theme_color': '#1E40AF'
            },
            {
                'key': 'business',
                'display_name': 'Business / Hustle',
                'default_image': 'business.jpg',
                'default_icon': 'briefcase',
                'theme_color': '#064E3B'
            },
            {
                'key': 'housing',
                'display_name': 'Land / Housing',
                'default_image': 'housing.jpg',
                'default_icon': 'home',
                'theme_color': '#92400E'
            },
            {
                'key': 'vehicle',
                'display_name': 'Vehicle (Car / Bike)',
                'default_image': 'vehicle.jpg',
                'default_icon': 'car',
                'theme_color': '#1F2937'
            },
            {
                'key': 'travel',
                'display_name': 'Travel / Vacation',
                'default_image': 'travel.jpg',
                'default_icon': 'plane',
                'theme_color': '#0E7490'
            },
            {
                'key': 'medical',
                'display_name': 'Medical / Health',
                'default_image': 'medical.jpg',
                'default_icon': 'heart-pulse',
                'theme_color': '#991B1B'
            },
            {
                'key': 'wedding',
                'display_name': 'Wedding / Ruracio',
                'default_image': 'wedding.jpg',
                'default_icon': 'heart',
                'theme_color': '#9D174D'
            },
            {
                'key': 'farming',
                'display_name': 'Farming / Agriculture',
                'default_image': 'farming.jpg',
                'default_icon': 'leaf',
                'theme_color': '#15803D'
            },
            {
                'key': 'gadgets',
                'display_name': 'Gadgets / Electronics',
                'default_image': 'gadgets.jpg',
                'default_icon': 'smartphone',
                'theme_color': '#4338CA'
            },
            {
                'key': 'investment',
                'display_name': 'Investment',
                'default_image': 'investment.jpg',
                'default_icon': 'trending-up',
                'theme_color': '#A16207'
            },
            {
                'key': 'retirement',
                'display_name': 'Retirement / Long-term Savings',
                'default_image': 'retirement.jpg',
                'default_icon': 'clock',
                'theme_color': '#374151'
            },
            {
                'key': 'other',
                'display_name': 'Other',
                'default_image': 'other.jpg',
                'default_icon': 'star',
                'theme_color': '#6B7280'
            },
        ]

        created_count = 0
        updated_count = 0

        for category_data in categories:
            obj, created = GoalCategory.objects.update_or_create(
                key=category_data['key'],
                defaults=category_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {obj.display_name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated: {obj.display_name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted! Created: {created_count}, Updated: {updated_count}'
            )
        )