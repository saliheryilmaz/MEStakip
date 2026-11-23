"""Stok kartlarını DİA scf2300b raporundan aktarır.

Örnek:
    python manage.py dia_sync_stok_rapor --tasarim-key 980 --kuru-calis
    python manage.py dia_sync_stok_rapor --tasarim-key 980
    python manage.py dia_sync_stok_rapor --tasarim-key 980 --stok-kodu 100101.00001

Rapor çağrısı DİA kontörü tüketebilir; --kuru-calis yalnızca yerel yazmayı
engeller, DİA çağrısını engellemez.
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'DİA stok kart raporunu alır; açıkça çalıştırıldığında stok kartlarını günceller'

    def add_arguments(self, parser):
        parser.add_argument('--tasarim-key', type=int, required=True,
                            help='DİA rapor tasarımının sayısal key değeri')
        parser.add_argument('--stok-kodu', default='',
                            help='İsteğe bağlı: yalnızca bu stok kodunu raporla')
        parser.add_argument('--kuru-calis', action='store_true',
                            help='Raporu DİA’dan alıp doğrula, yerel veritabanına yazma')

    def handle(self, *args, **options):
        from dia_integration.services.stok_service import StokService

        if options['kuru_calis']:
            self.stdout.write(self.style.WARNING(
                'DİA rapor çağrısı yapılacak ve kontör harcayabilir; '
                'yalnızca yerel veritabanına yazma kapalı.'
            ))
        try:
            sonuc = StokService.rapordan_senkronize_et(
                tasarim_key=options['tasarim_key'],
                stok_kodu=options['stok_kodu'],
                kuru_calis=options['kuru_calis'],
            )
        except Exception as exc:
            raise CommandError(f'Stok raporu alınamadı: {exc}') from exc

        if options['kuru_calis']:
            self.stdout.write(self.style.SUCCESS(
                f'Rapor doğrulandı: {sonuc.toplam} kart bulundu; veritabanı değiştirilmedi.'
            ))
            return
        self.stdout.write(self.style.SUCCESS(
            f'Rapor sync tamamlandı: {sonuc.toplam} kart, '
            f'{sonuc.eklenen} yeni, {sonuc.guncellenen} güncellendi.'
        ))
