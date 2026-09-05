"""python manage.py dia_sync_fatura [--tam] [--sayfa 100] [--baslangic YYYY-MM-DD]"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "DİA'dan fatura listesini MEStakip'e senkronize eder"

    def add_arguments(self, p):
        p.add_argument('--tam', action='store_true', default=False)
        p.add_argument('--sayfa', type=int, default=100)
        p.add_argument('--kalemler', action='store_true', default=None,
                       help='Kalem detaylarını da çek (varsayılan açık)')
        p.add_argument('--baslik-only', action='store_true', default=False,
                       help='Sadece fatura başlıklarını çek, kalemleri alma')
        p.add_argument('--baslangic', type=str, default='', help='DİA tarih filtresi başlangıcı (YYYY-MM-DD)')
        p.add_argument('--bitis', type=str, default='', help='DİA tarih filtresi bitişi (YYYY-MM-DD)')
        p.add_argument('--maksimum', type=int, default=0, help='En fazla kaç fatura işlenecek (0: sınırsız)')

    def handle(self, *args, **o):
        from dia_integration.services.fatura_service import FaturaService
        from dia_integration.exceptions import DiaBaseError
        kalem_cek = False if o['baslik_only'] else True
        self.stdout.write(
            f'Fatura sync... [{"TAM" if o["tam"] else "DELTA"}'
            f'{"+ kalemler" if kalem_cek else "+ sadece başlık"}]'
        )
        try:
            s = FaturaService.dia_dan_senkronize_et(
                delta=not o['tam'],
                sayfa_boyutu=o['sayfa'],
                kalem_cek=kalem_cek,
                baslangic_tarihi=o['baslangic'] or None,
                bitis_tarihi=o['bitis'] or None,
                maksimum_kayit=o['maksimum'] or None,
            )
            self.stdout.write(self.style.SUCCESS(
                f'✓ Tamamlandı: {s.toplam} kayıt, {s.eklenen} eklendi, {s.guncellenen} güncellendi, {s.hatali} hata'
            ))
        except DiaBaseError as e:
            raise CommandError(str(e)) from e
