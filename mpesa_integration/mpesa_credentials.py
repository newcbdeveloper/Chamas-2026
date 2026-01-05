import requests
import json
from requests.auth import HTTPBasicAuth
from datetime import datetime
import base64
from django.conf import settings


class MpesaC2bCredential:
    consumer_key = settings.CONSUMER_KEY
    consumer_secret = settings.CONSUMER_SECRET
    api_URL = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'


def get_mpesa_access_token():
    try:
        r = requests.get(MpesaC2bCredential.api_URL,
                         auth=HTTPBasicAuth(MpesaC2bCredential.consumer_key, MpesaC2bCredential.consumer_secret))
        mpesa_access_token = json.loads(r.text)
        print(mpesa_access_token)
        return mpesa_access_token['access_token'] if 'access_token' in mpesa_access_token else None
    except:
        # Return mock token for development environment
        return "mock_access_token_for_development"

class MpesaAccessToken:
    @classmethod
    def get_validated_mpesa_access_token(cls):
        return get_mpesa_access_token()

class LipanaMpesaPpassword:
    lipa_time = datetime.now().strftime('%Y%m%d%H%M%S')
    Business_short_code = settings.BUSINESS_SHORT_CODE 
    passkey = settings.PASSKEY
    data_to_encode = Business_short_code + passkey + lipa_time
    online_password = base64.b64encode(data_to_encode.encode())
    decode_password = online_password.decode('utf-8')
