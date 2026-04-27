from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Q
from .models import Merchant, BankAccount, Payout, LedgerEntry
from .services import create_payout, get_merchant_balance

class MerchantBalanceView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        total_balance = get_merchant_balance(merchant)

        # "Held" balance = sum of all pending payout debits
        held = LedgerEntry.objects.filter(
            merchant=merchant,
            entry_type='debit',
            payout__status__in=['pending', 'processing']
        ).aggregate(total=Sum('amount_paise'))['total'] or 0

        return Response({
            'merchant_id': merchant.id,
            'merchant_name': merchant.name,
            'available_balance_paise': total_balance - held,
            'held_balance_paise': held,
            'total_balance_paise': total_balance,
        })

class PayoutCreateView(APIView):
    def post(self, request, merchant_id):
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response({'error': 'Idempotency-Key header required'}, status=400)

        try:
            merchant = Merchant.objects.get(id=merchant_id)
            bank_account = BankAccount.objects.get(
                id=request.data.get('bank_account_id'), merchant=merchant
            )
        except (Merchant.DoesNotExist, BankAccount.DoesNotExist):
            return Response({'error': 'Not found'}, status=404)

        amount_paise = request.data.get('amount_paise')
        if not amount_paise or not isinstance(amount_paise, int):
            return Response({'error': 'amount_paise must be an integer'}, status=400)

        response_body, status_code, was_duplicate = create_payout(
            merchant, amount_paise, bank_account, idempotency_key
        )
        return Response(response_body, status=status_code)

class PayoutListView(APIView):
    def get(self, request, merchant_id):
        payouts = Payout.objects.filter(merchant_id=merchant_id).order_by('-created_at')[:20]
        return Response([{
            'id': str(p.id),
            'amount_paise': p.amount_paise,
            'status': p.status,
            'created_at': p.created_at.isoformat(),
        } for p in payouts])