import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from authentication.models import Profile
from notifications.models import UserFcmTokens
from chamas.models import Chama, Role

@pytest.mark.django_db
class TestAuthManager:
    def test_login_view_get(self, client):
        response = client.get(reverse('Login'))
        assert response.status_code == 200

    def test_login_view_post_invalid(self, client):
        response = client.post(reverse('Login'), {'un': 'nonexistent', 'password': 'wrong'})
        assert response.status_code == 200
        assert b'User not found' in response.content

    def test_signup_flow_and_verify_otp(self, client, settings, monkeypatch):
        # Mock OTP send
        settings.INFOBIP_API_BASE_URL = 'test'
        settings.INFOBIP_API_KEY = 'key'
        from authentication.services.otp_service import OTPService
        monkeypatch.setattr(OTPService, 'send_otp', lambda m, o: '200')

        # Start signup
        response = client.post(reverse('Sign_up'), {
            'nic_no': '12345', 'fname': 'John', 'lname': 'Doe',
            'phone_no': '0712345678', 'password': 'pass123'
        })
        assert response.status_code == 302
        assert reverse('verify_otp') in response.url

        # Verify OTP
        session = client.session
        otp = session['signup_data']['otp']
        session.save()
        response = client.post(reverse('verify_otp'), {'otp': otp})
        assert response.status_code == 302
        assert reverse('my_goals') in response.url
        user = User.objects.get(username='12345')
        assert Profile.objects.filter(owner=user).exists()

    def test_signup_step2_and_logout(self, client):
        # Prepare user and session
        user = User.objects.create_user(username='step2', password='p')
        Profile.objects.create(owner=user, NIC_No='step2', phone='+254700000000')
        session = client.session
        session['mobile'] = 'step2'
        session.save()

        # Signup step2 GET
        response = client.get(reverse('Sign_Up2'))
        assert response.status_code == 200

        # Signup step2 POST
        response = client.post(reverse('Sign_Up2'), {
            'email': 'a@b.com', 'Sex': 'M',
            'payment_gateway': 'PayPAL', 'how_find_us': 'Online'
        })
        assert response.status_code == 302
        assert reverse('Login') in response.url

        # Logout
        response = client.get(reverse('Logout'))
        assert response.status_code == 302
        assert reverse('Login') in response.url

@pytest.mark.django_db
class TestOTPService:
    def test_send_otp(self, monkeypatch):
        from authentication.services.otp_service import OTPService
        class DummyConn:
            def __init__(self, url): pass
            def request(self, *a): pass
            def getresponse(self): return self
            def read(self): return b'{"messages":[{"status":{"groupName":"DELIVERED"}}]}'
            status = 200
        monkeypatch.setattr('authentication.services.otp_service.http.client.HTTPSConnection', DummyConn)
        assert OTPService.send_otp('+254700000000', '1234') == '200'

    def test_verify_login_otp(self, client, settings, monkeypatch):
        # Setup user and profile
        user = User.objects.create_user(username='u1', password='p1')
        Profile.objects.create(owner=user, NIC_No='u1', phone='+254700000000')
        session = client.session
        session.update({'mobile': '+254700000000', 'Username': 'u1', 'Password': 'p1', 'search_str': 'token'})
        session.save()

        from authentication.services.otp_service import OTPService
        monkeypatch.setattr(OTPService, 'send_notif', lambda *a, **k: None)
        profile = Profile.objects.get(owner=user)
        profile.otp = '9999'
        profile.save()

        response = client.post(reverse('login_otp'), {'2facode': '9999'})
        assert response.status_code == 302
        assert reverse('my_goals') in response.url
        assert UserFcmTokens.objects.filter(user=user, token='token').exists()

@pytest.mark.django_db
class TestPasswordService:
    def test_forget_reset_update(self, client, settings, monkeypatch):
        user = User.objects.create_user(username='u2', password='old')
        Profile.objects.create(owner=user, NIC_No='u2', phone='+254700000001')
        settings.INFOBIP_API_BASE_URL = 'test'
        settings.INFOBIP_API_KEY = 'key'
        from authentication.services.otp_service import OTPService
        monkeypatch.setattr(OTPService, 'send_otp', lambda m, o: '200')

        # Forget password
        response = client.post(reverse('forget_password'), {'un': 'u2'})
        assert response.status_code == 302
        assert reverse('reset_password') in response.url

        # Reset password
        otp = client.session['otp']
        response = client.post(reverse('reset_password'), {'2facode': otp})
        assert response.status_code == 302
        assert reverse('update_password') in response.url

        # Update password
        response = client.post(reverse('update_password'), {'new_password': 'newpass'})
        assert response.status_code == 302
        assert reverse('Login') in response.url
        client.logout()
        assert client.login(username='u2', password='newpass')

@pytest.mark.django_db
class TestAccountService:
    def test_delete_account(self, client):
        user = User.objects.create_user(username='u3', password='p')
        client.login(username='u3', password='p')
        # Create required ChamaMember dependencies
        group = Chama.objects.create(name='g')
        role = Role.objects.create(name='r')
        from chamas.models import ChamaMember
        ChamaMember.objects.create(user=user, group=group, role=role)

        response = client.get(reverse('delete-account'))
        assert response.status_code == 302
        assert not User.objects.filter(username='u3').exists()