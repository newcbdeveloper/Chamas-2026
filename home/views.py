from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


# Create your views here.

def Home(request):
    """Root view that redirects based on authentication status"""
    if request.user.is_authenticated:
        return redirect('user_dashboard:home')  # Redirect to goals dashboard
    else:
        return redirect('homepage')  # Redirect to landing page

def homepage(request):
    """Landing page for non-authenticated users"""
    return render(request, 'index.html')


def term_conditions(request):
    return render(request, 'term_conditions.html')

def privacy_policies(request):
    return render(request, 'privacy_policy.html')

def features(request):
    return render(request, 'features.html')

def about(request):
    return render(request, 'about.html')

def contact_us(request):
    return render(request, 'contact_us.html')

def cookies(request):
    return render(request, 'cookies.html')

