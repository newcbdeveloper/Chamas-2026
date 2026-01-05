from chamas.models import *
from django.http import JsonResponse,HttpResponse
from django.forms.models import model_to_dict
import json
import uuid

class NotificationService:
    @staticmethod
    def create_notif_type(request,chama_id):
        try:
            chama = Chama.objects.get(pk=chama_id)

            data = json.loads(request.body)
            name = data.get('name')
            description = data.get('description')

            new_type = NotificationType.objects.create(name=name,chama=chama,description=description)

            data = {
                'status':'success',
                'message':'New notification type created succesfully',
                'type':model_to_dict(new_type)
            }
            return JsonResponse(data,status=200)

        except Exception as e:
            data = {
                'status':'failed',
                'message':f'An error occured:{e}'
            }

            return JsonResponse(data,status=200)
        
    @staticmethod
    def create_notif(request,chama_id):
        try:
            chama = Chama.objects.get(pk=chama_id)

            data = json.loads(request.body)
            member = data.get('member')
            message = str(data.get('message'))
            type = NotificationType.objects.get(pk=int(data.get('type')))

            if member == 'group':
                forGroup = True
                new_notif = NotificationItem.objects.create(
                forGroup = forGroup,
                message=message,
                type=type,
                chama=chama
            )
            else:
                forGroup = False

                try:
                    member = ChamaMember.objects.get(pk=int(member),group=chama)

                except Exception as e:
                    print(e)


                new_notif = NotificationItem.objects.create(
                member= member,
                message=message,
                type=type,
                chama=chama,
                forGroup=forGroup
            )
                
            
            data = {
                'status':'success',
                'message':'Notification sent succesfully',
                'notification':model_to_dict(new_notif)
            }

            return JsonResponse(data,status=200)
        except Exception as e:
            data = {
                'status':'failed',
                'message':f'An error occurred:{e}'
            }

            return JsonResponse(data,status=200)
