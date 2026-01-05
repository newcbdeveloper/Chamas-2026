
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import logging

from .models import MainWallet, WalletTransaction, PendingTransfer
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class WalletService:
    """
    Core service for Main Wallet operations
    All methods use atomic transactions and F-expressions for race-condition safety
    """
    
    @staticmethod
    def get_or_create_wallet(user):
        """
        Get or create wallet for user
        
        Args:
            user: User object
            
        Returns:
            MainWallet object
        """
        wallet, created = MainWallet.objects.get_or_create(
            user=user,
            defaults={
                'balance': Decimal('0.00'),
                'available_balance': Decimal('0.00'),
                'locked_balance': Decimal('0.00'),
                'currency': 'KES',
                'status': 'active',
            }
        )
        
        if created:
            logger.info(f"Created new main wallet for user {user.username}")
        
        return wallet
    
    @staticmethod
    def get_wallet_balance(user):
        """
        Get current wallet balance
        
        Args:
            user: User object
            
        Returns:
            dict with balance information
        """
        wallet = WalletService.get_or_create_wallet(user)
        
        return {
            'balance': wallet.balance,
            'available_balance': wallet.available_balance,
            'locked_balance': wallet.locked_balance,
            'currency': wallet.currency,
            'status': wallet.status,
        }
    
    @staticmethod
    @transaction.atomic
    def add_funds(user, amount, transaction_type, description, idempotency_key=None, 
                  mpesa_receipt=None, metadata=None, related_app=None):
        """
        Add funds to wallet (deposits, transfers in, etc.)
        Uses F-expressions for atomic updates
        
        Args:
            user: User object
            amount: Decimal amount to add
            transaction_type: Type of transaction (e.g., 'mpesa_deposit')
            description: Transaction description
            idempotency_key: Unique key to prevent duplicate processing
            mpesa_receipt: M-Pesa receipt number (optional)
            metadata: Additional data (optional)
            related_app: Related app name (optional)
            
        Returns:
            WalletTransaction object
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate amount
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero")
        
        # Check idempotency
        if idempotency_key:
            existing_txn = WalletTransaction.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            
            if existing_txn:
                logger.warning(
                    f"Duplicate transaction detected: {idempotency_key}. "
                    f"Returning existing transaction {existing_txn.reference_number}"
                )
                return existing_txn
        
        # Get wallet
        wallet = WalletService.get_or_create_wallet(user)
        
        # Check if wallet is active
        if not wallet.is_active():
            raise ValidationError(f"Wallet is {wallet.status}. Cannot process transaction.")
        
        # Record balance before
        wallet.refresh_from_db()
        balance_before = wallet.balance
        
        # Atomic update using F-expressions (prevents race conditions)
        MainWallet.objects.filter(pk=wallet.pk).update(
            available_balance=F('available_balance') + amount,
            balance=F('balance') + amount,
            total_deposited=F('total_deposited') + amount,
            last_transaction_date=timezone.now(),
            updated_at=timezone.now()
        )
        
        # Refresh to get new balance
        wallet.refresh_from_db()
        balance_after = wallet.balance
        
        # Create transaction record
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=transaction_type,
            amount=amount,
            currency=wallet.currency,
            balance_before=balance_before,
            balance_after=balance_after,
            status='completed',
            description=description,
            idempotency_key=idempotency_key,
            mpesa_receipt_number=mpesa_receipt,
            related_app=related_app,
            metadata=metadata or {},
            completed_at=timezone.now()
        )
        
        logger.info(
            f"Added {wallet.currency} {amount} to wallet for user {user.username}. "
            f"Transaction: {txn.reference_number}"
        )
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def deduct_funds(user, amount, transaction_type, description, idempotency_key=None,
                     metadata=None, related_app=None):
        """
        Deduct funds from wallet (withdrawals, transfers out, etc.)
        Uses F-expressions for atomic updates
        
        Args:
            user: User object
            amount: Decimal amount to deduct
            transaction_type: Type of transaction (e.g., 'mpesa_withdraw')
            description: Transaction description
            idempotency_key: Unique key to prevent duplicate processing
            metadata: Additional data (optional)
            related_app: Related app name (optional)
            
        Returns:
            WalletTransaction object
            
        Raises:
            ValidationError: If validation fails or insufficient balance
        """
        # Validate amount
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero")
        
        # Check idempotency
        if idempotency_key:
            existing_txn = WalletTransaction.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            
            if existing_txn:
                logger.warning(
                    f"Duplicate transaction detected: {idempotency_key}. "
                    f"Returning existing transaction {existing_txn.reference_number}"
                )
                return existing_txn
        
        # Get wallet
        wallet = WalletService.get_or_create_wallet(user)
        
        # Check if wallet is active
        if not wallet.is_active():
            raise ValidationError(f"Wallet is {wallet.status}. Cannot process transaction.")
        
        # Check sufficient balance
        wallet.refresh_from_db()
        if wallet.available_balance < amount:
            raise ValidationError(
                f"Insufficient balance. Available: {wallet.currency} {wallet.available_balance}, "
                f"Required: {wallet.currency} {amount}"
            )
        
        # Record balance before
        balance_before = wallet.balance
        
        # Atomic update using F-expressions
        MainWallet.objects.filter(pk=wallet.pk).update(
            available_balance=F('available_balance') - amount,
            balance=F('balance') - amount,
            total_withdrawn=F('total_withdrawn') + amount,
            last_transaction_date=timezone.now(),
            updated_at=timezone.now()
        )
        
        # Refresh to get new balance
        wallet.refresh_from_db()
        balance_after = wallet.balance
        
        # Create transaction record
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=transaction_type,
            amount=amount,
            currency=wallet.currency,
            balance_before=balance_before,
            balance_after=balance_after,
            status='completed',
            description=description,
            idempotency_key=idempotency_key,
            related_app=related_app,
            metadata=metadata or {},
            completed_at=timezone.now()
        )
        
        logger.info(
            f"Deducted {wallet.currency} {amount} from wallet for user {user.username}. "
            f"Transaction: {txn.reference_number}"
        )
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def lock_funds(user, amount, reason, metadata=None):
        """
        Lock funds (move from available to locked)
        Uses F-expressions for atomic updates
        
        Args:
            user: User object
            amount: Decimal amount to lock
            reason: Reason for locking (description)
            metadata: Additional data (optional)
            
        Returns:
            WalletTransaction object
            
        Raises:
            ValidationError: If validation fails or insufficient available balance
        """
        # Validate amount
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero")
        
        # Get wallet
        wallet = WalletService.get_or_create_wallet(user)
        
        # Check if wallet is active
        if not wallet.is_active():
            raise ValidationError(f"Wallet is {wallet.status}. Cannot lock funds.")
        
        # Check sufficient available balance
        wallet.refresh_from_db()
        if wallet.available_balance < amount:
            raise ValidationError(
                f"Insufficient available balance. Available: {wallet.currency} {wallet.available_balance}, "
                f"Required: {wallet.currency} {amount}"
            )
        
        # Record balance before
        balance_before = wallet.balance
        
        # Atomic update using F-expressions
        # Note: Total balance stays the same, just moves between available and locked
        MainWallet.objects.filter(pk=wallet.pk).update(
            available_balance=F('available_balance') - amount,
            locked_balance=F('locked_balance') + amount,
            last_transaction_date=timezone.now(),
            updated_at=timezone.now()
        )
        
        # Refresh to get new balance
        wallet.refresh_from_db()
        balance_after = wallet.balance
        
        # Create transaction record
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='lock',
            amount=amount,
            currency=wallet.currency,
            balance_before=balance_before,
            balance_after=balance_after,
            status='completed',
            description=f"Funds locked: {reason}",
            metadata=metadata or {},
            completed_at=timezone.now()
        )
        
        logger.info(
            f"Locked {wallet.currency} {amount} for user {user.username}. "
            f"Reason: {reason}. Transaction: {txn.reference_number}"
        )
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def unlock_funds(user, amount, reason, metadata=None):
        """
        Unlock funds (move from locked to available)
        Uses F-expressions for atomic updates
        
        Args:
            user: User object
            amount: Decimal amount to unlock
            reason: Reason for unlocking (description)
            metadata: Additional data (optional)
            
        Returns:
            WalletTransaction object
            
        Raises:
            ValidationError: If validation fails or insufficient locked balance
        """
        # Validate amount
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero")
        
        # Get wallet
        wallet = WalletService.get_or_create_wallet(user)
        
        # Check sufficient locked balance
        wallet.refresh_from_db()
        if wallet.locked_balance < amount:
            raise ValidationError(
                f"Insufficient locked balance. Locked: {wallet.currency} {wallet.locked_balance}, "
                f"Required: {wallet.currency} {amount}"
            )
        
        # Record balance before
        balance_before = wallet.balance
        
        # Atomic update using F-expressions
        # Note: Total balance stays the same, just moves between locked and available
        MainWallet.objects.filter(pk=wallet.pk).update(
            locked_balance=F('locked_balance') - amount,
            available_balance=F('available_balance') + amount,
            last_transaction_date=timezone.now(),
            updated_at=timezone.now()
        )
        
        # Refresh to get new balance
        wallet.refresh_from_db()
        balance_after = wallet.balance
        
        # Create transaction record
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='unlock',
            amount=amount,
            currency=wallet.currency,
            balance_before=balance_before,
            balance_after=balance_after,
            status='completed',
            description=f"Funds unlocked: {reason}",
            metadata=metadata or {},
            completed_at=timezone.now()
        )
        
        logger.info(
            f"Unlocked {wallet.currency} {amount} for user {user.username}. "
            f"Reason: {reason}. Transaction: {txn.reference_number}"
        )
        
        return txn
    
    @staticmethod
    def get_transaction_history(user, filters=None, limit=None):
        """
        Get transaction history for user
        
        Args:
            user: User object
            filters: Dict of filters (transaction_type, status, date_from, date_to)
            limit: Maximum number of transactions to return
            
        Returns:
            QuerySet of WalletTransaction objects
        """
        wallet = WalletService.get_or_create_wallet(user)
        
        transactions = WalletTransaction.objects.filter(wallet=wallet)
        
        # Apply filters
        if filters:
            if 'transaction_type' in filters:
                transactions = transactions.filter(transaction_type=filters['transaction_type'])
            
            if 'status' in filters:
                transactions = transactions.filter(status=filters['status'])
            
            if 'date_from' in filters:
                transactions = transactions.filter(created_at__gte=filters['date_from'])
            
            if 'date_to' in filters:
                transactions = transactions.filter(created_at__lte=filters['date_to'])
            
            if 'related_app' in filters:
                transactions = transactions.filter(related_app=filters['related_app'])
        
        transactions = transactions.order_by('-created_at')
        
        if limit:
            transactions = transactions[:limit]
        
        return transactions
    
    @staticmethod
    def get_transaction_by_reference(reference_number):
        """
        Get transaction by reference number
        
        Args:
            reference_number: Transaction reference
            
        Returns:
            WalletTransaction object or None
        """
        try:
            return WalletTransaction.objects.get(reference_number=reference_number)
        except WalletTransaction.DoesNotExist:
            return None
    
    @staticmethod
    def get_wallet_summary(user):
        """
        Get comprehensive wallet summary
        
        Args:
            user: User object
            
        Returns:
            dict with wallet summary data
        """
        from django.db.models import Sum, Count
        
        wallet = WalletService.get_or_create_wallet(user)
        
        # Get transaction statistics
        transactions = WalletTransaction.objects.filter(wallet=wallet, status='completed')
        
        total_deposits = transactions.filter(
            transaction_type__in=['mpesa_deposit', 'transfer_from_mgr', 'transfer_from_goals', 'migration']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        total_withdrawals = transactions.filter(
            transaction_type__in=['mpesa_withdraw', 'transfer_to_mgr', 'transfer_to_goals']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        transaction_count = transactions.count()
        
        recent_transactions = transactions.order_by('-created_at')[:10]
        
        return {
            'wallet': wallet,
            'balance': wallet.balance,
            'available_balance': wallet.available_balance,
            'locked_balance': wallet.locked_balance,
            'currency': wallet.currency,
            'status': wallet.status,
            'total_deposited': wallet.total_deposited,
            'total_withdrawn': wallet.total_withdrawn,
            'transaction_count': transaction_count,
            'recent_transactions': recent_transactions,
        }


class MpesaIntegrationService:
    """
    Service for M-Pesa integration with Main Wallet
    Reuses existing payment_integration app
    """
    
    @staticmethod
    @transaction.atomic
    def process_mpesa_deposit(user, amount, mpesa_receipt, phone_number):
        """
        Process M-Pesa deposit to main wallet
        Called from payment_integration callback
        
        Args:
            user: User object
            amount: Decimal amount
            mpesa_receipt: M-Pesa receipt/merchant ID
            phone_number: User's phone number
            
        Returns:
            WalletTransaction object
        """
        # Use M-Pesa receipt as idempotency key
        idempotency_key = f"mpesa-deposit-{mpesa_receipt}"
        
        metadata = {
            'mpesa_receipt': mpesa_receipt,
            'phone_number': phone_number,
            'source': 'mpesa_callback'
        }
        
        try:
            txn = WalletService.add_funds(
                user=user,
                amount=amount,
                transaction_type='mpesa_deposit',
                description=f"M-Pesa deposit from {phone_number}",
                idempotency_key=idempotency_key,
                mpesa_receipt=mpesa_receipt,
                metadata=metadata,
                related_app='system'
            )
            
            logger.info(f"M-Pesa deposit processed: {mpesa_receipt} for user {user.username}")
            
            return txn
            
        except Exception as e:
            logger.error(f"Failed to process M-Pesa deposit {mpesa_receipt}: {str(e)}")
            raise  
    

    @staticmethod
    @transaction.atomic
    def initiate_mpesa_withdrawal(user, amount, phone_number):
        """
        STEP 1: INITIATE withdrawal request (does NOT deduct funds)
        Creates PendingTransfer with status='awaiting_password'
        
        This is the FIRST step - just creates the withdrawal request.
        Funds are NOT deducted until password is verified.
        
        Args:
            user: User object
            amount: Decimal amount
            phone_number: Destination phone number (must be verified)
            
        Returns:
            PendingTransfer object (NOT a transaction)
            
        Raises:
            ValidationError: If validation fails
        """
        from authentication.models import Profile
        from user_dashboard.kyc_utils import is_kyc_verified
        
        # Validate KYC
        if not is_kyc_verified(user):
            raise ValidationError("KYC verification is required before withdrawal.")
        
        # Validate verified phone number
        try:
            profile = Profile.objects.get(owner=user)
            if not profile.phone:
                raise ValidationError("No verified phone number found in profile.")
            # Ensure the provided phone matches verified phone
            if phone_number != profile.phone:
                raise ValidationError("Withdrawal can only be sent to your verified phone number.")
        except Profile.DoesNotExist:
            raise ValidationError("User profile not found.")
        
        # Validate amount
        if amount < Decimal('50.00'):
            raise ValidationError("Minimum withdrawal amount is KES 50.")
        
        # Check sufficient balance (without deducting)
        wallet = WalletService.get_or_create_wallet(user)
        if wallet.available_balance < amount:
            raise ValidationError(
                f"Insufficient balance. Available: KES {wallet.available_balance}"
            )
        
        # Create metadata
        metadata = {
            'phone_number': phone_number,
            'withdrawal_method': 'mpesa',
            'kyc_verified_at': timezone.now().isoformat()
        }
        
        # Create pending transfer (NO FUNDS DEDUCTED)
        pending = PendingTransfer.objects.create(
            wallet=wallet,
            transfer_type='mpesa_withdraw',
            amount=amount,
            destination_app='mpesa',
            status='awaiting_password',  # Initial status
            requires_password_verification=True,
            metadata=metadata
        )
        
        logger.info(
            f"Withdrawal request initiated: KES {amount} for {user.username}, "
            f"Pending transfer ID: {pending.id}. NO FUNDS DEDUCTED YET."
        )
        
        return pending  # Return ONLY the pending transfer

    @staticmethod
    @transaction.atomic
    def process_approved_withdrawal(pending_transfer, phone_number):
        """
        STEP 3: PROCESS approved withdrawal (send actual M-Pesa B2C)
        Called only when PendingTransfer.status == 'approved'
        
        NOTE: Funds should ALREADY be deducted by this point.
        This method just sends the M-Pesa B2C request.
        
        Args:
            pending_transfer: Approved PendingTransfer instance
            phone_number: Destination phone number
            
        Returns:
            tuple: (success: bool, message: str)
        """
        from mpesa_integration.mpesa_credentials import (
            LipanaMpesaPpassword, 
            get_mpesa_access_token
        )
        import requests
        
        user = pending_transfer.wallet.user
        amount = pending_transfer.amount
        
        # Verify funds were already deducted
        if not pending_transfer.wallet_transaction:
            error_msg = "Cannot process withdrawal - no transaction record found"
            logger.error(f"{error_msg} for pending transfer #{pending_transfer.id}")
            return False, error_msg
        
        try:
            # Update status to processing
            pending_transfer.status = 'processing'
            pending_transfer.save()
            
            # Send actual M-Pesa B2C request
            access_token = get_mpesa_access_token()
            api_url = "https://api.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Format phone number for M-Pesa (remove + and leading 0)
            clean_phone = phone_number.replace('+', '').lstrip('0')
            if not clean_phone.startswith('254'):
                clean_phone = '254' + clean_phone
            
            payload = {
                "InitiatorName": LipanaMpesaPpassword.InitiatorName,
                "SecurityCredential": LipanaMpesaPpassword.SecurityCredential,
                "CommandID": "BusinessPayment",
                "Amount": float(amount),
                "PartyA": LipanaMpesaPpassword.Business_short_code,
                "PartyB": clean_phone,
                "Remarks": f"Withdrawal for {user.username}",
                "QueueTimeOutURL": "https://chamaspace.com/mpesa/timeout",
                "ResultURL": "https://chamaspace.com/mpesa/result",
                "Occasion": "WalletWithdrawal"
            }
            
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            result = response.json()
            
            logger.info(f"M-Pesa B2C request sent for pending #{pending_transfer.id}: {result}")
            
            if response.status_code == 200 and result.get('ResponseCode') == '0':
                # Update pending transfer
                pending_transfer.complete()
                logger.info(f"Withdrawal completed: Pending #{pending_transfer.id}")
                return True, "Withdrawal processed successfully"
            else:
                error_msg = result.get('errorMessage', 'Unknown M-Pesa error')
                logger.error(f"M-Pesa B2C failed for pending #{pending_transfer.id}: {error_msg}")
                pending_transfer.fail(reason=error_msg)
                return False, f"M-Pesa processing failed: {error_msg}"
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in process_approved_withdrawal: {error_msg}\n{traceback.format_exc()}")
            pending_transfer.fail(reason=error_msg)
            return False, error_msg


class MGRWalletIntegrationService:
    """
    Service for integrating Main Wallet with MGR Wallet
    """
    
    @staticmethod
    @transaction.atomic
    def transfer_to_mgr_wallet(user, amount, round_id=None):
        """
        Transfer funds from main wallet to MGR wallet
        
        Args:
            user: User object
            amount: Decimal amount
            round_id: Optional round ID for metadata
            
        Returns:
            WalletTransaction object
        """
        metadata = {
            'destination': 'mgr_wallet',
            'round_id': round_id
        }
        
        try:
            txn = WalletService.deduct_funds(
                user=user,
                amount=amount,
                transaction_type='transfer_to_mgr',
                description=f"Transfer to MGR Wallet" + (f" (Round #{round_id})" if round_id else ""),
                metadata=metadata,
                related_app='mgr'
            )
            
            logger.info(
                f"Transferred {amount} to MGR wallet for user {user.username}. "
                f"Transaction: {txn.reference_number}"
            )
            
            return txn
            
        except Exception as e:
            logger.error(f"Failed to transfer to MGR wallet: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def receive_from_mgr_wallet(user, amount, mgr_reference, round_id=None):
        """
        Receive funds from MGR wallet to main wallet
        
        Args:
            user: User object
            amount: Decimal amount
            mgr_reference: MGR transaction reference
            round_id: Optional round ID for metadata
            
        Returns:
            WalletTransaction object
        """
        # Use MGR reference as idempotency key
        idempotency_key = f"mgr-transfer-{mgr_reference}"
        
        metadata = {
            'source': 'mgr_wallet',
            'mgr_reference': mgr_reference,
            'round_id': round_id
        }
        
        try:
            txn = WalletService.add_funds(
                user=user,
                amount=amount,
                transaction_type='transfer_from_mgr',
                description=f"Received from MGR Wallet" + (f" (Round #{round_id})" if round_id else ""),
                idempotency_key=idempotency_key,
                metadata=metadata,
                related_app='mgr'
            )
            
            logger.info(
                f"Received {amount} from MGR wallet for user {user.username}. "
                f"Transaction: {txn.reference_number}"
            )
            
            return txn
            
        except Exception as e:
            logger.error(f"Failed to receive from MGR wallet: {str(e)}")
            raise


class GoalsIntegrationService:
    """
    Service for integrating Main Wallet with Goals app
    """
    
    @staticmethod
    @transaction.atomic
    def transfer_to_goals(user, amount, goal_type, goal_id=None):
        """
        Transfer funds from main wallet to Goals
        
        Args:
            user: User object
            amount: Decimal amount
            goal_type: Type of goal (express_saving, personal_goal, group_goal)
            goal_id: Optional goal ID
            
        Returns:
            WalletTransaction object
        """
        metadata = {
            'destination': 'goals',
            'goal_type': goal_type,
            'goal_id': goal_id
        }
        
        description_map = {
            'express_saving': 'Express Saving',
            'personal_goal': 'Personal Goal',
            'group_goal': 'Group Goal'
        }
        
        description = f"Transfer to {description_map.get(goal_type, 'Goals')}"
        if goal_id:
            description += f" (ID: {goal_id})"
        
        try:
            txn = WalletService.deduct_funds(
                user=user,
                amount=amount,
                transaction_type='transfer_to_goals',
                description=description,
                metadata=metadata,
                related_app='goals'
            )
            
            logger.info(
                f"Transferred {amount} to Goals ({goal_type}) for user {user.username}. "
                f"Transaction: {txn.reference_number}"
            )
            
            return txn
            
        except Exception as e:
            logger.error(f"Failed to transfer to Goals: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def receive_from_goals(user, amount, goal_type, goal_id=None, goal_reference=None):
        """
        Receive funds from Goals to main wallet (withdrawals)
        
        Args:
            user: User object
            amount: Decimal amount
            goal_type: Type of goal (express_saving, personal_goal, group_goal)
            goal_id: Optional goal ID
            goal_reference: Optional reference from Goals app
            
        Returns:
            WalletTransaction object
        """
        # Use goal reference as idempotency key if provided
        idempotency_key = f"goals-transfer-{goal_reference}" if goal_reference else None
        
        metadata = {
            'source': 'goals',
            'goal_type': goal_type,
            'goal_id': goal_id,
            'goal_reference': goal_reference
        }
        
        description_map = {
            'express_saving': 'Express Saving',
            'personal_goal': 'Personal Goal',
            'group_goal': 'Group Goal'
        }
        
        description = f"Withdrawal from {description_map.get(goal_type, 'Goals')}"
        if goal_id:
            description += f" (ID: {goal_id})"
        
        try:
            txn = WalletService.add_funds(
                user=user,
                amount=amount,
                transaction_type='transfer_from_goals',
                description=description,
                idempotency_key=idempotency_key,
                metadata=metadata,
                related_app='goals'
            )
            
            logger.info(
                f"Received {amount} from Goals ({goal_type}) for user {user.username}. "
                f"Transaction: {txn.reference_number}"
            )
            
            return txn
            
        except Exception as e:
            logger.error(f"Failed to receive from Goals: {str(e)}")
            raise


class AdminWalletService:
    """
    Service for admin operations on wallets
    """
    
    @staticmethod
    @transaction.atomic
    def manual_adjustment(user, amount, reason, admin_user, is_credit=True):
        """
        Manual balance adjustment by admin
        
        Args:
            user: User object
            amount: Decimal amount
            reason: Reason for adjustment
            admin_user: Admin user making the adjustment
            is_credit: True for credit, False for debit
            
        Returns:
            WalletTransaction object
        """
        metadata = {
            'adjusted_by': admin_user.username,
            'adjustment_reason': reason,
            'adjustment_type': 'credit' if is_credit else 'debit'
        }
        
        description = f"Admin adjustment: {reason}"
        
        try:
            if is_credit:
                txn = WalletService.add_funds(
                    user=user,
                    amount=amount,
                    transaction_type='adjustment',
                    description=description,
                    metadata=metadata,
                    related_app='system'
                )
            else:
                txn = WalletService.deduct_funds(
                    user=user,
                    amount=amount,
                    transaction_type='adjustment',
                    description=description,
                    metadata=metadata,
                    related_app='system'
                )
            
            # Record admin who made the adjustment
            txn.processed_by = admin_user
            txn.save()
            
            logger.warning(
                f"Admin {admin_user.username} made manual adjustment of "
                f"{'credit' if is_credit else 'debit'} {amount} for user {user.username}. "
                f"Reason: {reason}. Transaction: {txn.reference_number}"
            )
            
            return txn
            
        except Exception as e:
            logger.error(f"Failed to make admin adjustment: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def freeze_wallet(user, reason, admin_user):
        """
        Freeze a user's wallet
        
        Args:
            user: User object
            reason: Reason for freezing
            admin_user: Admin user freezing the wallet
        """
        wallet = WalletService.get_or_create_wallet(user)
        wallet.freeze(reason)
        
        logger.warning(
            f"Admin {admin_user.username} froze wallet for user {user.username}. "
            f"Reason: {reason}"
        )
        
        return wallet
    
    @staticmethod
    @transaction.atomic
    def unfreeze_wallet(user, admin_user):
        """
        Unfreeze a user's wallet
        
        Args:
            user: User object
            admin_user: Admin user unfreezing the wallet
        """
        wallet = WalletService.get_or_create_wallet(user)
        wallet.unfreeze()
        
        logger.info(
            f"Admin {admin_user.username} unfroze wallet for user {user.username}"
        )
        
        return wallet