from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Merchant, Payout, LedgerEntry, IdempotencyKey
import uuid

def get_merchant_balance(merchant):
    """
    Calculate balance at the DATABASE level using aggregation.
    Never fetch rows and sum in Python — that's wrong for concurrency.
    """
    result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
        credits=Sum('amount_paise', filter=Q(entry_type='credit')),
        debits=Sum('amount_paise', filter=Q(entry_type='debit')),
    )
    credits = result['credits'] or 0
    debits = result['debits'] or 0
    return credits - debits

def create_payout(merchant, amount_paise, bank_account, idempotency_key):
    """
    The critical function. Uses SELECT FOR UPDATE to prevent overdraft.
    The entire check-and-deduct is one atomic database transaction.
    """
    # First: check idempotency (outside the lock — read-only is fine)
    existing = IdempotencyKey.objects.filter(
        key=idempotency_key, merchant=merchant
    ).first()
    if existing:
        return existing.response_body, existing.response_status, True  # True = was duplicate

    with transaction.atomic():
        # SELECT FOR UPDATE locks this merchant's row until transaction ends.
        # Any other request for this merchant will WAIT here.
        merchant_locked = Merchant.objects.select_for_update().get(id=merchant.id)

        # Now calculate balance safely — no other transaction can modify it
        balance = get_merchant_balance(merchant_locked)

        if amount_paise > balance:
            return {'error': 'Insufficient balance'}, 400, False

        # Create the payout
        payout = Payout.objects.create(
            merchant=merchant_locked,
            bank_account=bank_account,
            amount_paise=amount_paise,
        )

        # Immediately hold the funds (debit entry)
        LedgerEntry.objects.create(
            merchant=merchant_locked,
            entry_type='debit',
            amount_paise=amount_paise,
            description=f'Payout hold - {payout.id}',
            payout=payout,
        )

        response_body = {
            'id': str(payout.id),
            'amount_paise': payout.amount_paise,
            'status': payout.status,
            'created_at': payout.created_at.isoformat(),
        }

        # Store the idempotency key so duplicate requests return same response
        IdempotencyKey.objects.create(
            key=idempotency_key,
            merchant=merchant,
            response_body=response_body,
            response_status=201,
        )

        return response_body, 201, False