# EXPLAINER.md

## 1. The Ledger

**Balance calculation query:**
```python
result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
    credits=Sum('amount_paise', filter=Q(entry_type='credit')),
    debits=Sum('amount_paise', filter=Q(entry_type='debit')),
)
balance = (result['credits'] or 0) - (result['debits'] or 0)
```

I modeled credits and debits as separate ledger entries instead of
storing a balance column. This means every rupee is traceable.
The balance is always derived from the sum of all transactions —
you can never have a balance that doesn't match the history.
Amounts are stored as BigIntegerField in paise (1 rupee = 100 paise)
to avoid floating point errors completely.

## 2. The Lock

**Exact code that prevents overdraft:**
```python
with transaction.atomic():
    merchant_locked = Merchant.objects.select_for_update().get(id=merchant.id)
    balance = get_merchant_balance(merchant_locked)
    if amount_paise > balance:
        return {'error': 'Insufficient balance'}, 400, False
    # deduct funds here
```

This relies on PostgreSQL row-level locking. SELECT FOR UPDATE
acquires an exclusive lock on the merchant row. Any concurrent
transaction attempting the same lock will WAIT at the database
level until the first transaction commits. This is a database
primitive — not Python threading. Python locks don't work across
multiple processes or database connections.

## 3. The Idempotency

The system checks the IdempotencyKey table before acquiring any lock.
If the key exists for that merchant, it returns the stored response
immediately without creating a new payout.

If the first request is still in-flight when the second arrives and
hasn't committed yet, both might pass the initial check. However,
the unique_together constraint on (key, merchant) means only one
INSERT will succeed — the other raises IntegrityError which we
catch and treat as a duplicate. Keys expire after 24 hours.

## 4. The State Machine

Located in `payouts/models.py` in the `Payout` model:

```python
ALLOWED_TRANSITIONS = {
    'pending': ['processing'],
    'processing': ['completed', 'failed'],
    'completed': [],
    'failed': [],
}

def transition_to(self, new_status):
    if new_status not in self.ALLOWED_TRANSITIONS[self.status]:
        raise ValueError(f"Illegal transition: {self.status} → {new_status}")
    self.status = new_status
    self.save(update_fields=['status', 'updated_at'])
```

`completed: []` means no transitions out of completed are allowed.
`failed: []` means failed is also terminal. The check happens before
every status change so it is impossible to go backwards.

## 5. The AI Audit

**What AI gave me (wrong):**
```python
# AI suggested calculating balance in Python like this
payouts = Payout.objects.filter(merchant=merchant, status='pending')
total = sum([p.amount_paise for p in payouts])
if total > balance:
    return error
```

**What was wrong:**
This fetches all rows into Python memory and sums them there.
Between the fetch and the check, another transaction could insert
a new payout — classic TOCTOU race condition. Also uses Python
arithmetic on fetched rows instead of database-level aggregation.

**What I replaced it with:**
```python
with transaction.atomic():
    merchant_locked = Merchant.objects.select_for_update().get(id=merchant.id)
    balance = LedgerEntry.objects.filter(merchant=merchant).aggregate(
        credits=Sum('amount_paise', filter=Q(entry_type='credit')),
        debits=Sum('amount_paise', filter=Q(entry_type='debit')),
    )
    # check and deduct inside same transaction
```

The entire check-and-deduct happens inside one atomic transaction
with a database lock. No other transaction can interfere.