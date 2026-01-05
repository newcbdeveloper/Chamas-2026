import json
from django.shortcuts import render,get_object_or_404, redirect

from chamas.decorators import is_user_chama_member
from .models import *
from django.http import JsonResponse
from django.forms.models import model_to_dict
from django.utils import timezone
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
import calendar
from django.http import FileResponse
import os
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


from .services.download_service import DownloadService
from .services.contribution_service import ContributionService
from .services.fine_service import FineService
from .services.loan_service import LoanService
from .services.finance_service import FinanceService
from .services.expense_service import ExpenseService
from .services.notification_service import NotificationService
from .services.chama_service import ChamaService
from .services.member_service import MemberService
# import logging
# logger = logging.getLogger(__name__)



# Create your views here.
def get_user_role(request):
    try:
        group_id = request.GET.get('group_id')
        if not group_id:
            return JsonResponse({'role': 'member', 'error': 'No group_id provided'})
        
        chama_member = ChamaMember.objects.get(user=request.user, group_id=group_id, active=True)
        role_name = chama_member.role.name if chama_member.role else 'member'
        return JsonResponse({'role': role_name})
    except ChamaMember.DoesNotExist:
        # User is not a member of this chama or has been deactivated
        return JsonResponse({'role': 'member', 'error': 'User not found in this chama'})
    except Exception as e:
        # Any other error - default to member role for security
        return JsonResponse({'role': 'member', 'error': 'Unable to determine role'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def dashboard(request,chama_id):
    chama = Chama.objects.get(pk=chama_id)

    total_contributions = ContributionRecord.objects.filter(member__group=chama).aggregate(total_contributions=Sum('amount_paid'))['total_contributions'] or 0
    total_savings = Saving.objects.filter(chama=chama).aggregate(total_savings=Sum('amount'))['total_savings'] or 0
    total_fines = FineItem.objects.filter(member__group=chama).aggregate(total_fines=Sum('fine_amount'))['total_fines'] or 0
    total_loans_issued = LoanItem.objects.filter(member__group=chama).exclude(status__in=['declined', 'application']).aggregate(total_loans_issued=Sum('amount'))['total_loans_issued'] or 0
    contributions_data, loans_data, fines_data = get_monthly_data(chama_id)
    # Handle pagination for documents - get page number from request
    page_number = request.GET.get('page', 1)
    documents_list = Document.objects.filter(chama=chama).order_by('-upload_date')
    documents_paginator = Paginator(documents_list, 10)  # 10 documents per page
    
    try:
        documents = documents_paginator.page(page_number)
    except PageNotAnInteger:
        documents = documents_paginator.page(1)
    except EmptyPage:
        documents = documents_paginator.page(documents_paginator.num_pages)

    # Convert Decimal values to float
    contributions_data_float = {k: float(v) for k, v in contributions_data.items()}
    loans_data_float = {k: float(v) for k, v in loans_data.items()}
    fines_data_float = {k: float(v) for k, v in fines_data.items()}

    # Serialize dictionaries to JSON format
    contributions_data_json = json.dumps(contributions_data_float)
    loans_data_json = json.dumps(loans_data_float)
    fines_data_json = json.dumps(fines_data_float)

    remaining_count = max(chama.member.count() - 5, 0)

    notifications = Paginator(NotificationItem.objects.filter(forGroup=True,chama=chama).order_by('-date'),3).page(1)
    member = None
    is_admin = False
    for chama_member in chama.member.all():
        if chama_member.user == request.user:
            member = chama_member
            # Check if user is admin
            if member.role and member.role.name.lower() in ['admin', 'administrator', 'chairman', 'secretary']:
                is_admin = True
            break
    my_notifications = Paginator(NotificationItem.objects.filter(forGroup=False,chama=chama,member=member).order_by('-date'),3).page(1)

    return render(request,
                  'chamas/dashboard.html',
                  {'chama': chama, 
                    'total_contributions': total_contributions, 
                    'total_savings': total_savings, 
                    'total_fines': total_fines, 
                    'total_loans': total_loans_issued, 
                    'documents':documents,
                    'contributions_data': contributions_data_json, 
                   'loans_data': loans_data_json, 
                   'fines_data': fines_data_json,
                   'remaining_count': remaining_count,
                   'notifications':notifications,
                   'my_notifications':my_notifications,
                   'is_admin': is_admin
                    })

def get_monthly_data(chama_id):
    # Get the current year
    current_year = timezone.now().year

    # Initialize dictionaries to store monthly data
    contributions_data = {}
    loans_data = {}
    fines_data = {}

    # Loop through each month
    for month in range(1, 13):
        # Get the name of the month
        month_name = calendar.month_abbr[month]

        # Get total contributions for the month
        total_contributions = ContributionRecord.objects.filter(
            date_created__year=current_year, date_created__month=month, member__group__id=chama_id
        ).aggregate(total_contributions=Sum('amount_paid'))['total_contributions'] or 0
        contributions_data[month_name] = total_contributions

        # Get total loans for the month
        total_loans = LoanItem.objects.filter(
            applied_on__year=current_year, applied_on__month=month, member__group__id=chama_id
        ).exclude(status__in=['declined', 'application']).aggregate(total_loans=Sum('amount'))['total_loans'] or 0
        loans_data[month_name] = total_loans

        # Get total fines for the month
        total_fines = FineItem.objects.filter(
            created__year=current_year, created__month=month, member__group__id=chama_id
        ).aggregate(total_fines=Sum('fine_amount'))['total_fines'] or 0
        fines_data[month_name] = total_fines

    return contributions_data, loans_data, fines_data

@login_required(login_url='/user/Login')
def upload_document(request, chama_id):
    if request.method == 'POST' and request.FILES.get('documentFile'):
        document = request.FILES['documentFile']
        name = request.POST.get('documentName', document.name)
        
        try:
            chama = Chama.objects.get(pk=chama_id)
        except Chama.DoesNotExist:
            return JsonResponse({'error': 'Chama not found'}, status=404)

        # Get file extension and size
        file_extension = document.name.split('.')[-1].lower() if '.' in document.name else 'unknown'
        file_size = document.size

        # Validate file type (only allow specific document types)
        allowed_types = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'jpg', 'jpeg', 'png']
        if file_extension not in allowed_types:
            return JsonResponse({'error': f'File type .{file_extension} not allowed. Allowed types: {", ".join(allowed_types)}'}, status=400)

        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if file_size > max_size:
            return JsonResponse({'error': 'File size exceeds 10MB limit'}, status=400)

        # Create document with backwards compatibility
        try:
            new_document = Document.objects.create(
                file=document, 
                name=name, 
                chama=chama,
                file_type=file_extension,
                file_size=file_size
            )
        except Exception as e:
            # Fallback for when new fields don't exist yet
            new_document = Document.objects.create(
                file=document, 
                name=name, 
                chama=chama
            )

        return JsonResponse({
            'message': 'Document uploaded successfully',
            'document_id': new_document.id,
            'document_name': new_document.name,
            'file_type': new_document.get_file_type(),
            'upload_date': new_document.upload_date.strftime('%B %d, %Y')
        }, status=200)
    else:
        return JsonResponse({'error': 'No document provided'}, status=400)

@login_required(login_url='/user/Login')
def download_document(request, document_id, chama_id):
    chama = Chama.objects.get(pk=chama_id)
    document = Document.objects.get(id=document_id, chama=chama)
    file_path = document.file.path
    
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'))
        
        # Ensure downloaded file has correct extension
        base_name = document.name
        extension = os.path.splitext(document.file.name)[1]  # e.g. ".pdf"
        
        # If the custom name doesn't already end with extension, append it
        if not base_name.lower().endswith(extension.lower()):
            base_name = f"{base_name}{extension}"
        
        response['Content-Disposition'] = f'attachment; filename="{base_name}"'
        return response
    else:
        return JsonResponse({'error': 'File not found'}, status=404)

@login_required(login_url='/user/Login')
def delete_document(request, chama_id, document_id):
    """Delete a document - only accessible by admin users"""
    if request.method == 'POST':
        try:
            chama = Chama.objects.get(pk=chama_id)
            document = Document.objects.get(id=document_id, chama=chama)
            
            # Check if user is admin (you may need to adjust this based on your admin check logic)
            member = None
            for chama_member in chama.member.all():
                if chama_member.user == request.user:
                    member = chama_member
                    break
            
            if member and member.role and member.role.name.lower() in ['admin', 'administrator', 'chairman', 'secretary']:
                # Delete the file from filesystem if it exists
                if document.file and os.path.exists(document.file.path):
                    os.remove(document.file.path)
                
                # Delete the document record
                document_name = document.name
                document.delete()
                
                return JsonResponse({
                    'message': f'Document "{document_name}" deleted successfully'
                }, status=200)
            else:
                return JsonResponse({'error': 'Unauthorized. Admin access required.'}, status=403)
                
        except Chama.DoesNotExist:
            return JsonResponse({'error': 'Chama not found'}, status=404)
        except Document.DoesNotExist:
            return JsonResponse({'error': 'Document not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': f'Error deleting document: {str(e)}'}, status=500)
    else:
        return JsonResponse({'error': 'Only POST method allowed'}, status=405) 


@login_required(login_url='/user/Login')
def chamas(request):
    return render(request,'chamas/chamas-home.html',{})


@login_required(login_url='/user/Login')
def your_chamas(request):
    user = request.user

    chama_memberships = ChamaMember.objects.filter(user=user, active=True)
    chama_list = []
    for chama_membership in chama_memberships:
        chama = chama_membership.group
        chama_name = chama.name
        member_count = chama.member.count() 
        id = chama.id
       
        is_admin = chama_membership.role.name == 'admin'  
        chama_list.append({
            'name': chama_name,
            'member_count': member_count,
            'is_admin': is_admin,
            'id':id
        })

    # logger.info("Chamas page rendered succesfully")
    return render(request, 'chamas/your-chamas.html', {'chama_list': chama_list})


def create_chama_type(request):
    if request.method == 'POST':
        return ChamaService.create_chama_type(request)
    
    else:
        data = {
            'status':'failed',
            'message':'wrong http method'
        }
        return JsonResponse(data,status=405)

def new_chama_form(request):
    roles = Role.objects.all()
    types = ChamaType.objects.all()
    return render(request,'chamas/new-chama.html',{'roles':roles,'types':types})


@login_required(login_url='/user/Login')
def create_chama(request):
    if request.method == 'POST':
        return ChamaService.create_chama(request)
        
    else:
        data = {
            'status':'failed',
            'message':'Invalid http method'
        }
        return JsonResponse(data,status=200)


@login_required(login_url='/user/Login')
def add_member_to_chama(request):
    if request.method == 'POST':
        return MemberService.add_member_to_chama(request)
  
    else:
        data = {
            'status':'failed',
            'message':'Invalid http method'
        }
        print(data)
        return JsonResponse(data,status=405)


@login_required(login_url='/user/Login')
def edit_member_in_chama(request):
    """
    View to edit an existing member's details in a chama.
    Only accessible by admin users.
    """
    if request.method == 'POST':
        return MemberService.edit_member_in_chama(request)
    else:
        return JsonResponse({
            'status': 'failed',
            'message': 'Invalid HTTP method'
        }, status=405)


@login_required(login_url='/user/Login')    
def remove_member_from_chama(request, member_id, chama_id):
    chama = get_object_or_404(Chama, pk=chama_id)

    if chama:
        return MemberService.remove_member_from_chama(member_id,chama)
        
    else:
        data = {
            'status':'failed',
            'message':'Invalid user or chama id.'
        }
        return JsonResponse(data,status=400)

@login_required(login_url='/user/Login')
def members(request,chama_id):
    try:
        chama = Chama.objects.get(pk=chama_id)
        
        # Highly optimized query with annotations for better performance
        members = ChamaMember.objects.filter(
            active=True, 
            group=chama
        ).select_related(
            'role', 'user'
        ).annotate(
            total_contributions_amount=models.Sum('member_records__amount_paid'),
            total_loans_count=models.Count('loans', distinct=True),
            total_outstanding_fines=models.Sum('fines__fine_balance'),
            active_loans_count=models.Count('loans', filter=models.Q(loans__status__in=['active', 'approved']), distinct=True)
        ).order_by('name')
        
        MemberService.audit_chama_members(chama.id)

        # Prepare member data with calculated totals
        members_data = []
        for member in members:
            member_data = {
                'id': member.id,
                'name': member.name,
                'email': member.email,
                'mobile': member.mobile,
                'role': member.role,
                'profile': member.profile,
                'member_since': member.member_since,
                'total_contributions': member.total_contributions_amount or 0,
                'total_loans': member.active_loans_count or 0,
                'total_fines': member.total_outstanding_fines or 0,
                'user': member.user
            }
            members_data.append(member_data)

        context = {
            'chama': chama,
            'group': chama,
            'members': members_data,
            'members_count': len(members_data),
            'roles': Role.objects.all(),
            'chama_id': chama_id
        }
        
        return render(request, 'chamas/members.html', context)
        
    except Chama.DoesNotExist:
        return render(request, 'chamas/members.html', {
            'chama': None,
            'error': 'Chama not found',
            'members': [],
            'roles': Role.objects.all(),
            'chama_id': chama_id
        })


@login_required(login_url='/user/Login')
def member_details(request, chama_member_id, group):
    try:
        chama = get_object_or_404(Chama, pk=group)
        member = get_object_or_404(ChamaMember, group=chama, id=chama_member_id)
        
        # Retrieve contributions with related data - optimized query
        contributions = ContributionRecord.objects.filter(
            member=member
        ).select_related('contribution').order_by('-date_created')[:20]
        
        contribution_dicts = []
        for contribution in contributions:
            contrib_data = {
                'id': contribution.id,
                'contribution_name': contribution.contribution.name if contribution.contribution else 'Unknown',
                'date_created': contribution.date_created.strftime('%d/%m/%Y'),
                'amount_expected': float(contribution.amount_expected),
                'amount_paid': float(contribution.amount_paid),
                'balance': float(contribution.balance),
                'status': 'Paid' if contribution.balance == 0 else ('Partial' if contribution.amount_paid > 0 else 'Pending')
            }
            contribution_dicts.append(contrib_data)

        # Retrieve loans with better formatting - optimized query
        loans = LoanItem.objects.filter(member=member).select_related('type').order_by('-start_date')[:20]
        loan_dicts = []
        for loan in loans:
            loan_data = {
                'id': loan.id,
                'amount': float(loan.amount),
                'total_amount_to_be_paid': float(loan.total_amount_to_be_paid or 0),
                'balance': float(loan.balance or 0),
                'total_paid': float(loan.total_paid or 0),
                'status': loan.status.title(),
                'start_date': loan.start_date.strftime('%d/%m/%Y') if loan.start_date else 'N/A',
                'end_date': loan.end_date.strftime('%d/%m/%Y') if loan.end_date else 'N/A',
                'loan_type': loan.type.name if loan.type else 'Unknown',
                'interest_rate': loan.intrest_rate or 0
            }
            loan_dicts.append(loan_data)

        # Retrieve fines with better formatting - optimized query
        fines = FineItem.objects.filter(member=member).select_related('fine_type').order_by('-created')[:20]
        fine_dicts = []
        for fine in fines:
            fine_data = {
                'id': fine.id,
                'fine_type': fine.fine_type.name if fine.fine_type else 'Unknown',
                'fine_amount': float(fine.fine_amount),
                'paid_fine_amount': float(fine.paid_fine_amount),
                'fine_balance': float(fine.fine_balance),
                'status': fine.status.title(),
                'created': fine.created.strftime('%d/%m/%Y'),
                'last_updated': fine.last_updated.strftime('%d/%m/%Y'),
                'for_loan': fine.forLoan,
                'for_contribution': fine.forContribution
            }
            fine_dicts.append(fine_data)

        # Calculate totals
        total_contributions = sum(c['amount_paid'] for c in contribution_dicts)
        total_outstanding_fines = sum(f['fine_balance'] for f in fine_dicts)
        
        # Serialize member data
        member_dict = {
            'id': member.id,
            'name': member.name,
            'email': member.email,
            'mobile': member.mobile,
            'member_id': member.member_id,
            'role': member.role.name if member.role else 'Member',
            'role_id': member.role.id if member.role else None,
            'member_since': member.member_since.strftime('%d/%m/%Y'),
            'active': member.active,
            'profile': member.profile.url if member.profile else None,
            'total_contributions': total_contributions,
            'total_loans': len(loan_dicts),
            'total_fines': total_outstanding_fines
        }



        data = {
            'status': 'success',
            'member': member_dict,
            'contributions': contribution_dicts,
            'loans': loan_dicts,
            'fines': fine_dicts
        }
        return JsonResponse(data, status=200)
    
    except (Chama.DoesNotExist, ChamaMember.DoesNotExist) as e:
        print(f"[ERROR] Member details error: {str(e)}")
        data = {
            'status': 'failed',
            'message': 'Chama or member could not be found.'
        }
        return JsonResponse(data, status=404)
    except Exception as e:
        print(f"[ERROR] Unexpected error in member_details: {str(e)}")
        data = {
            'status': 'failed',
            'message': 'An error occurred while loading member details.'
        }
        return JsonResponse(data, status=500)

def ascertain_member_role(request,chama_id):
    user = request.user
    chama = Chama.objects.get(pk=chama_id)
    member = None
    for member in chama.member.all():
        if member.user == user:
            member = member
            break
    
    data = {
        'status':'success',
        'role':member.role.name
    }
    return JsonResponse(data,status=200)



#Contribution Handlers
@login_required(login_url='/user/Login')
@is_user_chama_member
def create_contribution(request,chama_id):
    if request.method == 'POST':
        return ContributionService.create_contribution(request,chama_id)
        
@login_required(login_url='/user/Login')
@is_user_chama_member
def contributions(request,chama_id):
    chama = Chama.objects.get(pk=chama_id)
    contributions = Contribution.objects.filter(chama=chama.id).all()
    members = ChamaMember.objects.filter(group=chama).all()
    fines = FineType.objects.filter(chama=chama).all()
    
    # Add first round status for each contribution
    contributions_with_status = []
    for contribution in contributions:
        has_first_round = ContributionService.has_any_records(contribution, chama)
        contributions_with_status.append({
            'contribution': contribution,
            'has_any_records': has_first_round
        })
    
    return render(request,'chamas/contributions.html',{
        'contributions':contributions,
        'contributions_with_status': contributions_with_status,
        'members':members,
        'fine_types':fines,
        'chama': chama,
        'chama_id': chama_id
    })


@login_required(login_url='/user/Login')
@is_user_chama_member
def contributions_details(request, chama_id):
    if request.method == 'POST':
        return ContributionService.contribution_details(request,chama_id)
        
    else:
        data = {
            'status': 'error',
            'message': 'Invalid HTTP method. Only POST is allowed.',
        }
        return JsonResponse(data, status=405)




@login_required(login_url='/user/Login')
@is_user_chama_member
def create_contribution_record(request, chama_id):
    if request.method == 'POST':
        return ContributionService.create_contribution_record(request,chama_id)
    else:
        data = {
            'status': 'failed',
            'message': 'Invalid HTTP method'
        }

        return JsonResponse(data, status=405)
    

@login_required(login_url='/user/Login')
def pay_contribution(request, contribution_id):
    return ContributionService.pay_contribution(request,contribution_id)

@login_required(login_url='/user/Login')
@is_user_chama_member
def update_contribution(request, chama_id, contribution_id):
    if request.method == 'POST':
        return ContributionService.update_contribution(request, contribution_id)
    else:
        return JsonResponse({
            'status': 'failed',
            'message': 'Invalid HTTP method'
        }, status=405)

@login_required(login_url='/user/Login')
@is_user_chama_member
def get_contribution_details(request, chama_id, contribution_id):
    if request.method == 'GET':
        return ContributionService.get_contribution_details(request, contribution_id)
    else:
        return JsonResponse({
            'status': 'failed',
            'message': 'Invalid HTTP method'
        }, status=405)
    
#----------LOAN HANDLERS------------------
@login_required(login_url='/user/Login')
@is_user_chama_member
def chama_loans(request, chama_id):
    chama = Chama.objects.get(pk=chama_id)

    # Get all loan types associated with the chama
    loan_types = LoanType.objects.filter(chama=chama).all()

    # Get all loans associated with the chama and loan types
    chama_loans = []
    for loan_type in loan_types:
        for loan in loan_type.loan_records.all():
            chama_loans.append(loan)
            
    # Get All members of the chama
    members = ChamaMember.objects.filter(active=True,group=chama).all()
    member = None
    for member in members:
        if member.user == request.user:
            member = member
            break
    my_loans = LoanItem.objects.filter(chama=chama,member=member,status='active').all()

    # Get all loan applications for the chama
    applications = LoanItem.objects.filter(member__group=chama, status='application').all()

    active_loans = LoanItem.objects.filter(member__group = chama,status='active').all()
    
    # Add context variables for mobile My Loans section
    my_active_loans = LoanItem.objects.filter(chama=chama,member=member,status='active').all()
    my_completed_loans = LoanItem.objects.filter(chama=chama,member=member,status__in=['completed', 'cleared']).all()
    my_defaulted_loans = LoanItem.objects.filter(chama=chama,member=member,status='defaulted').all()
    
    # Add context variables for desktop Active Loans section  
    completed_loans = LoanItem.objects.filter(member__group = chama,status__in=['completed', 'cleared']).all()
    defaulted_loans = LoanItem.objects.filter(member__group = chama,status='defaulted').all()
     

    context = {
        'chama': chama,
        'chama_id': chama_id,
        'loans': chama_loans,
        'loan_types': loan_types,
        'applications': applications,
        'active_loans':active_loans,
        'members': members,
        'my_loans':my_loans,
        'my_active_loans': my_active_loans,
        'my_completed_loans': my_completed_loans, 
        'my_defaulted_loans': my_defaulted_loans,
        'completed_loans': completed_loans,
        'defaulted_loans': defaulted_loans
        
    }

    return render(request, 'chamas/loans.html', context)
            

@login_required(login_url='/user/Login')
@is_user_chama_member  
def create_loan_type(request,chama_id):
    if request.method == 'POST':
        return LoanService.create_loan_type(request,chama_id)
        
        
@login_required(login_url='/user/Login')
@is_user_chama_member
def issue_loan(request, chama_id):
    return LoanService.issue_loan(request,chama_id)
    


@login_required(login_url='/user/Login')
@is_user_chama_member
def apply_loan(request,chama_id):
    if request.method == 'POST':
        return LoanService.apply_loan(request,chama_id)
        
    else:
        data = {
            'status': 'failed',
            'message': 'Invalid HTTP method. Only POST is allowed.'
        }
        return JsonResponse(data, status=405)


@login_required(login_url='/user/Login')
@is_user_chama_member
def accept_loan_request(request, chama_id, loan_id):
    return LoanService.accept_loan_request(loan_id)
    


@login_required(login_url='/user/Login')
@is_user_chama_member
def decline_loan(request,loan_id,chama_id):
    return LoanService.decline_loan(loan_id)
    


@login_required(login_url='/user/Login')
def update_loan(request, loan_id):
    loan = LoanItem.objects.get(pk=loan_id)

    if request.method == 'POST':
        return LoanService.update_loan(request,loan)
        


#------------Fine handlers---------------------------------------------
@login_required(login_url='/user/Login')
@is_user_chama_member
def chama_fines(request,chama_id):

    chama = Chama.objects.get(pk=chama_id)

    loan_types = LoanType.objects.filter(chama=chama).all()
    loans = []
    for loan_type in loan_types:
        for loan in loan_type.loan_records.all():
            if loan.status == 'active':
                loans.append(loan)
            
    members = ChamaMember.objects.filter(group=chama).all()
    fine_types = FineType.objects.filter(chama=chama).all()

    active_fines = []
    contribution_fines = []
    for type in fine_types:
        type_fines = FineItem.objects.filter(fine_type=type,status = 'active').all()
        for fine in type_fines:
            if fine.forLoan:
                active_fines.append(fine)
            if fine.forContribution:
                contribution_fines.append(fine)

    my_contribution_fines = []
    my_loan_fines = []
    member = None

    for member in chama.member.all():
        if member.user == request.user:
            member = member
            break

    for type in fine_types:
        my_fines = FineItem.objects.filter(fine_type=type,member=member,status='active').all()
        for fine in my_fines:
            if fine.forContribution:
                my_contribution_fines.append(fine)
            elif fine.forLoan:
                my_loan_fines.append(fine)

    contributions = Contribution.objects.filter(chama=chama).all()

    
    context = {
        'chama': chama,
        'chama_id': chama_id,
        'loan_types':loan_types,
        'members':members,
        'fine_types':fine_types,
        'fines':active_fines,
        'loans':loans,
        'contributions':contributions,
        'contribution_fines':contribution_fines,
        'my_loan_fines':my_loan_fines,
        'my_contribution_fines':my_contribution_fines
    }

    return render(request,'chamas/fines.html',context)

@login_required(login_url='/user/Login')
@is_user_chama_member
def create_fine_type(request,chama_id):
    if request.method == 'POST':
        return FineService.create_fine_type(request,chama_id)
        
    else:
        data = {
            'status':'failed',
            'message':'invalid http method'
        }
        return JsonResponse(data,status=200)
    

@login_required(login_url='/user/Login')
def fine_contribution(request,contribution_id):
    if request.method == 'POST':
        return FineService.fine_contribution(request,contribution_id)
        
    else:
        data = {
            'status':'failed',
            'message':'Invalid http methods'
        }

        return JsonResponse(data,status=200)


@login_required(login_url='/user/Login')
def impose_fine(request):
    if request.method == 'POST':
        return FineService.impose_fine(request)
        
        

@login_required(login_url='/user/Login')
def update_fine(request):
    if request.method == 'POST':
        return FineService.update_fine(request)
        
    else:
        data = {
            'status':'failed',
            'message':'invalid http method'
        }

        return JsonResponse(data,status=200)


#--------------Expense handlers------------------------------------
@login_required(login_url='/user/Login')
@is_user_chama_member
def expenses(request,chama_id):
        chama = Chama.objects.get(pk=chama_id)

        expenses = Expense.objects.filter(chama=chama).all()
        
        # Check if current user is admin
        try:
                user_membership = ChamaMember.objects.get(user=request.user, group=chama)
                role_name = (user_membership.role.name or '').lower() if user_membership.role else ''
                is_admin = role_name in ['admin', 'administrator', 'chairman', 'secretary']
        except ChamaMember.DoesNotExist:
                is_admin = False
        
        # My expenses for member view
        my_expenses = Expense.objects.filter(chama=chama, created_by=user_membership).all() if 'user_membership' in locals() else Expense.objects.none()

        return render(request,'chamas/expenses.html',{
                'chama': chama,
                'chama_id': chama_id,
                'expenses':expenses,
                'is_admin': is_admin,
                'my_expenses': my_expenses
        })


@login_required(login_url='/user/Login')
@is_user_chama_member
def create_expense(request,chama_id):
    chama = Chama.objects.get(pk=chama_id)

    if request.method == 'POST':
        return ExpenseService.create_expense(request,chama)
        
        

#finance handlers
@login_required(login_url='/user/Login')
@is_user_chama_member
def finances(request,chama_id):
    chama = Chama.objects.get(pk=chama_id)
    # profile = get_object_or_404(Profile, owner=request.user)
    # chama_member = get_object_or_404(ChamaMember, mobile=profile.phone, group=chama)

    chama = Chama.objects.get(pk=chama_id)
    chama_member = None
    for member in chama.member.all():
        if member.user == request.user:
            chama_member = member
            break

    my_savings = Paginator(Saving.objects.filter(forGroup=False,chama=chama, owner=chama_member).order_by('-id').all(),6)
    my_savings = my_savings.page(1)

    individual_savings = Paginator(Saving.objects.filter(forGroup=False,chama=chama).order_by('-id').all(),6)
    individual_savings = individual_savings.page(1)

    group_savings = Paginator(Saving.objects.filter(forGroup=True,chama=chama).order_by('-id').all(),6)
    group_savings = group_savings.page(1)

    group_saving_tot = 0.00
    for saving in group_savings:
        group_saving_tot += int(saving.amount)

    group_investments = Paginator(Investment.objects.filter(chama=chama, forGroup=True).order_by('-id').all(),6)
    group_investments = group_investments.page(1)

    group_investments_tot = 0.00
    for investment in group_investments:
        group_investments_tot += int(investment.amount)

    group_investment_incomes = Paginator(Income.objects.filter(chama=chama,forGroup=True).order_by('-id').all(),6)
    group_investment_incomes = group_investment_incomes.page(1)

    group_investment_incomes_tot = 0.00
    for income in group_investment_incomes:
        group_investment_incomes_tot += int(income.amount)

    individual_investment_income = Paginator(Income.objects.filter(chama=chama,forGroup=False).order_by('-id').all(),6)
    individual_investment_income = individual_investment_income.page(1)
    
    my_investment_income = Paginator(Income.objects.filter(chama=chama,forGroup=False, owner=chama_member).order_by('-id').all(),6)
    my_investment_income = my_investment_income.page(1)

    members = ChamaMember.objects.filter(group=chama,active=True).all()
    saving_types = SavingType.objects.all()

    investments = Investment.objects.filter(chama=chama, forGroup=True).all()




    context = {
        'chama': chama,
        'chama_id': chama_id,
        'saving_types':saving_types,
        'members':members,
        'individual_savings':individual_savings,
        'my_savings':my_savings,
        'group_savings':group_savings,
        'group_savings_tot':group_saving_tot,
        'group_investments':group_investments,
        'group_investments_tot':group_investments_tot,
        'group_investment_incomes':group_investment_incomes,
        'group_investment_incomes_tot':group_investment_incomes_tot,
        'individual_investment_income':individual_investment_income,
        'my_investment_income':my_investment_income,
        'investments':investments

    }

    return render(request,'chamas/finances.html',context)


@login_required(login_url='/user/Login')
@is_user_chama_member
def create_saving(request,chama_id):
    if request.method == 'POST':
        return FinanceService.create_saving(request,chama_id)
        
    else:
        data = {
            'status':'failed',
            'message':'Invalid http method'
        }
        return JsonResponse(data,status=200)
        
@login_required(login_url='/user/Login')
@is_user_chama_member
def create_investment(request,chama_id):
    if request.method == 'POST':
        return FinanceService.create_investment(request,chama_id)
       

        
@login_required(login_url='/user/Login')
@is_user_chama_member
def create_income(request,chama_id):
    if request.method == 'POST':
        return FinanceService.create_income(request,chama_id)
        
    else:
        data = {
            'status':'failed',
            'message':'invalid http method'
        }

        return JsonResponse(data,status=200)

        

#reports handlers
@login_required(login_url='/user/Login')
@is_user_chama_member
def reports(request,chama_id):
    chama = Chama.objects.get(pk=chama_id)
    

    group_investment_incomes = Paginator(Income.objects.filter(chama=chama,forGroup=True).order_by('-id').all(),6).page(1)
    _group_investment_incomes = list(group_investment_incomes.object_list.values())
    for income in _group_investment_incomes:
        income['user_date'] = income['user_date'].strftime("%Y-%m-%d")
        income['date'] = income['date'].strftime("%Y-%m-%d")
        income['amount'] = float(income['amount'])

        try:
            i = Investment.objects.get(pk=int(income['investment_id']))
            income['investment_id'] = i.name
        except:
            pass
    group_investment_incomes = json.dumps(_group_investment_incomes)

    individual_investment_incomes = Paginator(Income.objects.filter(chama=chama,forGroup=False).order_by('-id'),10).page(1)
    _individual_investment_incomes = list(individual_investment_incomes.object_list.values())
    for income in _individual_investment_incomes:
        income['user_date'] = income['user_date'].strftime("%Y-%m-%d")
        income['date'] = income['date'].strftime("%Y-%m-%d")
        income['amount'] = float(income['amount'])

    
        try:
            i = Investment.objects.get(pk=int(income['investment_id']))
            income['investment_id'] = i.name
        except Exception as e:
            pass

        try:
            m = ChamaMember.objects.get(pk=int(income['owner_id']))
            income['owner_id'] = m.name
        except Exception as e:
            
            income['owner_id'] = 'group'
    individual_investment_incomes = json.dumps(_individual_investment_incomes)

    individual_savings = Paginator(Saving.objects.filter(forGroup=False,chama=chama).order_by('-id').all(),10).page(1)
    _individual_savings = list(individual_savings.object_list.values())
    for saving in _individual_savings:
        saving['date'] = saving['date'].strftime("%Y-%m-%d")
        saving['amount'] = float(saving['amount'])
       
         
        try:
            m = ChamaMember.objects.get(pk=int(saving['owner_id']))
            saving['owner_id'] = m.name
        except:
            pass

        try:
            t = SavingType.objects.get(pk=saving['saving_type_id'])
            saving['saving_type_id'] = t.name

        except:
            pass

    individual_savings = json.dumps(_individual_savings)


    group_savings = Paginator(Saving.objects.filter(forGroup=True,chama=chama).order_by('-id').all(),6).page(1)
    _group_savings = list(group_savings.object_list.values())
    for saving in _group_savings:
        saving['date'] = saving['date'].strftime("%Y-%m-%d")
        saving['amount'] = float(saving['amount'])

        try:
            t = SavingType.objects.get(pk=saving['saving_type_id'])
            saving['saving_type_id'] = t.name

        except:
            pass
    group_savings = json.dumps(_group_savings)
    c = ContributionRecord.objects.order_by('-id').all()

    # Get contribution records with proper joins
    contribution_records = ContributionRecord.objects.filter(chama=chama).select_related('contribution', 'member').order_by('-date_created')[:30]
    
    _group_contributions = []
    for record in contribution_records:
        # Simple, direct approach to get the data
        contrib_data = {
            'id': record.id,
            'date_created': record.date_created.strftime("%Y-%m-%d"),
            'last_updated': record.last_updated.strftime("%Y-%m-%d"),
            'amount_paid': float(record.amount_paid),
            'balance': float(record.balance),
            'amount_expected': float(record.amount_expected),
            'member_id': record.member.id if record.member else None,
            'member_name': record.member.name if record.member else 'Unknown Member',
        }
        
        # Handle contribution/scheme information
        if record.contribution:
            contrib_data['contribution'] = record.contribution.id
            contrib_data['scheme_name'] = record.contribution.name
        else:
            contrib_data['contribution'] = None
            contrib_data['scheme_name'] = 'No Scheme Linked'
            
        _group_contributions.append(contrib_data)
    group_contributions = json.dumps(_group_contributions)
    
    chama_expenses = Paginator(Expense.objects.filter(chama=chama).select_related('created_by').order_by('-created_on'),10).page(1)
    _chama_expenses = list(chama_expenses.object_list.values())
    expenses_tot = 0
    for expense in _chama_expenses:
        expense['created_on'] = expense['created_on'].strftime("%Y-%m-%d")
        expense['amount'] = float(expense['amount'])

        try:
            m = ChamaMember.objects.get(pk=int(expense['created_by_id']))
            expense['created_by_name'] = m.name  # Keep the name in a separate field
            # Keep created_by_id as the actual ID for consistency
        except:
            expense['created_by_name'] = 'Unknown'
        expenses_tot += expense['amount']
    chama_expenses = json.dumps(_chama_expenses)
    
    

    
    compute_group_savings = Paginator(Saving.objects.filter(forGroup=True,chama=chama).order_by('-id').all(),10).page(1)
    group_saving_tot = 0.00
    for saving in compute_group_savings:
        group_saving_tot += int(saving.amount)


    compute_group_investment_incomes = Paginator(Income.objects.filter(chama=chama,forGroup=True).order_by('-id').all(),10).page(1)
    group_investment_incomes_tot = 0.00
    for income in compute_group_investment_incomes:
        group_investment_incomes_tot += int(income.amount)

    
    loans = Paginator(LoanItem.objects.filter(chama=chama).order_by('-applied_on').all(),10).page(1)
    _loans = list(loans.object_list.values())
    for loan in _loans:
        if loan['start_date'] is not None:
            loan['start_date'] = loan['start_date'].strftime("%Y-%m-%d")
        if loan['end_date'] is not None:
            loan['end_date'] = loan['end_date'].strftime("%Y-%m-%d")
        if loan['amount'] is not None: 
            loan['amount'] = float(loan['amount'])
        if loan['total_paid'] is not None:
            loan['total_paid'] = float(loan['total_paid'])
        if loan['balance'] is not None:
            loan['balance'] = float(loan['balance'])
        if loan['intrest_rate'] is not None:
            loan['intrest_rate'] = float(loan['intrest_rate'])

        try:
            m = ChamaMember.objects.get(pk=int(loan['member_id']))
            loan['member_id'] = m.name
        except:
            pass

        try:
            t = LoanType.objects.get(pk=int(loan['type_id']))
            loan['type_id'] = t.name
        except:
            pass
    active_loans = json.dumps(_loans, cls=DjangoJSONEncoder)
    
    fine_types = FineType.objects.filter(chama=chama).all()
    _fines = []

    for fine_type in fine_types:
        _fines.extend(fine_type.fine_items.all())

    
    fines = json.dumps([{
    'member': fine.member.name if fine.member else None,
    'type': fine.fine_type.name,
    'loan_amount': float(fine.loan_amount) if fine.loan_amount else None,
    'loan_balance': float(fine.loan_balance) if fine.loan_balance else None,
    'fine_amount': float(fine.fine_amount),
    'paid_fine_amount': float(fine.paid_fine_amount),
    'fine_balance': float(fine.fine_balance),
    'status': fine.status,
    'created': fine.created.strftime('%Y-%m-%d'),
    'last_updated': fine.last_updated.strftime('%Y-%m-%d'),
    'forLoan': fine.forLoan,
    'forContribution': fine.forContribution,
    'contribution_balance': float(fine.contribution_balance) if fine.contribution_balance else None
    }   for fine in _fines if fine.status == 'cleared'], cls=DjangoJSONEncoder)


    unpaid_fines = json.dumps([{
    'member': fine.member.name if fine.member else None,
    'type': fine.fine_type.name,
    'loan_amount': float(fine.loan_amount) if fine.loan_amount else None,
    'loan_balance': float(fine.loan_balance) if fine.loan_balance else None,
    'fine_amount': float(fine.fine_amount),
    'paid_fine_amount': float(fine.paid_fine_amount),
    'fine_balance': float(fine.fine_balance),
    'status': fine.status,
    'created': fine.created.strftime('%Y-%m-%d'),
    'last_updated': fine.last_updated.strftime('%Y-%m-%d'),
    'forLoan': fine.forLoan,
    'forContribution': fine.forContribution,
    'contribution_balance': float(fine.contribution_balance) if fine.contribution_balance else None
    } for fine in _fines if fine.status == 'active'], cls=DjangoJSONEncoder)


    chama_cashflow_report = Paginator(CashflowReport.objects.filter(chama=chama).order_by('-date_created').all(),10).page(1)
    _chama_cashflow_reports = list(chama_cashflow_report.object_list.values())
    for report in _chama_cashflow_reports:
        report['object_date'] = report['object_date'].strftime("%Y-%m-%d")
        report['date_created'] = report['date_created'].strftime("%Y-%m-%d")
        report['amount'] = float(report['amount'])

        
        try:
            m = ChamaMember.objects.get(pk=int(report['member_id']))
            report['member_id'] = m.name
        except:
            pass 
    chama_cashflow_reports = json.dumps(_chama_cashflow_reports)

   

    total_contributions = Decimal('0.00')
    total_loan_disbursment = Decimal('0.00')
    total_loan_repayments = Decimal('0.00')
    total_issued_fines = Decimal('0.00')
    total_fines_collected = Decimal('0.00')
    total_expenses = Decimal('0.00')
    unpaid_fines_total = total_issued_fines - total_fines_collected

    compute_chama_cashflow_reports = Paginator(CashflowReport.objects.filter(chama=chama).order_by('-date_created').all(),5).page(1)
    for report in compute_chama_cashflow_reports:
        if report.type == 'contribution':
            total_contributions += Decimal(report.amount)
            

        elif report.type == 'loan disbursment':
            total_loan_disbursment += Decimal(report.amount)

        elif report.type == 'loan payment':
            total_loan_repayments += Decimal(report.amount)

        elif report.type == 'imposed fine':
            total_issued_fines += Decimal(report.amount)

        elif report.type == 'fine payment':
            total_fines_collected += Decimal(report.amount)

        elif report.type == 'expense':
            total_expenses += Decimal(report.amount)

    net_cashflow = (
    total_contributions 
    + total_loan_disbursment 
    + total_loan_repayments 
    + total_issued_fines 
    + total_fines_collected 
    + total_expenses
    )
    print('total contributions:',total_contributions)

    member = None
    for member in chama.member.all():
        if member.user:
            if member.user == request.user:
                member = member
                break

    my_reports = Paginator(CashflowReport.objects.filter(chama=chama,member=member).order_by('-date_created').all(),10).page(1)
    _my_reports = list(my_reports.object_list.values())
    for report in _my_reports:
        report['object_date'] = report['object_date'].strftime('%Y-%m-%d')
        report['date_created'] = report['date_created'].strftime('%Y-%m-%d')
        report['amount'] = float(report['amount'])

        try:
            m = ChamaMember.objects.get(pk=report['member_id'])
            report['member_id'] = m.name

        except:
            pass
    my_reports = json.dumps(_my_reports)


    my_investment_incomes = Paginator(Income.objects.filter(chama=chama,owner=member).order_by('-date').all(),10).page(1)
    _my_investment_income = list(my_investment_incomes.object_list.values())
    for income in _my_investment_income:
        income['date'] = income['date'].strftime('%Y-%m-%d')
        income['user_date'] = income['user_date'].strftime('%Y-%m-%d')
        income['amount'] = float(income['amount'])

        try:
            o = ChamaMember.objects.get(pk=int(income['owner_id']))
            income['owner_id'] = o.name

        except:
            pass

        try:
            i = Investment.objects.get(pk=int(income['investment_id']))
            income['investment'] = i.name
        except:
            pass
    my_investment_incomes = json.dumps(_my_investment_income)
    
    # Add investment data for the new Investments tab
    group_investments = Paginator(Investment.objects.filter(chama=chama,forGroup=True).order_by('-date').all(),10).page(1)
    _group_investments = list(group_investments.object_list.values())
    for investment in _group_investments:
        investment['date'] = investment['date'].strftime('%Y-%m-%d')
        investment['user_date'] = investment['user_date'].strftime('%Y-%m-%d')
        investment['amount'] = float(investment['amount'])
    group_investments = json.dumps(_group_investments)
    

    

    my_total_contributions = Decimal('0.00')
    my_total_loan_disbursment = Decimal('0.00')
    my_total_loan_repayments = Decimal('0.00')
    my_total_issued_fines = Decimal('0.00')
    my_total_fines_collected = Decimal('0.00')
    my_total_expenses = Decimal('0.00')

    compute_my_reports = Paginator(CashflowReport.objects.filter(chama=chama,member=member).order_by('-date_created').all(),10).page(1)
    for report in compute_my_reports:
        if report.type == 'contribution':
            my_total_contributions += Decimal(report.amount)

        elif report.type == 'loan disbursment':
            my_total_loan_disbursment += Decimal(report.amount)

        elif report.type == 'loan payment':
            my_total_loan_repayments += Decimal(report.amount)

        elif report.type == 'imposed fine':
            my_total_issued_fines += Decimal(report.amount)

        elif report.type == 'fine payment':
            my_total_fines_collected += Decimal(report.amount)

        elif report.type == 'expense':
            my_total_expenses += Decimal(report.amount)

    my_net_cashflow = (
    my_total_contributions 
    + my_total_loan_disbursment 
    + my_total_loan_repayments 
    + my_total_issued_fines 
    + my_total_fines_collected 
    + my_total_expenses
    )

    my_contributions_data = ContributionRecord.objects.filter(chama=chama,member=member).select_related('contribution', 'member').order_by('-date_created')[:30]
    _my_contributions = []
    for record in my_contributions_data:
        contrib_data = {
            'id': record.id,
            'date_created': record.date_created.strftime("%Y-%m-%d"),
            'last_updated': record.last_updated.strftime("%Y-%m-%d"),
            'amount_paid': float(record.amount_paid),
            'balance': float(record.balance),
            'amount_expected': float(record.amount_expected),
            'member_id': record.member.id if record.member else None,
            'member_name': record.member.name if record.member else 'Unknown Member',
        }
        
        if record.contribution:
            contrib_data['contribution'] = record.contribution.id
            contrib_data['scheme_name'] = record.contribution.name
        else:
            contrib_data['contribution'] = None
            contrib_data['scheme_name'] = 'No Scheme Linked'
            
        _my_contributions.append(contrib_data)
    
    my_contributions = json.dumps(_my_contributions)
    
    tot = 0.00
    for record in my_contributions_data:
        tot += float(record.amount_paid)

    contribution_schemes = Contribution.objects.filter(chama=chama).all()

    

    

    context = {
        'chama': chama,
        'chama_id': chama_id,
        'loans':loans,
        'unpaid_loans':active_loans,
        'group_investment_incomes':group_investment_incomes,
        'group_investment_incomes_tot':group_investment_incomes_tot,
        'member_investment_income':individual_investment_incomes,
        'individual_saving_report':individual_savings,
        'chama_cashflow_reports':chama_cashflow_reports,
        'net_cashflow':net_cashflow,
        'group_saving_report':group_savings,
        'group_savings_tot':group_saving_tot,
        'collected_fines':fines,
        'unpaid_fines':unpaid_fines,
        'members':ChamaMember.objects.filter(group=chama,active=True).all(),
        'total_contributions':total_contributions,
        'total_loan_disbursment':total_loan_disbursment,
        'total_loan_repayments':total_loan_repayments,
        'total_issued_fines':total_issued_fines,
        'total_fines_collected':total_fines_collected,
        'total_expenses':total_expenses,
        'my_reports':my_reports,
        'my_total_loan_disbursment':my_total_loan_disbursment,
        'my_total_loan_repayments':my_total_loan_repayments,
        'my_total_issued_fines':my_total_issued_fines,
        'my_total_fines_collected':my_total_fines_collected,
        'my_total_expenses':my_total_expenses,
        'my_net_cashflow':my_net_cashflow,
        'group_contributions':group_contributions,
        'unpaid_fines_total':unpaid_fines_total,
        'my_investment_incomes':my_investment_incomes,
        'my_contributions':my_contributions,
        'my_tot_contributions':tot,
        'chama_expense_reports':chama_expenses,
        'expenses_tot':expenses_tot,
        'schemes':contribution_schemes,
        'contributions':contribution_schemes,
        'group_investments':group_investments
        
    }



    return render(request,'chamas/reports.html',context)

#------------------------Report download handlers-----------------
@login_required(login_url='/user/Login')
@is_user_chama_member
def download_loan_report(request, chama_id):
    try:
        return DownloadService.download_loan_report(request, chama_id)
    except Exception as e:
        # Log the error and return a JSON error response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error downloading loan report for chama {chama_id}: {str(e)}")
        
        # Return an error response that the frontend can handle
        from django.http import JsonResponse
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to generate loan report: {str(e)}'
        }, status=500)



