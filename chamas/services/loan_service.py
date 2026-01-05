from chamas.models import *
from django.http import JsonResponse,HttpResponse
from django.forms.models import model_to_dict
import json
import uuid


class LoanService:
    @staticmethod
    def create_loan_type(request,chama_id):
        data =  json.loads(request.body)

        random_number = uuid.uuid4().int % 1000  
        type_id = f'LT{random_number:03d}' 
        name = data.get('name')
        max_loan_amount = data.get('max')
        grace_period = data.get('grace_period')

        max_due = data.get('max_due')
        late_fine = data.get('late_fine')
        intrest_rate = data.get('intrest_rate')
        description = data.get('description')
        schedule = data.get('schedule')


        try:
            chama = Chama.objects.get(pk=chama_id)
            new_type = LoanType.objects.create(
                
                type_id = type_id,
                name = name,
                max_loan_amount=max_loan_amount,
                grace_period=grace_period,
                late_fine=late_fine,
                intrest_rate=intrest_rate,
                description=description,
                chama= chama,
                max_due = max_due,
                schedule=schedule
            )
            

            data = {
                'status':'success',
                'message':'loan type created succesfully',
                'type':model_to_dict(new_type)
            }
            return JsonResponse(data,status=200)
        except Exception as e:
            data = {
                'status':'failed',
                'message':f'an error occurred:{e}'
            }
            print(2)
            return JsonResponse(data,status=200)
        
    @staticmethod
    def issue_loan(request,chama_id):
        chama = Chama.objects.get(pk=chama_id)

        data = json.loads(request.body)
        type = LoanType.objects.get(pk=data.get('type'))
        member = ChamaMember.objects.get(pk=data.get('member'))
        amount = int(data.get('amount'))
        schedule = type.schedule
        due = data.get('due')

        start_date_str = data.get('start_date')
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()

        status = 'active'

        if type.schedule == 'weekly':
            end_date = start_date + relativedelta(weeks=int(due))
            
        elif type.schedule == 'monthly':
            end_date = start_date + relativedelta(weeks=int(due))
        
        if schedule == 'monthly':
            if type.schedule == 'weekly':
                weeks = int(due) * 4
                if weeks < int(due):
                    data = {
                    'status':'failed',
                    'message':'the loan amount due is longer than the allowed period for this loan'
                    }
                    return JsonResponse(data,status=200)
                
            elif type.max_due < int(due):
                data = {
                    'status':'failed',
                    'message':'the loan amount due is longer than the allowed period for this loan'
                }
                return JsonResponse(data,status=200)


        elif schedule == 'weekly':
            if type.schedule == 'weekly':
                if type.max_due < int(due):
                    data = {
                    'status':'failed',
                    'message':'the loan amount due is longer than the allowed period for this loan'
                    }
                    return JsonResponse(data,status=200)
            elif type.schedule == 'monthly':
                weeks = type.max_due * 4
                if weeks < int(due):
                    data = {
                    'status':'failed',
                    'message':'the loan amount due is longer than the allowed period for this loan'
                    }
                    return JsonResponse(data,status=200)

        if(amount > type.max_loan_amount):
            data = {
                'status':'failed',
                'message':'The loan amount is greater than the maximum allowed for this loan'
            }
            return JsonResponse(data,status=406)

        new_loan = LoanItem.objects.create(
            member=member,
            amount=amount,
            intrest_rate=type.intrest_rate,  # Directly assign interest rate
            start_date=start_date,
            end_date=end_date,
            status=status,
            type=type,
            total_paid=Decimal('0.00'),
            chama=chama,
            due = due,
            schedule = schedule
        )
        new_loan.calc_tot_amount_to_be_paid()

        new_loan = model_to_dict(new_loan)
        new_loan['member'] = member.name
        new_loan['type'] = type.name

        data = {
            'status': 'success',
            'message': 'Loan issued successfully',
            'loan': new_loan
        }

        return JsonResponse(data, status=200)
    
    @staticmethod
    def apply_loan(request,chama_id):
        try:
            data = json.loads(request.body)

            loan_type_id = data.get('loan_type')
            amount = data.get('amount')
            due = data.get('due')
            
            # Validate required fields
            if not loan_type_id:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Loan type is required'
                }, status=400)
            
            if not amount:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Loan amount is required'
                }, status=400)
            
            if not due:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Loan duration is required'
                }, status=400)

            try:
                amount = float(amount)
                due = int(due)
            except (ValueError, TypeError):
                return JsonResponse({
                    'status': 'failed',
                    'message': 'Invalid amount or duration format'
                }, status=400)

            loan = LoanType.objects.get(pk=loan_type_id)
            chama = Chama.objects.get(pk=chama_id)

            # Validate loan amount
            if amount > loan.max_loan_amount:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'The loan amount exceeds the maximum allowed for this loan type'
                }, status=400)

            # Validate loan duration
            if due > loan.max_due:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'The loan duration exceeds the maximum allowed period for this loan type'
                }, status=400)

            # Find the member
            member = None
            try:
                member = ChamaMember.objects.get(user=request.user, group=chama)
            except ChamaMember.DoesNotExist:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'You are not a member of this chama'
                }, status=403)

            # Check if member has pending loan applications
            existing_application = LoanItem.objects.filter(
                member=member, 
                status='application'
            ).exists()
            
            if existing_application:
                return JsonResponse({
                    'status': 'failed',
                    'message': 'You already have a pending loan application'
                }, status=400)

            # Create the loan application
            new_application = LoanItem.objects.create(
                member=member,
                amount=amount,
                type=loan,
                chama=chama,
                due=due,
                schedule=loan.schedule,
                status='application'
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Loan application submitted successfully',
                'application': {
                    'id': new_application.id,
                    'amount': float(new_application.amount),
                    'due': new_application.due,
                    'schedule': new_application.schedule,
                    'status': new_application.status,
                    'applied_on': new_application.applied_on.strftime('%Y-%m-%d')
                }
            }, status=200)

        except LoanType.DoesNotExist:
            return JsonResponse({
                'status': 'failed',
                'message': 'Loan type not found'
            }, status=404)
        except Chama.DoesNotExist:
            return JsonResponse({
                'status': 'failed',
                'message': 'Chama not found'
            }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'failed',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            print(f"Error in apply_loan: {e}")
            return JsonResponse({
                'status': 'failed',
                'message': f'An error occurred while processing your loan application: {str(e)}'
            }, status=500)
        
    @staticmethod
    def accept_loan_request(loan_id):
        loan = LoanItem.objects.get(pk=loan_id)

        loan.status = 'active'
        loan.intrest_rate = loan.type.intrest_rate
        loan.start_date = timezone.now()
        if loan.schedule == 'monthly':
            loan.end_date = timezone.now() + relativedelta(months=loan.due)
        elif loan.schedule == 'weekly':
            loan.end_date = timezone.now() + relativedelta(weeks=loan.due)
        
        loan.total_paid = 0.00
        loan.last_updated = timezone.now()
        loan.calc_tot_amount_to_be_paid()
        loan.save()

        new_cashflow_object = CashflowReport.objects.create(
            object_date=loan.start_date,
            member=loan.member,
            type='loan disbursment',
            amount=loan.amount,
            chama=loan.chama,
            forGroup=False
        )

        data = {
            'status': 'success',
            'message': 'Loan approved successfully',
            'loan': model_to_dict(loan)
        }
        return JsonResponse(data, status=200)
    
    @staticmethod
    def decline_loan(loan_id):
        loan = LoanItem.objects.get(pk=loan_id)
        loan.status = 'declined'
        loan.last_updated = timezone.now()

        loan.save()

        data = {
            'status':'success',
            'message':'loan declined succesfully'

        }
        return JsonResponse(data,status = 200)
    
    @staticmethod
    def update_loan(request,loan):
        data = json.loads(request.body)

        loan_amount = data.get('loan_amount')

        if loan.status == 'active':
            loan.balance -= int(loan_amount)
            loan.total_paid += int(loan_amount)  # Add interest to total paid
            loan.last_updated = timezone.now()
            loan.save()

            if loan.balance <= Decimal('0.00'):
                loan.status = 'cleared'
                loan.save()

            new_cashflow_object = CashflowReport.objects.create(
                object_date=loan.start_date,
                type='loan payment',
                amount=Decimal(loan_amount),
                chama=loan.chama,
                forGroup=False,
                member=loan.member,
            )
        else:
            pass

        data = {
            'status': 'success',
            'message': 'Loan updated successfully',
            'loan': model_to_dict(loan)
        }

        return JsonResponse(data, status=200)




