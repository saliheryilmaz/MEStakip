"""
Management command: Veritabanında DiaBaglanti kaydı oluştur.

Kullanım:
    python manage.py dia_baglanti_olustur
    python manage.py dia_baglanti_olustur --ad "Meslas Demo" --sunucu diademo

Mevcut aktif bağlantı varsa günceller, yoksa yeni oluşturur.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Aktif DiaBaglanti kaydını oluşturur veya günceller (.env değerleriyle)'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--ad',
            type=str,
            default='Varsayılan DİA Bağlantısı',
            help='Bağlantı adı',
        )
        parser.add_argument(
            '--sunucu',
            type=str,
            help='DİA sunucu kodu (varsayılan: .env DIA_SERVER_CODE)',
        )

    def handle(self, *args, **options) -> None:
        from dia_integration.models import DiaBaglanti

        sunucu = options['sunucu'] or settings.DIA_SERVER_CODE
        ad = options['ad']

        # Şifreyi maskelenmiş olarak sakla (son 2 karakter görünür)
        gercek_sifre = settings.DIA_PASSWORD
        maskeli = '*' * max(0, len(gercek_sifre) - 2) + gercek_sifre[-2:] if gercek_sifre else '***'

        baglanti, olusturuldu = DiaBaglanti.objects.update_or_create(
            sunucu_kodu=sunucu,
            firma_kodu=settings.DIA_FIRMA_KODU,
            defaults={
                'ad': ad,
                'kullanici_adi': settings.DIA_USERNAME,
                'sifre_maskelenmiş': maskeli,
                'donem_kodu': settings.DIA_DONEM_KODU,
                'is_aktif': True,
            },
        )

        if olusturuldu:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ DiaBaglanti oluşturuldu: #{baglanti.pk} "{baglanti.ad}"'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ DiaBaglanti güncellendi: #{baglanti.pk} "{baglanti.ad}"'
                )
            )

        DiaBaglanti.objects.exclude(pk=baglanti.pk).update(is_aktif=False)

        self.stdout.write(
            f'  Sunucu  : {baglanti.sunucu_kodu}\n'
            f'  Kullanıcı: {baglanti.kullanici_adi}\n'
            f'  Firma   : {baglanti.firma_kodu} / Dönem: {baglanti.donem_kodu}\n'
            f'\nBağlantıyı test etmek için:\n'
            f'  python manage.py dia_test_baglanti'
        )
