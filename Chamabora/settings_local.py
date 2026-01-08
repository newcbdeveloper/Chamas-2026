"""
Local development settings for Chamabora project.
This file should be in .gitignore and is only used for local development.
"""

from .settings import *

# Override settings for local development
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '192.168.0.26','.ngrok-free.app',]

# Use SQLite for local development (easier and faster for testing)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_local.sqlite3',
    }
}

# Disable Cloudinary for local development (optional - use local file storage)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Console email backend for testing (emails print to console)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable HTTPS redirects for local development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Use dummy values for services you don't need locally
# (you can still use real values if you want to test integrations)
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='local-dev-sid')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='local-dev-token')
TWILIO_PHONE_NUMBER = env('TWILIO_PHONE_NUMBER', default='+1234567890')

# You can keep real Cloudinary credentials if you want to test file uploads
# Or comment them out to use local storage
# CLOUDINARY_STORAGE_CLOUD_NAME = 'test'
# CLOUDINARY_STORAGE_API_KEY = 'test'
# CLOUDINARY_STORAGE_API_SECRET = 'test'

# M-Pesa - use test values or keep real ones for testing
CONSUMER_KEY = env('CONSUMER_KEY')
CONSUMER_SECRET = env('CONSUMER_SECRET')
BUSINESS_SHORT_CODE = env('BUSINESS_SHORT_CODE', default='174379')
PASSKEY = env('PASSKEY', default='local-passkey')
CALLBACK_URL=env('CALLBACK_URL', default='https://chamaspace.com/load_money/callback')
INITIATOR_NAME=env('INITIATOR_NAME')
SECURITY_CREDENTIAL=env('SECURITY_CREDENTIAL')

# FCM - use dummy value for local
FCM_SERVER_KEY = env('FCM_SERVER_KEY', default='local-fcm-key')

# Infobip
INFOBIP_API_KEY = env('INFOBIP_API_KEY', default='local-infobip-key')
INFOBIP_SENDER_ID = env('INFOBIP_SENDER_ID', default='CHAMABORA')

# Media files stored locally
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media_local')

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_local')

# Disable cron jobs for local development
CRONJOBS = []

TIME_ZONE = 'Africa/Nairobi'
USE_TZ = True

print("🔧 Using LOCAL development settings")