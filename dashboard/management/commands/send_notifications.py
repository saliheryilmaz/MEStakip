from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.models import Notification
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Zamanı gelen bildirimleri gönder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Sadece kontrol et, gerçekten gönderme',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        # Zamanı gelen bekleyen bildirimleri bul
        pending_notifications = Notification.objects.filter(
            status='pending',
            scheduled_time__lte=now
        ).select_related('user', 'event')
        
        count = pending_notifications.count()
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'Gönderilecek {count} bildirim bulundu (dry-run modu)')
            )
            for notification in pending_notifications:
                self.stdout.write(f'  - {notification.title} ({notification.user.username})')
            return
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('Gönderilecek bildirim bulunamadı'))
            return
        
        sent_count = 0
        error_count = 0
        
        for notification in pending_notifications:
            try:
                # Bildirimi gönderildi olarak işaretle
                notification.mark_as_sent()
                sent_count += 1
                
                self.stdout.write(
                    f'✓ Bildirim gönderildi: {notification.title} -> {notification.user.username}'
                )
                
                # Burada gerçek bildirim gönderme işlemi yapılabilir
                # Örneğin: email, SMS, push notification vb.
                
            except Exception as e:
                error_count += 1
                logger.error(f'Bildirim gönderilirken hata: {notification.id} - {str(e)}')
                self.stdout.write(
                    self.style.ERROR(f'✗ Hata: {notification.title} - {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'İşlem tamamlandı: {sent_count} başarılı, {error_count} hata'
            )
        )