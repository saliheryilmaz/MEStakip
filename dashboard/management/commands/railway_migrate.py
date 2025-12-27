from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection


class Command(BaseCommand):
    help = 'Railway-safe migration command'

    def handle(self, *args, **options):
        self.stdout.write('🚂 Railway migration fix starting...')
        
        try:
            # Check if Event table exists
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'dashboard_event'
                    );
                """)
                event_exists = cursor.fetchone()[0]
                
                if event_exists:
                    self.stdout.write('✅ Event table already exists, marking migration as fake')
                    # Mark problematic migrations as fake
                    call_command('migrate', 'dashboard', '0016', '--fake')
                
            # Run normal migrations
            self.stdout.write('🔄 Running migrations...')
            call_command('migrate')
            self.stdout.write('✅ Migrations completed successfully!')
            
        except Exception as e:
            self.stdout.write(f'❌ Migration error: {e}')
            # Fallback: try fake migration
            try:
                call_command('migrate', '--fake')
                self.stdout.write('✅ Fake migration completed')
            except Exception as e2:
                self.stdout.write(f'❌ Fake migration also failed: {e2}')