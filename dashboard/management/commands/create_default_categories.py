from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from dashboard.models import TransactionCategory

class Command(BaseCommand):
    help = 'Her kullanıcı için varsayılan kategoriler oluşturur'

    def handle(self, *args, **options):
        # Varsayılan kategoriler
        default_categories = [
            'Satış',
            'Alış',
            'Personel Giderleri',
            'Kira',
            'Elektrik',
            'Su',
            'Telefon',
            'İnternet',
            'Yakıt',
            'Bakım-Onarım',
            'Vergi',
            'Sigorta',
            'Banka Masrafları',
            'Diğer Gelirler',
            'Diğer Giderler'
        ]
        
        users = User.objects.all()
        
        for user in users:
            self.stdout.write(f'Kullanıcı: {user.username} için kategoriler oluşturuluyor...')
            
            for category_name in default_categories:
                # Kategori zaten varsa atla
                if not TransactionCategory.objects.filter(name=category_name, created_by=user, parent=None).exists():
                    TransactionCategory.objects.create(
                        name=category_name,
                        created_by=user,
                        parent=None
                    )
                    self.stdout.write(f'  - {category_name} kategorisi oluşturuldu')
                else:
                    self.stdout.write(f'  - {category_name} kategorisi zaten mevcut')
        
        self.stdout.write(self.style.SUCCESS('Varsayılan kategoriler başarıyla oluşturuldu!'))