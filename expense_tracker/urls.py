from django.urls import path
from . import views

app_name = 'expense_tracker'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/create/', views.transaction_create, name='transaction_create'),
    path('transactions/<int:pk>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/<int:pk>/edit/', views.transaction_edit, name='transaction_edit'),
    path('transactions/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),
    
    # Quick transaction (AJAX endpoint)
    path('transactions/quick-add/', views.quick_add_transaction, name='quick_add_transaction'),
    
    # Charts
    path('charts/', views.charts_view, name='charts'),
    path('charts/data/', views.chart_data, name='chart_data'),
    
    # Reports
    path('reports/', views.reports_view, name='reports'),
    path('reports/export-csv/', views.export_csv, name='export_csv'),
    path('reports/export-pdf/', views.export_pdf, name='export_pdf'),
    path('reports/export-all/', views.export_all_data, name='export_all_data'),
    
    # Budgets
    path('budgets/', views.budget_list, name='budget_list'),
    path('budgets/create/', views.budget_create, name='budget_create'),
    path('budgets/<int:pk>/', views.budget_detail, name='budget_detail'),
    path('budgets/<int:pk>/edit/', views.budget_edit, name='budget_edit'),
    path('budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),
    
    # Recurring Transactions
    path('recurring/', views.recurring_list, name='recurring_list'),
    path('recurring/create/', views.recurring_create, name='recurring_create'),
    path('recurring/<int:pk>/', views.recurring_detail, name='recurring_detail'),
    path('recurring/<int:pk>/edit/', views.recurring_edit, name='recurring_edit'),
    path('recurring/<int:pk>/delete/', views.recurring_delete, name='recurring_delete'),
    path('recurring/<int:pk>/toggle/', views.recurring_toggle, name='recurring_toggle'),
    
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    
    # User Preferences
    path('preferences/', views.user_preferences, name='user_preferences'),
    
    # Insights
    path('insights/', views.insights_view, name='insights'),
    path('insights/<int:pk>/mark-read/', views.mark_insight_read, name='mark_insight_read'),
    
     #Data Management
    path('preferences/clear-data/', views.clear_all_data, name='clear_all_data'),
    path('preferences/export-data/', views.export_all_data, name='export_all_data'),

    # API Endpoints (for AJAX calls)
    path('api/summary/', views.api_summary, name='api_summary'),
    path('api/daily-totals/', views.api_daily_totals, name='api_daily_totals'),
    path('api/category-breakdown/', views.api_category_breakdown, name='api_category_breakdown'),
    path('api/categories/', views.api_categories, name='api_categories'),

]