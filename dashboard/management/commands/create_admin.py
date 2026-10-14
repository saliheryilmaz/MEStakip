from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from dashboard.models import UserProfile

class Command(BaseCommand):
    help = 'İlk admin kullanıcısını oluşturur'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help='Admin kullanıcı adı')
        parser.add_argument('--password', type=str, default='admin123', help='Admin şifresi')
        parser.add_argument('--email', type=str, default='admin@example.com', help='Admin e-posta')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        
        # Kullanici zaten var mi kontrol et
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Kullanici "{username}" zaten mevcut!')
            )
            return
        
        # Admin kullanicisi olustur
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name='Admin',
            last_name='User',
            is_staff=True,
            is_superuser=True
        )
        
        # Admin profili olustur
        UserProfile.objects.create(user=user, role='admin')
        
        self.stdout.write(
            self.style.SUCCESS(f'Admin kullanicisi basariyla olusturuldu!')
        )
        self.stdout.write(f'Kullanici Adi: {username}')
        self.stdout.write(f'Sifre: {password}')
        self.stdout.write(f'E-posta: {email}')
