from datetime import timedelta
from django.utils import timezone
from .models import LoanItem, FineItem
from datetime import datetime, timedelta
from django.utils import timezone
from .models import ChamaMember, Contribution
from .send_sms_function import send_sms

#Automated overdue loan fining
def fine_overdue_loans():
  
    today = timezone.now().date()

    # Query all active loans that are overdue
    overdue_loans = LoanItem.objects.filter(
        status='active',
        end_date__lt=today
    )

    for loan in overdue_loans:
      
        days_overdue = (today - loan.end_date).days

       
        late_fine = loan.type.late_fine
        fine_amount = late_fine * days_overdue

       
        fine = FineItem.objects.create(
            member=loan.member,
            fine_type=None,  # You might want to specify the fine type here
            loan_amount=loan.amount,
            loan_balance=loan.balance,
            fine_amount=fine_amount,
            paid_fine_amount=0,  # Initially, no fine amount paid
            fine_balance=fine_amount,  # Fine balance equals fine amount initially
            status='active',  # Initially, the fine is active
            loan=loan,
            forLoan=True,  # Indicate that the fine is for a loan
            created=timezone.now(),
            last_updated=timezone.now()
        )

        # Update loan status to indicate fined
        loan.status = 'fined'
        loan.save()

        # Update loan balance with fine amount
        loan.balance += fine_amount
        loan.save()

#Due contribution reminders
def send_contribution_reminders():
    # Get current date
    today = timezone.now().date()

    # Define the time frame for upcoming due dates (e.g., within the next 7 days)
    due_date_range_start = today
    due_date_range_end = today + timedelta(days=7)

    # Query all Chama members
    chama_members = ChamaMember.objects.all()

    for member in chama_members:
        # Query contributions for this member due within the specified time frame
        upcoming_contributions = Contribution.objects.filter(
            member=member,
            due_date__range=(due_date_range_start, due_date_range_end)
        )

        if upcoming_contributions.exists():
            # Generate reminder message for upcoming contributions
            reminder_message = "Hello {}, you have upcoming contributions due:".format(member.name)
            for contribution in upcoming_contributions:
                reminder_message += "\n- Contribution of {} due on {}".format(contribution.amount, contribution.due_date.strftime("%Y-%m-%d"))

            # Send SMS reminder
            send_sms(member.mobile, reminder_message, profile_code="your-profile-code")

#loan repayment reminder
def send_loan_due_reminders():
    # Get current date
    today = timezone.now().date()

    # Query all active loans
    active_loans = LoanItem.objects.filter(status='active')

    for loan in active_loans:
        # Calculate the due date based on the start date and the repayment term
        due_date = loan.start_date + timedelta(days=loan.repayment_term)

        # Calculate the grace period end date
        grace_period_end_date = loan.start_date + timedelta(days=loan.type.grace_period)

        if today >= grace_period_end_date and today <= due_date:
            
            reminder_message = "Hello {}, your loan of {} is due for repayment on {}".format(loan.member.name, loan.amount, due_date.strftime("%Y-%m-%d"))
          #  send_sms(loan.member.mobile, reminder_message, profile_code="your-profile-code")
            # Note: Replace "your-profile-code" with the actual profile code for sending SMS






