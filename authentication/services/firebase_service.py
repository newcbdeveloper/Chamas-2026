from django.http import HttpResponse

class FirebaseService:
    @staticmethod
    def serve_firebase_js(request):
        data = (
            'importScripts("https://www.gstatic.com/firebasejs/8.2.0/firebase-app.js");'
            'importScripts("https://www.gstatic.com/firebasejs/8.2.0/firebase-messaging.js");'
            'var firebaseConfig = {'
            ' apiKey: "AIzaSyBHYZJCR9UqOqmDM0YOtEVi9WhoVfNg2eU",'
            ' authDomain: "chamabora-b72ce.firebaseapp.com",'
            ' databaseURL: "https://chamabora-b72ce-default-rtdb.firebaseio.com/",'
            ' projectId: "chamabora-b72ce",'
            ' storageBucket: "chamabora-b72ce.appspot.com",'
            ' messagingSenderId: "716918897134",'
            ' appId: "1:716918897134:web:be99ac855e0d585341b6ff",'
            ' measurementId: "${config.measurementId}"'
            '};'
            'firebase.initializeApp(firebaseConfig);'
            'const messaging=firebase.messaging();'
            'messaging.setBackgroundMessageHandler(function (payload) {'
            ' console.log(payload);'
            ' const notification=JSON.parse(payload);'
            ' const notificationOption={'
            '    body:notification.body,'
            '    icon:notification.icon'
            ' };'
            ' return self.registration.showNotification(payload.notification.title,notificationOption);'
            '});'
        )
        return HttpResponse(data, content_type="text/javascript")