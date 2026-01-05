# user_dashboard/kyc_urls.py
from django.urls import path
from . import kyc_views

app_name = 'kyc'

urlpatterns = [
    # Main KYC dashboard
    path('', kyc_views.kyc_dashboard, name='dashboard'),
    
    # KYC flow
    path('start/', kyc_views.kyc_start, name='start'),
    path('verify-identity/', kyc_views.kyc_verify_identity, name='verify_identity'),
    path('upload-documents/', kyc_views.kyc_upload_documents, name='upload_documents'),
    path('upload-selfie/', kyc_views.kyc_upload_selfie, name='upload_selfie'),
    path('review-submit/', kyc_views.kyc_review_submit, name='review_submit'),
    
    # AJAX endpoints
    path('delete-document/', kyc_views.kyc_delete_document, name='delete_document'),
]


