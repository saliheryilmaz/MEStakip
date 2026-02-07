from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from dashboard.models import JokerSatisDosya, JokerSatisHareketi


class Command(BaseCommand):
    help = 'Joker satış dosyalarına ve hareketlerine kullanıcı ataması yapar'

    def handle(self, *args, **options):
        # İlk admin kullanıcıyı al
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.first()
            
            if not admin_user:
                self.stdout.write(self.style.ERROR('Hiç kullanıcı bulunamadı!'))
                return
            
            # Kullanıcısı olmayan dosyaları güncelle
            dosyalar = JokerSatisDosya.objects.filter(kullanici__isnull=True)
            dosya_count = dosyalar.count()
            dosyalar.update(kullanici=admin_user)
            
            # Kullanıcısı olmayan hareketleri güncelle
            hareketler = JokerSatisHareketi.objects.filter(kullanici__isnull=True)
            hareket_count = hareketler.count()
            hareketler.update(kullanici=admin_user)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Başarıyla {dosya_count} dosya ve {hareket_count} hareket '
                    f'{admin_user.username} kullanıcısına atandı.'
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Hata: {str(e)}'))
