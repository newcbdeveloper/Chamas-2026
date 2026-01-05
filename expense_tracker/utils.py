from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from .models import Transaction, Budget, Category, Insight
import calendar
from django.db import transaction
from .models import RecurringTransaction, Transaction

def get_date_range(period='today', start_date=None, end_date=None):
    """
    Get start and end dates based on period
    Returns tuple: (start_date, end_date)
    """
    today = timezone.now().date()
    
    if period == 'today':
        return today, today
    
    elif period == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    
    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    
    elif period == 'last_week':
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end
    
    elif period == 'this_month':
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
        return start, end
    
    elif period == 'last_month':
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    
    elif period == 'this_year':
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return start, end
    
    elif period == 'custom' and start_date and end_date:
        return start_date, end_date
    
    return today, today


def calculate_summary(user, start_date=None, end_date=None):
    """
    Calculate financial summary for a user over a date range
    Returns dict with income, expenses, balance, and transaction count
    """
    transactions = Transaction.objects.filter(user=user)
    
    if start_date:
        transactions = transactions.filter(date__gte=start_date)
    if end_date:
        transactions = transactions.filter(date__lte=end_date)
    
    income = transactions.filter(type='income').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    expenses = transactions.filter(type='expense').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    balance = income - expenses
    
    transaction_count = transactions.count()
    
    return {
        'income': income,
        'expenses': expenses,
        'balance': balance,
        'transaction_count': transaction_count,
        'start_date': start_date,
        'end_date': end_date,
    }