@login_required(login_url='/user/Login')
@is_user_chama_member
def download_loan_repayment_schedule(request, chama_id):
    member_id = request.GET.get('member_id')
    return DownloadService.download_loan_repayment_schedule(chama_id, member_id)
    

    
@login_required(login_url='/user/Login')
@is_user_chama_member
def download_group_investment_income(request, chama_id):
    return DownloadService.download_group_investment_income(request, chama_id)
   

    
@login_required(login_url='/user/Login')
@is_user_chama_member
def download_member_investment_income(request, chama_id):
    return DownloadService.download_member_investment_income(request,chama_id)

@login_required(login_url='/user/Login')
@is_user_chama_member
def download_my_investment_income(request, chama_id):
    return DownloadService.download_my_investment_income(request, chama_id)

@login_required(login_url='/user/Login')
@is_user_chama_member
def download_group_investments(request, chama_id):
    return DownloadService.download_group_investments(request, chama_id)
    


@login_required(login_url='/user/Login')
@is_user_chama_member
def download_individual_saving_report(request, chama_id):
    return DownloadService.download_individual_saving_report(request,chama_id)
    


@login_required(login_url='/user/Login')
@is_user_chama_member
def download_group_saving_report(request, chama_id):
    return DownloadService.download_group_saving_report(request,chama_id)

