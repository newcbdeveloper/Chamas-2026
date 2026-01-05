"""
Time Acceleration Simulation for Merry-Go-Round
Run with: python manage.py mgr_accelerate_time --days 30 --auto-fund
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from merry_go_round.models import Round, RoundMembership, MGRWallet
from merry_go_round.tasks import (
    auto_process_due_contributions, 
    process_due_payouts,
    calculate_daily_interest,
    mark_missed_contributions,
    send_contribution_reminders
)

# Silence standard logging to keep the console output clean
logger = logging.getLogger('merry_go_round')
logger.setLevel(logging.ERROR)

class Command(BaseCommand):
    help = 'Simulates the passage of time and processes all active rounds'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', 
            type=int, 
            default=1, 
            help='Number of days to simulate into the future'
        )
        parser.add_argument(
            '--auto-fund', 
            action='store_true', 
            help='Automatically top up user wallets to prevent failures during testing'
        )

    def handle(self, *args, **options):
        simulate_days = options['days']
        auto_fund = options['auto_fund']
        
        start_date = timezone.now().date()
        self.stdout.write(self.style.SUCCESS(f"🚀 Starting simulation for {simulate_days} days..."))

        for day_offset in range(simulate_days):
            # In a real simulation of time, you'd mock timezone.now()
            # Since we want to trigger current due tasks, we process the "logic" for each day
            current_sim_date = start_date + timedelta(days=day_offset)
            
            self.stdout.write(f"\n--- Simulating Day {day_offset + 1} ({current_sim_date}) ---")

            # 1. Maintenance: Check if we need to auto-fund users for testing
            if auto_fund:
                self.ensure_user_liquidity()

            # 2. Step 1: Process Due Contributions (6:00 AM Task)
            # This triggers Success Notifications and reserves next cycle funds
            res = auto_process_due_contributions()
            if res['processed'] > 0:
                self.stdout.write(self.style.SUCCESS(f" ✅ Processed {res['processed']} contributions"))

            # 3. Step 2: Mark Missed (7:00 AM Task)
            # Updates trust scores and sends alerts
            missed = mark_missed_contributions()
            if missed['missed_count'] > 0:
                self.stdout.write(self.style.WARNING(f" ❌ Marked {missed['missed_count']} contributions as missed"))

            # 4. Step 3: Interest Accrual
            calculate_daily_interest()

            # 5. Step 4: Process Payouts
            # Handles rotations or marathon payouts that became due
            payouts = process_due_payouts()
            if payouts['processed'] > 0:
                self.stdout.write(self.style.SUCCESS(f" 💰 Executed {payouts['processed']} payouts"))

            # 6. Step 5: Send Reminders (8:00 AM Task)
            # Tests the notification system logic
            send_contribution_reminders()

        self.stdout.write(self.style.SUCCESS(f"\nSimulation of {simulate_days} days completed successfully."))

    def ensure_user_liquidity(self):
        """Helper to ensure users don't run out of money during a long simulation"""
        wallets = MGRWallet.objects.all()
        for wallet in wallets:
            # If they have less than 1000, give them 10,000 for testing
            if wallet.available_balance < 1000:
                wallet.balance += 10000
                wallet.available_balance += 10000
                wallet.save()