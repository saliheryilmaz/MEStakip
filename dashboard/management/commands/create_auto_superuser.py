"""
Auto-create superuser if none exists
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from dashboard.models import UserProfile
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Automatically create superuser if none exists'

    def handle(self, *args, **options):
        # Production environment'de çalış
        if not os.environ.get('DEBUG', 'False').lower() == 'true':
            # Eğer hiç kullanıcı yoksa, otomatik oluştur
            if User.objects.filter(is_superuser=True).count() == 0:
                username = os.environ.get('ADMIN_USERNAME', 'admin')
                email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
                password = os.environ.get('ADMIN_PASSWORD', '').strip()
                if not password:
                    raise CommandError('ADMIN_PASSWORD boş bırakılamaz.')
                
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_superuser(
                        username=username,
                        email=email,
                        password=password
                    )
                    
                    # UserProfile oluştur ve role='admin' ver
                    UserProfile.objects.get_or_create(
                        user=user,
                        defaults={'role': 'admin'}
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Superuser "{username}" otomatik oluşturuldu! (Role: admin)'
                        )
                    )
                else:
                    # Kullanıcı var ama profil yoksa oluştur
                    user = User.objects.get(username=username)
                    profile, created = UserProfile.objects.get_or_create(
                        user=user,
                        defaults={'role': 'admin'}
                    )
                    if not created and profile.role != 'admin':
                        # Profil var ama role admin değilse güncelle
                        profile.role = 'admin'
                        profile.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✅ User "{username}" profili admin rolüne güncellendi!'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠️  Superuser "{username}" zaten var'
                            )
                        )
            else:
                # Superuser var ama profil kontrolü yap
                admin_users = User.objects.filter(is_superuser=True)
                for user in admin_users:
                    profile, created = UserProfile.objects.get_or_create(
                        user=user,
                        defaults={'role': 'admin'}
                    )
                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✅ User "{user.username}" için admin profili oluşturuldu!'
                            )
                        )
                    elif profile.role != 'admin':
                        profile.role = 'admin'
                        profile.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✅ User "{user.username}" profili admin rolüne güncellendi!'
                            )
                        )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        '✅ Superuser zaten mevcut'
                    )
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    'ℹ️  Local environment - skipping auto superuser'
                )
            )