def get_category_breakdown(user, transaction_type='expense', start_date=None, end_date=None):
    """
    Get spending/income breakdown by category
    Returns list of dicts with category name, amount, and percentage
    """
    transactions = Transaction.objects.filter(user=user, type=transaction_type)
    
    if start_date:
        transactions = transactions.filter(date__gte=start_date)
    if end_date:
        transactions = transactions.filter(date__lte=end_date)
    
    breakdown = transactions.values(
        'category__name', 'category__color', 'category__icon'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Calculate total for percentage
    total_amount = sum(item['total'] for item in breakdown)
    
    # Add percentage to each item
    result = []
    for item in breakdown:
        percentage = (item['total'] / total_amount * 100) if total_amount > 0 else 0
        result.append({
            'category': item['category__name'] or 'Uncategorized',
            'color': item['category__color'] or '#95a5a6',
            'icon': item['category__icon'] or '💰',
            'amount': item['total'],
            'count': item['count'],
            'percentage': round(percentage, 1)
        })
    
    return result


def get_spending_trend(user, days=30):
    """
    Get daily spending trend for the last N days
    Returns list of dicts with date and amount
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    transactions = Transaction.objects.filter(
        user=user,
        type='expense',
        date__gte=start_date,
        date__lte=end_date
    ).values('date').annotate(
        total=Sum('amount')
    ).order_by('date')
    
    # Create a dict for easy lookup
    transaction_dict = {item['date']: item['total'] for item in transactions}
    
    # Fill in missing dates with zero
    result = []
    current_date = start_date
    while current_date <= end_date:
        result.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'amount': float(transaction_dict.get(current_date, Decimal('0.00')))
        })
        current_date += timedelta(days=1)
    
    return result


def get_comparison_data(user, period='month'):
    """
    Compare current period with previous period
    Returns dict with current, previous, and change percentage
    """
    today = timezone.now().date()
    
    if period == 'week':
        current_start, current_end = get_date_range('this_week')
        previous_start, previous_end = get_date_range('last_week')
    else:  # month
        current_start, current_end = get_date_range('this_month')
        previous_start, previous_end = get_date_range('last_month')
    
    current_summary = calculate_summary(user, current_start, current_end)
    previous_summary = calculate_summary(user, previous_start, previous_end)
    
    # Calculate percentage change
    def calc_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return ((current - previous) / previous) * 100
    
    return {
        'current': current_summary,
        'previous': previous_summary,
        'income_change': calc_change(current_summary['income'], previous_summary['income']),
        'expense_change': calc_change(current_summary['expenses'], previous_summary['expenses']),
        'balance_change': calc_change(current_summary['balance'], previous_summary['balance']),
    }


def check_budget_alerts(user):
    """
    Check all active budgets and create alerts if thresholds are exceeded
    Returns list of budget alerts
    """
    alerts = []
    budgets = Budget.objects.filter(user=user, is_active=True)
    
    for budget in budgets:
        percentage_used = budget.get_percentage_used()
        
        if percentage_used >= 100:
            alerts.append({
                'budget': budget,
                'type': 'danger',
                'message': f'Budget exceeded for {budget.category.name}!',
                'percentage': percentage_used
            })
        elif percentage_used >= budget.alert_threshold:
            alerts.append({
                'budget': budget,
                'type': 'warning',
                'message': f'{budget.category.name} budget at {percentage_used:.0f}%',
                'percentage': percentage_used
            })
    
    return alerts


def generate_insights(user):
    """
    Generate AI-like insights based on spending patterns
    Creates Insight objects in the database
    """
    today = timezone.now().date()
    this_month_start, this_month_end = get_date_range('this_month')
    last_month_start, last_month_end = get_date_range('last_month')
    
    # Get this month and last month spending by category
    this_month_spending = Transaction.objects.filter(
        user=user,
        type='expense',
        date__gte=this_month_start,
        date__lte=this_month_end
    ).values('category').annotate(total=Sum('amount'))
    
    last_month_spending = Transaction.objects.filter(
        user=user,
        type='expense',
        date__gte=last_month_start,
        date__lte=last_month_end
    ).values('category').annotate(total=Sum('amount'))
    
    # Create dict for comparison
    this_month_dict = {item['category']: item['total'] for item in this_month_spending}
    last_month_dict = {item['category']: item['total'] for item in last_month_spending}
    
    insights_created = []
    
    # Compare and create insights
    for category_id, this_month_amount in this_month_dict.items():
        last_month_amount = last_month_dict.get(category_id, Decimal('0.00'))
        
        if last_month_amount > 0:
            change_percentage = ((this_month_amount - last_month_amount) / last_month_amount) * 100
            
            if abs(change_percentage) >= 20:  # Significant change threshold
                try:
                    category = Category.objects.get(id=category_id)
                    
                    if change_percentage > 0:
                        insight = Insight.objects.create(
                            user=user,
                            type='increase',
                            title=f'{category.name} spending increased',
                            message=f'Your {category.name} spending increased by {change_percentage:.0f}% this month (KSh {this_month_amount:,.2f} vs KSh {last_month_amount:,.2f} last month).',
                            category=category
                        )
                    else:
                        insight = Insight.objects.create(
                            user=user,
                            type='decrease',
                            title=f'{category.name} spending decreased',
                            message=f'Great job! Your {category.name} spending decreased by {abs(change_percentage):.0f}% this month (KSh {this_month_amount:,.2f} vs KSh {last_month_amount:,.2f} last month).',
                            category=category
                        )
                    
                    insights_created.append(insight)
                except Category.DoesNotExist:
                    continue
    
    # Check for budget warnings
    budgets = Budget.objects.filter(user=user, is_active=True)
    for budget in budgets:
        if budget.should_alert():
            percentage = budget.get_percentage_used()
            remaining = budget.get_remaining_amount()
            
            # Check if insight already exists for this budget
            existing = Insight.objects.filter(
                user=user,
                type='budget_warning',
                category=budget.category,
                created_at__gte=budget.get_period_start()
            ).exists()
            
            if not existing:
                insight = Insight.objects.create(
                    user=user,
                    type='budget_warning',
                    title=f'{budget.category.name} budget warning',
                    message=f'You have used {percentage:.0f}% of your {budget.get_period_display().lower()} {budget.category.name} budget. Only KSh {remaining:,.2f} remaining.',
                    category=budget.category
                )
                insights_created.append(insight)
    
    return insights_created


def format_currency(amount, currency='KSh'):
    """Format amount with currency symbol"""
    return f"{currency} {amount:,.2f}"


def get_top_categories(user, transaction_type='expense', limit=5, start_date=None, end_date=None):
    """
    Get top N categories by spending/income
    """
    transactions = Transaction.objects.filter(user=user, type=transaction_type)
    
    if start_date:
        transactions = transactions.filter(date__gte=start_date)
    if end_date:
        transactions = transactions.filter(date__lte=end_date)
    
    top_categories = transactions.values(
        'category__name', 'category__icon'
    ).annotate(
        total=Sum('amount')
    ).order_by('-total')[:limit]
    
    return list(top_categories)


def calculate_daily_average(user, days=30):
    """
    Calculate average daily spending over the last N days
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    total_expenses = Transaction.objects.filter(
        user=user,
        type='expense',
        date__gte=start_date,
        date__lte=end_date
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    return total_expenses / days if days > 0 else Decimal('0.00')

# RECURRING TRANSACTIONS


def generate_recurring_transactions(user=None, max_instances_per_recurring=100):
    """
    Generate pending recurring transactions.
    
    Args:
        user: Optional. If None, processes all users.
        max_instances_per_recurring: Safety cap to prevent infinite loops (e.g., daily backfill over 10 years).
    
    Returns:
        total_created (int): Number of transactions created.
    """
    today = timezone.now().date()
    
    queryset = RecurringTransaction.objects.filter(
        is_active=True,
        auto_generate=True,
        next_occurrence__lte=today  # Only those due or overdue
    )
    
    if user:
        queryset = queryset.filter(user=user)
    
    total_created = 0
    
    for rec in queryset.select_related('user', 'category'):
        created_count = 0
        
        # Backfill from next_occurrence up to today (or end_date, whichever comes first)
        current = rec.next_occurrence
        
        # Respect end_date if set
        cutoff = rec.end_date if rec.end_date and rec.end_date < today else today
        
        while current <= cutoff and created_count < max_instances_per_recurring:
            # Create transaction
            Transaction.objects.create(
                user=rec.user,
                type=rec.type,
                category=rec.category,
                amount=rec.amount,
                description=rec.description or f"Recurring: {rec}",
                date=current,
                time=timezone.now().time(),
                is_recurring=True,
                recurring_transaction=rec,
            )
            total_created += 1
            created_count += 1
            
            # Calculate next
            current = rec.calculate_next_occurrence(current_date=current)
        
        # Update next_occurrence (even if we hit max_instances, resume later)
        rec.next_occurrence = current
        rec.save(update_fields=['next_occurrence'])
        
    return total_created