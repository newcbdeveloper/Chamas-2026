from django.core.management.base import BaseCommand
from chamas.models import ChamaType

class Command(BaseCommand):
    help = 'Initialize group types'

    def handle(self,*args,**options):
        variables = [
            ('saving group'),
            ('contribution group'),
            ('lending group'),
            ('Investment group'),
            ('combined saving and loan group'),
            ('business investment group')

        ]
        for name in variables:
            try:
                chama_type = ChamaType.objects.get(name=name)
                self.stdout.write(self.style.SUCCESS(f'type {name} already exists'))
            except ChamaType.DoesNotExist:
                new_type = ChamaType.objects.create(name=name)
                self.stdout.write(self.style.SUCCESS(f'chama type {name} created succefully.'))
        self.stdout.write(self.style.SUCCESS(f'all types created succesfully'))

    