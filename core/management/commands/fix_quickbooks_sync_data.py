from django.core.management.base import BaseCommand
from django.db import transaction
from collections import defaultdict

from core.models import QuickBooksCustomerSync


class Command(BaseCommand):
    help = 'Fix QuickBooks sync data inconsistencies and constraint violations'

    def handle(self, *args, **options):
        self.stdout.write('🔧 Starting QuickBooks sync data cleanup...')
        
        with transaction.atomic():
            # Find all records with empty string quickbooks_customer_id
            empty_id_records = QuickBooksCustomerSync.objects.filter(
                quickbooks_customer_id=''
            )
            
            empty_count = empty_id_records.count()
            self.stdout.write(f'Found {empty_count} records with empty quickbooks_customer_id')
            
            # Update empty strings to NULL
            if empty_count > 0:
                updated_count = empty_id_records.update(quickbooks_customer_id=None)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Updated {updated_count} records to have NULL quickbooks_customer_id')
                )
            
            # Find and remove duplicate records (keeping the latest one per student)
            all_records = QuickBooksCustomerSync.objects.all().order_by('created_at')
            student_records = defaultdict(list)
            
            # Group records by (tenant, student)
            for record in all_records:
                key = (record.tenant_id, record.student_id)
                student_records[key].append(record)
            
            duplicates_removed = 0
            
            # For each student, keep only the latest record
            for (tenant_id, student_id), records in student_records.items():
                if len(records) > 1:
                    # Keep the latest record, delete the rest
                    records_to_delete = records[:-1]  # All except the last one
                    
                    for record in records_to_delete:
                        self.stdout.write(f'  Removing duplicate record for student {record.student_id}: {record.id}')
                        record.delete()
                        duplicates_removed += 1
            
            if duplicates_removed > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Removed {duplicates_removed} duplicate sync records')
                )
            else:
                self.stdout.write('No duplicate records found')
            
            # Report final state
            total_records = QuickBooksCustomerSync.objects.count()
            synced_records = QuickBooksCustomerSync.objects.filter(sync_status='synced').count()
            pending_records = QuickBooksCustomerSync.objects.filter(sync_status='pending').count()
            failed_records = QuickBooksCustomerSync.objects.filter(sync_status='failed').count()
            
            self.stdout.write('\n📊 Final state:')
            self.stdout.write(f'  Total sync records: {total_records}')
            self.stdout.write(f'  Synced: {synced_records}')
            self.stdout.write(f'  Pending: {pending_records}')
            self.stdout.write(f'  Failed: {failed_records}')
            
            self.stdout.write(
                self.style.SUCCESS('✅ QuickBooks sync data cleanup completed!')
            )