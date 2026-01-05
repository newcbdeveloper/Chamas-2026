from chamas.models import *
from django.http import JsonResponse,HttpResponse
from django.forms.models import model_to_dict
import json
import uuid



class FinanceService:
    @staticmethod
    def create_saving(request,chama_id):
        try:
            chama = Chama.objects.get(pk=chama_id)
            data = json.loads(request.body)
            owner = data.get('owner')
            amount = data.get('amount')
            saving_type = data.get('saving-type')
            saving_type = SavingType.objects.get(pk=int(saving_type))


            if owner == 'group':
                forGroup = True
                new_saving = Saving.objects.create(
                    chama = chama,
                    forGroup = forGroup,
                    amount=amount,
                    saving_type = saving_type

                )

            else:
                forGroup = False
                owner = ChamaMember.objects.get(pk=int(owner))
                new_saving = Saving.objects.create(
                    owner = owner,
                    chama = chama,
                    forGroup = forGroup,
                    amount = amount,
                    saving_type = saving_type
                )
            
            data = {
                'status':'success',
                'message':'Saving created succesfully',
                'saving':model_to_dict(new_saving)
            }
            return JsonResponse(data,status=200)

        except Exception as e:
            data = {
                'status':'failed',
                'message':f'an error occured:{e}'
            }
            return JsonResponse(data,status=200)
        
    @staticmethod
    def create_investment(request,chama_id):
        data = json.loads(request.body)
        name = data.get('name')
        amount = data.get('amount')
        date = data.get('date')

        chama = Chama.objects.get(pk=chama_id)

        try:
            # Always create group investments - individual ownership is no longer supported
            new_investment = Investment.objects.create(
                name = name,
                amount = amount,
                chama = chama,
                user_date = date,
                forGroup = True,
                owner = None
            )
            
            data = {
                'status':'success',
                'message':'New investment created successfully',
                'investment':model_to_dict(new_investment)
            }

            return JsonResponse(data,status=200)

        except Exception as e:
            data = {
                'status':'failed',
                'message':f'an error occurred: {e}'
            }

            return JsonResponse(data,status=200)
        
    @staticmethod
    def create_income(request,chama_id):
        data = json.loads(request.body)
        name = data.get('name')
        owner = data.get('owner')
        chama = Chama.objects.get(pk=chama_id)
        amount = data.get('amount')
        date = data.get('date')
        investment = data.get('investment-scheme')

        if investment == 'others':
            try:
                investment = Investment.object.get(name='others',chama=chama)

            except Exception as e:
                new_investment = Investment.objects.create(name='others',amount=Decimal('0.00'),chama=chama)
                investment = new_investment
        else:
            investment = Investment.objects.get(pk=int(investment))
        
        if owner == 'group':
            forGroup = True
            new_income = Income.objects.create(
                name = name,
                chama = chama,
                forGroup = forGroup,
                amount = amount,
                user_date = date,
                investment = investment
            )

        else:
            forGroup = False
            owner = ChamaMember.objects.get(pk=int(owner))
            new_income = Income.objects.create(
                name = name,
                owner = owner,
                chama = chama,
                forGroup = forGroup,
                amount = amount,
                investment = investment
            )

        data = {
            'status':'success',
            'message':'new income created succesfully',
            'income':model_to_dict(new_income)
        }

        return JsonResponse(data,status=200)


