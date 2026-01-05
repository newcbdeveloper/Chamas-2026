from chamas.models import *
from django.http import JsonResponse,HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
from reportlab.platypus             import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Table, TableStyle, Spacer
)
from datetime import datetime

class DownloadService:
    @staticmethod
    def download_loan_report(request,chama_id):
        try:
            chama = Chama.objects.get(pk=chama_id)
            loans = LoanItem.objects.filter(chama=chama)
        except Exception as e:
            # If there's an error getting the chama or loans, return an error response
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="loan_report_error.pdf"'
            
            doc = BaseDocTemplate(
                response,
                pagesize=letter,
                leftMargin=36, rightMargin=36,
                topMargin=72, bottomMargin=36
            )
            frame = Frame(
                doc.leftMargin, doc.bottomMargin,
                doc.width, doc.height,
                id='normal'
            )
            
            def draw_error_header(canvas, doc):
                canvas.saveState()
                canvas.setFont('Times-Bold', 16)
                canvas.drawCentredString(letter[0]/2, letter[1]-40, "Error Generating Report")
                canvas.setFont('Times-Roman', 12)
                canvas.drawCentredString(letter[0]/2, letter[1]-60, f"Error: {str(e)}")
                canvas.restoreState()
            
            doc.addPageTemplates([
                PageTemplate(id='WithHeader', frames=frame, onPage=draw_error_header)
            ])
            
            error_data = [['Error', 'Description'], ['Database Error', str(e)]]
            error_table = Table(error_data)
            doc.build([Spacer(1, 40), error_table])
            return response

        
        response = HttpResponse(content_type='application/pdf')
        # Sanitize the chama name for filename to avoid issues with special characters
        safe_chama_name = "".join(c for c in chama.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_chama_name = safe_chama_name.replace(' ', '_')
        if not safe_chama_name:
            safe_chama_name = "chama"
        response['Content-Disposition'] = (
            f'attachment; filename="{safe_chama_name}_loan_report.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-60,
                "Loan Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-75,
                datetime.now().strftime("%Y-%m-%d")
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

    
        data = [[
            'Member Name', 'Loan Type',
            'Start Date', 'Due Date',
            'Amount', 'Total Paid',
            'Balance', 'Status'
        ]]
        
        # Check if there are any loans
        if not loans.exists():
            data.append([
                'No loans found',
                '-',
                '-',
                '-',
                '-',
                '-',
                '-',
                '-'
            ])
        else:
            for loan in loans:
                try:
                    # Handle potential None values safely
                    member_name = loan.member.name if loan.member else 'N/A'
                    loan_type = loan.type.name if loan.type else 'N/A'
                    start_date = loan.start_date.strftime('%Y-%m-%d') if loan.start_date else 'N/A'
                    end_date = loan.end_date.strftime('%Y-%m-%d') if loan.end_date else 'N/A'
                    amount = f'ksh {loan.amount}' if loan.amount else 'ksh 0'
                    total_paid = f'ksh {loan.total_paid}' if loan.total_paid else 'ksh 0'
                    balance = f'ksh {loan.balance}' if loan.balance else 'ksh 0'
                    status = loan.status if loan.status else 'N/A'
                    
                    data.append([
                        member_name,
                        loan_type,
                        start_date,
                        end_date,
                        amount,
                        total_paid,
                        balance,
                        status,
                    ])
                except Exception as e:
                    # If there's an error with a specific loan, add a row with error info
                    data.append([
                        'Error',
                        'Error',
                        'Error',
                        'Error',
                        'Error',
                        'Error',
                        'Error',
                        f'Error: {str(e)[:50]}',
                    ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        try:
            story = [
                Spacer(1, 40),  # space below header
                table
            ]
            doc.build(story)
            return response
        except Exception as e:
            # If there's an error building the PDF, return a simple error response
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="loan_report_error.pdf"'
            
            # Create a simple error document
            error_doc = BaseDocTemplate(
                response,
                pagesize=letter,
                leftMargin=36, rightMargin=36,
                topMargin=72, bottomMargin=36
            )
            error_frame = Frame(
                error_doc.leftMargin, error_doc.bottomMargin,
                error_doc.width, error_doc.height,
                id='normal'
            )
            
            def draw_pdf_error_header(canvas, doc):
                canvas.saveState()
                canvas.setFont('Times-Bold', 16)
                canvas.drawCentredString(letter[0]/2, letter[1]-40, "PDF Generation Error")
                canvas.setFont('Times-Roman', 12)
                canvas.drawCentredString(letter[0]/2, letter[1]-60, f"Error: {str(e)}")
                canvas.restoreState()
            
            error_doc.addPageTemplates([
                PageTemplate(id='WithHeader', frames=error_frame, onPage=draw_pdf_error_header)
            ])
            
            error_data = [['Error Type', 'Description'], ['PDF Generation Error', str(e)[:100]]]
            error_table = Table(error_data)
            error_doc.build([Spacer(1, 40), error_table])
            return response
    
    @staticmethod
    def download_loan_repayment_schedule(chama_id, member_id=None):
        # 1) Fetch Chama and active Loans
        chama = Chama.objects.get(pk=chama_id)
        
        # Filter loans by member if specified
        filters = {'chama': chama, 'status__in': ['approved', 'active', 'partially_paid']}
        if member_id:
            member = ChamaMember.objects.get(pk=member_id)
            filters['member'] = member
            
        loans = LoanItem.objects.filter(**filters)

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        filename = f"{chama.name}_loan_repayment_schedule"
        if member_id:
            member = ChamaMember.objects.get(pk=member_id)
            filename += f"_{member.name}"
        filename += ".pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            subtitle = "Loan Repayment Schedule"
            if member_id:
                member = ChamaMember.objects.get(pk=member_id)
                subtitle += f" - {member.name}"
            canvas.drawCentredString(
                letter[0]/2, letter[1]-60,
                subtitle
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-75,
                datetime.now().strftime("%Y-%m-%d")
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data & style
        if member_id:
            # For specific member, don't show member name column
            data = [[
                'Loan Type', 'Amount', 'Total to Pay', 'Total Paid',
                'Balance', 'Start Date', 'End Date', 'Next Due', 
                'Schedule', 'Status'
            ]]
            for loan in loans:
                data.append([
                    loan.type.name if loan.type else 'N/A',
                    f'ksh {loan.amount}' if loan.amount else 'ksh 0',
                    f'ksh {loan.total_amount_to_be_paid}' if loan.total_amount_to_be_paid else 'ksh 0',
                    f'ksh {loan.total_paid}' if loan.total_paid else 'ksh 0',
                    f'ksh {loan.balance}' if loan.balance else 'ksh 0',
                    loan.start_date.strftime('%Y-%m-%d') if loan.start_date else 'N/A',
                    loan.end_date.strftime('%Y-%m-%d') if loan.end_date else 'N/A',
                    loan.next_due.strftime('%Y-%m-%d') if loan.next_due else 'N/A',
                    loan.schedule,
                    loan.status,
                ])
        else:
            # For all members, include member name column
            data = [[
                'Member Name', 'Loan Type', 'Amount', 'Total to Pay', 'Total Paid',
                'Balance', 'Start Date', 'End Date', 'Next Due', 
                'Schedule', 'Status'
            ]]
            for loan in loans:
                data.append([
                    loan.member.name if loan.member else 'N/A',
                    loan.type.name if loan.type else 'N/A',
                    f'ksh {loan.amount}' if loan.amount else 'ksh 0',
                    f'ksh {loan.total_amount_to_be_paid}' if loan.total_amount_to_be_paid else 'ksh 0',
                    f'ksh {loan.total_paid}' if loan.total_paid else 'ksh 0',
                    f'ksh {loan.balance}' if loan.balance else 'ksh 0',
                    loan.start_date.strftime('%Y-%m-%d') if loan.start_date else 'N/A',
                    loan.end_date.strftime('%Y-%m-%d') if loan.end_date else 'N/A',
                    loan.next_due.strftime('%Y-%m-%d') if loan.next_due else 'N/A',
                    loan.schedule,
                    loan.status,
                ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 5) Assemble & build
        story = [
            Spacer(1, 40),  # space below header
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_group_investment_income(request, chama_id):
        # 1) Fetch Chama and group Income data
        chama   = Chama.objects.get(pk=chama_id)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        
        # Base queryset
        incomes = Income.objects.filter(chama=chama, forGroup=True)
        
        # Apply date filters
        if start_date:
            incomes = incomes.filter(user_date__gte=start_date)
        if end_date:
            incomes = incomes.filter(user_date__lte=end_date)
            
        incomes = incomes.order_by('-date')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{chama.name}_group_investment_income.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-60,
                "Group Investment Income"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-75,
                datetime.now().strftime("%Y-%m-%d")
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data & style
        data = [[
            'Income Name', 'Investment',
            'Date', 'Amount'
        ]]
        for inc in incomes:
            data.append([
                inc.name,
                inc.investment.name if inc.investment else 'N/A',
                inc.date.strftime('%Y-%m-%d') if inc.date else 'N/A',
                f'ksh {inc.amount}',
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 5) Assemble & build
        story = [
            Spacer(1, 40),  # space below header
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_member_investment_income(request,chama_id):
        # 1) Fetch Chama and Income data
        chama = Chama.objects.get(pk=chama_id)
        member_id = request.GET.get('member_id', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)

        # Base queryset
        incomes = Income.objects.filter(chama=chama, forGroup=False)
        
        # Apply member filter with proper error handling
        if member_id:
            try:
                # Clean the member_id by taking only the numeric part before any '?' characters
                clean_member_id = str(member_id).split('?')[0].strip()
                if clean_member_id.isdigit():
                    member = ChamaMember.objects.get(pk=int(clean_member_id))
                    incomes = incomes.filter(owner=member)
                else:
                    # If member_id is not valid, skip member filtering
                    member_id = None
            except (ValueError, ChamaMember.DoesNotExist):
                # If member_id is invalid or member doesn't exist, skip member filtering
                member_id = None
            
        # Apply date filters
        if start_date:
            incomes = incomes.filter(user_date__gte=start_date)
        if end_date:
            incomes = incomes.filter(user_date__lte=end_date)
            
        incomes = incomes.order_by('-date')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{chama.name}_member_investment_income.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                "Member Investment Income"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime("%Y-%m-%d")
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data & style
        data = [[
            'Income Name', 'Member Name',
            'Investment', 'Amount', 'Date'
        ]]
        for income in incomes:
            data.append([
                income.name,
                income.owner.name if income.owner else 'N/A',
                income.investment.name if income.investment else 'N/A',
                f'ksh {income.amount}',
                income.date.strftime('%Y-%m-%d') if income.date else 'N/A'
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 5) Assemble & build
        story = [
            Spacer(1, 40),  # space below header
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_my_investment_income(request, chama_id):
        # 1) Fetch Chama and personal Income data
        chama = Chama.objects.get(pk=chama_id)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        
        # Get current user's member record
        try:
            member = ChamaMember.objects.get(user=request.user, group=chama)
        except ChamaMember.DoesNotExist:
            # Return empty PDF if user is not a member
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{chama.name}_my_investment_income.pdf"'
            return response
        
        # Base queryset for personal investment incomes
        incomes = Income.objects.filter(chama=chama, forGroup=False, owner=member)
        
        # Apply date filters
        if start_date:
            incomes = incomes.filter(user_date__gte=start_date)
        if end_date:
            incomes = incomes.filter(user_date__lte=end_date)
            
        incomes = incomes.order_by('-date')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{chama.name}_my_investment_income.pdf"'

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                "My Investment Income"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime("%Y-%m-%d")
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data & style
        data = [[
            'Income Name', 'Investment',
            'Amount', 'Date'
        ]]
        for income in incomes:
            data.append([
                income.name,
                income.investment.name if income.investment else 'N/A',
                f'ksh {income.amount}',
                income.user_date.strftime('%Y-%m-%d') if income.user_date else income.date.strftime('%Y-%m-%d')
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 5) Assemble & build
        story = [
            Spacer(1, 40),  # space below header
            table
        ]
        doc.build(story)
        return response

    @staticmethod
    def download_individual_saving_report(request,chama_id):
        # 1) Fetch Chama and individual saving data
        chama = Chama.objects.get(pk=chama_id)
        member_id = request.GET.get('member_id', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)

        # Base queryset
        savings = Saving.objects.filter(chama=chama, forGroup=False)
        
        # Apply member filter with proper error handling
        if member_id:
            try:
                # Clean the member_id by taking only the numeric part before any '?' characters
                clean_member_id = str(member_id).split('?')[0].strip()
                if clean_member_id.isdigit():
                    member = ChamaMember.objects.get(pk=int(clean_member_id))
                    savings = savings.filter(owner=member)
                else:
                    # If member_id is not valid, skip member filtering
                    member_id = None
            except (ValueError, ChamaMember.DoesNotExist):
                # If member_id is invalid or member doesn't exist, skip member filtering
                member_id = None
            
        # Apply date filters
        if start_date:
            savings = savings.filter(date__date__gte=start_date)
        if end_date:
            savings = savings.filter(date__date__lte=end_date)
            
        savings = savings.order_by('-date')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{chama.name}_individual_savings_report.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='main'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-60,
                "Individual Savings Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data & style
        data = [[
            'Member', 'Amount', 'Type', 'Date'
        ]]
        for s in savings:
            data.append([
                s.owner.name,
                f'ksh {s.amount}',
                s.saving_type.name,
                s.date.strftime('%Y-%m-%d')
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 5) Assemble & build document
        story = [
            Spacer(1, 40),  # space below header
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_group_saving_report(request,chama_id):
        # 1) Fetch Chama and group Saving data
        chama   = Chama.objects.get(pk=chama_id)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        
        # Base queryset
        savings = Saving.objects.filter(chama=chama, forGroup=True)
        
        # Apply date filters
        if start_date:
            savings = savings.filter(date__date__gte=start_date)
        if end_date:
            savings = savings.filter(date__date__lte=end_date)
            
        savings = savings.order_by('-date')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{chama.name}_group_savings_report.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-60,
                "Group Savings Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data & style
        data = [[
            'Amount', 'Type', 'Date'
        ]]
        for s in savings:
            data.append([
                f'ksh {s.amount}',
                s.saving_type.name,
                s.date.strftime('%Y-%m-%d')
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 5) Assemble & build
        story = [
            Spacer(1, 40),  # space below header
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_my_saving_report(request, chama_id):
        # 1) Fetch Chama and personal Saving data
        chama = Chama.objects.get(pk=chama_id)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        
        # Get current user's member record
        try:
            member = ChamaMember.objects.get(user=request.user, group=chama)
        except ChamaMember.DoesNotExist:
            # Return empty PDF if user is not a member
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{chama.name}_my_savings_report.pdf"'
            return response
        
        # Base queryset for personal savings
        savings = Saving.objects.filter(chama=chama, forGroup=False, owner=member)
        
        # Apply date filters
        if start_date:
            savings = savings.filter(date__date__gte=start_date)
        if end_date:
            savings = savings.filter(date__date__lte=end_date)
            
        savings = savings.order_by('-date')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{chama.name}_my_savings_report.pdf"'

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-60,
                "My Savings Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0]/2, letter[1]-75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data & style
        data = [[
            'Amount', 'Type', 'Date'
        ]]
        for s in savings:
            data.append([
                f'ksh {s.amount}',
                s.saving_type.name if s.saving_type else 'N/A',
                s.date.strftime('%Y-%m-%d')
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 5) Assemble & build
        story = [
            Spacer(1, 40),  # space below header
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_group_contributions_report(chama_id,contribution_id):
        # ─────────────────────────────────────────────
        # 1) Fetch & flatten your contribution records
        # ─────────────────────────────────────────────
        try:
            chama = Chama.objects.get(pk=chama_id)
        except Chama.DoesNotExist:
            from django.http import JsonResponse
            return JsonResponse({
                'status': 'error',
                'message': f'Chama with ID {chama_id} not found'
            }, status=404)
            
        contribution = Contribution.objects.filter(chama=chama,id=contribution_id).first()
        if not contribution:
            from django.http import JsonResponse
            return JsonResponse({
                'status': 'error',
                'message': f'Contribution scheme with ID {contribution_id} not found for this chama'
            }, status=404)
            
        contributions = []
        contributions.extend(contribution.records.all())
        contributions = sorted(
            contributions,
            key=lambda x: x.date_created,
            reverse=True
        )

        # ─────────────────────────────────────────────
        # 2) Prepare HTTP + PDF document
        # ─────────────────────────────────────────────
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{chama.name}_group_contributions_report.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # ─────────────────────────────────────────────
        # 3) Define header callback (runs on every page)
        # ─────────────────────────────────────────────
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0]/2, letter[1] - 40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0]/2, letter[1] - 60,
                f"Group Contributions Report for '{contribution.name}'"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0]/2, letter[1] - 75,
                datetime.now().strftime("%Y-%m-%d")
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])


        data = [[
            'Member', 'Contribution Type', 'Date',
            'Expected Amount', 'Amount Paid', 'Balance'
        ]]
        for c in contributions:
            data.append([
                c.member.name,
                c.contribution.name,
                c.date_created.strftime('%Y-%m-%d'),
                f'ksh {c.amount_expected}',
                f'ksh {c.amount_paid}',
                f'ksh {c.balance}',
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

    
        story = [
            Spacer(1, 40),  # gives some space below header
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_member_contribution_report(chama_id, member_id=None, scheme_id=None):
        try:
            # 1) Retrieve Chama
            chama = Chama.objects.get(pk=chama_id)
            
            # 2) Build filters for contributions
            filters = {'chama': chama}
            
            if member_id:
                member = ChamaMember.objects.get(pk=member_id)
                filters['member'] = member
                
            if scheme_id:
                contribution = Contribution.objects.get(pk=scheme_id)
                filters['contribution'] = contribution
                
            # Get contribution records
            contributions = ContributionRecord.objects.filter(**filters).order_by('-date_created')

            # 3) Prepare PDF response
            response = HttpResponse(content_type='application/pdf')
            
            # Generate filename based on filters
            filename_parts = [chama.name.replace(' ', '_')]
            if member_id:
                member = ChamaMember.objects.get(pk=member_id)
                filename_parts.append(member.name.replace(' ', '_'))
            if scheme_id:
                contribution = Contribution.objects.get(pk=scheme_id)
                filename_parts.append(contribution.name.replace(' ', '_'))
            filename_parts.append('contribution_report.pdf')
            
            response['Content-Disposition'] = (
                f'attachment; filename="{"_".join(filename_parts)}"'
            )

            # 4) Setup BaseDocTemplate with header on each page
            doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
            )
            frame = Frame(
                doc.leftMargin, doc.bottomMargin,
                doc.width, doc.height,
                id='normal'
            )

            # Header callback
            def draw_header(canvas, doc):
                canvas.saveState()
                # Title line
                canvas.setFont('Times-Bold', 14)
                title = "Member Contribution Report"
                if member_id:
                    member = ChamaMember.objects.get(pk=member_id)
                    title += f" - {member.name}"
                if scheme_id:
                    contribution = Contribution.objects.get(pk=scheme_id)
                    title += f" - {contribution.name}"
                canvas.drawCentredString(
                    letter[0]/2, letter[1] - 40,
                    title
                )
                # Date line
                canvas.setFont('Times-Roman', 10)
                canvas.drawCentredString(
                    letter[0]/2, letter[1] - 55,
                    datetime.now().strftime('%Y-%m-%d')
                )
                canvas.restoreState()

            doc.addPageTemplates([
                PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
            ])

            # 5) Build table data
            if member_id and scheme_id:
                # For specific member and scheme, don't show member and scheme columns
                data = [['Date', 'Expected Amount', 'Amount Paid', 'Balance', 'Status']]
            elif member_id:
                # For specific member, don't show member column
                data = [['Scheme', 'Date', 'Expected Amount', 'Amount Paid', 'Balance', 'Status']]
            elif scheme_id:
                # For specific scheme, don't show scheme column
                data = [['Member', 'Date', 'Expected Amount', 'Amount Paid', 'Balance', 'Status']]
            else:
                # Show all columns
                data = [['Member', 'Scheme', 'Date', 'Expected Amount', 'Amount Paid', 'Balance', 'Status']]
            
            # Check if there are contributions
            if not contributions.exists():
                # Add empty row
                empty_row = ['No contributions found'] + ['-'] * (len(data[0]) - 1)
                data.append(empty_row)
            else:
                for contrib in contributions:
                    try:
                        member_name = contrib.member.name if contrib.member else 'N/A'
                        scheme_name = contrib.contribution.name if contrib.contribution else 'N/A'
                        date_created = contrib.date_created.strftime('%Y-%m-%d') if contrib.date_created else 'N/A'
                        amount_expected = f'ksh {contrib.amount_expected}' if contrib.amount_expected else 'ksh 0'
                        amount_paid = f'ksh {contrib.amount_paid}' if contrib.amount_paid else 'ksh 0'
                        balance = f'ksh {contrib.balance}' if contrib.balance else 'ksh 0'
                        status = 'Fully Paid' if contrib.balance <= 0 else 'Partial' if contrib.amount_paid > 0 else 'Unpaid'
                        
                        if member_id and scheme_id:
                            row = [date_created, amount_expected, amount_paid, balance, status]
                        elif member_id:
                            row = [scheme_name, date_created, amount_expected, amount_paid, balance, status]
                        elif scheme_id:
                            row = [member_name, date_created, amount_expected, amount_paid, balance, status]
                        else:
                            row = [member_name, scheme_name, date_created, amount_expected, amount_paid, balance, status]
                        
                        data.append(row)
                    except Exception as e:
                        # Add error row
                        error_row = ['Error'] + [f'Error: {str(e)[:20]}'] * (len(data[0]) - 1)
                        data.append(error_row)

            # 6) Create table with repeating header row
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
                ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
                ('GRID',         (0, 0), (-1, -1), 1, colors.black),
            ]))

            # 7) Build story
            story = [
                Spacer(1, 40),
                table
            ]
            doc.build(story)
            return response
            
        except Exception as e:
            # Return error PDF if something goes wrong
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="contribution_report_error.pdf"'
            
            error_doc = BaseDocTemplate(
                response,
                pagesize=letter,
                leftMargin=36, rightMargin=36,
                topMargin=72, bottomMargin=36
            )
            error_frame = Frame(
                error_doc.leftMargin, error_doc.bottomMargin,
                error_doc.width, error_doc.height,
                id='normal'
            )
            
            def draw_error_header(canvas, doc):
                canvas.saveState()
                canvas.setFont('Times-Bold', 16)
                canvas.drawCentredString(letter[0]/2, letter[1]-40, "Error Generating Report")
                canvas.setFont('Times-Roman', 12)
                canvas.drawCentredString(letter[0]/2, letter[1]-60, f"Error: {str(e)}")
                canvas.restoreState()
            
            error_doc.addPageTemplates([
                PageTemplate(id='WithHeader', frames=error_frame, onPage=draw_error_header)
            ])
            
            error_data = [['Error Type', 'Description'], ['Contribution Report Error', str(e)[:100]]]
            error_table = Table(error_data)
            error_doc.build([Spacer(1, 40), error_table])
            return response
    
    @staticmethod
    def download_collected_fine_report(request, chama_id):
        # 1) Fetch Chama and cleared fines
        chama = Chama.objects.get(pk=chama_id)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        
        # Base queryset for cleared fines
        fines = FineItem.objects.filter(fine_type__chama=chama, status='cleared')
        
        # Apply date filters
        if start_date:
            fines = fines.filter(created__date__gte=start_date)
        if end_date:
            fines = fines.filter(created__date__lte=end_date)
            
        fines = fines.order_by('-created')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{chama.name}_collected_fines_report.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            # Main title
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            # Subtitle and date
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                "Collected Fines Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data
        data = [[
            'Member', 'Type', 'Amount', 'Paid Amount',
            'Balance', 'Status', 'Created', 'Last Updated'
        ]]
        for fine in fines:
            data.append([
                fine.member.name,
                fine.fine_type.name,
                f'ksh {fine.fine_amount}',
                f'ksh {fine.paid_fine_amount}',
                f'ksh {fine.fine_balance}',
                fine.status,
                fine.created.strftime('%Y-%m-%d'),
                fine.last_updated.strftime('%Y-%m-%d')
            ])

        # 5) Create table with header row repeated
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 6) Assemble and build document
        story = [
            Spacer(1, 40),  # space below header
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_uncollected_fines_report(request, chama_id):
        # 1) Fetch Chama and active fines
        chama = Chama.objects.get(pk=chama_id)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        
        # Base queryset for active fines
        fines = FineItem.objects.filter(fine_type__chama=chama, status='active')
        
        # Apply date filters
        if start_date:
            fines = fines.filter(created__date__gte=start_date)
        if end_date:
            fines = fines.filter(created__date__lte=end_date)
            
        fines = fines.order_by('-created')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{chama.name}_uncollected_fines_report.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                "Uncollected Fines Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data
        data = [[
            'Member', 'Type', 'Amount', 'Paid Amount',
            'Balance', 'Status', 'Created', 'Last Updated'
        ]]
        for fine in fines:
            data.append([
                fine.member.name,
                fine.fine_type.name,
                f'ksh {fine.fine_amount}',
                f'ksh {fine.paid_fine_amount}',
                f'ksh {fine.fine_balance}',
                fine.status,
                fine.created.strftime('%Y-%m-%d'),
                fine.last_updated.strftime('%Y-%m-%d')
            ])

        # 5) Create table with header row repeated
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 6) Assemble and build document
        story = [
            Spacer(1, 40),
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_cashflow_report(chama_id):
         # 1) Fetch Chama and Cashflow Report data
        chama = Chama.objects.get(pk=chama_id)
        reports = CashflowReport.objects.filter(chama=chama).order_by('-date_created')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{chama.name}_cashflow_report.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                "Cashflow Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data
        data = [['Member', 'Type', 'Amount', 'Date Created']]
        for report in reports:
            member_name = report.member.name if report.member else 'Group'
            data.append([
                member_name,
                report.type,
                f'ksh {report.amount}',
                report.object_date.strftime('%Y-%m-%d')
            ])

        # 5) Create table with header row repeated
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 6) Assemble and build document
        story = [
            Spacer(1, 40),
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_member_cashflow_report(chama_id,member_id):
        # 1) Fetch Chama, Member, and Cashflow Report data
        chama  = Chama.objects.get(pk=chama_id)
        member = ChamaMember.objects.get(pk=member_id)
        reports = CashflowReport.objects.filter(chama=chama, member=member).order_by('-date_created')

        # 2) Prepare PDF response & BaseDocTemplate
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{member.name}_cashflow_report.pdf"'
        )

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                f"{member.name} Cashflow Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Build table data
        data = [['Member', 'Type', 'Amount', 'Date Created']]
        for report in reports:
            data.append([
                report.member.name,
                report.type,
                f'ksh {report.amount}',
                report.date_created.strftime('%Y-%m-%d')
            ])

        # 5) Create table with header row repeated
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 6) Assemble and build document
        story = [
            Spacer(1, 40),
            table
        ]
        doc.build(story)
        return response
    
    @staticmethod
    def download_my_cashflow_report(request,chama_id):
        # 1) Fetch Chama and current user's member record
        chama = Chama.objects.get(pk=chama_id)
        try:
            user_member = chama.member.get(user=request.user)
        except ChamaMember.DoesNotExist:
            return HttpResponse("You are not a member of this chama.", status=403)

        # 2) Fetch Cashflow Reports
        reports = CashflowReport.objects.filter(chama=chama, member=user_member).order_by('-date_created')

        # 3) Create PDF response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="my_cashflow_report.pdf"'

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 4) Header callback for every page
        def draw_header(canvas, doc):
            canvas.saveState()
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                "My Cashflow Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 5) Build table data
        data = [['Member', 'Type', 'Amount', 'Date Created']]
        for report in reports:
            data.append([
                report.member.name,
                report.type,
                f'ksh {report.amount}',
                report.date_created.strftime('%Y-%m-%d')
            ])

        # 6) Create and style table
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 7) Assemble and build document
        story = [
            Spacer(1, 40),
            table
        ]
        doc.build(story)

        return response
    
    @staticmethod
    def download_expense_report(request, chama_id):
        # 1) Retrieve Chama and expenses
        chama = Chama.objects.get(pk=chama_id)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        
        # Base queryset for expenses
        expenses = Expense.objects.filter(chama=chama)
        
        # Apply date filters
        if start_date:
            expenses = expenses.filter(created_on__date__gte=start_date)
        if end_date:
            expenses = expenses.filter(created_on__date__lte=end_date)
            
        expenses = expenses.order_by('-created_on')

        # 2) Create PDF response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="expense_report.pdf"'

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback
        def draw_header(canvas, doc):
            canvas.saveState()
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                "Expense Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Define table data
        data = [['Name', 'Created By', 'Created On', 'Amount']]
        for expense in expenses:
            data.append([
                expense.name,
                expense.created_by.name if expense.created_by else '',
                expense.created_on.strftime('%Y-%m-%d') if expense.created_on else '',
                f'ksh {expense.amount}'
            ])

        # 5) Create and style table
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 6) Assemble and build document
        story = [
            Spacer(1, 40),
            table
        ]
        doc.build(story)

        return response

    @staticmethod
    def download_group_investments(request, chama_id):
        # 1) Fetch Chama and group investments
        chama = Chama.objects.get(pk=chama_id)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        
        # Base queryset for group investments
        investments = Investment.objects.filter(chama=chama, forGroup=True)
        
        # Apply date filters
        if start_date:
            investments = investments.filter(date__date__gte=start_date)
        if end_date:
            investments = investments.filter(date__date__lte=end_date)
            
        investments = investments.order_by('-date')

        # 2) Create PDF response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="group_investments_report.pdf"'

        doc = BaseDocTemplate(
            response,
            pagesize=letter,
            leftMargin=36, rightMargin=36,
            topMargin=72, bottomMargin=36
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )

        # 3) Header callback
        def draw_header(canvas, doc):
            canvas.saveState()
            canvas.setFont('Times-Bold', 16)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 40,
                chama.name
            )
            canvas.setFont('Times-Bold', 12)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 60,
                "Group Investments Report"
            )
            canvas.setFont('Times-Roman', 10)
            canvas.drawCentredString(
                letter[0] / 2, letter[1] - 75,
                datetime.now().strftime('%Y-%m-%d')
            )
            canvas.restoreState()

        doc.addPageTemplates([
            PageTemplate(id='WithHeader', frames=frame, onPage=draw_header)
        ])

        # 4) Define table data
        data = [['Investment Name', 'Amount', 'Date']]
        for investment in investments:
            data.append([
                investment.name,
                f'ksh {investment.amount}',
                investment.date.strftime('%Y-%m-%d') if investment.date else ''
            ])

        # 5) Create and style table
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1, 0), 'Times-Bold'),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 12),
            ('GRID',         (0, 0), (-1, -1), 1, colors.black),
        ]))

        # 6) Assemble and build document
        story = [
            Spacer(1, 40),
            table
        ]
        doc.build(story)

        return response



