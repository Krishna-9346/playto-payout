from django.core.management.base import BaseCommand
from django.db import transaction
from payouts.models import Merchant, BankAccount, LedgerEntry

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with transaction.atomic():
            # Merchant 1
            m1, _ = Merchant.objects.get_or_create(name='Rahul Designs', email='rahul@example.com')
            BankAccount.objects.get_or_create(merchant=m1, account_number='1234567890',
                ifsc_code='HDFC0001234', account_holder_name='Rahul Kumar')
            LedgerEntry.objects.create(merchant=m1, entry_type='credit',
                amount_paise=500000, description='Payment from client USA - $60')
            LedgerEntry.objects.create(merchant=m1, entry_type='credit',
                amount_paise=250000, description='Payment from client UK - $30')

            # Merchant 2
            m2, _ = Merchant.objects.get_or_create(name='Priya Consulting', email='priya@example.com')
            BankAccount.objects.get_or_create(merchant=m2, account_number='9876543210',
                ifsc_code='ICIC0005678', account_holder_name='Priya Singh')
            LedgerEntry.objects.create(merchant=m2, entry_type='credit',
                amount_paise=1000000, description='Payment from client Germany - $120')

        self.stdout.write(self.style.SUCCESS('Seeded successfully'))