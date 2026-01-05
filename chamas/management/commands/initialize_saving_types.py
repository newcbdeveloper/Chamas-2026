from django.core.management.base import BaseCommand
from chamas.models import SavingType

class Command(BaseCommand):
    help = 'Initialize saving types'

    def handle(self,*args,**options):
        variables = [
            ('cash at hand'),
            ('cash at bank'),
           
        ]
        for name in variables:
            type = SavingType.objects.filter(name=name).first()
            if type:
                 self.stdout.write(self.style.SUCCESS(f'saving type {name} already exists'))
            else:
                new_type = SavingType.objects.create(name=name)
                self.stdout.write(self.style.SUCCESS(f'saving type {name} created succefully.'))
                
        self.stdout.write(self.style.SUCCESS(f'all types created succesfully'))

    