@login_required(login_url='/user/Login')
@is_user_chama_member
def download_my_saving_report(request, chama_id):
    return DownloadService.download_my_saving_report(request, chama_id)
    


@login_required(login_url='/user/Login')
@is_user_chama_member
def download_group_contributions_report(request, chama_id,contribution_id):
    try:
        return DownloadService.download_group_contributions_report(chama_id,contribution_id)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error downloading group contributions report for chama {chama_id}, contribution {contribution_id}: {str(e)}")
        
        from django.http import JsonResponse
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to generate group contributions report: {str(e)}'
        }, status=500)
    

@login_required(login_url='/user/Login')
@is_user_chama_member
def download_member_contribution_report(request, chama_id, member_id=None, scheme_id=None):
    # Get parameters from URL path or query string
    if member_id is None:
        member_id = request.GET.get('member_id')
    if scheme_id is None:
        scheme_id = request.GET.get('scheme_id')
        
    try:
        return DownloadService.download_member_contribution_report(chama_id, member_id, scheme_id)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error downloading member contribution report for chama {chama_id}: {str(e)}")
        
        from django.http import JsonResponse
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to generate contribution report: {str(e)}'
        }, status=500)
    



@login_required(login_url='/user/Login')
@is_user_chama_member
def download_collected_fine_report(request, chama_id):
    return DownloadService.download_collected_fine_report(request, chama_id)
    


