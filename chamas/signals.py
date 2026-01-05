from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import ChamaMember
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def link_user_to_existing_memberships(sender, instance, created, **kwargs):
    """
    Signal to link newly registered users to existing chama memberships
    based on their username (ID number) or email.
    """
    if created:  # Only for newly created users
        try:
            # Find existing ChamaMember records that match this user by ID or email
            # First try by username (ID number)
            matching_members = ChamaMember.objects.filter(
                member_id=instance.username,
                user__isnull=True,  # Not already linked to a user
                active=True
            )
            
            # If no match by ID, try by email
            if not matching_members.exists():
                matching_members = ChamaMember.objects.filter(
                    email__iexact=instance.email,
                    user__isnull=True,  # Not already linked to a user
                    active=True
                )
            
            # Link all matching memberships to this user
            linked_count = 0
            for member in matching_members:
                # Update the member record with user information
                member.user = instance
                member.name = f"{instance.first_name} {instance.last_name}".strip() or member.name
                member.email = instance.email
                
                # Get profile picture if available
                try:
                    from authentication.models import Profile
                    profile = Profile.objects.get(owner=instance)
                    if profile.picture:
                        member.profile = profile.picture
                    if profile.phone:
                        member.mobile = profile.phone
                except Profile.DoesNotExist:
                    pass
                
                member.save()
                linked_count += 1
                
                logger.info(f"Linked user {instance.username} to chama membership {member.id} in {member.group.name}")
            
            if linked_count > 0:
                logger.info(f"Successfully linked user {instance.username} to {linked_count} chama membership(s)")
                
        except Exception as e:
            logger.error(f"Error linking user {instance.username} to chama memberships: {str(e)}")