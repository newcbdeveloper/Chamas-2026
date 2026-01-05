from django.urls import path
from .views import index,send,showFirebaseJS

urlpatterns = [

    path('token/', index),
    path('send/', send),
    path('firebase-messaging-sw.js', showFirebaseJS, name="show_firebase_js"),
]