@login_required(login_url='/user/Login')
@is_user_chama_member
def download_uncollected_fines_report(request, chama_id):
    return DownloadService.download_uncollected_fines_report(request, chama_id)
    

@login_required(login_url='/user/Login')
@is_user_chama_member
def download_cashflow_report(request, chama_id):

    return DownloadService.download_cashflow_report(chama_id)


@login_required(login_url='/user/Login')
@is_user_chama_member
def download_member_cashflow_report(request, chama_id, member_id):
    return DownloadService.download_member_cashflow_report(chama_id,member_id)
    


@login_required(login_url='/user/Login')
@is_user_chama_member
def download_my_cashflow_report(request, chama_id):
    return DownloadService.download_my_cashflow_report(request,chama_id)
    

@login_required(login_url='/user/Login')
@is_user_chama_member
def download_expense_report(request, chama_id):
    return DownloadService.download_expense_report(request, chama_id)
    



#notification handlers
@login_required(login_url='/user/Login')
@is_user_chama_member
def notifications(request,chama_id):
    chama = Chama.objects.get(pk=chama_id)

    if chama:   
        notification_types = NotificationType.objects.filter(chama=chama).all()

        chama_notifications = NotificationItem.objects.filter(chama=chama,forGroup=True,member=None).all()

        member = None
        for m in chama.member.all():
            if request.user == m.user:
                member = m
                break
      
        # Determine admin status
        try:
            role_name = (member.role.name or '').lower() if member and member.role else ''
            is_admin = role_name in ['admin', 'administrator', 'chairman', 'secretary']
        except Exception:
            is_admin = False

        my_notifications = NotificationItem.objects.filter(member=member,chama=chama,forGroup=False).all()

        context = {
            'chama': chama,
            'chama_id': chama_id,
            'types': notification_types,
            'chama_notifs': chama_notifications,
            'my_notifs': my_notifications,
            'members': ChamaMember.objects.filter(active=True,group=chama),
            'is_admin': is_admin
        }
    return render(request,'chamas/notifications.html',context)


