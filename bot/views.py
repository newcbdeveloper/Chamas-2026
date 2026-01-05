import os, json, re
import requests
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from chamas.decorators import is_user_chama_member
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from chamas.models import *
from .models import *
from decimal import Decimal

from .services.contribution_service import ContributionService
from .services.member_service import MemberService
from .services.fine_service import FineService
from .services.loan_service import LoanService



INFOBIP_API_KEY    = settings.INFOBIP_API_KEY
INFOBIP_SENDER_ID  = settings.INFOBIP_SENDER_ID 
INFOBIP_BASE_URL   = "https://api.infobip.com"



def _sanitize_amount(raw: str) -> str | None:
    """
    Strip out currency words, commas, spaces. 
    Return a pure digit[.digit] string, or None if invalid.
    """
    # drop any letters (e.g. "ksh", "usd"), keep digits, commas, dots
    s = re.sub(r'(?i)[^0-9\.,]', '', raw)
    # remove commas
    s = s.replace(',', '')
    # strip leading/trailing whitespace
    s = s.strip()
    # must be something like "1234" or "1234.56"
    if re.fullmatch(r'\d+(\.\d+)?', s):
        return s
    return None

@csrf_exempt
def receive_message(request):
    if request.method != "POST":
        return JsonResponse({"error": "invalid method"}, status=405)

    data = json.loads(request.body)

    for result in data.get("results", []):
        sender = result.get("sender")
        content = result.get("content", [])
        text = content[0].get("text", "").strip() if content else ""

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return ContributionService.send_message(
                "Empty message received. Please resend with a valid tag.",
                sender
            )

        tag = lines[0].upper()
        if tag not in ("#CONTRIBUTION", "#FINE", "#LOAN","#MEMBER"):
            return ContributionService.send_message(
                "Invalid message tag. First line must be one of #CONTRIBUTION, #LOAN, or #FINE.",
                sender
            )

        
        # common sanitization for the amount line (always index 2)
        if tag != "#MEMBER":
            if len(lines) >= 3:
                raw_amount = lines[2]
                clean_amount = _sanitize_amount(raw_amount)
                if clean_amount is None:
                    return MemberService.send_message(
                        f"Invalid amount format: '{raw_amount}'. Please use e.g. 2000 or Ksh 2,000",
                        sender
                    )
            else:
                clean_amount = None

        if tag == "#CONTRIBUTION":
            if len(lines) < 5:
                missing = ["member ID", "amount", "contribution name", "chama name"][len(lines)-1]
                return ContributionService.send_message(
                    f"Missing required field: {missing}. Please format as:\n"
                    "#CONTRIBUTION\nmember_id\namount\ncontribution_name\nchama_name",
                    sender
                )

            payload = {
                "member_id":         lines[1],
                "amount":            clean_amount,
                "contribution_name": lines[3],
                "chama_name":        lines[4],
            }
            return ContributionService.process_contribution(payload, sender)

        elif tag == "#FINE":
            if len(lines) < 4:
                missing = ["member ID", "amount", "chama name"][len(lines)-1]
                return FineService.send_message(
                    f"Missing required field: {missing}. Please format as:\n"
                    "#FINE\nmember_id\namount\nchama_name",
                    sender
                )

            payload = {
                "member_id":  lines[1],
                "amount":     clean_amount,
                "chama_name": lines[3],
            }
            return FineService.process_fine(payload, sender)

        elif tag == "#LOAN":
            if len(lines) < 4:
                missing = ["member ID", "amount", "chama name"][len(lines)-1]
                return LoanService.send_message(
                    f"Missing required field: {missing}. Please format as:\n"
                    "#LOAN\nmember_id\namount\nchama_name",
                    sender
                )

            payload = {
                "member_id":  lines[1],
                "amount":     clean_amount,
                "chama_name": lines[3],
            }
            return LoanService.process_loan(payload, sender)
        
        elif tag == "#MEMBER":
            if len(lines) < 7:
                missing = ['member name','email','member ID','phone number','role','chama name'][len(lines) - 1]
                return MemberService.send_message(
                    f"Missing required field: {missing}. Please format as:\n"
                    "#MEMBER\nmember name\nmember email\nmember ID number\nphone number\nmember role\nchama name",
                    sender
                )
            payload = {
                "name": lines[1],
                "email": lines[2],
                "id_number": lines[3],
                "phone": lines[4],
                "role": lines[5],
                "chama": lines[6]
            }

            return MemberService.process_member(payload,sender)
            

    return JsonResponse({"status": "no inbound messages"}, status=200)

