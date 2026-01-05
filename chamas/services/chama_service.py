from chamas.models import *
from django.http import JsonResponse,HttpResponse
from django.forms.models import model_to_dict
import json
from django.db import transaction
from authentication.models import Profile
from datetime import datetime
from django.utils.dateparse import parse_date


class ChamaService:
    @staticmethod
    def create_chama_type(request):
        name = request.POST['name']

        try:
            new_type = ChamaType.objects.create(name=name)
            data = {
                'status':'success',
                'message':'chama type created succesfully',
                'type':model_to_dict(new_type)

            }
            return JsonResponse(data,status=200)
        except Exception as e:
            data = {
                'status':'failed',
                'message':f'an error occured:{e}'

            }
            return JsonResponse(data,status=400)
        
    @staticmethod
    def create_chama(request):
        try:
            with transaction.atomic():
                data = json.loads(request.body)
                name = data.get('name')
                start_date_str = data.get('date')
                type = data.get('type')
                members = data.get('members', [])
                created_by = request.user

                # Validation
                if not name or not start_date_str or not type:
                    return JsonResponse({
                        'status': 'failed',
                        'message': 'Please fill in all required fields (name, start date, and type)'
                    }, status=400)

                # Parse and validate the date
                try:
                    if isinstance(start_date_str, str):
                        start_date = parse_date(start_date_str)
                        if start_date is None:
                            return JsonResponse({
                                'status': 'failed',
                                'message': 'Invalid date format. Please use YYYY-MM-DD format.'
                            }, status=400)
                    else:
                        start_date = start_date_str
                except Exception as e:
                    return JsonResponse({
                        'status': 'failed',
                        'message': 'Invalid date provided'
                    }, status=400)

                try:
                    _type = ChamaType.objects.get(pk=int(type))
                except ChamaType.DoesNotExist:
                    return JsonResponse({
                        'status': 'failed',
                        'message': 'Invalid chama type selected'
                    }, status=400)

                # Create the chama
                new_chama = Chama.objects.create(
                    name=name,
                    type=_type,
                    created_by=created_by,
                    start_date=start_date
                )

                # Add creator as admin member
                creator_name = f'{created_by.first_name} {created_by.last_name}'.strip()
                if not creator_name:
                    creator_name = created_by.username
                    
                admin_role = Role.objects.filter(name='admin').first()
                if not admin_role:
                    # Create admin role if it doesn't exist
                    admin_role = Role.objects.create(name='admin')

                # Get creator's profile details
                try:
                    profile = Profile.objects.get(owner=created_by)
                    creator_mobile = profile.phone if profile.phone else ''
                except Profile.DoesNotExist:
                    creator_mobile = ''

                creator_member = ChamaMember.objects.create(
                    name=creator_name,
                    email=created_by.email,
                    mobile=creator_mobile,
                    group=new_chama,
                    role=admin_role,
                    user=created_by
                )

                # Add additional members
                added_members = []
                member_creation_errors = []

                for member_data in members:
                    try:
                        # Get role
                        member_role = Role.objects.get(pk=member_data['role_id'])
                        
                        # Check if user exists by ID or email
                        user = None
                        if member_data.get('id_number'):
                            user = User.objects.filter(username=member_data['id_number']).first()
                        if not user:
                            user = User.objects.filter(email__iexact=member_data['email']).first()

                        # Format phone number
                        mobile = member_data['mobile']
                        if mobile and not mobile.startswith('+'):
                            if mobile.startswith('0'):
                                mobile = '+254' + mobile[1:]
                            elif mobile.startswith('254'):
                                mobile = '+' + mobile
                            else:
                                mobile = '+254' + mobile

                        # Create member
                        if user:
                            try:
                                user_profile = Profile.objects.get(owner=user)
                                profile_picture = user_profile.picture
                                actual_mobile = user_profile.phone or mobile
                                actual_name = f"{user.first_name} {user.last_name}".strip() if user.first_name else member_data['name']
                            except Profile.DoesNotExist:
                                profile_picture = None
                                actual_mobile = mobile
                                actual_name = f"{user.first_name} {user.last_name}".strip() if user.first_name else member_data['name']
                            
                            new_member = ChamaMember.objects.create(
                                name=actual_name,
                                email=user.email,
                                mobile=actual_mobile,
                                group=new_chama,
                                role=member_role,
                                user=user,
                                profile=profile_picture,
                                member_id=member_data.get('id_number') or user.username
                            )
                        else:
                            # Create member without user association but store ID for future linking
                            new_member = ChamaMember.objects.create(
                                name=member_data['name'],
                                mobile=mobile,
                                email=member_data['email'],
                                group=new_chama,
                                role=member_role,
                                member_id=member_data.get('id_number'),  # Store ID for future linking
                                user=None  # Will be linked when user registers
                            )
                        
                        added_members.append({
                            'name': new_member.name,
                            'email': new_member.email,
                            'role': new_member.role.name
                        })
                        
                    except Role.DoesNotExist:
                        member_creation_errors.append(f"Invalid role for member {member_data['name']}")
                    except Exception as e:
                        member_creation_errors.append(f"Error adding member {member_data['name']}: {str(e)}")

                # Prepare response with proper date formatting
                start_date_formatted = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
                
                response_data = {
                    'status': 'success',
                    'message': f'Chama "{name}" created successfully!',
                    'chama': {
                        'id': new_chama.id,
                        'name': new_chama.name,
                        'type': new_chama.type.name,
                        'created_by': creator_name,
                        'start_date': start_date_formatted,
                        'total_members': new_chama.member.filter(active=True).count()
                    },
                    'added_members': added_members
                }

                if member_creation_errors:
                    response_data['warnings'] = member_creation_errors
                    response_data['message'] += f' Note: {len(member_creation_errors)} member(s) could not be added.'

                return JsonResponse(response_data, status=200)
        
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'failed',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            print(f"Error creating chama: {e}")
            return JsonResponse({
                'status': 'failed',
                'message': f'An error occurred while creating the chama: {str(e)}'
            }, status=500)
       


