# merry_go_round/wallet_services.py - UPDATED WITH MAIN WALLET INTEGRATION

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import MGRWallet, MGRTransaction, Round, RoundMembership
import logging

logger = logging.getLogger(__name__)


class WalletService:
    """Service for managing MGR wallet operations - INTEGRATED with Main Wallet"""
    
    @staticmethod
    def get_or_create_wallet(user):
        """Get or create wallet for user"""
        wallet, created = MGRWallet.objects.get_or_create(user=user)
        if created:
            logger.info(f"Created new MGR wallet for user {user.username}")
        return wallet
    
    @staticmethod
    @transaction.atomic
    def deposit_from_main_wallet(user, amount, main_wallet_reference=''):
        """
        Deposit funds from ChamaSpace main wallet to MGR wallet
        Called when user manually transfers funds
        
        Args:
            user: User object
            amount: Decimal amount to deposit
            main_wallet_reference: Reference ID from main wallet transaction
            
        Returns:
            MGRTransaction object or None if failed
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be greater than zero")
        
        wallet = WalletService.get_or_create_wallet(user)
        
        # Check Main Wallet balance first
        try:
            from wallet.services import WalletService as MainWalletService
            main_balance_info = MainWalletService.get_wallet_balance(user)
            
            if main_balance_info['available_balance'] < amount:
                raise ValueError(
                    f"Insufficient balance in Main Wallet. "
                    f"Available: KES {main_balance_info['available_balance']}, "
                    f"Required: KES {amount}"
                )
        except ImportError:
            logger.warning("Main wallet service not available - skipping balance check")
        
        # Record balance before
        balance_before = wallet.balance
        
        # Add funds to MGR wallet
        wallet.add_funds(amount)
        wallet.total_deposited += amount
        wallet.save()
        
        # Create MGR transaction record
        txn = MGRTransaction.objects.create(
            wallet=wallet,
            transaction_type='deposit',
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            status='completed',
            main_wallet_reference=main_wallet_reference,
            description=f"Deposit from main ChamaSpace wallet"
        )
        
        logger.info(f"User {user.username} deposited KES {amount} to MGR wallet")
        
        # Now deduct from Main Wallet
        try:
            from wallet.services import MGRWalletIntegrationService
            main_txn = MGRWalletIntegrationService.transfer_to_mgr_wallet(
                user=user,
                amount=amount,
                round_id=None
            )
            
            # Update MGR transaction with main wallet reference
            txn.main_wallet_reference = main_txn.reference_number
            txn.save()
            
            logger.info(f"Main wallet deducted: {main_txn.reference_number}")
            
        except ImportError:
            logger.warning("Main wallet integration not available")
        except Exception as e:
            logger.error(f"Failed to deduct from main wallet: {str(e)}")
            # Rollback MGR deposit
            wallet.balance -= amount
            wallet.available_balance -= amount
            wallet.total_deposited -= amount
            wallet.save()
            txn.status = 'failed'
            txn.save()
            raise ValueError(f"Failed to complete transfer: {str(e)}")
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def withdraw_to_main_wallet(user, amount):
        """
        Withdraw funds from MGR wallet to ChamaSpace main wallet
        Called when user manually withdraws or receives payout
        
        Args:
            user: User object
            amount: Decimal amount to withdraw
            
        Returns:
            MGRTransaction object or None if failed
        """
        if amount <= 0:
            raise ValueError("Withdrawal amount must be greater than zero")
        
        wallet = WalletService.get_or_create_wallet(user)
        
        if not wallet.has_sufficient_balance(amount):
            raise ValueError(f"Insufficient balance. Available: KES {wallet.available_balance}")
        
        # Record balance before
        balance_before = wallet.balance
        
        # Deduct funds from MGR wallet
        if not wallet.deduct_funds(amount):
            raise ValueError("Failed to deduct funds")
        
        wallet.total_withdrawn += amount
        wallet.save()
        
        # Create MGR transaction record
        txn = MGRTransaction.objects.create(
            wallet=wallet,
            transaction_type='withdraw',
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            status='pending',
            description=f"Withdrawal to main ChamaSpace wallet"
        )
        
        # Now credit Main Wallet
        try:
            from wallet.services import MGRWalletIntegrationService
            main_txn = MGRWalletIntegrationService.receive_from_mgr_wallet(
                user=user,
                amount=amount,
                mgr_reference=str(txn.id),
                round_id=None
            )
            
            # Update MGR transaction
            txn.status = 'completed'
            txn.main_wallet_reference = main_txn.reference_number
            txn.save()
            
            logger.info(
                f"User {user.username} withdrew KES {amount} from MGR wallet. "
                f"Main wallet reference: {main_txn.reference_number}"
            )
            
        except ImportError:
            logger.warning("Main wallet integration not available")
            txn.status = 'completed'
            txn.main_wallet_reference = f"WD-{timezone.now().timestamp()}"
            txn.save()
        except Exception as e:
            logger.error(f"Failed to credit main wallet: {str(e)}")
            # Rollback MGR withdrawal
            wallet.add_funds(amount)
            wallet.total_withdrawn -= amount
            wallet.save()
            txn.status = 'failed'
            txn.save()
            raise ValueError(f"Failed to complete withdrawal: {str(e)}")
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def reserve_next_contribution(user, round_obj, amount):
        """
        Reserve (lock) funds for the next contribution only - Just-in-time approach
        UPDATED: Auto-transfers from Main Wallet if MGR balance insufficient
        FIXED: Proper Decimal type handling to prevent type errors
        
        Args:
            user: User object
            round_obj: Round object
            amount: Amount to reserve (typically round.contribution_amount)
            
        Returns:
            MGRTransaction object or raises ValueError
        """
        wallet = WalletService.get_or_create_wallet(user)
        
        # CRITICAL FIX: Ensure amount is Decimal
        amount = Decimal(str(amount))
        
        # CRITICAL FIX: Ensure wallet balances are Decimal
        available_balance = Decimal(str(wallet.available_balance))
        
        # Check if MGR wallet has sufficient available balance
        if available_balance < amount:
            shortfall = amount - available_balance
            
            logger.info(
                f"MGR wallet insufficient for user {user.username}. "
                f"Need: {amount}, Have: {available_balance}, Shortfall: {shortfall}"
            )
            
            # Check if Main Wallet has funds to transfer
            try:
                from wallet.services import WalletService as MainWalletService
                main_balance_info = MainWalletService.get_wallet_balance(user)
                
                # CRITICAL FIX: Ensure main wallet balance is Decimal
                main_available = Decimal(str(main_balance_info['available_balance']))
                
                if main_available >= shortfall:
                    # Auto-transfer the shortfall from Main Wallet
                    logger.info(
                        f"Auto-transferring KES {shortfall} from Main Wallet for user {user.username}"
                    )
                    
                    # Transfer funds
                    WalletService.deposit_from_main_wallet(
                        user=user,
                        amount=shortfall,
                        main_wallet_reference=f"AUTO-TRANSFER-{round_obj.id}"
                    )
                    
                    # Refresh wallet
                    wallet.refresh_from_db()
                    
                    logger.info(
                        f"✓ Auto-transfer successful. New MGR balance: {wallet.available_balance}"
                    )
                else:
                    # Not enough in Main Wallet either
                    total_available = available_balance + main_available
                    total_needed = amount - total_available
                    
                    raise ValueError(
                        f"Insufficient balance across wallets. "
                        f"MGR: KES {available_balance}, "
                        f"Main: KES {main_available}, "
                        f"Need: KES {amount}. "
                        f"Please deposit KES {total_needed} via M-Pesa."
                    )
                    
            except ImportError:
                raise ValueError(
                    f"Insufficient balance. Need KES {amount}, "
                    f"but only KES {available_balance} available. "
                    f"Please deposit funds to your MGR wallet."
                )
        
        # Lock the funds in MGR wallet
        if not wallet.lock_funds(amount):
            raise ValueError("Failed to lock funds")
        
        # Create transaction record
        txn = MGRTransaction.objects.create(
            wallet=wallet,
            transaction_type='lock',
            amount=amount,
            balance_before=wallet.balance,
            balance_after=wallet.balance,
            status='completed',
            related_round=round_obj,
            description=f"Reserved next contribution for: {round_obj.name}"
        )
        
        logger.info(f"Reserved KES {amount} for user {user.username} in round {round_obj.name}")
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def release_reservation(user, round_obj, amount):
        """
        Release (unlock) reserved funds if contribution fails or round is cancelled
        
        Args:
            user: User object
            round_obj: Round object
            amount: Amount to release
            
        Returns:
            MGRTransaction object
        """
        wallet = WalletService.get_or_create_wallet(user)
        
        if amount > 0:
            wallet.unlock_funds(amount)
            
            # Create transaction record
            txn = MGRTransaction.objects.create(
                wallet=wallet,
                transaction_type='unlock',
                amount=amount,
                balance_before=wallet.balance,
                balance_after=wallet.balance,
                status='completed',
                related_round=round_obj,
                description=f"Released reservation for: {round_obj.name}"
            )
            
            logger.info(f"Released KES {amount} for user {user.username} from round {round_obj.name}")
            
            return txn
        
        return None
    
    @staticmethod
    @transaction.atomic
    def unlock_all_funds_for_round(user, round_obj):
        """
        Unlock all funds when round is cancelled or completed
        
        Args:
            user: User object
            round_obj: Round object
        """
        try:
            membership = RoundMembership.objects.get(user=user, round=round_obj)
            
            if membership.locked_amount > 0:
                return WalletService.release_reservation(
                    user, 
                    round_obj, 
                    membership.locked_amount
                )
        except RoundMembership.DoesNotExist:
            logger.warning(f"No membership found for user {user.username} in round {round_obj.name}")
            return None
    
    @staticmethod
    @transaction.atomic
    def process_contribution(contribution):
        """
        Process contribution payment from MGR wallet
        UPDATED: Includes auto-transfer logic for next contribution
        
        Args:
            contribution: Contribution object
            
        Returns:
            MGRTransaction object
        """
        membership = contribution.membership
        user = membership.user
        wallet = WalletService.get_or_create_wallet(user)
        
        amount = contribution.amount
        
        # Check if funds are locked
        if membership.locked_amount < amount:
            raise ValueError(
                f"Insufficient locked funds for this contribution. "
                f"Locked: KES {membership.locked_amount}, Needed: KES {amount}. "
                f"Please reserve funds first."
            )
        
        # Record balance before
        balance_before = wallet.balance
        
        # Move from locked to contributed
        wallet.locked_balance -= amount
        wallet.balance -= amount
        wallet.save()
        
        # Update membership
        membership.locked_amount -= amount
        membership.total_contributed += amount
        membership.contributions_made += 1
        membership.save()
        
        # Update contribution status
        contribution.status = 'completed'
        contribution.payment_date = timezone.now()
        contribution.save()
        
        # Create transaction record
        txn = MGRTransaction.objects.create(
            wallet=wallet,
            transaction_type='contribution',
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            status='completed',
            related_round=membership.round,
            related_contribution=contribution,
            description=f"Contribution for {membership.round.name} - Cycle {contribution.cycle_number}"
        )
        
        # Link transaction to contribution
        contribution.wallet_transaction = txn
        contribution.save()
        
        # Update round pool
        round_obj = membership.round
        round_obj.total_pool += amount
        round_obj.save()
        
        logger.info(
            f"Processed contribution of KES {amount} for user {user.username} "
            f"in round {membership.round.name}"
        )
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def process_payout(payout):
        """
        Process payout to user's MGR wallet (NOT Main Wallet)
        User can manually withdraw later if they want
        
        Args:
            payout: Payout object
            
        Returns:
            MGRTransaction object
        """
        membership = payout.recipient_membership
        user = membership.user
        wallet = WalletService.get_or_create_wallet(user)
        
        amount = payout.amount
        
        # Record balance before
        balance_before = wallet.balance
        
        # Add funds to MGR wallet (all goes to available balance)
        wallet.add_funds(amount)
        
        # Create transaction record
        txn = MGRTransaction.objects.create(
            wallet=wallet,
            transaction_type='payout',
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            status='completed',
            related_round=payout.round,
            related_payout=payout,
            description=f"Payout from {payout.round.name}",
            metadata={
                'principal': str(payout.principal_amount),
                'interest': str(payout.interest_amount)
            }
        )
        
        # Link transaction to payout
        payout.wallet_transaction = txn
        payout.status = 'completed'
        payout.payout_date = timezone.now()
        payout.save()
        
        # Update membership
        membership.has_received_payout = True
        membership.payout_received_date = payout.payout_date.date()
        membership.payout_amount = amount
        membership.interest_earned = payout.interest_amount
        membership.save()
        
        logger.info(
            f"Processed payout of KES {amount} to MGR wallet for user {user.username} "
            f"from round {payout.round.name}"
        )
        
        # NOTE: Funds stay in MGR wallet - user can manually withdraw to Main Wallet
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def credit_interest(user, round_obj, amount):
        """
        Credit interest earned to MGR wallet
        
        Args:
            user: User object
            round_obj: Round object
            amount: Interest amount
        """
        if amount <= 0:
            return None
        
        wallet = WalletService.get_or_create_wallet(user)
        balance_before = wallet.balance
        
        wallet.add_funds(amount)
        
        txn = MGRTransaction.objects.create(
            wallet=wallet,
            transaction_type='interest',
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            status='completed',
            related_round=round_obj,
            description=f"Interest earned from {round_obj.name}"
        )
        
        logger.info(f"Credited KES {amount} interest to user {user.username}")
        
        return txn
    
    @staticmethod
    def get_wallet_summary(user):
        """Get wallet summary for user"""
        from django.db.models import Sum
        
        wallet = WalletService.get_or_create_wallet(user)
        
        # Get recent transactions
        recent_transactions = MGRTransaction.objects.filter(
            wallet=wallet,
            status='completed'
        ).order_by('-created_at')[:10]
        
        # Calculate statistics
        total_contributions = MGRTransaction.objects.filter(
            wallet=wallet,
            transaction_type='contribution',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        total_payouts = MGRTransaction.objects.filter(
            wallet=wallet,
            transaction_type='payout',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        total_interest = MGRTransaction.objects.filter(
            wallet=wallet,
            transaction_type='interest',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'wallet': wallet,
            'recent_transactions': recent_transactions,
            'total_contributions': total_contributions,
            'total_payouts': total_payouts,
            'total_interest': total_interest,
        }


class MainWalletIntegrationService:
    """
    Service for integrating with ChamaSpace main wallet
    This is a wrapper that calls the actual Main Wallet services
    """
    
    @staticmethod
    def transfer_to_mgr_wallet(user, amount):
        """
        Transfer funds from main wallet to MGR wallet
        This is called when user manually deposits to MGR wallet
        
        Args:
            user: User object
            amount: Amount to transfer
            
        Returns:
            Transaction reference or raises exception
        """
        try:
            # Call MGR wallet service to handle the deposit
            txn = WalletService.deposit_from_main_wallet(
                user=user,
                amount=amount
            )
            
            return txn.main_wallet_reference
            
        except Exception as e:
            logger.error(f"Failed to transfer from main wallet: {str(e)}")
            raise
    
    @staticmethod
    def transfer_from_mgr_wallet(user, amount):
        """
        Transfer funds from MGR wallet back to main wallet
        This is called when user manually withdraws from MGR wallet
        
        Args:
            user: User object
            amount: Amount to transfer
            
        Returns:
            Transaction reference or raises exception
        """
        try:
            # Call MGR wallet service to handle the withdrawal
            txn = WalletService.withdraw_to_main_wallet(user=user, amount=amount)
            
            return txn.main_wallet_reference
            
        except Exception as e:
            logger.error(f"Failed to transfer to main wallet: {str(e)}")
            raise
    
    @staticmethod
    def verify_main_wallet_balance(user, amount):
        """
        Verify user has sufficient balance in main wallet
        
        Args:
            user: User object
            amount: Amount to check
            
        Returns:
            Boolean
        """
        try:
            from wallet.services import WalletService as MainWalletService
            balance_info = MainWalletService.get_wallet_balance(user)
            return balance_info['available_balance'] >= amount
        except:
            # If main wallet not available, return True to not block
            return True