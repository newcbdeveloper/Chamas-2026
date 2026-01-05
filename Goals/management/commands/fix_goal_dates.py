from django.core.management.base import BaseCommand
from django.utils import timezone
from Goals.models import Goal, GroupGoal

class Command(BaseCommand):
    help = 'Fix past dates in existing goals for testing'

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Fix Personal Goals
        past_goals = Goal.objects.filter(start_date__lt=today)
        for goal in past_goals:
            self.stdout.write(f"Fixing goal: {goal.name}")
            goal.start_date = today
            if goal.end_date and goal.end_date < today:
                # Set end_date to 30 days from today
                goal.end_date = today + timezone.timedelta(days=30)
            # Save without validation
            super(Goal, goal).save()
        
        # Fix Group Goals
        past_group_goals = GroupGoal.objects.filter(start_date__lt=today)
        for goal in past_group_goals:
            self.stdout.write(f"Fixing group goal: {goal.goal_name}")
            goal.start_date = today
            if goal.end_date and goal.end_date < today:
                goal.end_date = today + timezone.timedelta(days=30)
            # Save without validation
            super(GroupGoal, goal).save()
        
        self.stdout.write(self.style.SUCCESS('Successfully fixed all goals'))
