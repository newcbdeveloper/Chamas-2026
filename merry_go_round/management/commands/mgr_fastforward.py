"""
Advanced Time Acceleration Simulation
Ensures all Celery tasks in tasks.py are executed in the correct daily sequence.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging
from freezegun import freeze_time

from merry_go_round.models import Round, RoundMembership, MGRWallet
from merry_go_round.tasks import (
    auto_process_due_contributions, 
    process_due_payouts,
    calculate_daily_interest,
    mark_missed_contributions,
    send_contribution_reminders,
    check_and_complete_rounds,
    check_pending_invitations_quota
)

logger = logging.getLogger('merry_go_round')
logger.setLevel(logging.ERROR)

class Command(BaseCommand):
    help = 'Force-advances the system clock and runs the full suite of daily tasks'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Number of days to simulate')
        parser.add_argument('--auto-fund', action='store_true', help='Keep wallets topped up')

    def handle(self, *args, **options):
        days_to_simulate = options['days']
        auto_fund = options['auto_fund']
        start_time = timezone.now()
        
        self.stdout.write(self.style.SUCCESS(f"⏩ Accelerating time by {days_to_simulate} days..."))

        for day in range(days_to_simulate):
            # Advance the clock by exactly one day per loop
            current_date = start_time + timedelta(days=day)
            
            with freeze_time(current_date):
                self.stdout.write(f"\n📅 Simulating: {current_date.date()}")

                # 1. MAINTENANCE (Mocking user behavior)
                if auto_fund:
                    self.ensure_funds()

                # 2. MORNING TASKS (6:00 AM - 8:00 AM)
                # Process today's due payments
                contrib_res = auto_process_due_contributions()
                
                # Mark anything missed from yesterday
                missed_res = mark_missed_contributions()
                
                # Send reminders for tomorrow's payments
                send_contribution_reminders()

                # 3. MID-DAY TASKS
                # Accrue interest for the day
                calculate_daily_interest()
                
                # Check for stale invitations
                check_pending_invitations_quota()

                # 4. END OF DAY / MIDNIGHT TASKS (Critical for Completion)
                # This marks rounds as 'completed' once requirements are met
                completion_res = check_and_complete_rounds()
                
                # Process any payouts that are now due (including those from newly completed rounds)
                payout_res = process_due_payouts()

                # Reporting
                self.report_progress(contrib_res, completion_res, payout_res)

        self.stdout.write(self.style.SUCCESS("\n✅ Full lifecycle simulation complete."))

    def ensure_funds(self):
        """Prevents the simulation from stopping due to empty wallets"""
        for wallet in MGRWallet.objects.all():
            if wallet.available_balance < 2000:
                wallet.balance += 10000
                wallet.available_balance += 10000
                wallet.save()

    def report_progress(self, contrib, completion, payout):
        if contrib['processed'] > 0:
            self.stdout.write(self.style.SUCCESS(f"   - Paid: {contrib['processed']} contributions"))
        if completion['marked_complete'] > 0:
            self.stdout.write(self.style.SUCCESS(f"   - 🏁 Round(s) Completed: {completion['marked_complete']}"))
        if payout['processed'] > 0:
            self.stdout.write(self.style.SUCCESS(f"   - 💰 Payouts Executed: {payout['processed']}"))