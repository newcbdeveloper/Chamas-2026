# wallet/views.py - Corrected with enhanced withdrawal security

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import authenticate
from decimal import Decimal
import logging
import traceback
from django.db.models import Sum, Q
from datetime import timedelta

from .models import MainWallet, WalletTransaction, PendingTransfer
from .services import (
    WalletService, 
    MpesaIntegrationService,
    MGRWalletIntegrationService,
    GoalsIntegrationService
)
from authentication.models import Profile
from notifications.models import UserNotificationHistory
from user_dashboard.kyc_utils import is_kyc_verified, get_kyc_status

logger = logging.getLogger(__name__)


# REPLACE your wallet_dashboard view in views.py

@login_required(login_url='Login')
def wallet_dashboard(request):
    """
    Main wallet dashboard showing balance and recent transactions
    ENHANCED: Now shows pending withdrawals
    """
    try:
        # Step 1: Get user profile
        try:
            user_profile = Profile.objects.get(owner=request.user)
            logger.info(f"User profile loaded for {request.user.username}")
        except Profile.DoesNotExist:
            logger.error(f"Profile does not exist for user {request.user.username}")
            messages.error(request, "User profile not found. Please contact support.")
            return redirect('user_dashboard:home')
        
        # Step 2: Get wallet summary
        try:
            summary = WalletService.get_wallet_summary(request.user)
            logger.info(f"Wallet summary loaded for {request.user.username}")
        except Exception as e:
            logger.error(f"Error getting wallet summary: {str(e)}\n{traceback.format_exc()}")
            messages.error(request, f"Error loading wallet data: {str(e)}")
            return redirect('user_dashboard:home')
        
        # Step 3: Get recent transactions
        try:
            transactions = WalletService.get_transaction_history(
                request.user, 
                limit=10
            )
            logger.info(f"Transactions loaded: {transactions.count()} records")
        except Exception as e:
            logger.error(f"Error getting transactions: {str(e)}\n{traceback.format_exc()}")
            transactions = []
        
        # Step 4: Get PENDING WITHDRAWALS (NEW)
        try:
            pending_withdrawals = PendingTransfer.objects.filter(
                wallet__user=request.user,
                transfer_type='mpesa_withdraw',
                status='pending'
            ).order_by('-initiated_at')
            
            logger.info(f"Found {pending_withdrawals.count()} pending withdrawals")
        except Exception as e:
            logger.error(f"Error getting pending withdrawals: {str(e)}")
            pending_withdrawals = []
        
        # Step 5: Get notifications
        try:
            user_notifications = UserNotificationHistory.objects.filter(
                user=request.user
            ).order_by('-created_at')[:6]
        except Exception as e:
            logger.error(f"Error getting notifications: {str(e)}")
            user_notifications = []
        
        # Step 6: Prepare context
        context = {
            'user_profile': user_profile,
            'wallet': summary['wallet'],
            'balance': summary['balance'],
            'available_balance': summary['available_balance'],
            'locked_balance': summary['locked_balance'],
            'total_deposited': summary['total_deposited'],
            'total_withdrawn': summary['total_withdrawn'],
            'transaction_count': summary['transaction_count'],
            'recent_transactions': transactions,
            'pending_withdrawals': pending_withdrawals,  # NEW
            'user_notifications': user_notifications,
        }
        
        logger.info(f"Wallet dashboard rendering for {request.user.username}")
        return render(request, 'wallet/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Unexpected error in wallet_dashboard: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, f"System error: {str(e)}")
        return redirect('user_dashboard:home')


@login_required(login_url='Login')
def deposit_via_mpesa(request):
    """
    Initiate M-Pesa STK push for deposit
    Reuses payment_integration templates and logic
    """
    try:
        user_profile = Profile.objects.get(owner=request.user)
        
        context = {
            'user_profile': user_profile,
            'phone_number': user_profile.phone,
        }
        
        if request.method == 'POST':
            amount = request.POST.get('amount')
            
            try:
                amount = Decimal(amount)
                
                if amount < 10:
                    messages.error(request, "Minimum deposit is KES 10")
                    return render(request, 'wallet/deposit_mpesa.html', context)
                
                # Get phone number
                phone_input = user_profile.phone
                without_plus = phone_input[1:] if phone_input.startswith('+') else phone_input
                phone = int(''.join(filter(str.isdigit, without_plus)))
                
                # Import M-Pesa credentials
                from payment_integration.mpesa_credentials import (
                    LipanaMpesaPpassword, 
                    get_mpesa_access_token
                )
                import requests
                
                # Get access token
                access_token = get_mpesa_access_token()
                
                # Prepare STK push request
                api_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
                headers = {"Authorization": f"Bearer {access_token}"}
                
                payload = {
                    "BusinessShortCode": LipanaMpesaPpassword.Business_short_code,
                    "Password": LipanaMpesaPpassword.decode_password,
                    "Timestamp": LipanaMpesaPpassword.lipa_time,
                    "TransactionType": "CustomerPayBillOnline",
                    "Amount": int(amount),
                    "PartyA": phone,
                    "PartyB": LipanaMpesaPpassword.Business_short_code,
                    "PhoneNumber": phone,
                    "CallBackURL": "https://chamaspace.com/load_money/callback",
                    "AccountReference": "ChamaSpace Wallet",
                    "TransactionDesc": "Deposit to Main Wallet"
                }
                
                response = requests.post(api_url, json=payload, headers=headers)
                data = response.json()
                
                logger.info(f"M-Pesa STK push response: {data}")
                
                if data.get('ResponseCode') == "0":
                    messages.success(
                        request, 
                        "STK push sent! Please check your phone and enter your M-Pesa PIN."
                    )
                    return redirect('wallet:stk_push_success')
                else:
                    messages.error(
                        request, 
                        "Failed to initiate payment. Please try again."
                    )
                    return redirect('wallet:stk_push_fail')
                    
            except ValueError:
                messages.error(request, "Invalid amount entered")
                return render(request, 'wallet/deposit_mpesa.html', context)
            except Exception as e:
                logger.error(f"M-Pesa deposit error: {str(e)}\n{traceback.format_exc()}")
                messages.error(request, "Payment processing error. Please try again.")
                return redirect('wallet:stk_push_fail')
        
        return render(request, 'wallet/deposit_mpesa.html', context)
        
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found")
        return redirect('user_dashboard:home')


@login_required(login_url='Login')
def stk_push_success(request):
    """Success page after STK push"""
    try:
        user_profile = Profile.objects.get(owner=request.user)
        
        context = {
            'user_profile': user_profile,
            'phone_number': user_profile.phone,
        }
        
        return render(request, 'wallet/stk_push_success.html', context)
    except Profile.DoesNotExist:
        return redirect('user_dashboard:home')


@login_required(login_url='Login')
def stk_push_fail(request):
    """Failure page after STK push"""
    try:
        user_profile = Profile.objects.get(owner=request.user)
        
        context = {
            'user_profile': user_profile,
            'phone_number': user_profile.phone,
        }
        
        return render(request, 'wallet/stk_push_fail.html', context)
    except Profile.DoesNotExist:
        return redirect('user_dashboard:home')


@login_required(login_url='Login')
def withdraw_via_mpesa(request):
    """
    STEP 1: Initiate withdrawal request (NO funds deducted yet)
    - Show withdrawal form
    - Validate KYC
    - Create PendingTransfer with 'awaiting_password' status
    - Redirect to password verification page
    """
    try:
        user_profile = Profile.objects.get(owner=request.user)
        wallet = WalletService.get_or_create_wallet(request.user)
        
        # SECURITY CHECK 1: KYC Verification
        if not is_kyc_verified(request.user):
            messages.warning(
                request,
                "KYC verification is required before you can withdraw funds. "
                "This helps us protect your money and comply with financial regulations."
            )
            return redirect('user_dashboard:kyc:dashboard')
        
        # Get verified phone number from profile
        verified_phone = user_profile.phone
        if not verified_phone:
            messages.error(
                request,
                "No verified phone number found. Please update your profile."
            )
            return redirect('user_dashboard:settings')
        
        context = {
            'user_profile': user_profile,
            'wallet': wallet,
            'phone_number': verified_phone,
            'is_kyc_verified': True,
            'withdrawal_threshold': 2000,  # KES 2,000 threshold
        }
        
        if request.method == 'POST':
            amount = request.POST.get('amount')
            
            try:
                amount = Decimal(amount)
                
                # Validate minimum withdrawal
                if amount < 50:
                    messages.error(request, "Minimum withdrawal is KES 50")
                    return render(request, 'wallet/withdraw_mpesa.html', context)
                
                # Check sufficient balance
                if amount > wallet.available_balance:
                    messages.error(
                        request, 
                        f"Insufficient balance. Available: KES {wallet.available_balance}"
                    )
                    return render(request, 'wallet/withdraw_mpesa.html', context)
                
                # STEP 1: Create pending transfer (NO FUNDS DEDUCTED YET)
                pending = MpesaIntegrationService.initiate_mpesa_withdrawal(
                    user=request.user,
                    amount=amount,
                    phone_number=verified_phone
                )
                
                logger.info(
                    f"Withdrawal request initiated: Pending ID {pending.id} for {request.user.username}, "
                    f"Amount: KES {amount}"
                )
                
                       
                # STEP 2: Redirect to password verification
                messages.info(
                    request,
                    "Please verify your identity to complete the withdrawal."
                )
                return redirect('wallet:verify_withdrawal_password', pending_id=pending.id)
                
            except ValueError:
                messages.error(request, "Invalid amount entered")
                return render(request, 'wallet/withdraw_mpesa.html', context)
            except Exception as e:
                logger.error(f"Withdrawal initiation error: {str(e)}\n{traceback.format_exc()}")
                messages.error(request, f"Error initiating withdrawal: {str(e)}")
                return render(request, 'wallet/withdraw_mpesa.html', context)
        
        return render(request, 'wallet/withdraw_mpesa.html', context)
        
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found")
        return redirect('user_dashboard:home')


@login_required(login_url='Login')
def verify_withdrawal_password(request, pending_id):
    """
    STEP 2: Verify password and process withdrawal
    - Verify user's password
    - If correct: deduct funds and update status
    - If amount ≤ 2000: auto-approve and send to M-Pesa
    - If amount > 2000: mark as pending admin approval
    """
    try:
        pending = PendingTransfer.objects.get(
            id=pending_id,
            wallet__user=request.user,
            transfer_type='mpesa_withdraw',
            status='awaiting_password'
        )
    except PendingTransfer.DoesNotExist:
        messages.error(request, "Invalid or already processed withdrawal request.")
        return redirect('wallet:wallet_dashboard')
    
    user_profile = Profile.objects.get(owner=request.user)
    
    context = {
        'user_profile': user_profile,
        'pending': pending,
        'withdrawal_amount': pending.amount,
        'phone_number': pending.metadata.get('phone_number', '—'),
        'requires_approval': pending.amount > Decimal('2000.00'),
        'password_error': None,  # NEW: For error display
    }
    
    if request.method == 'POST':
        password = request.POST.get('password')
        
        if not password:
            context['password_error'] = "Password is required to confirm withdrawal"
            return render(request, 'wallet/verify_password.html', context)
        
        # SECURITY CHECK 2: Verify password
        user = authenticate(username=request.user.username, password=password)
        if user is None:
            # FIXED: Pass error to context instead of messages
            context['password_error'] = "Incorrect password. Please try again."
            logger.warning(
                f"Failed password verification for withdrawal by {request.user.username}"
            )
            return render(request, 'wallet/verify_password.html', context)
        
        # Password verified successfully
        logger.info(f"Password verified for withdrawal by {request.user.username}")
        
        try:
            # STEP 3: Deduct funds from wallet (NOW we deduct)
            if pending.amount > Decimal('2000.00'):
                txn_status = 'pending'
                txn_description = f"M-Pesa withdrawal to {pending.metadata['phone_number']} (Pending approval)"
            else:
                txn_status = 'processing'
                txn_description = f"M-Pesa withdrawal to {pending.metadata['phone_number']}"
            
            txn = WalletTransaction.objects.create(
                wallet=pending.wallet,
                transaction_type='mpesa_withdraw',
                amount=pending.amount,
                currency='KES',
                balance_before=pending.wallet.balance,
                balance_after=pending.wallet.balance - pending.amount,
                status=txn_status,
                description=txn_description,
                metadata={
                    'phone_number': pending.metadata['phone_number'],
                    'pending_transfer_id': pending.id,
                    'withdrawal_method': 'mpesa',
                    'requires_admin_approval': pending.amount > Decimal('2000.00')
                },
                related_app='system'
            )
            
            # Actually deduct the funds using F-expressions
            from django.db.models import F
            MainWallet.objects.filter(pk=pending.wallet.pk).update(
                available_balance=F('available_balance') - pending.amount,
                balance=F('balance') - pending.amount,
                total_withdrawn=F('total_withdrawn') + pending.amount,
                last_transaction_date=timezone.now(),
                updated_at=timezone.now()
            )
            
            # Link transaction to pending transfer
            pending.wallet_transaction = txn
            pending.verify_password()
            
            logger.info(
                f"Funds deducted for withdrawal: {txn.reference_number}, "
                f"Auto-approved: {pending.auto_approved}, Status: {txn.status}"
            )
            
            # STEP 4: Check if auto-approved (amount ≤ 2000)
            if pending.auto_approved and pending.status == 'approved':
                # Process immediately via M-Pesa B2C
                phone_number = pending.metadata.get('phone_number')
                
                success, message = MpesaIntegrationService.process_approved_withdrawal(
                    pending_transfer=pending,
                    phone_number=phone_number
                )
                
                if success:
                    # Mark transaction as completed
                    txn.status = 'completed'
                    txn.completed_at = timezone.now()
                    txn.save()
                    
                    # FIXED: Better success message for auto-approved withdrawals
                    messages.success(
                        request,
                        f"Withdrawal of KES {pending.amount} has been processed and sent to M-Pesa! "
                        f"You should receive it shortly at {phone_number}."
                    )
                    
                    # Send success notification
                    UserNotificationHistory.objects.create(
                        user=request.user,
                        notification_title='Withdrawal Completed',
                        notification_body=(
                            f'Your withdrawal of KES {pending.amount} has been processed '
                            f'and sent to {phone_number}. Transaction: {txn.reference_number}'
                        )
                    )
                else:
                    # M-Pesa processing failed
                    pending.fail(reason=message)
                    txn.status = 'failed'
                    txn.save()
                    
                    messages.error(
                        request,
                        "Withdrawal approved but M-Pesa processing failed. "
                        "Support has been notified and will resolve this shortly."
                    )
                    logger.error(f"M-Pesa disbursement failed for pending #{pending.id}: {message}")
            
            else:
                # Requires admin approval (amount > 2000)
                messages.info(
                    request,
                    f"Your withdrawal of KES {pending.amount} has been submitted for approval. "
                    f"You'll receive a notification once it's processed (usually within 24 hours)."
                )
                
                # Send notification
                UserNotificationHistory.objects.create(
                    user=request.user,
                    notification_title='Withdrawal Pending Approval',
                    notification_body=(
                        f'Your withdrawal of KES {pending.amount} to '
                        f'{pending.metadata.get("phone_number")} is pending admin approval. '
                        f'Transaction: {txn.reference_number}'
                    )
                )
            
            return redirect('wallet:wallet_dashboard')
            
        except Exception as e:
            logger.error(
                f"Error processing withdrawal after password verification: {str(e)}\n"
                f"{traceback.format_exc()}"
            )
            messages.error(
                request, 
                f"Error processing withdrawal: {str(e)}. Please contact support."
            )
            return render(request, 'wallet/verify_password.html', context)
    
    # GET request - show password verification form
    return render(request, 'wallet/verify_password.html', context)    


@login_required(login_url='Login')
def transaction_history(request):
    """
    Transaction history with filtering, pagination, and monthly summary
    """
    try:
        user_profile = Profile.objects.get(owner=request.user)
        wallet = WalletService.get_or_create_wallet(request.user)
        
        # Get filter parameters
        transaction_type = request.GET.get('type')
        status = request.GET.get('status')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Build filters for transactions
        filters = {}
        if transaction_type:
            filters['transaction_type'] = transaction_type
        if status:
            filters['status'] = status
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        
        # Get filtered transactions
        transactions = WalletService.get_transaction_history(
            request.user, 
            filters=filters
        )
        
        # Determine date range for summary calculations
        if date_from and date_to:
            summary_start_date = date_from
            summary_end_date = date_to
        elif date_from:
            summary_start_date = date_from
            summary_end_date = timezone.now().date().isoformat()
        elif date_to:
            end_date = timezone.datetime.fromisoformat(date_to).date()
            summary_start_date = end_date.replace(day=1).isoformat()
            summary_end_date = date_to
        else:
            # Default to current month
            today = timezone.now().date()
            summary_start_date = today.replace(day=1).isoformat()
            if today.month == 12:
                next_month = today.replace(year=today.year + 1, month=1, day=1)
            else:
                next_month = today.replace(month=today.month + 1, day=1)
            summary_end_date = (next_month - timedelta(days=1)).isoformat()
            
            filters['date_from'] = summary_start_date
            filters['date_to'] = summary_end_date
            transactions = WalletService.get_transaction_history(
                request.user, 
                filters=filters
            )
            date_from = summary_start_date
            date_to = summary_end_date
        
        # Calculate summary metrics
        summary_filters = {'date_from': summary_start_date, 'date_to': summary_end_date}
        all_transactions_in_period = WalletService.get_transaction_history(
            request.user,
            filters=summary_filters
        )
        
        INFLOW_TYPES = ['mpesa_deposit', 'transfer_from_mgr', 'transfer_from_goals', 'unlock']
        
        base_queryset = WalletTransaction.objects.filter(
            wallet=wallet,
            created_at__date__gte=summary_start_date,
            created_at__date__lte=summary_end_date
        )
        
        if status:
            base_queryset = base_queryset.filter(status=status)
        
        if transaction_type:
            if transaction_type in INFLOW_TYPES:
                inflow_transactions = base_queryset.filter(transaction_type=transaction_type)
            else:
                inflow_transactions = base_queryset.none()
        else:
            inflow_transactions = base_queryset.filter(transaction_type__in=INFLOW_TYPES)
        
        if transaction_type:
            if transaction_type not in INFLOW_TYPES:
                outflow_transactions = base_queryset.filter(transaction_type=transaction_type)
            else:
                outflow_transactions = base_queryset.none()
        else:
            outflow_transactions = base_queryset.exclude(transaction_type__in=INFLOW_TYPES)
        
        total_inflow = inflow_transactions.aggregate(total=Sum('amount'))['total'] or 0
        total_outflow = outflow_transactions.aggregate(total=Sum('amount'))['total'] or 0
        net_balance = total_inflow - total_outflow
        
        # Paginate
        paginator = Paginator(transactions, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'user_profile': user_profile,
            'page_obj': page_obj,
            'selected_type': transaction_type,
            'selected_status': status,
            'date_from': date_from,
            'date_to': date_to,
            'total_inflow': total_inflow,
            'total_outflow': total_outflow,
            'net_balance': net_balance,
        }
        
        return render(request, 'wallet/transaction_history.html', context)
        
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found")
        return redirect('user_dashboard:home')


@login_required(login_url='Login')
def transaction_detail(request, transaction_id):
    """Single transaction detail view"""
    try:
        user_profile = Profile.objects.get(owner=request.user)
        wallet = WalletService.get_or_create_wallet(request.user)
        
        transaction = get_object_or_404(
            WalletTransaction,
            pk=transaction_id,
            wallet=wallet
        )
        
        context = {
            'user_profile': user_profile,
            'transaction': transaction,
        }
        
        return render(request, 'wallet/transaction_detail.html', context)
        
    except Profile.DoesNotExist:
        messages.error(request, "User profile not found")
        return redirect('user_dashboard:home')


# API Endpoints for AJAX

@login_required(login_url='Login')
def api_wallet_balance(request):
    """API endpoint to get current wallet balance (for AJAX)"""
    try:
        balance_info = WalletService.get_wallet_balance(request.user)
        
        return JsonResponse({
            'success': True,
            'balance': float(balance_info['balance']),
            'available_balance': float(balance_info['available_balance']),
            'locked_balance': float(balance_info['locked_balance']),
            'currency': balance_info['currency'],
            'status': balance_info['status'],
        })
        
    except Exception as e:
        logger.error(f"API balance error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required(login_url='Login')
def api_recent_transactions(request):
    """API endpoint to get recent transactions (for AJAX)"""
    try:
        limit = int(request.GET.get('limit', 10))
        transactions = WalletService.get_transaction_history(request.user, limit=limit)
        
        data = [{
            'reference': txn.reference_number,
            'type': txn.get_transaction_type_display(),
            'amount': float(txn.amount),
            'status': txn.status,
            'date': txn.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'description': txn.description,
        } for txn in transactions]
        
        return JsonResponse({
            'success': True,
            'transactions': data
        })
        
    except Exception as e:
        logger.error(f"API transactions error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# Transfer endpoints (for manual transfers - mostly for testing)

@login_required(login_url='Login')
def transfer_to_mgr(request):
    """Manual transfer to MGR wallet (usually automatic)"""
    if request.method == 'POST':
        amount = request.POST.get('amount')
        round_id = request.POST.get('round_id')
        
        try:
            amount = Decimal(amount)
            
            txn = MGRWalletIntegrationService.transfer_to_mgr_wallet(
                user=request.user,
                amount=amount,
                round_id=round_id
            )
            
            messages.success(
                request,
                f"Successfully transferred KES {amount} to MGR Wallet. "
                f"Transaction: {txn.reference_number}"
            )
            
        except Exception as e:
            logger.error(f"Transfer to MGR error: {str(e)}")
            messages.error(request, str(e))
        
        return redirect('wallet:wallet_dashboard')
    
    return redirect('wallet:wallet_dashboard')


@login_required(login_url='Login')
def transfer_to_goals(request):
    """Manual transfer to Goals (usually automatic)"""
    if request.method == 'POST':
        amount = request.POST.get('amount')
        goal_type = request.POST.get('goal_type')
        goal_id = request.POST.get('goal_id')
        
        try:
            amount = Decimal(amount)
            
            txn = GoalsIntegrationService.transfer_to_goals(
                user=request.user,
                amount=amount,
                goal_type=goal_type,
                goal_id=goal_id
            )
            
            messages.success(
                request,
                f"Successfully transferred KES {amount} to Goals. "
                f"Transaction: {txn.reference_number}"
            )
            
        except Exception as e:
            logger.error(f"Transfer to Goals error: {str(e)}")
            messages.error(request, str(e))
        
        return redirect('wallet:wallet_dashboard')
    
    return redirect('wallet:wallet_dashboard')