from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import json
from django.db import transaction

from .models import (
    Transaction, Category, Budget, RecurringTransaction, 
    UserPreferences, Insight
)
from .forms import (
    TransactionForm, CategoryForm, BudgetForm, 
    RecurringTransactionForm, UserPreferencesForm, DateRangeForm
)
from .utils import (
    get_date_range, calculate_summary, get_category_breakdown,
    get_spending_trend, get_comparison_data, check_budget_alerts,
    generate_insights, get_top_categories, calculate_daily_average
)



# ==================== DASHBOARD ====================

@login_required
def dashboard(request):
    """
    Main dashboard view showing daily overview
    """
    # Get selected date from request or use today
    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()

    # Add date navigation helpers
    previous_date = (selected_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (selected_date + timedelta(days=1)).strftime('%Y-%m-%d')
    today = timezone.now().date()

    # Get transactions for selected date
    transactions = Transaction.objects.filter(
        user=request.user,
        date=selected_date
    ).select_related('category').order_by('-time')

    # Calculate daily summary
    daily_summary = calculate_summary(
        request.user,
        start_date=selected_date,
        end_date=selected_date
    )

    # Get budget alerts
    budget_alerts = check_budget_alerts(request.user)

    # Get recent insights (unread)
    recent_insights = Insight.objects.filter(
        user=request.user,
        is_read=False
    )[:3]

    # Get monthly comparison
    comparison = get_comparison_data(request.user, period='month')

    context = {
        'selected_date': selected_date,
        'previous_date': previous_date,
        'next_date': next_date,
        'today': today,
        'transactions': transactions,
        'daily_summary': daily_summary,
        'budget_alerts': budget_alerts,
        'recent_insights': recent_insights,
        'comparison': comparison,
    }

    return render(request, 'expense_tracker/dashboard.html', context)


# ==================== INSIGHTS ====================

@login_required
def insights_view(request):
    """
    View all insights
    """
    # Generate new insights if needed
    if request.GET.get('generate') == 'true':
        new_insights = generate_insights(request.user)
        if new_insights:
            messages.success(request, f'{len(new_insights)} new insights generated!')
        else:
            messages.info(request, 'No new insights at this time.')
    
    # Get all insights
    insights = Insight.objects.filter(
        user=request.user
    ).select_related('category').order_by('-created_at')
    
    # Separate read and unread
    unread_insights = insights.filter(is_read=False)
    read_insights = insights.filter(is_read=True)[:20]  # Limit read insights
    
    context = {
        'unread_insights': unread_insights,
        'read_insights': read_insights,
    }
    
    return render(request, 'expense_tracker/insights.html', context)


@login_required
@require_http_methods(["POST"])
def mark_insight_read(request, pk):
    """
    Mark an insight as read
    """
    insight = get_object_or_404(
        Insight,
        pk=pk,
        user=request.user
    )
    
    insight.is_read = True
    insight.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Insight marked as read.')
    return redirect('expense_tracker:insights')


# ==================== API ENDPOINTS ====================

@login_required
def api_summary(request):
    """
    API endpoint for summary data
    """
    period = request.GET.get('period', 'today')
    start_date, end_date = get_date_range(period)
    
    summary = calculate_summary(request.user, start_date, end_date)
    
    return JsonResponse({
        'income': float(summary['income']),
        'expenses': float(summary['expenses']),
        'balance': float(summary['balance']),
        'transaction_count': summary['transaction_count'],
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    })


@login_required
def api_daily_totals(request):
    """
    API endpoint for daily totals over a period
    """
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    # Get daily totals
    daily_data = Transaction.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    ).values('date', 'type').annotate(
        total=Sum('amount')
    ).order_by('date')
    
    # Organize by date
    result = {}
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.isoformat()
        result[date_str] = {
            'date': date_str,
            'income': 0,
            'expenses': 0,
            'balance': 0,
        }
        current_date += timedelta(days=1)
    
    # Fill in actual data
    for item in daily_data:
        date_str = item['date'].isoformat()
        if date_str in result:
            amount = float(item['total'])
            if item['type'] == 'income':
                result[date_str]['income'] = amount
            else:
                result[date_str]['expenses'] = amount
    
    # Calculate balances
    for date_str in result:
        result[date_str]['balance'] = result[date_str]['income'] - result[date_str]['expenses']
    
    return JsonResponse({
        'data': list(result.values())
    })


