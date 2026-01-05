from django.shortcuts import render
from django.http.request import HttpHeaders

from django.http import HttpResponse
import requests
import json


# Create your views here.

def send_notification(registration_ids, message_title, message_desc):
    fcm_api = ""
    url = "https://fcm.googleapis.com/fcm/send"

    headers = {
        "Content-Type": "application/json",
        "Authorization": 'key=' + fcm_api}

    payload = {
        "registration_ids": registration_ids,
        "priority": "high",
        "notification": {
            "body": message_desc,
            "title": message_title,
            "image": "https://i.ytimg.com/vi/m5WUPHRgdOA/hqdefault.jpg?sqp=-oaymwEXCOADEI4CSFryq4qpAwkIARUAAIhCGAE=&rs=AOn4CLDwz-yjKEdwxvKjwMANGk5BedCOXQ",
            "icon": "https://yt3.ggpht.com/ytc/AKedOLSMvoy4DeAVkMSAuiuaBdIGKC7a5Ib75bKzKO3jHg=s900-c-k-c0x00ffffff-no-rj",

        }
    }

    result = requests.post(url, data=json.dumps(payload), headers=headers)
    print(result.json())


def index(request):
    print("im in")
    return render(request, 'index.html')


def send(request):
    resgistration = ['fGqD6gdf_shF7h_aFBBwe8:APA91bFCw6Zjcecj0J5AXn8i8qDeOCFfkF7qH9Hcg92SwVPUczLHf52Y2saGyEtIwa_OW7mM9Ztt6g4hHO1rWr7xe81p4liZ0uU-mX6kwZUvuWe-2uEzhOqoOfoS_QRHmqMJ7Il_W7QD']
    send_notification(resgistration, 'Code Keen added a new video', 'Code Keen new video alert')
    return HttpResponse("sent")


def showFirebaseJS(request):
    data = 'importScripts("https://www.gstatic.com/firebasejs/8.2.0/firebase-app.js");' \
           'importScripts("https://www.gstatic.com/firebasejs/8.2.0/firebase-messaging.js"); ' \
           'var firebaseConfig = {' \
           '        apiKey: "AIzaSyBHYZJCR9UqOqmDM0YOtEVi9WhoVfNg2eU",' \
           '        authDomain: "chamabora-b72ce.firebaseapp.com",' \
           '        databaseURL: "https://chamabora-b72ce-default-rtdb.firebaseio.com/",' \
           '        projectId: "chamabora-b72ce",' \
           '        storageBucket: "chamabora-b72ce.appspot.com",' \
           '        messagingSenderId: "716918897134",' \
           '        appId: "1:716918897134:web:be99ac855e0d585341b6ff",' \
           '        measurementId: "${config.measurementId}"' \
           ' };' \
           'firebase.initializeApp(firebaseConfig);' \
           'const messaging=firebase.messaging();' \
           'messaging.setBackgroundMessageHandler(function (payload) {' \
           '    console.log(payload);' \
           '    const notification=JSON.parse(payload);' \
           '    const notificationOption={' \
           '        body:notification.body,' \
           '        icon:notification.icon' \
           '    };' \
           '    return self.registration.showNotification(payload.notification.title,notificationOption);' \
           '});'

    return HttpResponse(data, content_type="text/javascript")
