from django.utils import timezone
from .models import UserPreferences


class ExpenseTrackerMiddleware:
    """
    Middleware for expense tracker functionality
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        
        if request.user.is_authenticated:
            # Ensure user has preferences
            UserPreferences.objects.get_or_create(user=request.user)
        
        response = self.get_response(request)
        
        # Code to be executed for each request/response after
        # the view is called.
        
        return response