"""
Management command: DİA stok senkronizasyonu.

Kullanım:
    python manage.py dia_sync_stok               # delta sync
    python manage.py dia_sync_stok --tam         # tam sync
    python manage.py dia_sync_stok --depolar     # sadece depoları sync et
    python manage.py dia_sync_stok --miktarlar   # sadece depo miktarlarını güncelle
    python manage.py dia_sync_stok --hepsi       # stok + depo + miktar
    python manage.py dia_sync_stok --kuru-calis  # veritabanına yazma
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'DİA\'dan stok kartlarını ve depo miktarlarını MEStakip\'e senkronize eder'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--tam', action='store_true', default=False,
                            help='Tam sync (varsayılan: sadece değişenler)')
        parser.add_argument('--sayfa', type=int, default=100, help='Sayfa boyutu')
        parser.add_argument('--depolar', action='store_true', default=False,
                            help='Sadece depo tanımlarını sync et')
        parser.add_argument('--miktarlar', action='store_true', default=False,
                            help='Sadece depo miktarlarını güncelle')
        parser.add_argument('--hepsi', action='store_true', default=False,
                            help='Stok + depo + miktar — hepsini çalıştır')
        parser.add_argument('--kuru-calis', action='store_true', default=False,
                            help='Veritabanına yazma (test modu)')

    def handle(self, *args, **options) -> None:
        from dia_integration.services import StokService
        from dia_integration.exceptions import DiaBaseError

        kuru = options['kuru_calis']

        if kuru:
            self.stdout.write(self.style.WARNING('⚠ KURU ÇALIŞMA — veritabanına yazılmayacak'))
            from dia_integration.client import DiaClient
            try:
                with DiaClient() as client:
                    sayfa = client.listele('scf', 'scf_stokkart_listele', limit=options['sayfa'])
                self.stdout.write(self.style.SUCCESS(f'✓ {len(sayfa)} stok çekildi (yazılmadı).'))
                if sayfa:
                    self.stdout.write(f'  Örnek: {sayfa[0].get("stokkartkodu")} — {sayfa[0].get("aciklama")}')
            except DiaBaseError as exc:
                raise CommandError(f'DİA hatası: {exc}') from exc
            return

        try:
            # Depo sync
            if options['depolar'] or options['hepsi']:
                self.stdout.write('Depolar senkronize ediliyor...')
                n = StokService.depolari_senkronize_et()
                self.stdout.write(self.style.SUCCESS(f'  ✓ {n} depo senkronize edildi.'))

            # Stok sync (--depolar veya --miktarlar verilmemişse veya --hepsi)
            if not options['depolar'] and not options['miktarlar'] or options['hepsi']:
                delta = not options['tam']
                mod = 'DELTA' if delta else 'TAM'
                self.stdout.write(f'Stok sync başlıyor... [{mod} mod, sayfa:{options["sayfa"]}]')
                sonuc = StokService.dia_dan_senkronize_et(
                    delta=delta,
                    sayfa_boyutu=options['sayfa'],
                )
                self.stdout.write(self.style.SUCCESS(
                    f'\n✓ Stok sync tamamlandı:\n'
                    f'  Toplam    : {sonuc.toplam}\n'
                    f'  Eklenen   : {sonuc.eklenen}\n'
                    f'  Güncellenen: {sonuc.guncellenen}\n'
                    f'  Hatalı    : {sonuc.hatali}'
                ))
                if sonuc.hatalar:
                    self.stdout.write(self.style.WARNING('\nHatalar:'))
                    for h in sonuc.hatalar[:10]:
                        self.stdout.write(f'  - {h}')

            # Depo miktarları
            if options['miktarlar'] or options['hepsi']:
                self.stdout.write('Depo miktarları güncelleniyor...')
                n = StokService.depo_miktarlarini_guncelle()
                self.stdout.write(self.style.SUCCESS(f'  ✓ {n} stok-depo miktarı güncellendi.'))

        except DiaBaseError as exc:
            raise CommandError(f'DİA hatası: {exc}') from exc
        except Exception as exc:
            raise CommandError(f'Beklenmedik hata: {exc}') from exc
