from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@dataclass
class Kontrol:
    ad: str
    durum: str
    detay: str = ''


class Command(BaseCommand):
    help = 'DIA entegrasyonu ve deploy oncesi hazirlik kontrollerini calistirir'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--dia',
            action='store_true',
            default=False,
            help='DIA web servisine canli baglanti ve ornek listeleme testleri yap',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=3,
            help='DIA ornek listeleme testlerinde cekilecek kayit sayisi',
        )
        parser.add_argument(
            '--strict',
            action='store_true',
            default=False,
            help='Uyari varsa da basarisiz cikis kodu don',
        )

    def handle(self, *args, **options) -> None:
        kontroller: list[Kontrol] = []
        kontroller.extend(self._yerel_kontroller())

        if options['dia']:
            kontroller.extend(self._dia_kontroller(limit=options['limit']))
        else:
            kontroller.append(Kontrol(
                'DIA canli test',
                'UYARI',
                '--dia verilmedi; web servis login/listeleme testi atlandi.',
            ))

        self.stdout.write('\nDIA / deploy hazirlik kontrolu\n')
        for kontrol in kontroller:
            style = self.style.SUCCESS
            if kontrol.durum == 'HATA':
                style = self.style.ERROR
            elif kontrol.durum == 'UYARI':
                style = self.style.WARNING
            self.stdout.write(style(f'[{kontrol.durum}] {kontrol.ad}'))
            if kontrol.detay:
                self.stdout.write(f'       {kontrol.detay}')

        hata_var = any(k.durum == 'HATA' for k in kontroller)
        uyari_var = any(k.durum == 'UYARI' for k in kontroller)
        if hata_var:
            raise SystemExit(1)
        if uyari_var and options['strict']:
            raise SystemExit(2)

    def _yerel_kontroller(self) -> list[Kontrol]:
        kontroller: list[Kontrol] = []

        kontroller.append(Kontrol(
            'DEBUG',
            'UYARI' if settings.DEBUG else 'OK',
            'Production/Coolify icin DEBUG=False olmali.' if settings.DEBUG else 'DEBUG=False',
        ))
        kontroller.append(Kontrol(
            'SECRET_KEY',
            'OK' if bool(getattr(settings, 'SECRET_KEY', '')) else 'HATA',
            'SECRET_KEY tanimli.' if getattr(settings, 'SECRET_KEY', '') else 'SECRET_KEY eksik.',
        ))
        kontroller.append(Kontrol(
            'ALLOWED_HOSTS',
            'OK' if settings.ALLOWED_HOSTS else 'HATA',
            ', '.join(settings.ALLOWED_HOSTS) if settings.ALLOWED_HOSTS else 'ALLOWED_HOSTS bos.',
        ))

        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            kontroller.append(Kontrol('Veritabani', 'OK', connection.settings_dict['ENGINE']))
        except Exception as exc:
            kontroller.append(Kontrol('Veritabani', 'HATA', str(exc)))

        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                kontroller.append(Kontrol('Migration', 'HATA', f'{len(plan)} bekleyen migration var.'))
            else:
                kontroller.append(Kontrol('Migration', 'OK', 'Bekleyen migration yok.'))
        except Exception as exc:
            kontroller.append(Kontrol('Migration', 'HATA', str(exc)))

        try:
            from dia_integration.models import DiaBaglanti

            aktifler = DiaBaglanti.objects.filter(is_aktif=True)
            if aktifler.count() == 1:
                baglanti = aktifler.first()
                kontroller.append(Kontrol(
                    'Aktif DIA baglantisi',
                    'OK',
                    f'{baglanti.sunucu_kodu} / firma {baglanti.firma_kodu} / donem {baglanti.donem_kodu}',
                ))
            elif aktifler.count() == 0:
                kontroller.append(Kontrol('Aktif DIA baglantisi', 'HATA', 'Aktif DiaBaglanti kaydi yok.'))
            else:
                kontroller.append(Kontrol('Aktif DIA baglantisi', 'HATA', f'{aktifler.count()} aktif kayit var.'))
        except Exception as exc:
            kontroller.append(Kontrol('Aktif DIA baglantisi', 'HATA', str(exc)))

        return kontroller

    def _dia_kontroller(self, limit: int) -> list[Kontrol]:
        kontroller: list[Kontrol] = []
        try:
            from dia_integration.client import DiaClient

            client = DiaClient()
            try:
                session_id = client.login()
                kontroller.append(Kontrol('DIA login', 'OK', f'Session {session_id[:8]}...'))

                firmalar = client.ozel_cagri(
                    modul='sis',
                    servis_adi='sis_yetkili_firma_donem_sube_depo',
                    data={},
                    firma_donem_ekle=False,
                ).get('result', [])
                kontroller.append(Kontrol('DIA firma/donem yetki', 'OK', f'{len(firmalar)} firma goruldu.'))

                self._ornek_listele(kontroller, client, 'Cari listeleme', 'scf_carikart_listele', limit)
                self._ornek_listele(kontroller, client, 'Stok listeleme', 'scf_stokkart_listele', limit)
                self._ornek_listele(kontroller, client, 'Fatura listeleme', 'scf_fatura_listele', limit)
            finally:
                client.logout()
        except Exception as exc:
            kontroller.append(Kontrol('DIA canli test', 'HATA', str(exc)))
        return kontroller

    def _ornek_listele(self, kontroller: list[Kontrol], client, ad: str, servis: str, limit: int) -> None:
        try:
            kayitlar = client.listele(
                modul='scf',
                servis_adi=servis,
                limit=limit,
                offset=0,
            )
            kontroller.append(Kontrol(ad, 'OK', f'{len(kayitlar)} kayit dondu.'))
        except Exception as exc:
            kontroller.append(Kontrol(ad, 'HATA', str(exc)))
