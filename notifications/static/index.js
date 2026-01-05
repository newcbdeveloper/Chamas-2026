import firebase from "firebase/app";
import "firebase/messaging";


function getMessagingObject() {
  // [START messaging_get_messaging_object]
  const messaging = firebase.messaging();
  // [END messaging_get_messaging_object]
}

function receiveMessage() {
  const messaging = firebase.messaging();
  // [START messaging_receive_message]
  // Handle incoming messages. Called when:
  // - a message is received while the app has focus
  // - the user clicks on an app notification created by a service worker
  //   `messaging.onBackgroundMessage` handler.
  messaging.onMessage((payload) => {
    console.log('Message received. ', payload);
    // ...
  });
  // [END messaging_receive_message]
}

function getToken() {
  const messaging = firebase.messaging();
  // [START messaging_get_token]
  // Get registration token. Initially this makes a network call, once retrieved
  // subsequent calls to getToken will return from cache.
  messaging.getToken({ vapidKey: 'BEOKcWRX3Th6qOijJPEbQczW_L2zYD9rnIAXAvdBVzJ8_Bo2-rHlFgfsnnbg_z5hVaONFY7h4NCT13Gt71-Di_A' }).then((currentToken) => {
    if (currentToken) {
      console.log(currentToken)
    } else {
      // Show permission request UI
      console.log('No registration token available. Request permission to generate one.');
      // ...
    }
  }).catch((err) => {
    console.log('An error occurred while retrieving token. ', err);
    // ...
  });
  // [END messaging_get_token]
}

function requestPermission() {
  // [START messaging_request_permission]
  Notification.requestPermission().then((permission) => {
    if (permission === 'granted') {
      console.log('Notification permission granted.');
      // TODO(developer): Retrieve a registration token for use with FCM.
      // ...
    } else {
      console.log('Unable to get permission to notify.');
    }
  });
  // [END messaging_request_permission]
}

function deleteToken() {
  const messaging = firebase.messaging();

  // [START messaging_delete_token]
  messaging.deleteToken().then(() => {
    console.log('Token deleted.');
    // ...
  }).catch((err) => {
    console.log('Unable to delete token. ', err);
  });
  // [END messaging_delete_token]
}