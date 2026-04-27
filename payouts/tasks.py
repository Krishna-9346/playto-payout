from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Payout, LedgerEntry
import random
import time

@shared_task
def process_payout(payout_id):
    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        return

    if payout.status != 'pending':
        return

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        payout.transition_to('processing')
        payout.processing_started_at = timezone.now()
        payout.attempts += 1
        payout.save(update_fields=['processing_started_at', 'attempts', 'updated_at'])

    # Simulate bank call
    time.sleep(2)
    outcome = random.choices(
        ['success', 'failure', 'processing'],
        weights=[70, 20, 10]
    )[0]

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)

        if outcome == 'success':
            payout.transition_to('completed')

        elif outcome == 'failure':
            payout.transition_to('failed')
            # Return funds atomically
            LedgerEntry.objects.create(
                merchant=payout.merchant,
                entry_type='credit',
                amount_paise=payout.amount_paise,
                description=f'Payout failed - funds returned - {payout.id}',
                payout=payout,
            )

@shared_task
def retry_stuck_payouts():
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(seconds=30)

    # Retry stuck payouts
    stuck = Payout.objects.filter(
        status='processing',
        processing_started_at__lt=cutoff,
        attempts__lt=3
    )
    for payout in stuck:
        process_payout.delay(str(payout.id))

    # Fail payouts that exceeded max attempts
    failed_stuck = Payout.objects.filter(
        status='processing',
        processing_started_at__lt=cutoff,
        attempts__gte=3
    )
    for payout in failed_stuck:
        with transaction.atomic():
            p = Payout.objects.select_for_update().get(id=payout.id)
            p.transition_to('failed')
            LedgerEntry.objects.create(
                merchant=p.merchant,
                entry_type='credit',
                amount_paise=p.amount_paise,
                description=f'Max retries exceeded - funds returned - {p.id}',
                payout=p,
            )