from .models import UserPreferences, Insight
from .utils import check_budget_alerts


def expense_tracker_context(request):
    """
    Add expense tracker related context to all templates
    """
    context = {}
    
    if request.user.is_authenticated:
        # Get user preferences
        try:
            preferences = UserPreferences.objects.get(user=request.user)
            context['user_preferences'] = preferences
            context['currency_symbol'] = preferences.currency
        except UserPreferences.DoesNotExist:
            context['currency_symbol'] = 'KSh'
        
        # Get unread insights count
        unread_insights_count = Insight.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        context['unread_insights_count'] = unread_insights_count
        
        # Get budget alerts count
        budget_alerts = check_budget_alerts(request.user)
        context['budget_alerts_count'] = len(budget_alerts)
        context['has_alerts'] = len(budget_alerts) > 0
    
    return context