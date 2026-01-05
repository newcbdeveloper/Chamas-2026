from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Create a superuser if it does not exist'

    def handle(self, *args, **kwargs):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@chamaspace.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Pass@123')

        # print(username, email, password)
        User.objects.filter(username=username).delete()
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS('Superuser created'))
        else:
            self.stdout.write(self.style.SUCCESS('Superuser already exists'))

        user = User.objects.get(username=username) 
        user.set_password(password) 
        user.is_superuser = True
        user.is_staff = True
        user.save()


