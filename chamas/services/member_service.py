from chamas.models import *
from django.http import JsonResponse,HttpResponse
from django.forms.models import model_to_dict
import json
from authentication.models import Profile
from django.db import IntegrityError
from django.db import models


class MemberService:
    @staticmethod
    def add_member_to_chama(request):
        try:
            if not request.body:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Empty request body'
                }, status=400)
            
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Invalid JSON data: {str(e)}'
                }, status=400)
        
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            mobile = data.get('mobile', '').strip()
            role_id = data.get('role')
            group_id = data.get('group') or data.get('chama_id')
            id_number = data.get('id_number') or data.get('member_id')
            
            # Validate required fields
            if not all([name, email, mobile, role_id, group_id]):
                missing_fields = []
                if not name: missing_fields.append('name')
                if not email: missing_fields.append('email')
                if not mobile: missing_fields.append('mobile')
                if not role_id: missing_fields.append('role')
                if not group_id: missing_fields.append('chama_id')
                
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=400)
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Please enter a valid email address'
                }, status=400)
            
            try:
                group = Chama.objects.get(pk=int(group_id))
            except Chama.DoesNotExist:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Chama with ID {group_id} not found'
                }, status=400)
            except ValueError as e:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Invalid chama ID: {group_id}'
                }, status=400)
            
            try:
                role = Role.objects.get(pk=int(role_id))
            except Role.DoesNotExist:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Role with ID {role_id} not found'
                }, status=400)
            except ValueError as e:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Invalid role ID: {role_id}'
                }, status=400)
            
            # Format phone number if needed
            if mobile and not mobile.startswith('+'):
                if mobile.startswith('0'):
                    mobile = '+254' + mobile[1:]
                elif mobile.startswith('254'):
                    mobile = '+' + mobile
                else:
                    mobile = '+254' + mobile
            
            # Check for existing member with same email or mobile in this chama
            existing_member = ChamaMember.objects.filter(
                group=group,
                active=True
            ).filter(
                models.Q(email__iexact=email) | models.Q(mobile=mobile)
            ).first()
            
            if existing_member:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'A member with this email or phone number already exists in this chama'
                }, status=400)
            
            # Check if user exists by ID number or email
            user = None
            if id_number:
                user = User.objects.filter(username=id_number).first()
            if not user:
                user = User.objects.filter(email__iexact=email).first()
            
            # Create member
            if user:
                try:
                    profile = Profile.objects.get(owner=user)
                    profile_picture = profile.picture
                    actual_mobile = profile.phone or mobile
                    actual_name = f"{user.first_name} {user.last_name}".strip() if user.first_name else name
                except Profile.DoesNotExist:
                    profile_picture = None
                    actual_mobile = mobile
                    actual_name = f"{user.first_name} {user.last_name}".strip() if user.first_name else name
                
                new_member = ChamaMember.objects.create(
                    name=actual_name,
                    email=user.email,
                    mobile=actual_mobile,
                    group=group,
                    role=role,
                    user=user,
                    profile=profile_picture,
                    member_id=id_number or user.username
                )
            else:
                # Create member without user association but store ID for future linking
                new_member = ChamaMember.objects.create(
                    name=name,
                    mobile=mobile,
                    email=email,
                    group=group,
                    role=role,
                    member_id=id_number,  # Store ID number for future user linking
                    user=None  # Will be linked when user registers
                )
            

            
            # Return member data for frontend
            member_data = {
                'id': new_member.id,
                'name': new_member.name,
                'email': new_member.email,
                'mobile': new_member.mobile,
                'role': new_member.role.name,
                'member_since': new_member.member_since.strftime('%b %Y'),
                'profile': new_member.profile.url if new_member.profile else None
            }
            
            return JsonResponse({
                'status': 'success',
                'message': f'{new_member.name} added successfully to the chama',
                'member': member_data
            }, status=200)
            
        except IntegrityError as e:
            return JsonResponse({
                'status': 'failed',
                'message': 'A member with this information already exists in the chama'
            }, status=400)
        except (Chama.DoesNotExist, Role.DoesNotExist) as e:
            return JsonResponse({
                'status': 'failed',
                'message': 'Invalid chama or role specified'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'failed',
                'message': 'An error occurred while adding the member'
            }, status=500)
    
    @staticmethod
    def audit_chama_members(chama_id):
        chama = Chama.objects.get(pk=chama_id)
        for member in chama.member.all():
            user = User.objects.filter(username=member.member_id).first()
            if user:
                member.user = user
                member.save()
                
    @staticmethod
    def remove_member_from_chama(member_id, chama):
        try:
            chama_member = ChamaMember.objects.get(group=chama, id=member_id, active=True)
            
            # Check if member is the chama creator
            if chama_member.user == chama.created_by:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Cannot remove {chama_member.name} - they are the chama creator!'
                }, status=400)
            
            try:
                # Soft delete - set member as inactive
                chama_member.active = False
                chama_member.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'{chama_member.name} has been successfully removed from {chama.name}',
                    'member_id': member_id,
                    'member_name': chama_member.name
                }, status=200)
                
            except Exception as e:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Failed to remove member due to a database error'
                }, status=500)
                
        except ChamaMember.DoesNotExist:
            return JsonResponse({
                'status': 'failed',
                'message': 'Member not found in this chama or already removed'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'failed',
                'message': 'An unexpected error occurred while removing the member'
            }, status=500)
    
    @staticmethod
    def edit_member_in_chama(request):
        """
        Edit an existing member's details in a chama.
        Only admin users can edit member details.
        """
        try:
            if not request.body:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Empty request body'
                }, status=400)
            
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Invalid JSON data: {str(e)}'
                }, status=400)
        
            # Extract data
            member_id = data.get('member_id')
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            mobile = data.get('mobile', '').strip()
            role_id = data.get('role')
            chama_id = data.get('chama_id')
            id_number = data.get('id_number', '').strip()
            
            # Validate required fields
            if not all([member_id, name, email, mobile, role_id, chama_id]):
                missing_fields = []
                if not member_id: missing_fields.append('member_id')
                if not name: missing_fields.append('name')
                if not email: missing_fields.append('email')
                if not mobile: missing_fields.append('mobile')
                if not role_id: missing_fields.append('role')
                if not chama_id: missing_fields.append('chama_id')
                
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=400)
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Please enter a valid email address'
                }, status=400)
            
            # Get the chama and member
            try:
                chama = Chama.objects.get(pk=int(chama_id))
                member = ChamaMember.objects.get(pk=int(member_id), group=chama, active=True)
            except (Chama.DoesNotExist, ChamaMember.DoesNotExist):
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Member or chama not found'
                }, status=404)
            except ValueError:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Invalid member or chama ID'
                }, status=400)
            
            # Check if requesting user is admin
            try:
                requesting_user_membership = ChamaMember.objects.get(
                    user=request.user, 
                    group=chama, 
                    active=True
                )
                if not requesting_user_membership.role or requesting_user_membership.role.name != 'admin':
                    return JsonResponse({
                        'status': 'failed',
                        'message': 'Only admin users can edit member details'
                    }, status=403)
            except ChamaMember.DoesNotExist:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'You are not a member of this chama'
                }, status=403)
            
            # Get role
            try:
                role = Role.objects.get(pk=int(role_id))
            except Role.DoesNotExist:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Role with ID {role_id} not found'
                }, status=400)
            except ValueError:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'Invalid role ID: {role_id}'
                }, status=400)
            
            # Format phone number if needed
            if mobile and not mobile.startswith('+'):
                if mobile.startswith('0'):
                    mobile = '+254' + mobile[1:]
                elif mobile.startswith('254'):
                    mobile = '+' + mobile
                else:
                    mobile = '+254' + mobile
            
            # Check for existing member with same email or mobile in this chama (excluding current member)
            existing_member = ChamaMember.objects.filter(
                group=chama,
                active=True
            ).filter(
                models.Q(email__iexact=email) | models.Q(mobile=mobile)
            ).exclude(pk=member.pk).first()
            
            if existing_member:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Another member with this email or phone number already exists in this chama'
                }, status=400)
            
            # Check if we need to update user association
            old_member_id = member.member_id
            user_to_link = None
            
            if id_number and id_number != old_member_id:
                # Check if user exists with this ID
                user_to_link = User.objects.filter(username=id_number).first()
                
                if user_to_link:
                    # Check if this user is already associated with another member in this chama
                    existing_user_member = ChamaMember.objects.filter(
                        group=chama,
                        user=user_to_link,
                        active=True
                    ).exclude(pk=member.pk).first()
                    
                    if existing_user_member:
                        return JsonResponse({
                            'status': 'failed',
                            'message': f'User with ID {id_number} is already a member of this chama'
                        }, status=400)
            
            # Update member details
            member.name = name
            member.email = email
            member.mobile = mobile
            member.role = role
            member.member_id = id_number if id_number else member.member_id
            
            # Update user association if needed
            if user_to_link:
                member.user = user_to_link
                # Update with user's actual information if available
                try:
                    from authentication.models import Profile
                    profile = Profile.objects.get(owner=user_to_link)
                    if profile.picture:
                        member.profile = profile.picture
                    actual_name = f"{user_to_link.first_name} {user_to_link.last_name}".strip()
                    if actual_name:
                        member.name = actual_name
                    member.email = user_to_link.email
                    if profile.phone:
                        member.mobile = profile.phone
                except Profile.DoesNotExist:
                    pass
            elif not id_number:
                # If ID number is cleared, unlink user
                member.user = None
            
            member.save()
            
            # Return updated member data
            member_data = {
                'id': member.id,
                'name': member.name,
                'email': member.email,
                'mobile': member.mobile,
                'role': member.role.name,
                'member_id': member.member_id,
                'user_linked': member.user is not None
            }
            
            return JsonResponse({
                'status': 'success',
                'message': f'{member.name} has been updated successfully',
                'member': member_data
            }, status=200)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'status': 'failed',
                'message': 'An error occurred while updating the member'
            }, status=500)

