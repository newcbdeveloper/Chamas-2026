# Add to mgr_fastforward.py or create mgr_fund_wallets.py
from django.core.management.base import BaseCommand
from merry_go_round.models import MGRWallet, RoundMembership
from decimal import Decimal

class Command(BaseCommand):
    help = 'Fund all member wallets for upcoming contributions'
    
    def handle(self, *args, **options):
        memberships = RoundMembership.objects.filter(
            round__status='active',
            status='active'
        )
        
        for membership in memberships:
            wallet = MGRWallet.objects.get(user=membership.user)
            round_obj = membership.round
            
            # Ensure they have 2x contribution amount available
            needed = round_obj.contribution_amount * 2
            current_total = wallet.available_balance + wallet.locked_balance
            
            if current_total < needed:
                add_amount = needed - current_total
                wallet.balance += add_amount
                wallet.available_balance += add_amount
                wallet.save()
                
                print(f"Added KES {add_amount} to {membership.user.username}")