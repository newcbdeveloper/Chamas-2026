from django.urls import path
from . import views

app_name = 'chamas'
urlpatterns = [
    path('chamas/',views.chamas,name='chamas'),
    path('new-chama-form/',views.new_chama_form,name='new-chama-form'),
    path('new-chama/',views.create_chama,name='new-chama'),
    path('your-chamas/',views.your_chamas,name='your-chamas'),
    path('create-new-chama-type/',views.create_chama_type,name='new-chama-type'),
    
    path('add-member/',views.add_member_to_chama,name='add-member'),
    path('edit-member/',views.edit_member_in_chama,name='edit-member'),
    path('members/<int:chama_id>/',views.members,name='members'),
    path('remove-member-from-chama/<int:member_id>/<int:chama_id>/',views.remove_member_from_chama,name='remove-member-from-chama'),
    path('member-detail/<int:chama_member_id>/<int:group>/',views.member_details,name='member-details'),
    path('ascertain-member-role/<int:chama_id>/',views.ascertain_member_role,name="ascertain-member-role"),

    path('chama-dashboard/<int:chama_id>/',views.dashboard,name='chama-dashboard'),
    path('upload-document/<int:chama_id>/',views.upload_document,name='upload-document'),
    path('download-document/<int:chama_id>/<int:document_id>/',views.download_document,name='download-document'),
    path('delete-document/<int:chama_id>/<int:document_id>/',views.delete_document,name='delete-document'),

    path('contributions/<int:chama_id>/',views.contributions,name='contributions'),
    path('create-contribution-record/<int:chama_id>/',views.create_contribution_record,name='create-contribution-record'),
    path('create-contribution/<int:chama_id>/',views.create_contribution,name='create-contribution'),
    path('retrieve-contribution/<int:chama_id>/',views.contributions_details,name='contribution-details'),
    path('update-contribution/<int:chama_id>/<int:contribution_id>/',views.update_contribution,name='update-contribution'),
    path('get-contribution/<int:chama_id>/<int:contribution_id>/',views.get_contribution_details,name='get-contribution-details'),
    path('pay-contribution/<int:contribution_id>/',views.pay_contribution,name='pay-contribution'),

    path('chama-loans/<int:chama_id>/',views.chama_loans,name='chama-loans'),
    path('create-loan-type/<int:chama_id>/',views.create_loan_type,name='create-loan-type'),
    path('issue-loan/<int:chama_id>/',views.issue_loan,name='issue-loan'),
    path('apply-loan/<int:chama_id>/',views.apply_loan,name='apply-loans'),
    path('approve-loan/<int:chama_id>/<int:loan_id>/',views.accept_loan_request,name='accept-loan-request'),
    path('decline-loan/<int:chama_id>/<int:loan_id>/',views.decline_loan,name='decline_loan'),
    path('update-loan/<int:loan_id>/',views.update_loan,name='update-loan'),


    path('chama-fines/<int:chama_id>/',views.chama_fines,name='chama-fines'),
    path('create-fine-type/<int:chama_id>/',views.create_fine_type,name='create-fine-type'),
    path('impose-fine/',views.impose_fine,name='impose-fine'),
    path('update-fine/',views.update_fine,name='update-fine'),
    path('fine-contribution/<int:contribution_id>/',views.fine_contribution,name='fine-contribution'),


    path('chama-expenses/<int:chama_id>/',views.expenses,name='chama-expenses'),
    path('create-expense/<int:chama_id>/',views.create_expense,name='create-expense'),

    path('chama-finances/<int:chama_id>/',views.finances,name='finances'),
    path('create-saving/<int:chama_id>/',views.create_saving,name='create-saving'),
    path('create-investment/<int:chama_id>/',views.create_investment,name='create-investment'),
    path('create-income/<int:chama_id>/',views.create_income,name='create-income'),

    path('chama-reports/<int:chama_id>/',views.reports,name='reports'),
    path('download-full-loan-report/<int:chama_id>/',views.download_loan_report,name='download-loan-report'),
    path('download-loan-repayment-schedule/<int:chama_id>/',views.download_loan_repayment_schedule,name='download-loan-repayment-schedule'),
    path('download-group-investment-income/<int:chama_id>/',views.download_group_investment_income,name='download-group-investment-income'),
    path('download-member-investment-income/<int:chama_id>/',views.download_member_investment_income,name='download-member-investment-income'),
    path('download-my-investment-income/<int:chama_id>/',views.download_my_investment_income,name='download-my-investment-income'),
    path('download-group-investments/<int:chama_id>/',views.download_group_investments,name='download-group-investments'),
    path('download-individual-saving-report/<int:chama_id>/',views.download_individual_saving_report,name='download-individual-saving-report'),
    path('download-group-saving-report/<int:chama_id>/',views.download_group_saving_report,name='download-group-saving-report'),
    path('download-my-saving-report/<int:chama_id>/',views.download_my_saving_report,name='download-my-saving-report'),
    path('download-group-contributions-report/<int:chama_id>/<int:contribution_id>/',views.download_group_contributions_report,name='download-group-contributions-report'),
    path('download-member-contributions-report/<int:chama_id>/<int:member_id>/<int:scheme_id>/',views.download_member_contribution_report,name='download-member-contribution-report'),
    path('download-member-contributions-report/<int:chama_id>/',views.download_member_contribution_report,name='download-member-contribution-report-query'),
    path('download-collected-fines-report/<int:chama_id>/',views.download_collected_fine_report,name='download-collected-fines-report'),
    path('download-uncollected-fines-report/<int:chama_id>/',views.download_uncollected_fines_report,name='download-uncollected-fines-report'),
    path('download-chama-cashflow-report/<int:chama_id>/',views.download_cashflow_report,name='download-chama-cashflow-report'),
    path('download-member-cashflow-report/<int:chama_id>/<int:member_id>/',views.download_member_cashflow_report,name='download-member-cashflow-report'),
    path('download-my-cashflow-report/<int:chama_id>/',views.download_my_cashflow_report,name='download-my-cashflow-report'),
    path('download-expense-report/<int:chama_id>/',views.download_expense_report,name='download-expense-report'),

    path('chama-notifications/<int:chama_id>/',views.notifications,name='notifications'),
    path('new-notification-type/<int:chama_id>/',views.create_notif_type,name='create-notification-type'),
    path('new-notification/<int:chama_id>/',views.create_notif,name='create-notification'),

    path('get_user_role/', views.get_user_role, name='get_user_role'),
    path('get-member-cashflow-data/<int:chama_id>/', views.get_member_cashflow_data, name='get-member-cashflow-data'),
    path('get-loan-repayment-schedule/<int:chama_id>/', views.get_loan_repayment_schedule, name='get-loan-repayment-schedule'),
    path('get-member-contributions-data/<int:chama_id>/', views.get_member_contributions_data, name='get-member-contributions-data'),
    path('get-group-investment-income-data/<int:chama_id>/', views.get_group_investment_income_data, name='get-group-investment-income-data'),
    path('get-member-investment-income-data/<int:chama_id>/', views.get_member_investment_income_data, name='get-member-investment-income-data'),
    path('get-my-investment-income-data/<int:chama_id>/', views.get_my_investment_income_data, name='get-my-investment-income-data'),
    path('get-individual-saving-data/<int:chama_id>/', views.get_individual_saving_data, name='get-individual-saving-data'),
    path('get-group-saving-data/<int:chama_id>/', views.get_group_saving_data, name='get-group-saving-data'),
    path('get-my-saving-data/<int:chama_id>/', views.get_my_saving_data, name='get-my-saving-data'),
    path('get-collected-fines-data/<int:chama_id>/', views.get_collected_fines_data, name='get-collected-fines-data'),
    path('get-unpaid-fines-data/<int:chama_id>/', views.get_unpaid_fines_data, name='get-unpaid-fines-data'),
    path('get-expenses-data/<int:chama_id>/', views.get_expenses_data, name='get-expenses-data'),
    
    # My Chamas view
    path('my-chamas/', views.my_chamas_view, name='my-chamas'),

]
