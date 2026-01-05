from chamas.models import *
from django.http import JsonResponse,HttpResponse
from django.forms.models import model_to_dict
import json

class FineService:
    @staticmethod
    def create_fine_type(request,chama_id):
        data = json.loads(request.body)

        name = data.get('name')
        amount = int(data.get('amount'))
        description = str(data.get('description'))
        chama = Chama.objects.get(pk = chama_id)

        try:
            new_fine_type = FineType.objects.create(
                name = name,
                amount=amount,
                description=description,
                chama=chama
            )

            data = {
                'status':'success',
                'message':'fine type created succesfully',
                'fine_type':model_to_dict(new_fine_type)
            }
            return JsonResponse(data,status=200)

        except Exception as e:

            data = {
                'status':'failed',
                'message':f'an error occcurred:{e}'
            }

            return JsonResponse(data,status=200)
        
    @staticmethod
    def fine_contribution(request,contribution_id):
        try:
            data = json.loads(request.body)
            contribution_item = ContributionRecord.objects.get(pk=contribution_id)
            contribution = contribution_item.contribution
            member = contribution_item.member
            fine_type_id = data.get('fine_type_id') or data.get('fine')  # Support both formats
            
            if not fine_type_id:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Fine type ID is required'
                }, status=400)
                
            fine = FineType.objects.get(pk=fine_type_id)
            contribution_balance = contribution_item.balance

            # Check if contribution has a balance to fine
            if contribution_balance <= 0:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Cannot apply fine to a fully paid contribution'
                }, status=400)
            new_fine_object = FineItem.objects.create(
                fine_type = fine,
                member = member,
                fine_amount = fine.amount,
                paid_fine_amount = 0.00,
                fine_balance = fine.amount,
                contribution = contribution,
                contribution_record = contribution_item,
                forLoan = False,
                forContribution = True,
                contribution_balance = Decimal(contribution_balance)
            )
            new_cashflow_object = CashflowReport.objects.create(
                        object_date = new_fine_object.created,
                        member = new_fine_object.member,
                        type = 'imposed fine',
                        amount = new_fine_object.fine_amount,
                        chama = new_fine_object.fine_type.chama,
                        forGroup = False
                    )
            fine = model_to_dict(new_fine_object)
            fine['member'] = member.name
            fine['fine_type'] = new_fine_object.fine_type.name

            data = {
                'status':'success',
                'message':f'Fine imposed on {member.name} successfully',

            }

            return JsonResponse(data,status=200)
    
        except ContributionRecord.DoesNotExist:
            return JsonResponse({
                'status': 'failed',
                'message': 'Contribution record not found'
            }, status=404)
        except FineType.DoesNotExist:
            return JsonResponse({
                'status': 'failed',
                'message': 'Fine type not found'
            }, status=404)
        except Exception as e:
            print(f"Error in fine_contribution: {e}")
            return JsonResponse({
                'status': 'failed',
                'message': 'An error occurred while applying the fine'
            }, status=500)
        
    @staticmethod
    def impose_fine(request):
        data = json.loads(request.body)

        loan = LoanItem.objects.get(pk=int(data.get('loan_id')))

        member = loan.member
        fine_type = FineType.objects.get(pk = int(data.get('fine_type')))


        loan_amount = loan.amount
        loan_balance = loan.balance
        fine_amount = fine_type.amount
        paid_fine_amount = 0.00
        fine_balance = fine_type.amount

        try:
            new_fine_object = FineItem.objects.create(
                member = member,
                fine_type = fine_type,
                loan_amount=loan_amount,
                loan_balance=loan_balance,
                fine_amount=fine_amount,
                paid_fine_amount = paid_fine_amount,
                fine_balance=fine_balance,
                loan = loan,
                forLoan = True
            )

            new_cashflow_object = CashflowReport.objects.create(
                        object_date = new_fine_object.created,
                        member = new_fine_object.member,
                        type = 'imposed fine',
                        amount = new_fine_object.fine_amount,
                        chama = new_fine_object.fine_type.chama,
                        forGroup = False
                    )

            data = {
                'status' :'success',
                'message':f'Fine imposed on {member.name} succesfully.'
            }

            return JsonResponse(data,status=200)


        except Exception as e:
            data = {
                'status':'failed',
                'message':f'An error occurred:{e}'
            }
            return JsonResponse(data,status=200)
        
    @staticmethod
    def update_fine(request):
        data = json.loads(request.body)
        fine = FineItem.objects.get(pk = int(data.get('fine_id')))
        loan = fine.loan

        if fine.forLoan:
            fine.loan_balance = loan.balance
            fine.paid_fine_amount += int(data.get('fine-amount'))
            fine.fine_balance -= int(data.get('fine-amount'))
            fine.last_updated = timezone.now()
            if fine.fine_balance <= 0.00:
                fine.status = 'cleared'
            
            fine.save()
        
        elif fine.forContribution:
            fine.paid_fine_amount += int(data.get('fine-amount'))
            fine.fine_balance -= int(data.get('fine-amount'))
            fine.last_updated = timezone.now()
            if fine.fine_balance <= 0.00:
                fine.status = 'cleared'

            fine.save()

        new_cashflow_object = CashflowReport.objects.create(
            object_date = fine.created,
            type = 'fine payment',
            amount = Decimal(data.get('fine-amount')),
            chama = fine.fine_type.chama,
            forGroup = False,
            member = fine.member
        )

        

        data = {
            'status':'success',
            'message':'fine updated succesfully',
            'fine':model_to_dict(fine)
        }

        return JsonResponse(data,status=200)

