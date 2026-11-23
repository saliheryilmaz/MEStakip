"""MesRapor01 çıktısının alanlarını kayıt değerlerini göstermeden listeler."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from dia_integration.exceptions import DiaBaseError
from dia_integration.services.rapor_service import RaporService


class Command(BaseCommand):
    help = 'MesRapor01 JSON alanlarını DİA’dan (kontörlü) veya yerel dosyadan inceler.'

    def add_arguments(self, parser):
        parser.add_argument('--dosya', type=Path, help='Daha önce çözülmüş rapor JSON dosyası')
        parser.add_argument('--ayrintili', action='store_true', help='İç içe alanları ve tiplerini de yaz')

    def handle(self, *args, **options):
        dosya = options['dosya']
        try:
            if dosya is not None:
                veri = json.loads(dosya.read_text(encoding='utf-8-sig'))
            else:
                veri = RaporService.mes_raporu_json_al().json_verisi
        except (DiaBaseError, OSError, ValueError) as exc:
            raise CommandError(f'MesRapor01 alınamadı: {exc}') from exc

        rapor = veri.get('rapor_json') if isinstance(veri, dict) else None
        tablolar = rapor.get('veriler') if isinstance(rapor, dict) else None
        if not isinstance(tablolar, dict):
            raise CommandError('MesRapor01 çıktısında rapor_json.veriler nesnesi bulunamadı.')

        for alan in ('basarili', 'son_paket', 'firma_kodu', 'donem_kodu', 'paket_boyutu'):
            deger = rapor.get(alan)
            if type(deger) in (bool, int):
                self.stdout.write(f'{alan}: {deger}')

        for ad, satirlar in tablolar.items():
            if options['ayrintili']:
                self._alanlari_yaz(satirlar, f'rapor_json.veriler.{ad}')
            elif isinstance(satirlar, list):
                ornek = next((satir for satir in satirlar if isinstance(satir, dict)), {})
                anahtarlar = ', '.join(alan for alan in ornek if alan.startswith('_key'))
                self.stdout.write(f'{ad}: {len(satirlar)} satır' + (f' | {anahtarlar}' if anahtarlar else ''))
            else:
                self.stdout.write(f'{ad}: {type(satirlar).__name__}')

    def _alanlari_yaz(self, veri, yol, derinlik=0):
        if derinlik >= 10:
            self.stdout.write(f'{yol}: iç içe alanlar')
        elif isinstance(veri, dict) and veri:
            for alan, deger in veri.items():
                self._alanlari_yaz(deger, f'{yol}.{alan}', derinlik + 1)
        elif isinstance(veri, list):
            self.stdout.write(f'{yol}: {len(veri)} satır')
            ornek = next((satir for satir in veri if satir is not None), None)
            if ornek is not None:
                self._alanlari_yaz(ornek, f'{yol}[]', derinlik + 1)
        else:
            self.stdout.write(f'{yol}: {type(veri).__name__}')
