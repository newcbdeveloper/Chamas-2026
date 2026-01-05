"""
Create this file: merry_go_round/management/commands/mgr_list_rounds.py
"""
from django.core.management.base import BaseCommand
from merry_go_round.models import Round, RoundMembership
from django.db.models import Count


class Command(BaseCommand):
    help = 'List all rounds with their IDs and status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            type=str,
            help='Filter by status (active, open, completed, etc.)',
        )

    def handle(self, *args, **options):
        status = options.get('status')
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('  ROUNDS LIST'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        
        # Get rounds
        rounds = Round.objects.all()
        if status:
            rounds = rounds.filter(status=status)
        
        rounds = rounds.annotate(
            member_count=Count('memberships')
        ).order_by('-created_at')
        
        if not rounds.exists():
            self.stdout.write(self.style.WARNING('No rounds found.'))
            return
        
        for round_obj in rounds:
            # Status color coding
            if round_obj.status == 'active':
                status_style = self.style.SUCCESS
            elif round_obj.status == 'completed':
                status_style = self.style.HTTP_INFO
            elif round_obj.status == 'open':
                status_style = self.style.WARNING
            else:
                status_style = self.style.ERROR
            
            self.stdout.write('\n' + '-'*80)
            self.stdout.write(self.style.HTTP_SUCCESS(f'NAME: {round_obj.name}'))
            self.stdout.write(f'ID: {round_obj.id}')
            self.stdout.write(status_style(f'STATUS: {round_obj.status.upper()}'))
            self.stdout.write(f'TYPE: {round_obj.get_round_type_display()}')
            self.stdout.write(f'MODEL: {round_obj.get_payout_model_display()}')
            self.stdout.write(f'MEMBERS: {round_obj.member_count}/{round_obj.max_members}')
            self.stdout.write(f'CONTRIBUTION: KES {round_obj.contribution_amount}')
            self.stdout.write(f'FREQUENCY: {round_obj.get_frequency_display()}')
            
            if round_obj.start_date:
                self.stdout.write(f'START DATE: {round_obj.start_date}')
            if round_obj.end_date:
                self.stdout.write(f'END DATE: {round_obj.end_date}')
            
            self.stdout.write(f'TOTAL POOL: KES {round_obj.total_pool}')
            self.stdout.write(f'CREATED: {round_obj.created_at.strftime("%Y-%m-%d %H:%M")}')
            
            # Show members
            memberships = RoundMembership.objects.filter(round=round_obj)
            if memberships.exists():
                self.stdout.write('\nMEMBERS:')
                for membership in memberships:
                    self.stdout.write(
                        f'  - {membership.user.username} '
                        f'(Status: {membership.status}, '
                        f'Contributed: KES {membership.total_contributed})'
                    )
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'Total rounds: {rounds.count()}\n'))
        
        # Show quick commands
        self.stdout.write(self.style.WARNING('\nQUICK COMMANDS:'))
        self.stdout.write('  Fast-forward by name:')
        self.stdout.write('    python manage.py mgr_fastforward --round-name="Round Name" --days=0')
        self.stdout.write('\n  Fast-forward by ID:')
        self.stdout.write('    python manage.py mgr_fastforward --round-id=<UUID> --days=0')
        self.stdout.write('\n')