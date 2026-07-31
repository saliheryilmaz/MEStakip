"""
Management command: DİA bağlantısını test et.

Kullanım:
    python manage.py dia_test_baglanti
    python manage.py dia_test_baglanti --sunucu diademo --kullanici ws --sifre ws
    python manage.py dia_test_baglanti --firma 34 --donem 1

Bu komut Celery olmadan doğrudan çalışır — kurulum doğrulaması için idealdir.
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'DİA ERP bağlantısını test eder (login → firma/dönem sorgula → logout)'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--sunucu', type=str, help='DİA sunucu kodu (varsayılan: .env\'den)')
        parser.add_argument('--kullanici', type=str, help='DİA kullanıcı adı')
        parser.add_argument('--sifre', type=str, help='DİA şifre')
        parser.add_argument('--firma', type=str, help='Firma kodu')
        parser.add_argument('--donem', type=str, help='Dönem kodu')
        parser.add_argument(
            '--firma-donem-kaydet',
            action='store_true',
            default=False,
            help='Firma/dönem bilgisini aktif DiaBaglanti kaydına kaydet',
        )

    def handle(self, *args, **options) -> None:
        from dia_integration.client import DiaClient
        from dia_integration.exceptions import DiaBaseError

        kwargs: dict = {}
        if options['sunucu']:
            kwargs['server_code'] = options['sunucu']
        if options['kullanici']:
            kwargs['username'] = options['kullanici']
        if options['sifre']:
            kwargs['password'] = options['sifre']
        if options['firma']:
            kwargs['firma_kodu'] = options['firma']
        if options['donem']:
            kwargs['donem_kodu'] = options['donem']

        self.stdout.write('DİA bağlantısı test ediliyor...')

        try:
            baslangic = time.monotonic()
            client = DiaClient(**kwargs)

            # 1. Login
            self.stdout.write('  [1/3] Login yapılıyor...')
            session_id = client.login()
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Login başarılı. Session: {session_id[:8]}...')
            )

            # 2. Firma/dönem bilgisi
            self.stdout.write('  [2/3] Firma/dönem/şube/depo bilgisi sorgulanıyor...')
            yanit = client.ozel_cagri(
                modul='sis',
                servis_adi='sis_yetkili_firma_donem_sube_depo',
                data={},
            )
            firmalar = yanit.get('result', [])
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ {len(firmalar)} firma bulundu.')
            )
            for firma in firmalar:
                donemler = firma.get('donemler', [])
                subeler = firma.get('subeler', [])
                self.stdout.write(
                    f'    Firma: {firma.get("firmaadi", firma.get("unvan", "?"))} '
                    f'(kod: {firma.get("firmakodu", firma.get("kod", "?"))}) — '
                    f'{len(donemler)} dönem, {len(subeler)} şube'
                )

            # İsteğe bağlı: firma/dönem bilgisini kaydet
            if options['firma_donem_kaydet']:
                from dia_integration.models import DiaBaglanti
                from django.utils import timezone
                baglanti = DiaBaglanti.objects.filter(is_aktif=True).first()
                if baglanti:
                    baglanti.firma_donem_bilgisi = firmalar
                    baglanti.firma_donem_guncellendi = timezone.now()
                    baglanti.save(update_fields=['firma_donem_bilgisi', 'firma_donem_guncellendi'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Firma/dönem bilgisi DiaBaglanti #{baglanti.pk} kaydına yazıldı.'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            '  ⚠ Aktif DiaBaglanti kaydı bulunamadı; kaydetme atlandı.'
                        )
                    )

            # 3. Logout
            self.stdout.write('  [3/3] Logout yapılıyor...')
            client.logout()
            self.stdout.write(self.style.SUCCESS('  ✓ Logout başarılı.'))

            sure = time.monotonic() - baslangic
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Bağlantı testi tamamlandı. Toplam süre: {sure:.2f}s'
                )
            )

        except DiaBaseError as exc:
            raise CommandError(f'DİA hatası: {exc}') from exc
        except Exception as exc:
            raise CommandError(f'Beklenmedik hata: {exc}') from exc