@login_required
def api_category_breakdown(request):
    """
    API endpoint for category breakdown
    """
    transaction_type = request.GET.get('type', 'expense')
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    breakdown = get_category_breakdown(
        request.user,
        transaction_type,
        start_date,
        end_date
    )
    
    # Convert Decimal to float for JSON serialization
    for item in breakdown:
        item['amount'] = float(item['amount'])
    
    return JsonResponse({
        'breakdown': breakdown,
        'total': sum(item['amount'] for item in breakdown),
    })


# ==================== ERROR HANDLERS ====================

def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, 'expense_tracker/404.html', status=404)


def handler500(request):
    """Custom 500 error handler"""
    return render(request, 'expense_tracker/500.html', status=500)  


# ==================== TRANSACTIONS ====================

@login_required
def transaction_list(request):
    """
    List all transactions with filtering options
    """
    # Get filter parameters
    transaction_type = request.GET.get('type', '')
    category_id = request.GET.get('category', '')
    period = request.GET.get('period', 'this_month')
    
    # Base queryset
    transactions = Transaction.objects.filter(
        user=request.user
    ).select_related('category')
    
    # Apply filters
    if transaction_type:
        transactions = transactions.filter(type=transaction_type)
    
    if category_id:
        transactions = transactions.filter(category_id=category_id)
    
    # Date range filter
    start_date, end_date = get_date_range(period)
    transactions = transactions.filter(date__gte=start_date, date__lte=end_date)
    
    # Calculate summary for filtered results
    summary = calculate_summary(request.user, start_date, end_date)
    
    # Pagination
    paginator = Paginator(transactions, 20)  # 20 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter dropdown
    categories = Category.get_user_categories(request.user)
    
    context = {
        'page_obj': page_obj,
        'summary': summary,
        'categories': categories,
        'selected_type': transaction_type,
        'selected_category': category_id,
        'selected_period': period,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'expense_tracker/transaction_list.html', context)


@login_required
def transaction_create(request):
    """
    Create a new transaction
    """
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            
            messages.success(request, 'Transaction added successfully!')
            
            # Redirect based on next parameter or default to dashboard
            next_url = request.GET.get('next', 'expense_tracker:dashboard')
            return redirect(next_url)
    else:
        # Pre-fill with today's date and current time
        initial = {
            'date': timezone.now().date(),
            'time': timezone.now().time(),
        }
        form = TransactionForm(user=request.user, initial=initial)
    
    context = {
        'form': form,
        'title': 'Add Transaction',
        'submit_text': 'Add Transaction',
    }
    
    return render(request, 'expense_tracker/transaction_form.html', context)


@login_required
def transaction_detail(request, pk):
    """
    View transaction details
    """
    transaction = get_object_or_404(
        Transaction,
        pk=pk,
        user=request.user
    )
    
    context = {
        'transaction': transaction,
    }
    
    return render(request, 'expense_tracker/transaction_detail.html', context)