@login_required(login_url='/user/Login')
@is_user_chama_member
def bot_records(request,chama_id):
    chama = Chama.objects.filter(id=chama_id).first()
    contributions = BotContribution.objects.filter(chama=chama,approved=False).order_by('-id').all()

    loans = BotLoan.objects.filter(chama=chama,approved=False).order_by('-id').all()

    fines = BotFine.objects.filter(chama=chama,approved=False).order_by('-id').all()

    members = BotMember.objects.filter(chama=chama,approved=False).order_by('-id').all()

    return render(request,'bot/records.html',{
        'chama': chama,
        'contributions': contributions,
        'loans': loans,
        'fines': fines,
        'members': members
    })

@login_required(login_url='/user/login')
@is_user_chama_member
@csrf_exempt
def approve_contribution(request, chama_id):
    if request.method != "POST":
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        payload = json.loads(request.body)
        bot_contribution_id = payload.get('record_id')
        amount = payload.get('amount')

        if not bot_contribution_id:
            return JsonResponse({'error': 'Missing record_id'}, status=400)

        bot_record = BotContribution.objects.filter(id=bot_contribution_id).first()
        if not bot_record:
            return JsonResponse({'error': 'Bot contribution not found'}, status=404)

        if bot_record.approved:
            return JsonResponse({'status': 'success', 'message': 'Contribution already approved'})
        
        if bot_record.record:
            try:
                if bot_record.record.amount_paid != Decimal(amount):
                    balance = bot_record.record.contribution.amount - Decimal(amount)
                    bot_record.record.amount_paid = Decimal(amount)
                    bot_record.record.balance = balance
                    bot_record.record.save()
                
            except Exception as e:
                return JsonResponse({'error':f'Transaction record could not be edited;'},status=400)
                

        bot_record.approved = True
        bot_record.save()

        return JsonResponse({'status': 'success', 'message': 'Contribution approved ✅'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        print(e)
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/user/login')
@is_user_chama_member
@csrf_exempt
def approve_fine(request, chama_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        payload     = json.loads(request.body)
        bot_fine_id = payload.get('record_id')
        if not bot_fine_id:
            return JsonResponse({'error': 'Missing record_id'}, status=400)

        record = BotFine.objects.filter(id=bot_fine_id).first()
        if not record:
            return JsonResponse({'error': 'Bot fine record not found'}, status=404)

        if record.approved:
            return JsonResponse({'status': 'success', 'message': 'Already approved'})

        record.approved = True
        record.save()
        return JsonResponse({'status': 'success', 'message': 'Fine approved'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/user/login/')
@is_user_chama_member
@csrf_exempt
def approve_loan(request, chama_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        payload     = json.loads(request.body)
        bot_loan_id = payload.get('record_id')
        if not bot_loan_id:
            return JsonResponse({'error': 'Missing record_id'}, status=400)

        record = BotLoan.objects.filter(id=bot_loan_id).first()
        if not record:
            return JsonResponse({'error': 'Bot loan record not found'}, status=404)

        if record.approved:
            return JsonResponse({'status': 'success', 'message': 'Already approved'})

        record.approved = True
        record.save()

        return JsonResponse({'status': 'success', 'message': 'Loan approved'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/user/login/')
@is_user_chama_member
@csrf_exempt
def approve_member(request,chama_id):
    if request.method != 'POST':
        return JsonResponse({'error':'Invalid Method'}, status = 405)
    
    try:
        payload = json.loads(request.body)
        bot_member_id = payload.get('record_id')

        if not bot_member_id:
            return JsonResponse({'error':'missing record id'},status=404)
        
        record = BotMember.objects.filter(id=bot_member_id).first()
        if not record:
            return JsonResponse({'error': 'Bot member record not found'},status=404)
        
        if record.approved:
            return JsonResponse({'status':'success','message':'member already approved'})
        
        record.approved = True
        record.save()

        return JsonResponse({'status':'success','message':'member already approved'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload'},status=400)
    
    except Exception as e:
        return JsonResponse({'error': str(e)},status=500)
    

@login_required(login_url='/user/login/')
@is_user_chama_member
def flag_contribution(request,chama_id):
    if request.method != 'POST':
        return JsonResponse({'error':'Invalid method'},status=405)
    
    try:
        payload = json.loads(request.body)
        bot_contribution_id = payload.get('record_id')

        record = BotContribution.objects.filter(id=bot_contribution_id).first()

        record.record.delete()

        record.record = None
        record.approved = True

        record.save()

        flag = ContributionFraud.objects.create(record=record)

        return JsonResponse({'status':'success','message':'Transaction marked as fraud'})

    except json.JSONDecodeError:
        return JsonResponse({'error':'Invalid JSON payload'},status=400)
    
    except Exception as e:
        return JsonResponse({'error':str(e)},status=500)
    
@login_required(login_url='/user/login/')
@is_user_chama_member
def flag_fine(request,chama_id):
    if request.method != 'POST':
        return JsonResponse({'error':'Invalid Method'},status=405)
    
    try:
        payload = json.loads(request.body)
        bot_fine_id = payload.get('record_id')

        record = BotFine.objects.filter(id=bot_fine_id).first()
        original_fine = record.edited_fine

        original_fine.fine_balance += record.amount_paid

        if original_fine.status == 'cleared':
            original_fine.status = 'active'

        original_fine.last_updated = timezone.now()

        record.approved = True
        record.save()

        original_fine.save()

        fraud = FineFraud.objects.create(record=record)

        return JsonResponse({'status':'success','message':'Transaction marked as fraud'})


    except json.JSONDecodeError:
        return JsonResponse({'error':'Invalid JSON payload'},status=400)
    
    except Exception as e:
        return JsonResponse({'error':str(e)},status=500)

@login_required(login_url='/user/login/')
@is_user_chama_member
def flag_loan(request,chama_id):
    if request.method != 'POST':
        return JsonResponse({'error':'Invalid method'},status=405)
    
    try:
        payload = json.loads(request.body)
        bot_loan_id = payload.get('record_id')

        record = BotLoan.objects.filter(id=bot_loan_id).first()
        original_loan = record.updated_loan

        original_loan.balance += record.amount_paid

        if original_loan.status == 'cleared':
            original_loan.status = "active"

        original_loan.total_paid -= record.amount_paid
        original_loan.last_updated = timezone.now()

        original_loan.save()

        record.approved = True
        record.save()

        fraud = LoanFraud.objects.create(record=record)

        return JsonResponse({'status':'Success','message':'Transaction has been flagged succesfully'})

    except json.JSONDecodeError:
        return JsonResponse({'error':'Invalid JSON payload'},status=400)
    
    except Exception as e:
        print(e)
        return JsonResponse({'error': str(e)},status=500)

@login_required(login_url='/user/login/')
@is_user_chama_member
def flag_member(request,chama_id):
    if request.method != 'POST':
        return JsonResponse({'error':'Invalid method'},status=405)
    
    try:
        chama = Chama.objects.filter(id=chama_id).first()

        payload = json.loads(request.body)
        bot_member_id = payload.get('member_id')

        record = BotMember.objects.filter(id=bot_member_id).first()

        member = ChamaMember.objects.filter(group=chama,member_id=record.id_number).first()
        if member:
            member.delete()

        fraud = MemberFraud.objects.create(record=record)

        record.approved = True
        record.member_id = None
        record.save()

        return JsonResponse({'status':'success','message':'Member removed from group succesfully'})


    except json.JSONDecodeError:
        return JsonResponse({'error':'Invalid JSON payload'})
    
    except Exception as e:
        print(e)
        return JsonResponse({'error':str(e)},status=500)