@login_required(login_url='/user/Login')
@is_user_chama_member
def create_notif_type(request,chama_id):
    if request.method == 'POST':
        return NotificationService.create_notif_type(request,chama_id)
        
    else:
        data = {
            'status':'failed',
            'message':'Invalid http method'
        }

        return JsonResponse(data,status=405)


@login_required(login_url='/user/Login')
@is_user_chama_member
def create_notif(request,chama_id):
    if request.method == 'POST':
        return NotificationService.create_notif(request,chama_id)
        
    else:
        data = {
            'status':'failed',
            'message':'invalid http method'
        }

        return JsonResponse(data,status=405)


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_member_cashflow_data(request, chama_id):
    """
    AJAX endpoint to get member cashflow data for filtering
    """
    if request.method == 'GET':
        member_id = request.GET.get('member_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Build query filters
            filters = {'chama': chama}
            if member_id:
                member = ChamaMember.objects.get(pk=member_id)
                filters['member'] = member
                
            if start_date:
                filters['object_date__gte'] = start_date
            if end_date:
                filters['object_date__lte'] = end_date
                
            # Get cashflow reports
            reports = CashflowReport.objects.filter(**filters).order_by('-date_created')
            
            # Format data for JSON response
            data = []
            for report in reports:
                data.append({
                    'id': report.id,
                    'member_name': report.member.name if report.member else 'Group',
                    'member_id': report.member.id if report.member else None,
                    'type': report.type,
                    'amount': float(report.amount),
                    'object_date': report.object_date.strftime('%Y-%m-%d'),
                    'date_created': report.date_created.strftime('%Y-%m-%d')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_loan_repayment_schedule(request, chama_id):
    """
    AJAX endpoint to get loan repayment schedule data for filtering
    """
    if request.method == 'GET':
        member_id = request.GET.get('member_id')
        member_name = request.GET.get('member_name')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Build query filters
            filters = {'chama': chama}
            
            # Filter by member if specified (by ID or name)
            if member_id:
                member = ChamaMember.objects.get(pk=member_id)
                filters['member'] = member
            elif member_name:
                member = ChamaMember.objects.get(name=member_name, group=chama)
                filters['member'] = member
                
            # Only get approved/active loans for repayment schedule
            filters['status__in'] = ['approved', 'active', 'partially_paid']
                
            if start_date:
                filters['start_date__gte'] = start_date
            if end_date:
                filters['end_date__lte'] = end_date
                
            # Get loan items
            loans = LoanItem.objects.filter(**filters).order_by('-applied_on')
            
            # Format data for JSON response
            data = []
            for loan in loans:
                # Calculate repayment details
                monthly_payment = 0
                if loan.schedule == 'monthly' and loan.total_amount_to_be_paid:
                    # Calculate months between start and end date
                    if loan.start_date and loan.end_date:
                        months = ((loan.end_date.year - loan.start_date.year) * 12 + 
                                loan.end_date.month - loan.start_date.month)
                        if months > 0:
                            monthly_payment = float(loan.total_amount_to_be_paid) / months
                
                data.append({
                    'id': loan.id,
                    'member_name': loan.member.name if loan.member else 'N/A',
                    'member_id': loan.member.id if loan.member else None,
                    'loan_type': loan.type.name if loan.type else 'N/A',
                    'amount': float(loan.amount) if loan.amount else 0,
                    'total_amount_to_be_paid': float(loan.total_amount_to_be_paid) if loan.total_amount_to_be_paid else 0,
                    'balance': float(loan.balance) if loan.balance else 0,
                    'total_paid': float(loan.total_paid) if loan.total_paid else 0,
                    'interest_rate': loan.intrest_rate if loan.intrest_rate else 0,
                    'start_date': loan.start_date.strftime('%Y-%m-%d') if loan.start_date else 'N/A',
                    'end_date': loan.end_date.strftime('%Y-%m-%d') if loan.end_date else 'N/A',
                    'next_due': loan.next_due.strftime('%Y-%m-%d') if loan.next_due else 'N/A',
                    'schedule': loan.schedule,
                    'status': loan.status,
                    'monthly_payment': round(monthly_payment, 2),
                    'applied_on': loan.applied_on.strftime('%Y-%m-%d') if loan.applied_on else 'N/A'
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_member_contributions_data(request, chama_id):
    """
    AJAX endpoint to get member contributions data for filtering
    """
    if request.method == 'GET':
        member_id = request.GET.get('member_id')
        scheme_id = request.GET.get('scheme_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Build query filters
            filters = {'chama': chama}
            
            # Filter by member if specified
            if member_id:
                member = ChamaMember.objects.get(pk=member_id)
                filters['member'] = member
                
            # Filter by contribution scheme if specified
            if scheme_id:
                try:
                    contribution = Contribution.objects.get(pk=scheme_id)
                    filters['contribution'] = contribution
                except Contribution.DoesNotExist:
                    # Log the error but continue without scheme filter
                    pass
                
            if start_date:
                filters['date_created__gte'] = start_date
            if end_date:
                filters['date_created__lte'] = end_date
                
            # Get contribution records
            contributions = ContributionRecord.objects.filter(**filters).order_by('-date_created')
            
            # Format data for JSON response
            data = []
            for contrib in contributions:
                data.append({
                    'id': contrib.id,
                    'member_name': contrib.member.name if contrib.member else 'N/A',
                    'member_id': contrib.member.id if contrib.member else None,
                    'scheme_name': contrib.contribution.name if contrib.contribution else 'N/A',
                    'scheme_id': contrib.contribution.id if contrib.contribution else None,
                    'amount_expected': float(contrib.amount_expected) if contrib.amount_expected else 0,
                    'amount_paid': float(contrib.amount_paid) if contrib.amount_paid else 0,
                    'balance': float(contrib.balance) if contrib.balance else 0,
                    'date_created': contrib.date_created.strftime('%Y-%m-%d') if contrib.date_created else 'N/A',
                    'last_updated': contrib.last_updated.strftime('%Y-%m-%d') if contrib.last_updated else 'N/A',
                    'payment_status': 'Fully Paid' if contrib.balance <= 0 else 'Partial' if contrib.amount_paid > 0 else 'Unpaid'
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_group_investment_income_data(request, chama_id):
    """AJAX endpoint to get filtered group investment income data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get filter parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for group investment incomes
            queryset = Income.objects.filter(chama=chama, forGroup=True).select_related('investment')
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(user_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(user_date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-date')
            
            # Build response data
            data = []
            for income in queryset:
                data.append({
                    'id': income.id,
                    'name': income.name,
                    'investment_name': income.investment.name if income.investment else 'N/A',
                    'investment_id': income.investment.id if income.investment else None,
                    'amount': float(income.amount),
                    'date': income.user_date.strftime('%Y-%m-%d'),
                    'created_date': income.date.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})




@login_required(login_url='/user/Login')
@is_user_chama_member
def get_member_investment_income_data(request, chama_id):
    """AJAX endpoint to get filtered member investment income data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get filter parameters
            member_id = request.GET.get('member_id')
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for member investment incomes
            queryset = Income.objects.filter(chama=chama, forGroup=False).select_related('investment', 'owner')
            
            # Apply member filter
            if member_id:
                queryset = queryset.filter(owner_id=member_id)
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(user_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(user_date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-date')
            
            # Build response data
            data = []
            for income in queryset:
                data.append({
                    'id': income.id,
                    'name': income.name,
                    'investment_name': income.investment.name if income.investment else 'N/A',
                    'investment_id': income.investment.id if income.investment else None,
                    'member_name': income.owner.name if income.owner else 'N/A',
                    'member_id': income.owner.id if income.owner else None,
                    'amount': float(income.amount),
                    'date': income.user_date.strftime('%Y-%m-%d'),
                    'created_date': income.date.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_my_investment_income_data(request, chama_id):
    """AJAX endpoint to get filtered personal investment income data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get current user's member record
            try:
                member = ChamaMember.objects.get(user=request.user, group=chama)
            except ChamaMember.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'You are not a member of this chama'
                })
            
            # Get filter parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for personal investment incomes
            queryset = Income.objects.filter(chama=chama, forGroup=False, owner=member).select_related('investment')
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(user_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(user_date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-date')
            
            # Build response data
            data = []
            for income in queryset:
                data.append({
                    'id': income.id,
                    'name': income.name,
                    'investment_name': income.investment.name if income.investment else 'N/A',
                    'investment_id': income.investment.id if income.investment else None,
                    'amount': float(income.amount),
                    'date': income.user_date.strftime('%Y-%m-%d'),
                    'created_date': income.date.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required(login_url='/user/Login')
@is_user_chama_member
def get_individual_saving_data(request, chama_id):
    """AJAX endpoint to get filtered individual saving data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get filter parameters
            member_id = request.GET.get('member_id')
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for individual savings
            queryset = Saving.objects.filter(chama=chama, forGroup=False).select_related('owner', 'saving_type')
            
            # Apply member filter
            if member_id:
                queryset = queryset.filter(owner_id=member_id)
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(date__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(date__date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-date')
            
            # Build response data
            data = []
            for saving in queryset:
                data.append({
                    'id': saving.id,
                    'member_name': saving.owner.name if saving.owner else 'N/A',
                    'member_id': saving.owner.id if saving.owner else None,
                    'saving_type_name': saving.saving_type.name if saving.saving_type else 'N/A',
                    'saving_type_id': saving.saving_type.id if saving.saving_type else None,
                    'amount': float(saving.amount),
                    'date': saving.date.strftime('%Y-%m-%d'),
                    'created_date': saving.date.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_group_saving_data(request, chama_id):
    """AJAX endpoint to get filtered group saving data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get filter parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for group savings
            queryset = Saving.objects.filter(chama=chama, forGroup=True).select_related('saving_type')
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(date__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(date__date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-date')
            
            # Build response data
            data = []
            for saving in queryset:
                data.append({
                    'id': saving.id,
                    'saving_type_name': saving.saving_type.name if saving.saving_type else 'N/A',
                    'saving_type_id': saving.saving_type.id if saving.saving_type else None,
                    'amount': float(saving.amount),
                    'date': saving.date.strftime('%Y-%m-%d'),
                    'created_date': saving.date.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_my_saving_data(request, chama_id):
    """AJAX endpoint to get filtered personal saving data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get current user's member record
            try:
                member = ChamaMember.objects.get(user=request.user, group=chama)
            except ChamaMember.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'You are not a member of this chama'
                })
            
            # Get filter parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for personal savings
            queryset = Saving.objects.filter(chama=chama, forGroup=False, owner=member).select_related('saving_type')
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(date__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(date__date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-date')
            
            # Build response data
            data = []
            for saving in queryset:
                data.append({
                    'id': saving.id,
                    'saving_type_name': saving.saving_type.name if saving.saving_type else 'N/A',
                    'saving_type_id': saving.saving_type.id if saving.saving_type else None,
                    'amount': float(saving.amount),
                    'date': saving.date.strftime('%Y-%m-%d'),
                    'created_date': saving.date.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_collected_fines_data(request, chama_id):
    """AJAX endpoint to get filtered collected fines data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get filter parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for collected fines (status = 'cleared')
            queryset = FineItem.objects.filter(fine_type__chama=chama, status='cleared').select_related('member', 'fine_type')
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(created__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(created__date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-created')
            
            # Build response data
            data = []
            for fine in queryset:
                data.append({
                    'id': fine.id,
                    'member_name': fine.member.name if fine.member else 'N/A',
                    'member_id': fine.member.id if fine.member else None,
                    'fine_type_name': fine.fine_type.name if fine.fine_type else 'N/A',
                    'fine_type_id': fine.fine_type.id if fine.fine_type else None,
                    'fine_amount': float(fine.fine_amount),
                    'paid_fine_amount': float(fine.paid_fine_amount),
                    'fine_balance': float(fine.fine_balance),
                    'status': fine.status,
                    'created': fine.created.strftime('%Y-%m-%d'),
                    'created_datetime': fine.created.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_updated': fine.last_updated.strftime('%Y-%m-%d')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_unpaid_fines_data(request, chama_id):
    """AJAX endpoint to get filtered unpaid fines data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get filter parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for unpaid fines (status = 'active')
            queryset = FineItem.objects.filter(fine_type__chama=chama, status='active').select_related('member', 'fine_type')
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(created__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(created__date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-created')
            
            # Build response data
            data = []
            for fine in queryset:
                data.append({
                    'id': fine.id,
                    'member_name': fine.member.name if fine.member else 'N/A',
                    'member_id': fine.member.id if fine.member else None,
                    'fine_type_name': fine.fine_type.name if fine.fine_type else 'N/A',
                    'fine_type_id': fine.fine_type.id if fine.fine_type else None,
                    'fine_amount': float(fine.fine_amount),
                    'paid_fine_amount': float(fine.paid_fine_amount),
                    'fine_balance': float(fine.fine_balance),
                    'status': fine.status,
                    'created': fine.created.strftime('%Y-%m-%d'),
                    'created_datetime': fine.created.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_updated': fine.last_updated.strftime('%Y-%m-%d')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required(login_url='/user/Login')
@is_user_chama_member
def get_expenses_data(request, chama_id):
    """AJAX endpoint to get filtered expenses data"""
    if request.method == 'GET':
        try:
            chama = Chama.objects.get(pk=chama_id)
            
            # Get filter parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset for expenses
            queryset = Expense.objects.filter(chama=chama).select_related('created_by')
            
            # Apply date filters
            if start_date:
                queryset = queryset.filter(created_on__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_on__date__lte=end_date)
            
            # Order by most recent
            queryset = queryset.order_by('-created_on')
            
            # Build response data
            data = []
            for expense in queryset:
                data.append({
                    'id': expense.id,
                    'name': expense.name,
                    'description': expense.description,
                    'amount': float(expense.amount),
                    'created_by_name': expense.created_by.name if expense.created_by else 'N/A',
                    'created_by_id': expense.created_by.id if expense.created_by else None,
                    'created_on': expense.created_on.strftime('%Y-%m-%d'),
                    'created_on_datetime': expense.created_on.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            return JsonResponse({
                'status': 'success',
                'data': data,
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required(login_url='/user/Login')
def my_chamas_view(request):
    """
    View to display all chamas that the current user is a member of.
    This includes both linked and unlinked memberships.
    """
    try:
        from authentication.models import Profile
        user_profile = Profile.objects.get(owner=request.user)
        
        # Get all chama memberships for this user
        user_memberships = ChamaMember.objects.filter(
            user=request.user,
            active=True
        ).select_related('group', 'role').order_by('-member_since')
        
        # Format the data for template
        chamas_data = []
        for membership in user_memberships:
            chamas_data.append({
                'chama': membership.group,
                'role': membership.role.name if membership.role else 'Member',
                'member_since': membership.member_since,
                'is_admin': membership.role and membership.role.name == 'admin'
            })
        
        context = {
            'user_profile': user_profile,
            'user_chamas': chamas_data,
            'chamas_count': len(chamas_data)
        }
        
        return render(request, 'chamas/my-chamas.html', context)
        
    except Profile.DoesNotExist:
        from django.contrib import messages
        messages.error(request, 'User profile not found. Please complete your profile setup.')
        return redirect('Setting')
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f'Error loading your chamas: {str(e)}')
        return redirect('Dashboard')

