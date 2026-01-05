from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.conf import settings
from expense_tracker.models import UserPreferences, Budget, Insight
from expense_tracker.utils import calculate_summary, check_budget_alerts
from datetime import timedelta


class Command(BaseCommand):
    help = 'Send email notifications and weekly summaries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['budget_alerts', 'weekly_summary', 'all'],
            default='all',
            help='Type of notification to send',
        )

    def handle(self, *args, **options):
        notification_type = options['type']
        
        if notification_type in ['budget_alerts', 'all']:
            self.send_budget_alerts()
        
        if notification_type in ['weekly_summary', 'all']:
            self.send_weekly_summaries()

    def send_budget_alerts(self):
        """Send budget alert emails to users who have budget_alerts enabled"""
        self.stdout.write('Sending budget alerts...')
        
        # Get users with budget alerts enabled
        preferences = UserPreferences.objects.filter(
            budget_alerts=True,
            email_notifications=True
        ).select_related('user')
        
        count = 0
        for pref in preferences:
            user = pref.user
            
            # Check for budget alerts
            alerts = check_budget_alerts(user)
            
            if alerts:
                # Send email
                subject = f'Budget Alert - {len(alerts)} budget(s) need attention'
                
                context = {
                    'user': user,
                    'alerts': alerts,
                }
                
                html_message = render_to_string('expense_tracker/emails/budget_alert.html', context)
                plain_message = strip_tags(html_message)
                
                try:
                    send_mail(
                        subject=subject,
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    count += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent budget alert to {user.email}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Failed to send to {user.email}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'Sent {count} budget alert email(s)'))

    def send_weekly_summaries(self):
        """Send weekly summary emails"""
        self.stdout.write('Sending weekly summaries...')
        
        # Get users with weekly summary enabled
        preferences = UserPreferences.objects.filter(
            weekly_summary=True,
            email_notifications=True
        ).select_related('user')
        
        # Calculate date range (last 7 days)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)
        
        count = 0
        for pref in preferences:
            user = pref.user
            
            # Get summary data
            summary = calculate_summary(user, start_date, end_date)
            
            # Get recent insights
            insights = Insight.objects.filter(
                user=user,
                created_at__gte=start_date
            ).order_by('-created_at')[:5]
            
            # Get budget status
            budgets = Budget.objects.filter(
                user=user,
                is_active=True
            ).select_related('category')
            
            budget_data = []
            for budget in budgets:
                budget_data.append({
                    'budget': budget,
                    'spent': budget.get_spent_amount(),
                    'remaining': budget.get_remaining_amount(),
                    'percentage': budget.get_percentage_used(),
                })
            
            subject = f'Your Weekly Financial Summary - {start_date} to {end_date}'
            
            context = {
                'user': user,
                'summary': summary,
                'insights': insights,
                'budget_data': budget_data,
                'start_date': start_date,
                'end_date': end_date,
            }
            
            html_message = render_to_string('expense_tracker/emails/weekly_summary.html', context)
            plain_message = strip_tags(html_message)
            
            try:
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                count += 1
                self.stdout.write(self.style.SUCCESS(f'Sent weekly summary to {user.email}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send to {user.email}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'Sent {count} weekly summary email(s)'))