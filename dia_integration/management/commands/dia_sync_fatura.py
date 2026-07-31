"""python manage.py dia_sync_fatura [--tam] [--sayfa 100]"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "DİA'dan fatura listesini MEStakip'e senkronize eder"

    def add_arguments(self, p):
        p.add_argument('--tam', action='store_true', default=False)
        p.add_argument('--sayfa', type=int, default=100)
        p.add_argument('--kalemler', action='store_true', default=False,
                       help='Kalem detaylarını da çek (yavaş — her fatura için ayrı API çağrısı)')

    def handle(self, *args, **o):
        from dia_integration.services.fatura_service import FaturaService
        from dia_integration.exceptions import DiaBaseError
        self.stdout.write(f'Fatura sync... [{"TAM" if o["tam"] else "DELTA"}{"+ kalemler" if o["kalemler"] else ""}]')
        try:
            s = FaturaService.dia_dan_senkronize_et(
                delta=not o['tam'],
                sayfa_boyutu=o['sayfa'],
                kalem_cek=o['kalemler'],
            )
            self.stdout.write(self.style.SUCCESS(
                f'✓ Tamamlandı: {s.toplam} kayıt, {s.eklenen} eklendi, {s.guncellenen} güncellendi, {s.hatali} hata'
            ))
        except DiaBaseError as e:
            raise CommandError(str(e)) from e
