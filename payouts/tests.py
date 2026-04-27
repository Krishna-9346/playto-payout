from django.test import TestCase, TransactionTestCase
from concurrent.futures import ThreadPoolExecutor
from .models import Merchant, BankAccount, LedgerEntry
from .services import create_payout
import uuid

class ConcurrencyTest(TransactionTestCase):
    def test_two_simultaneous_payouts_only_one_succeeds(self):
        merchant = Merchant.objects.create(
            name='Test Merchant', 
            email='test@test.com'
        )
        bank = BankAccount.objects.create(
            merchant=merchant,
            account_number='111',
            ifsc_code='TEST0001',
            account_holder_name='Test User'
        )
        LedgerEntry.objects.create(
            merchant=merchant,
            entry_type='credit',
            amount_paise=10000,
            description='Test credit'
        )

        results = []

        def request_payout():
            body, status, _ = create_payout(
                merchant, 6000, bank, str(uuid.uuid4())
            )
            results.append(status)

        with ThreadPoolExecutor(max_workers=2) as ex:
            ex.submit(request_payout)
            ex.submit(request_payout)

        success_count = results.count(201)
        fail_count = results.count(400)
        self.assertEqual(success_count, 1, "Exactly one payout should succeed")
        self.assertEqual(fail_count, 1, "Exactly one should fail")

class IdempotencyTest(TestCase):
    def test_same_key_returns_same_response(self):
        merchant = Merchant.objects.create(
            name='Test Merchant 2',
            email='test2@test.com'
        )
        bank = BankAccount.objects.create(
            merchant=merchant,
            account_number='222',
            ifsc_code='TEST0002',
            account_holder_name='Test User 2'
        )
        LedgerEntry.objects.create(
            merchant=merchant,
            entry_type='credit',
            amount_paise=20000,
            description='Test credit'
        )

        key = str(uuid.uuid4())
        body1, status1, dup1 = create_payout(merchant, 5000, bank, key)
        body2, status2, dup2 = create_payout(merchant, 5000, bank, key)

        self.assertEqual(status1, 201)
        self.assertEqual(status2, 201)
        self.assertEqual(body1['id'], body2['id'])
        self.assertFalse(dup1)
        self.assertTrue(dup2)
        self.assertEqual(merchant.payouts.count(), 1)