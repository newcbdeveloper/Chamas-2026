from bot.models import *
from django.conf import settings
from decimal import Decimal, InvalidOperation
from django.db.models import Q
from .message_service import MessageService


class ContributionService:
    INFOBIP_API_KEY   = settings.INFOBIP_API_KEY
    INFOBIP_SENDER_ID = settings.INFOBIP_SENDER_ID     
    INFOBIP_BASE_URL  = "https://api.infobip.com"

    @staticmethod
    def process_contribution(message, sender):
        member_id         = message['member_id']
        raw_amount        = message['amount']
        contribution_name = message['contribution_name']
        chama_name        = message['chama_name']

        # 1) Parse amount into Decimal
        try:
            # support commas: "2,000" → "2000"
            amount = Decimal(str(raw_amount).replace(',', '').strip())
        except (InvalidOperation, AttributeError):
            return MessageService.send_message(
                f"Invalid amount '{raw_amount}'. Please provide a numeric value.",
                sender
            )

        # 2) Find the chama
        terms = chama_name.strip().split()
        q = Q()
        for term in terms:
            q &= Q(name__icontains=term)
        chamas = Chama.objects.filter(q)

        if not chamas.exists():
            return MessageService.send_message(f"No chama found matching '{chama_name}'", sender)
        if chamas.count() > 1:
            chamas = chamas.filter(chamamember__member_id=member_id).distinct()
            if not chamas.exists():
                return MessageService.send_message(
                    f"Multiple chamas match '{chama_name}', but none have member {member_id}",
                    sender
                )
        chama = chamas.first()

        # 3) Find the contribution definition
        contributions = Contribution.objects.filter(
            name__icontains=contribution_name,
            chama=chama
        )
        if not contributions.exists():
            return MessageService.send_message(
                f"No contribution named '{contribution_name}' in chama '{chama.name}'",
                sender
            )
        contribution = contributions.first()

        # 4) Find the member
        member = ChamaMember.objects.filter(member_id=member_id, group=chama).first()
        if not member:
            admin_role = Role.objects.filter(name='admin').first()
            admin = ChamaMember.objects.filter(group=chama,role=admin_role).first()

            if admin.user.username != member_id:
                return MessageService.send_message("Member not found in the chama", sender)
            
            else:
                member = admin

            

        # 5) Compute balance
        balance = contribution.amount - amount
        bot_contribution = BotContribution.objects.create(
            submitted_contribution = contribution_name,
            retrieved_contribution = contribution,
            amount_paid            = amount,
            submitted_member       = f"{member.name} - {member.mobile}",
            submitted_chama        = chama_name,
            retrieved_chama        = chama,
            chama                  = chama,
            member_id              = member_id,
            sender=sender
        )


        # 7) Create real ContributionRecord
        record = ContributionRecord.objects.create(
            contribution    = contribution,
            date_created    = bot_contribution.date_created,
            amount_expected = contribution.amount,
            amount_paid     = amount,
            balance         = balance,
            member          = member,
            chama           = chama,
        )

        bot_contribution.record = record
        bot_contribution.save()

        # 8) Notify user
        return MessageService.send_message("Contribution recorded successfully ✅", sender)
    
    