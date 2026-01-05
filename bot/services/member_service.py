from bot.models import *
from django.conf import settings
from decimal import Decimal, InvalidOperation
from django.db.models import Q
from chamas.models import *
from authentication.models import Profile
from django.db import IntegrityError
from django.http import JsonResponse
import requests
from .message_service import MessageService


class MemberService:
    INFOBIP_API_KEY   = settings.INFOBIP_API_KEY
    INFOBIP_SENDER_ID = settings.INFOBIP_SENDER_ID     
    INFOBIP_BASE_URL  = "https://api.infobip.com"


    @staticmethod
    def process_member(message,sender):
        name = message['name']
        email = message['email']
        id_number = message['id_number']
        phone = message['phone']
        role = message['role'].lower()
        chama_name = message['chama']

        terms = chama_name.strip().split()
        q = Q()
        for term in terms:
            q &= Q(name__icontains=term)
        chamas = Chama.objects.filter(q)
        if not chamas.exists():
            return MessageService.send_message(f"No chama found matching '{chama_name}'",sender)
        
        if chamas.count() > 1:
            return MessageService.send_message(f"Multiple chamas match the submitted name,please add the user manually",sender)
        
        chama = chamas.first()

        role = Role.objects.filter(name = str(role)).first()
        if not role:
            return MessageService.send_message("Submitted role is not valid,please submit a valid role",sender)
        
        user = User.objects.filter(username=id_number).first()

        existing_member = ChamaMember.objects.filter(group=chama,member_id=id_number).first()
        if existing_member:
            return MessageService.send_message("Member with that ID already exists in  this chama",sender)

        try:
            if user:
                profile = Profile.objects.get(owner=user)

                new_member = ChamaMember.objects.create(
                    name = user.first_name + ' ' + user.last_name,
                    email = user.email,
                    mobile = profile.phone,
                    group = chama,
                    role = role,
                    user=user,
                    profile=profile.picture,
                    member_id=id_number
                )
            else:
                new_member = ChamaMember.objects.create(
                    name = name,
                    mobile=phone,
                    email=email,
                    group=chama,
                    role=role,
                    member_id=id_number
                )
            new_bot_member = BotMember.objects.create(
                name=name,
                email=email,
                id_number=id_number,
                phone=phone,
                role=role,
                chama_name=chama.name,
                member=new_member,
                chama=chama,
                sender=sender
            )

            return MessageService.send_message(f"New member with id {id_number} succesfully added to chama '{chama.name}'",sender)

        except IntegrityError:
            return MessageService.send_message(f"Member with that ID already exists in chama '{chama_name}'",sender)
        
        except:
            return MessageService.send_message(f'An error occured during member creation,please try again.',sender)
        
   