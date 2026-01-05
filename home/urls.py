from django.urls import path
from . import views


urlpatterns=[
path('', views.Home, name='index'),
path('landing', views.homepage, name='homepage'),
path('term_conditions', views.term_conditions, name='term_conditions'),
path('privacy_policies', views.privacy_policies, name='privacy_policies'),
path('features', views.features, name='features'),
path('about', views.about, name='about'),
path('contact_us', views.contact_us, name='contact_us'),
path('cookies', views.cookies, name='cookies'),
]