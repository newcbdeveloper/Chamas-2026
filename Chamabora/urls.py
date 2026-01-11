"""Chamabora URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from authentication.views import showFirebaseJS
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Public / non-logged-in landing page
    path('', include('home.urls')),

    # Authentication (login, signup, etc.)
    path('user/', include('authentication.urls')),

    # ========== PRIMARY DASHBOARD (NEW & ACTIVE) ==========
    path('dashboard/', include('user_dashboard.urls', namespace='user_dashboard')),

    # ========== GOALS / WEKEZA (ACTIVE) ==========
    path('goals/', include('Goals.urls', namespace='goals')),
    #path('wekeza/', include('Goals.urls', namespace='wekeza')),  # kept for backward compatibility

    # ========== WALLET & PAYMENTS (ACTIVE) ==========
    path('wallet/', include('wallet.urls', namespace='wallet')),
    path('load_money/', include('mpesa_integration.urls')),
    path('withdraw/', include('pyment_withdraw.urls')),

    # ========== NOTIFICATIONS ==========
    path('notifications/', include('notifications.urls')),
    # path('send/', include('notifications.urls')),  # ← duplicate, commented out

    # ========== OTHER ACTIVE APPS ==========
    path('firebase-messaging-sw.js', showFirebaseJS, name="show_firebase_js"),
    path('subscriptions/', include('subscriptions.urls')),
    path('chamas-bookeeping/', include('chamas.urls')),
    path('bot/', include('bot.urls')),
    path('tinymce/', include('tinymce.urls')),
    path('blog/', include('blog.urls')),
    path('expense-tracker/', include('expense_tracker.urls')),
    path('merry-go-round/', include('merry_go_round.urls')),

    # ========== SUPPORT APP ==========
    path('support/', include('support.urls', namespace='support')),

    # CONTACT US FORM
    path('contact/', include('contact.urls')),

    # ========== LEGACY REDIRECTS (KEEP THESE!) ==========
    # These ensure old links still work and redirect to the NEW dashboard
    #path('my_goals/', RedirectView.as_view(pattern_name='user_dashboard:home'), name='my_goals'),
    #path('Dashboard/', RedirectView.as_view(pattern_name='user_dashboard:home')),
    #path('user-dash/', RedirectView.as_view(pattern_name='user_dashboard:home')),

    # ========== OLD / UNUSED / CONFLICTING PATHS (COMMENTED OUT) ==========
    # path('user-dash/', include('Dashboard.urls')),           # ← OLD Dashboard app — REMOVED
    # path('dashboard/', include('Goals.urls')),                # ← Was conflicting — REMOVED
    # path('send/', include('notifications.urls')),             # ← Duplicate of /notifications/
    # path('Dashboard/', RedirectView.as_view(pattern_name='user_dashboard:home')),  # ← Already covered above
]

# Static & Media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)