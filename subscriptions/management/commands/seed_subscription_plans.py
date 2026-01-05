from django.core.management.base import BaseCommand
from subscriptions.models import SubscriptionPlan
from datetime import timedelta

class Command(BaseCommand):
    help = 'Seed subscription plans'

    def handle(self, *args, **options):
        default_plans = [
            {
                'name': 'Standard Plan',
                'price': 2000.00,
                'trial_duration': timedelta(days=14),
                'grace_period': timedelta(days=2),
            },
        ]

        for plan_data in default_plans:
            plan, created = SubscriptionPlan.objects.get_or_create(
                name=plan_data['name'],
                defaults={
                    'price': plan_data['price'],
                    'trial_duration': plan_data['trial_duration'],
                    'grace_period': plan_data['grace_period']
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'Subscription plan "{plan.name}" created successfully'))
            else:
                self.stdout.write(self.style.WARNING(f'Subscription plan "{plan.name}" already exists'))
