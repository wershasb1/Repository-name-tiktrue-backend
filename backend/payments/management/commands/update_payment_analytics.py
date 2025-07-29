from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from payments.models import PaymentAnalytics

class Command(BaseCommand):
    help = 'Update payment analytics for specified date range'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date to update (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to update (default: 7)',
        )
        parser.add_argument(
            '--from-date',
            type=str,
            help='Start date for range update (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--to-date',
            type=str,
            help='End date for range update (YYYY-MM-DD format)',
        )

    def handle(self, *args, **options):
        if options['date']:
            # Update specific date
            try:
                date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                self.update_date(date)
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD')
                )
                return

        elif options['from_date'] and options['to_date']:
            # Update date range
            try:
                from_date = datetime.strptime(options['from_date'], '%Y-%m-%d').date()
                to_date = datetime.strptime(options['to_date'], '%Y-%m-%d').date()
                self.update_date_range(from_date, to_date)
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD')
                )
                return

        else:
            # Update last N days
            days = options['days']
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days-1)
            self.update_date_range(start_date, end_date)

        self.stdout.write(
            self.style.SUCCESS('Successfully updated payment analytics')
        )

    def update_date(self, date):
        """Update analytics for a specific date"""
        self.stdout.write(f'Updating analytics for {date}...')
        analytics = PaymentAnalytics.update_daily_stats(date)
        self.stdout.write(
            f'  {analytics.total_payments} payments, '
            f'{analytics.successful_payments} successful'
        )

    def update_date_range(self, start_date, end_date):
        """Update analytics for a date range"""
        self.stdout.write(f'Updating analytics from {start_date} to {end_date}...')
        
        current_date = start_date
        total_updated = 0
        
        while current_date <= end_date:
            analytics = PaymentAnalytics.update_daily_stats(current_date)
            self.stdout.write(
                f'  {current_date}: {analytics.total_payments} payments, '
                f'{analytics.successful_payments} successful'
            )
            current_date += timedelta(days=1)
            total_updated += 1
            
        self.stdout.write(f'Updated analytics for {total_updated} days')