@login_required
def transaction_edit(request, pk):
    """
    Edit an existing transaction
    """
    transaction = get_object_or_404(
        Transaction,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transaction updated successfully!')
            return redirect('expense_tracker:dashboard')
    else:
        form = TransactionForm(instance=transaction, user=request.user)
    
    context = {
        'form': form,
        'transaction': transaction,
        'title': 'Edit Transaction',
        'submit_text': 'Update Transaction',
    }
    
    return render(request, 'expense_tracker/transaction_form.html', context)


@login_required
def transaction_delete(request, pk):
    """
    Delete a transaction
    """
    transaction = get_object_or_404(
        Transaction,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, 'Transaction deleted successfully!')
        return redirect('expense_tracker:dashboard')
    
    context = {
        'transaction': transaction,
    }
    
    return render(request, 'expense_tracker/transaction_confirm_delete.html', context)


@login_required
@require_http_methods(["POST"])
def quick_add_transaction(request):
    """
    AJAX endpoint for quickly adding transactions
    """
    try:
        data = json.loads(request.body)
        
        # Get or create category
        category_id = data.get('category_id')
        category = None
        if category_id:
            category = Category.objects.filter(
                id=category_id,
                user=request.user
            ).first() or Category.objects.filter(
                id=category_id,
                is_default=True
            ).first()
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            type=data.get('type'),
            category=category,
            amount=Decimal(data.get('amount')),
            description=data.get('description', ''),
            date=data.get('date', timezone.now().date()),
            time=data.get('time', timezone.now().time()),
        )
        
        return JsonResponse({
            'success': True,
            'transaction_id': transaction.id,
            'message': 'Transaction added successfully!'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


# ==================== CHARTS ====================

@login_required
def charts_view(request):
    """
    Charts and visualizations page
    """
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    # Get summary for the period
    summary = calculate_summary(request.user, start_date, end_date)
    
    context = {
        'summary': summary,
        'selected_period': period,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'expense_tracker/charts.html', context)


@login_required
def chart_data(request):
    """
    AJAX endpoint to get chart data
    """
    chart_type = request.GET.get('type', 'category_breakdown')
    period = request.GET.get('period', 'this_month')
    transaction_type = request.GET.get('transaction_type', 'expense')
    
    start_date, end_date = get_date_range(period)
    
    if chart_type == 'category_breakdown':
        # Pie chart data
        breakdown = get_category_breakdown(
            request.user,
            transaction_type,
            start_date,
            end_date
        )
        
        return JsonResponse({
            'labels': [item['category'] for item in breakdown],
            'data': [float(item['amount']) for item in breakdown],
            'colors': [item['color'] for item in breakdown],
        })
    
    elif chart_type == 'spending_trend':
        # Line chart data
        days = int(request.GET.get('days', 30))
        trend = get_spending_trend(request.user, days)
        
        return JsonResponse({
            'labels': [item['date'] for item in trend],
            'data': [item['amount'] for item in trend],
        })
    
    elif chart_type == 'income_vs_expense':
        # Bar chart comparing income and expenses
        summary = calculate_summary(request.user, start_date, end_date)
        
        return JsonResponse({
            'labels': ['Income', 'Expenses'],
            'data': [float(summary['income']), float(summary['expenses'])],
            'colors': ['#27ae60', '#e74c3c'],
        })
    
    return JsonResponse({'error': 'Invalid chart type'}, status=400)


# ==================== REPORTS ====================

@login_required
def reports_view(request):
    """
    Reports and analytics page
    """
    form = DateRangeForm(request.GET or None)
    
    # Default to current month
    period = 'this_month'
    start_date, end_date = get_date_range(period)
    
    if form.is_valid():
        period = form.cleaned_data.get('period', 'this_month')
        if period == 'custom':
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
        else:
            start_date, end_date = get_date_range(period)
    
    # Calculate comprehensive summary
    summary = calculate_summary(request.user, start_date, end_date)
    
    # Category breakdowns
    expense_breakdown = get_category_breakdown(
        request.user,
        'expense',
        start_date,
        end_date
    )
    
    income_breakdown = get_category_breakdown(
        request.user,
        'income',
        start_date,
        end_date
    )
    
    # Top categories
    top_expenses = get_top_categories(
        request.user,
        'expense',
        limit=5,
        start_date=start_date,
        end_date=end_date
    )
    
    # Daily average
    days_in_period = (end_date - start_date).days + 1
    avg_daily_expense = summary['expenses'] / days_in_period if days_in_period > 0 else Decimal('0.00')
    
    # Comparison with previous period
    comparison = get_comparison_data(request.user, period='month')
    
    context = {
        'form': form,
        'summary': summary,
        'expense_breakdown': expense_breakdown,
        'income_breakdown': income_breakdown,
        'top_expenses': top_expenses,
        'avg_daily_expense': avg_daily_expense,
        'comparison': comparison,
        'start_date': start_date,
        'end_date': end_date,
        'days_in_period': days_in_period,
    }
    
    return render(request, 'expense_tracker/reports.html', context)


@login_required
def export_csv(request):
    """
    Export transactions to CSV
    """
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    transactions = Transaction.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('category').order_by('date', 'time')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_{start_date}_{end_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'Type', 'Category', 'Amount', 'Description'])
    
    for transaction in transactions:
        writer.writerow([
            transaction.date,
            transaction.time,
            transaction.get_type_display(),
            transaction.category.name if transaction.category else 'Uncategorized',
            transaction.amount,
            transaction.description,
        ])
    
    return response


@login_required
def export_pdf(request):
    """
    Export report to PDF
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from io import BytesIO
        
        period = request.GET.get('period', 'this_month')
        start_date, end_date = get_date_range(period)
        
        # Calculate summary
        summary = calculate_summary(request.user, start_date, end_date)
        expense_breakdown = get_category_breakdown(request.user, 'expense', start_date, end_date)
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
        )
        
        elements.append(Paragraph(f'Expense Report', title_style))
        elements.append(Paragraph(f'{start_date} to {end_date}', styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Summary table
        summary_data = [
            ['Summary', 'Amount (KSh)'],
            ['Total Income', f'{summary["income"]:,.2f}'],
            ['Total Expenses', f'{summary["expenses"]:,.2f}'],
            ['Net Balance', f'{summary["balance"]:,.2f}'],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Expense breakdown
        if expense_breakdown:
            elements.append(Paragraph('Expense Breakdown by Category', styles['Heading2']))
            elements.append(Spacer(1, 0.2*inch))
            
            breakdown_data = [['Category', 'Amount (KSh)', 'Percentage']]
            for item in expense_breakdown:
                breakdown_data.append([
                    item['category'],
                    f'{item["amount"]:,.2f}',
                    f'{item["percentage"]}%'
                ])
            
            breakdown_table = Table(breakdown_data, colWidths=[2*inch, 2*inch, 1.5*inch])
            breakdown_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(breakdown_table)
        
        # Build PDF
        doc.build(elements)
        
        # Return response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="expense_report_{start_date}_{end_date}.pdf"'
        
        return response
    
    except ImportError:
        messages.error(request, 'PDF export requires reportlab. Please install it: pip install reportlab')
        return redirect('expense_tracker:reports')


# ==================== BUDGETS ====================

@login_required
def budget_list(request):
    """
    List all budgets
    """
    budgets = Budget.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('category').order_by('category__name')
    
    # Add current status to each budget
    budget_data = []
    for budget in budgets:
        budget_data.append({
            'budget': budget,
            'spent': budget.get_spent_amount(),
            'remaining': budget.get_remaining_amount(),
            'percentage': budget.get_percentage_used(),
            'status': 'danger' if budget.get_percentage_used() >= 100 else 
                     'warning' if budget.get_percentage_used() >= budget.alert_threshold else 'success'
        })
    
    context = {
        'budget_data': budget_data,
    }
    
    return render(request, 'expense_tracker/budget_list.html', context)


@login_required
def budget_create(request):
    """
    Create a new budget
    """
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.next_occurrence = budget.start_date
            budget.save()
            
            messages.success(request, 'Budget created successfully!')
            return redirect('expense_tracker:budget_list')
    else:
        form = BudgetForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create Budget',
        'submit_text': 'Create Budget',
    }
    
    return render(request, 'expense_tracker/budget_form.html', context)


@login_required
def budget_detail(request, pk):
    """
    View budget details
    """
    budget = get_object_or_404(
        Budget,
        pk=pk,
        user=request.user
    )
    
    # Get transactions for this budget's category in current period
    start_date = budget.get_period_start()
    end_date = budget.get_period_end()
    
    transactions = Transaction.objects.filter(
        user=request.user,
        category=budget.category,
        type='expense',
        date__gte=start_date,
        date__lte=end_date
    ).order_by('-date', '-time')
    
    context = {
        'budget': budget,
        'transactions': transactions,
        'spent': budget.get_spent_amount(),
        'remaining': budget.get_remaining_amount(),
        'percentage': budget.get_percentage_used(),
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'expense_tracker/budget_detail.html', context)


@login_required
def budget_edit(request, pk):
    """
    Edit an existing budget
    """
    budget = get_object_or_404(
        Budget,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Budget updated successfully!')
            return redirect('expense_tracker:budget_list')
    else:
        form = BudgetForm(instance=budget, user=request.user)
    
    context = {
        'form': form,
        'budget': budget,
        'title': 'Edit Budget',
        'submit_text': 'Update Budget',
    }
    
    return render(request, 'expense_tracker/budget_form.html', context)


@login_required
def budget_delete(request, pk):
    """
    Delete a budget
    """
    budget = get_object_or_404(
        Budget,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        budget.delete()
        messages.success(request, 'Budget deleted successfully!')
        return redirect('expense_tracker:budget_list')
    
    context = {
        'budget': budget,
    }
    
    return render(request, 'expense_tracker/budget_confirm_delete.html', context)


# ==================== RECURRING TRANSACTIONS ====================

@login_required
def recurring_list(request):
    """
    List all recurring transactions
    """
    recurring_transactions = RecurringTransaction.objects.filter(
        user=request.user
    ).select_related('category').order_by('-is_active', 'next_occurrence')
    
    context = {
        'recurring_transactions': recurring_transactions,
    }
    
    return render(request, 'expense_tracker/recurring_list.html', context)


@login_required
def recurring_create(request):
    """
    Create a new recurring transaction
    """
    if request.method == 'POST':
        form = RecurringTransactionForm(request.POST, user=request.user)
        if form.is_valid():
            recurring = form.save(commit=False)
            recurring.user = request.user
            recurring.next_occurrence = recurring.start_date
            recurring.save()
            
            messages.success(request, 'Recurring transaction created successfully!')
            return redirect('expense_tracker:recurring_list')
    else:
        form = RecurringTransactionForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create Recurring Transaction',
        'submit_text': 'Create',
    }
    
    return render(request, 'expense_tracker/recurring_form.html', context)


@login_required
def recurring_detail(request, pk):
    """
    View recurring transaction details
    """
    recurring = get_object_or_404(
        RecurringTransaction,
        pk=pk,
        user=request.user
    )
    
    # Get generated transactions
    generated_transactions = Transaction.objects.filter(
        recurring_transaction=recurring
    ).order_by('-date', '-time')[:10]
    
    context = {
        'recurring': recurring,
        'generated_transactions': generated_transactions,
    }
    
    return render(request, 'expense_tracker/recurring_detail.html', context)


@login_required
def recurring_edit(request, pk):
    """
    Edit a recurring transaction
    """
    recurring = get_object_or_404(
        RecurringTransaction,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        form = RecurringTransactionForm(request.POST, instance=recurring, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Recurring transaction updated successfully!')
            return redirect('expense_tracker:recurring_list')
    else:
        form = RecurringTransactionForm(instance=recurring, user=request.user)
    
    context = {
        'form': form,
        'recurring': recurring,
        'title': 'Edit Recurring Transaction',
        'submit_text': 'Update',
    }
    
    return render(request, 'expense_tracker/recurring_form.html', context)


@login_required
def recurring_delete(request, pk):
    """
    Delete a recurring transaction
    """
    recurring = get_object_or_404(
        RecurringTransaction,
        pk=pk,
        user=request.user
    )
    
    if request.method == 'POST':
        recurring.delete()
        messages.success(request, 'Recurring transaction deleted successfully!')
        return redirect('expense_tracker:recurring_list')
    
    context = {
        'recurring': recurring,
    }
    
    return render(request, 'expense_tracker/recurring_confirm_delete.html', context)


@login_required
@require_http_methods(["POST"])
def recurring_toggle(request, pk):
    """
    Toggle recurring transaction active status
    """
    recurring = get_object_or_404(
        RecurringTransaction,
        pk=pk,
        user=request.user
    )
    
    recurring.is_active = not recurring.is_active
    recurring.save()
    
    status = 'activated' if recurring.is_active else 'deactivated'
    messages.success(request, f'Recurring transaction {status}!')
    
    return redirect('expense_tracker:recurring_list')


# ==================== CATEGORIES ====================

@login_required
def category_list(request):
    """
    List and manage categories
    """
    expense_categories = Category.get_user_categories(request.user, 'expense')
    income_categories = Category.get_user_categories(request.user, 'income')
    
    context = {
        'expense_categories': expense_categories,
        'income_categories': income_categories,
    }
    
    return render(request, 'expense_tracker/category_list.html', context)

@login_required
def api_categories(request):
    """
    API endpoint to get categories filtered by type
    """
    category_type = request.GET.get('type')
    
    # ✅ Validate type
    if category_type and category_type not in ['income', 'expense']:
        return JsonResponse({'error': 'Invalid type. Use "income" or "expense".'}, status=400)
    
    categories = Category.get_user_categories(request.user, category_type)
    
    data = {
        'categories': [
            {
                'id': cat.id,
                'name': cat.name,
                'icon': cat.icon,
                'type': cat.type
            }
            for cat in categories
        ]
    }
    
    return JsonResponse(data)

@login_required
def category_create(request):
    """
    Create a new category
    """
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.is_default = False
            category.save()
            
            messages.success(request, 'Category created successfully!')
            return redirect('expense_tracker:category_list')
    else:
        form = CategoryForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create Category',
        'submit_text': 'Create',
    }
    
    return render(request, 'expense_tracker/category_form.html', context)


@login_required
def category_edit(request, pk):
    """
    Edit a category (only custom categories)
    """
    category = get_object_or_404(
        Category,
        pk=pk,
        user=request.user
    )
    
    if category.is_default:
        messages.error(request, 'Cannot edit default categories!')
        return redirect('expense_tracker:category_list')
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('expense_tracker:category_list')
    else:
        form = CategoryForm(instance=category, user=request.user)
    
    context = {
        'form': form,
        'category': category,
        'title': 'Edit Category',
        'submit_text': 'Update',
    }
    
    return render(request, 'expense_tracker/category_form.html', context)


@login_required
def category_delete(request, pk):
    """
    Delete a category (only custom categories)
    """
    category = get_object_or_404(
        Category,
        pk=pk,
        user=request.user
    )
    
    if category.is_default:
        messages.error(request, 'Cannot delete default categories!')
        return redirect('expense_tracker:category_list')
    
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted successfully!')
        return redirect('expense_tracker:category_list')
    
    context = {
        'category': category,
    }
    
    return render(request, 'expense_tracker/category_confirm_delete.html', context)


# ==================== USER SETTINGS ====================

@login_required
def user_preferences(request):
    """
    User preferences and settings
    """
    preferences, created = UserPreferences.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=preferences)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferences updated successfully!')
            return redirect('expense_tracker:user_preferences')
    else:
        form = UserPreferencesForm(instance=preferences)
    
    # Get statistics for data management
    transaction_count = Transaction.objects.filter(user=request.user).count()
    budget_count = Budget.objects.filter(user=request.user).count()
    category_count = Category.objects.filter(user=request.user).count()
    
    context = {
        'form': form,
        'preferences': preferences,
        'transaction_count': transaction_count,
        'budget_count': budget_count,
        'category_count': category_count,
    }
    
    return render(request, 'expense_tracker/preferences.html', context)



@login_required
@require_http_methods(["POST"])
def clear_all_data(request):
    confirm = request.POST.get('confirm')
    
    if confirm == 'DELETE':
        with transaction.atomic():
            # Delete only user-owned data
            Transaction.objects.filter(user=request.user).delete()
            Budget.objects.filter(user=request.user).delete()
            RecurringTransaction.objects.filter(user=request.user).delete()
            Insight.objects.filter(user=request.user).delete()

            # Delete ONLY user-created (non-default) categories
            Category.objects.filter(user=request.user, is_default=False).delete()
            # DO NOT delete Category.objects.filter(is_default=True) — they have user=None

        # Ensure default categories exist (idempotent)
        Category.create_default_categories()

        messages.success(request, 'All your personal data has been cleared. Default categories are preserved.')
        return redirect('expense_tracker:dashboard')
    else:
        messages.error(request, 'Data deletion cancelled. Please type DELETE to confirm.')
        return redirect('expense_tracker:user_preferences')


@login_required
def export_all_data(request):
    """
    Export all user data to CSV
    """
    import csv
    from io import StringIO
    import zipfile
    from io import BytesIO
    
    # Create a zip file in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Export Transactions
        transactions = Transaction.objects.filter(user=request.user).select_related('category')
        if transactions.exists():
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(['Date', 'Time', 'Type', 'Category', 'Amount', 'Description', 'Is Recurring'])
            
            for transaction in transactions:
                writer.writerow([
                    transaction.date,
                    transaction.time,
                    transaction.get_type_display(),
                    transaction.category.name if transaction.category else 'Uncategorized',
                    transaction.amount,
                    transaction.description,
                    'Yes' if transaction.is_recurring else 'No',
                ])
            
            zip_file.writestr('transactions.csv', csv_buffer.getvalue())
        
        # Export Budgets
        budgets = Budget.objects.filter(user=request.user).select_related('category')
        if budgets.exists():
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(['Category', 'Amount', 'Period', 'Start Date', 'Rollover Enabled', 'Alert Threshold'])
            
            for budget in budgets:
                writer.writerow([
                    budget.category.name,
                    budget.amount,
                    budget.get_period_display(),
                    budget.start_date,
                    'Yes' if budget.rollover_enabled else 'No',
                    budget.alert_threshold,
                ])
            
            zip_file.writestr('budgets.csv', csv_buffer.getvalue())
        
        # Export Recurring Transactions
        recurring = RecurringTransaction.objects.filter(user=request.user).select_related('category')
        if recurring.exists():
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(['Type', 'Category', 'Amount', 'Description', 'Frequency', 'Start Date', 'Next Occurrence', 'Is Active'])
            
            for rec in recurring:
                writer.writerow([
                    rec.get_type_display(),
                    rec.category.name if rec.category else 'Uncategorized',
                    rec.amount,
                    rec.description,
                    rec.get_frequency_display(),
                    rec.start_date,
                    rec.next_occurrence,
                    'Yes' if rec.is_active else 'No',
                ])
            
            zip_file.writestr('recurring_transactions.csv', csv_buffer.getvalue())
        
        # Export Categories
        categories = Category.objects.filter(user=request.user)
        if categories.exists():
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(['Name', 'Type', 'Icon', 'Color'])
            
            for category in categories:
                writer.writerow([
                    category.name,
                    category.get_type_display(),
                    category.icon,
                    category.color,
                ])
            
            zip_file.writestr('categories.csv', csv_buffer.getvalue())
    
    # Prepare response
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="chamaspace_expense_data.zip"'
    
    return response


# ==================== API ENDPOINTS ====================

@login_required
def api_summary(request):
    """
    API endpoint for summary data
    """
    period = request.GET.get('period', 'today')
    start_date, end_date = get_date_range(period)
    
    summary = calculate_summary(request.user, start_date, end_date)
    
    return JsonResponse({
        'income': float(summary['income']),
        'expenses': float(summary['expenses']),
        'balance': float(summary['balance']),
        'transaction_count': summary['transaction_count'],
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    })


@login_required
def api_daily_totals(request):
    """
    API endpoint for daily totals over a period
    """
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    # Get daily totals
    daily_data = Transaction.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    ).values('date', 'type').annotate(
        total=Sum('amount')
    ).order_by('date')
    
    # Organize by date
    result = {}
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.isoformat()
        result[date_str] = {
            'date': date_str,
            'income': 0,
            'expenses': 0,
            'balance': 0,
        }
        current_date += timedelta(days=1)
    
    # Fill in actual data
    for item in daily_data:
        date_str = item['date'].isoformat()
        if date_str in result:
            amount = float(item['total'])
            if item['type'] == 'income':
                result[date_str]['income'] = amount
            else:
                result[date_str]['expenses'] = amount
    
    # Calculate balances
    for date_str in result:
        result[date_str]['balance'] = result[date_str]['income'] - result[date_str]['expenses']
    
    return JsonResponse({
        'data': list(result.values())
    })


@login_required
def api_category_breakdown(request):
    """
    API endpoint for category breakdown
    """
    transaction_type = request.GET.get('type', 'expense')
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    breakdown = get_category_breakdown(
        request.user,
        transaction_type,
        start_date,
        end_date
    )
    
    # Convert Decimal to float for JSON serialization
    for item in breakdown:
        item['amount'] = float(item['amount'])
    
    return JsonResponse({
        'breakdown': breakdown,
        'total': sum(item['amount'] for item in breakdown),
    })


# ==================== ERROR HANDLERS ====================

def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, 'expense_tracker/404.html', status=404)


def handler500(request):
    """Custom 500 error handler"""
    return render(request, 'expense_tracker/500.html', status=500)