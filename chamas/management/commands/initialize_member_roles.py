from django.core.management.base import BaseCommand
from chamas.models import Role

class Command(BaseCommand):
    help = 'Initialize member roles'

    def handle(self,*args,**options):
        variables = [
            ('member'),
            ('admin'),
            ('treasurer'),
            ('chairman')

        ]
        for name in variables:
            try:
                role = Role.objects.get(name=name)
                self.stdout.write(self.style.SUCCESS(f'role {name} already exists'))
            except Role.DoesNotExist:
                new_role = Role.objects.create(name=name)
                self.stdout.write(self.style.SUCCESS(f'role {name} created succefully.'))
        self.stdout.write(self.style.SUCCESS(f'all roles created succesfully'))

    