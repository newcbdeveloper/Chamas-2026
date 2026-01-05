
"""
Convenience helpers for creating notifications across all ChamaSpace apps.

This wraps your existing notification system (send_sms, send_notif) 
with easy-to-use methods that automatically categorize notifications.

Usage:
    from notifications.helpers import NotificationHelper
    
    NotificationHelper.notify_deposit(
        user=request.user,
        amount=1000,
        destination="Vacation goal"
    )
"""

from .utils import create_unified_notification
import logging

logger = logging.getLogger(__name__)


class NotificationHelper:
    """
    Convenience methods for creating standardized notifications
    All methods use create_unified_notification() which handles:
    - Database entry (UserNotificationHistory)
    - SMS (via Twilio)
    - Push notification (via FCM)
    """
    
    # ========================================
    # GOAL NOTIFICATIONS
    # ========================================
    
    @staticmethod
    def notify_goal_created(user, goal_name):
        """
        Notify user that a new goal was created
        
        Example:
            NotificationHelper.notify_goal_created(
                user=request.user,
                goal_name="Vacation Fund"
            )
        """
        return create_unified_notification(
            user=user,
            title="Congratulation",
            message=f"You have successfully started your new goal {goal_name}",
            category='goal'
        )
    
    @staticmethod
    def notify_goal_deposit(user, amount, goal_name):
        """
        Notify user of a deposit to a goal
        
        Example:
            NotificationHelper.notify_goal_deposit(
                user=request.user,
                amount=1000,
                goal_name="Vacation Fund"
            )
        """
        return create_unified_notification(
            user=user,
            title="Congratulation",
            message=f"Successfully deposit {amount}Ksh to your {goal_name}",
            category='deposit'
        )
    
    @staticmethod
    def notify_goal_withdrawal(user, amount, goal_name, target="Main Wallet", achieved=False):
        """
        Notify user of a withdrawal from a goal
        
        Example:
            NotificationHelper.notify_goal_withdrawal(
                user=request.user,
                amount=5000,
                goal_name="Vacation Fund",
                target="Main Wallet",
                achieved=True
            )
        """
        achievement_text = " (Target amount achieved! 🎯)" if achieved else ""
        
        message = (
            f"✅ Withdrawal Successful! KES {amount} has been withdrawn from goal '{goal_name}'{achievement_text}. "
            f"The funds are now in your {target}. You can: "
            f"• Withdraw to M-Pesa • Use for other ChamaSpace features • Transfer to another goal"
        )
        
        return create_unified_notification(
            user=user,
            title="Withdrawal Successful",
            message=message,
            category='withdrawal'
        )
    
    # ========================================
    # EXPRESS SAVING NOTIFICATIONS
    # ========================================
    
    @staticmethod
    def notify_express_deposit(user, amount):
        """
        Notify user of a deposit to express saving
        
        Example:
            NotificationHelper.notify_express_deposit(
                user=request.user,
                amount=500
            )
        """
        return create_unified_notification(
            user=user,
            title="Congratulation",
            message=f"Successfully deposit {amount} Ksh to express saving.",
            category='deposit'
        )
    
    @staticmethod
    def notify_express_withdrawal(user, amount, target="Main Wallet"):
        """
        Notify user of withdrawal from express saving
        
        Example:
            NotificationHelper.notify_express_withdrawal(
                user=request.user,
                amount=2500,
                target="Main Wallet"
            )
        """
        message = (
            f"✅ Successfully withdrawn KES {amount} from Express Saving to your {target}. "
            f"You can now withdraw to M-Pesa or use for other ChamaSpace features."
        )
        
        return create_unified_notification(
            user=user,
            title="Withdrawal Successful",
            message=message,
            category='withdrawal'
        )
    
    # ========================================
    # GROUP GOAL NOTIFICATIONS
    # ========================================
    
    @staticmethod
    def notify_group_goal_created(user, goal_name):
        """Notify user that a group goal was created"""
        return create_unified_notification(
            user=user,
            title="Congratulation",
            message=f"You have successfully created group goal: {goal_name}",
            category='goal'
        )
    
    @staticmethod
    def notify_group_goal_joined(user, goal_name):
        """Notify user they joined a group goal"""
        return create_unified_notification(
            user=user,
            title="Congratulation",
            message=f"Successfully joined {goal_name}",
            category='goal'
        )
    
    @staticmethod
    def notify_group_goal_deposit(user, amount, goal_name):
        """Notify user of deposit to group goal"""
        return create_unified_notification(
            user=user,
            title="Congratulation",
            message=f"Successfully deposit {amount}Ksh to your {goal_name}",
            category='deposit'
        )
    
    @staticmethod
    def notify_group_goal_withdrawal(user, amount, goal_name, achieved=False):
        """Notify creator of group goal withdrawal"""
        achievement_text = " (Target amount achieved! 🎯)" if achieved else ""
        
        message = (
            f"✅ Group Goal Withdrawal Successful! KES {amount} has been withdrawn from group goal "
            f"'{goal_name}'{achievement_text}. The funds are now in your Main Wallet."
        )
        
        return create_unified_notification(
            user=user,
            title="Withdrawal Successful",
            message=message,
            category='withdrawal'
        )
    
    @staticmethod
    def notify_group_goal_completed(user, goal_name, creator_name, amount):
        """Notify members that group goal was completed"""
        message = (
            f"🎉 Group Goal Completed! {creator_name} has withdrawn funds from group goal "
            f"'{goal_name}'. Total withdrawn: KES {amount}. Thank you for participating!"
        )
        
        return create_unified_notification(
            user=user,
            title="Group Goal Completed",
            message=message,
            category='goal'
        )
    
    # ========================================
    # WALLET NOTIFICATIONS
    # ========================================
    
    @staticmethod
    def notify_wallet_deposit(user, amount, source="M-Pesa"):
        """
        Notify user of deposit to main wallet
        
        Example:
            NotificationHelper.notify_wallet_deposit(
                user=request.user,
                amount=5000,
                source="M-Pesa"
            )
        """
        return create_unified_notification(
            user=user,
            title="Deposit Successful",
            message=f"Successfully deposited KES {amount} from {source} to your Main Wallet",
            category='deposit'
        )
    
    @staticmethod
    def notify_wallet_withdrawal(user, amount, destination="M-Pesa"):
        """Notify user of withdrawal from main wallet"""
        return create_unified_notification(
            user=user,
            title="Withdrawal Successful",
            message=f"Successfully withdrawn KES {amount} to {destination}",
            category='withdrawal'
        )
    
    @staticmethod
    def notify_wallet_transfer(user, amount, from_wallet, to_wallet):
        """Notify user of wallet-to-wallet transfer"""
        return create_unified_notification(
            user=user,
            title="Transfer Complete",
            message=f"Successfully transferred KES {amount} from {from_wallet} to {to_wallet}",
            category='wallet'
        )
    
    @staticmethod
    def notify_insufficient_balance(user, amount, purpose):
        """Notify user of insufficient balance"""
        return create_unified_notification(
            user=user,
            title="Insufficient Balance",
            message=f"Your wallet has insufficient balance for {purpose}. Please deposit KES {amount} to continue.",
            category='wallet'
        )
    
    # ========================================
    # MERRY-GO-ROUND (MGR) NOTIFICATIONS
    # ========================================
    
    @staticmethod
    def notify_mgr_joined(user, round_name, locked_amount):
        """
        Notify user they joined a merry-go-round
        
        Example:
            NotificationHelper.notify_mgr_joined(
                user=request.user,
                round_name="Teachers Round",
                locked_amount=1000
            )
        """
        return create_unified_notification(
            user=user,
            title=f"Joined {round_name}",
            message=f"You have successfully joined {round_name}. KES {locked_amount} has been reserved for your first contribution.",
            category='mgr'
        )
    
    @staticmethod
    def notify_mgr_contribution(user, amount, round_name, cycle):
        """Notify user of MGR contribution processed"""
        return create_unified_notification(
            user=user,
            title="Contribution Processed",
            message=f"Your contribution of KES {amount} for cycle {cycle} in {round_name} has been processed successfully.",
            category='mgr'
        )
    
    @staticmethod
    def notify_mgr_payout(user, amount, round_name):
        """Notify user of MGR payout received"""
        return create_unified_notification(
            user=user,
            title="Payout Received",
            message=f"You have received your payout of KES {amount} from {round_name} in your MGR wallet.",
            category='mgr'
        )
    
    @staticmethod
    def notify_mgr_round_started(user, round_name, first_contribution_date):
        """Notify user that round has started"""
        return create_unified_notification(
            user=user,
            title=f"{round_name} Has Started!",
            message=f"The round has started. First contribution is due on {first_contribution_date}.",
            category='mgr'
        )
    
    @staticmethod
    def notify_mgr_contribution_reminder(user, amount, round_name, due_date):
        """Remind user of upcoming contribution"""
        return create_unified_notification(
            user=user,
            title="Contribution Due Tomorrow",
            message=f"Your contribution of KES {amount} for {round_name} will be auto-processed tomorrow ({due_date}). Ensure sufficient wallet balance.",
            category='mgr'
        )
    
    @staticmethod
    def notify_mgr_contribution_failed(user, amount, round_name, reason):
        """Notify user that contribution failed"""
        return create_unified_notification(
            user=user,
            title="Contribution Failed",
            message=f"Your contribution of KES {amount} for {round_name} failed: {reason}. Please ensure sufficient balance.",
            category='mgr'
        )
    
    # ========================================
    # GENERAL NOTIFICATIONS
    # ========================================
    
    @staticmethod
    def notify_custom(user, title, message, category='general'):
        """
        Create a custom notification
        
        Example:
            NotificationHelper.notify_custom(
                user=request.user,
                title="Important Update",
                message="Your profile has been verified",
                category='general'
            )
        """
        return create_unified_notification(
            user=user,
            title=title,
            message=message,
            category=category
        )