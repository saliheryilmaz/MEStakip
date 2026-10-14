"""
Management command: DİA cari senkronizasyonu.

Kullanım:
    python manage.py dia_sync_cari               # delta sync (varsayılan)
    python manage.py dia_sync_cari --tam          # tam sync (tüm cariler)
    python manage.py dia_sync_cari --sayfa 50     # sayfa boyutu
    python manage.py dia_sync_cari --kuru-calis   # veritabanına yazmadan test
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'DİA\'dan cari listesini MEStakip\'e senkronize eder'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--tam',
            action='store_true',
            default=False,
            help='Tam sync: tüm carileri çek (varsayılan: sadece değişenler)',
        )
        parser.add_argument(
            '--sayfa',
            type=int,
            default=100,
            help='Sayfa boyutu (varsayılan: 100)',
        )
        parser.add_argument(
            '--kuru-calis',
            action='store_true',
            default=False,
            help='DİA\'dan çek ama veritabanına yazma (test modu)',
        )

    def handle(self, *args, **options) -> None:
        from dia_integration.services import CariService
        from dia_integration.models import SyncTetikleyen
        from dia_integration.exceptions import DiaBaseError

        delta = not options['tam']
        sayfa = options['sayfa']
        kuru = options['kuru_calis']

        mod = 'DELTA' if delta else 'TAM'
        self.stdout.write(f'Cari sync başlıyor... [{mod} mod, sayfa:{sayfa}]')

        if kuru:
            self.stdout.write(self.style.WARNING('⚠ KURU ÇALIŞMA — veritabanına yazılmayacak'))
            # Sadece bağlantı ve ilk sayfayı test et
            from dia_integration.client import DiaClient
            try:
                with DiaClient() as client:
                    sayfa_data = client.listele(
                        modul='scf',
                        servis_adi='scf_carikart_listele',
                        limit=sayfa,
                    )
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {len(sayfa_data)} cari çekildi (yazılmadı).')
                )
                if sayfa_data:
                    ornek = sayfa_data[0]
                    self.stdout.write(
                        f'  Örnek: {ornek.get("carikartkodu")} — {ornek.get("unvan")}'
                    )
            except DiaBaseError as exc:
                raise CommandError(f'DİA hatası: {exc}') from exc
            return

        try:
            sonuc = CariService.dia_dan_senkronize_et(
                delta=delta,
                sayfa_boyutu=sayfa,
                tetikleyen=SyncTetikleyen.SISTEM,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Cari sync tamamlandı:\n'
                    f'  Toplam işlenen : {sonuc.toplam}\n'
                    f'  Yeni eklenen   : {sonuc.eklenen}\n'
                    f'  Güncellenen    : {sonuc.guncellenen}\n'
                    f'  Hatalı         : {sonuc.hatali}'
                )
            )

            if sonuc.hatalar:
                self.stdout.write(self.style.WARNING('\nHatalar:'))
                for hata in sonuc.hatalar[:10]:
                    self.stdout.write(f'  - {hata}')
                if len(sonuc.hatalar) > 10:
                    self.stdout.write(f'  ... ve {len(sonuc.hatalar) - 10} hata daha')

        except DiaBaseError as exc:
            raise CommandError(f'DİA hatası: {exc}') from exc
        except Exception as exc:
            raise CommandError(f'Beklenmedik hata: {exc}') from exc
