from django.core.management.base import BaseCommand
from django.db.models import Q
from account.models import User
import shortuuid


class Command(BaseCommand):
    help = 'Populate referral codes for all users who don\'t have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate codes for all users (including those who already have codes)',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        # Filter for users without referral codes
        if force:
            users_to_update = User.objects.all()
            self.stdout.write(self.style.WARNING('Regenerating codes for ALL users...'))
        else:
            users_to_update = User.objects.filter(Q(refferal_code__isnull=True) | Q(refferal_code=''))
            self.stdout.write(f'Found {users_to_update.count()} users without referral codes')
        
        if not users_to_update.exists():
            self.stdout.write(self.style.SUCCESS('All users already have referral codes!'))
            return
        
        # Initialize ShortUUID with same settings as model
        su = shortuuid.ShortUUID(alphabet='FR1234567890')
        updated_count = 0
        
        for user in users_to_update:
            # Generate a unique code with prefix
            code = 'AB' + su.random(8)
            
            # Ensure it's unique
            attempts = 0
            while User.objects.filter(refferal_code=code).exclude(pk=user.pk).exists() and attempts < 100:
                code = 'AB' + su.random(8)
                attempts += 1
            
            if attempts >= 100:
                self.stdout.write(self.style.ERROR(f'Could not generate unique code for user {user.email}'))
                continue
            
            user.refferal_code = code
            user.save(update_fields=['refferal_code'])
            updated_count += 1
            self.stdout.write(f'✓ {user.email}: {code}')
        
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully updated {updated_count} users'))
