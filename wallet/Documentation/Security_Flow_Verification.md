


Flow 1: Small Withdrawal (≤ KES 2,000) - Auto-Approved

1. User clicks "Withdraw" → withdraw_via_mpesa view
   ✓ KYC verified
   ✓ Amount validated
   ✓ Balance checked
   → Creates PendingTransfer (status='awaiting_password')
   → NO notification sent
   → NO funds deducted

2. Redirects to password verification → verify_withdrawal_password
   ✓ User enters password
   ✓ Password verified
   → Deducts funds
   → Creates WalletTransaction (status='processing')
   → PendingTransfer.verify_password() → auto_approved=True, status='approved'
   → Immediately calls MpesaIntegrationService.process_approved_withdrawal()
   → Sends M-Pesa B2C request
   → Updates transaction status to 'completed'
   → Shows success message: "Withdrawal processed and sent to M-Pesa!"
   → Sends notification: "Withdrawal Completed"

Result: User receives funds immediately, no admin action needed


Flow 2: Large Withdrawal (> KES 2,000) - Requires Approval

1. User clicks "Withdraw" → withdraw_via_mpesa view
   ✓ KYC verified
   ✓ Amount validated
   ✓ Balance checked
   → Creates PendingTransfer (status='awaiting_password')
   → NO notification sent
   → NO funds deducted

2. Redirects to password verification → verify_withdrawal_password
   ✓ User enters password
   ✓ Password verified
   → Deducts funds
   → Creates WalletTransaction (status='pending')
   → PendingTransfer.verify_password() → auto_approved=False, status='pending'
   → Shows info message: "Submitted for approval (usually within 24 hours)"
   → Sends notification: "Withdrawal Pending Approval"

3. Admin reviews in Django Admin
   → Sees pending transfer in admin changelist
   → Clicks to view details
   → change_form.html shows approval buttons
   
   Option A: Admin clicks "APPROVE & SEND TO M-PESA"
   → approve_and_process_transfers action
   → Calls MpesaIntegrationService.process_approved_withdrawal()
   → Sends M-Pesa B2C request
   → Updates transaction to 'completed'
   → User notified: "Withdrawal Approved & Processed"
   
   Option B: Admin clicks "REJECT & REFUND"
   → reject_transfers action
   → Creates reversal transaction
   → Refunds full amount to wallet
   → Marks original transaction as 'reversed'
   → User notified: "Withdrawal Rejected - Funds Refunded"


   Flow 3: User Enters Wrong Password

1. User at password verification page
2. Enters incorrect password
3. authenticate() returns None
4. Context updated with password_error
5. Same page re-renders with error message
6. NO redirect, NO funds deducted
7. User can try again