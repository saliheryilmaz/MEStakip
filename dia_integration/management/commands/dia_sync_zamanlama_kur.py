"""
Management command: Celery Beat periyodik sync zamanlamalarını veritabanına yazar.

Kullanım:
    python manage.py dia_sync_zamanlama_kur

Bu komut, PythonAnywhere'e deploy ettikten sonra bir kez çalıştırılır.
Django admin panelinden de görüntülenip düzenlenebilir:
  /admin/django_celery_beat/periodictask/
"""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Celery Beat periyodik DİA sync zamanlamalarını kurar'

    def handle(self, *args, **options) -> None:
        from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
        import json

        self.stdout.write('Periyodik sync zamanlamaları kuruluyor...\n')

        genel_aralik = self._env_int('DIA_SYNC_INTERVAL_MINUTES', 1)
        cari_aralik = self._env_int('DIA_CARI_SYNC_INTERVAL_MINUTES', genel_aralik)
        stok_aralik = self._env_int('DIA_STOK_SYNC_INTERVAL_MINUTES', genel_aralik)
        fatura_aralik = self._env_int('DIA_FATURA_SYNC_INTERVAL_MINUTES', genel_aralik)
        miktar_aralik = self._env_int('DIA_STOK_MIKTAR_SYNC_INTERVAL_MINUTES', genel_aralik)

        # ── Kısa aralıklarla delta sync ─────────────────────────
        cari_interval, _ = IntervalSchedule.objects.get_or_create(
            every=cari_aralik,
            period=IntervalSchedule.MINUTES,
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Cari Delta Sync',
            defaults={
                'task': 'dia_integration.sync_cari_listesi',
                'interval': cari_interval,
                'crontab': None,
                'kwargs': json.dumps({'delta': True}),
                'enabled': True,
            },
        )
        self._yazdir(f'Cari delta sync ({cari_aralik} dk)', olusturuldu)

        stok_interval, _ = IntervalSchedule.objects.get_or_create(
            every=stok_aralik,
            period=IntervalSchedule.MINUTES,
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Stok Delta Sync',
            defaults={
                'task': 'dia_integration.sync_stok_listesi',
                'interval': stok_interval,
                'crontab': None,
                'kwargs': json.dumps({'delta': True}),
                'enabled': True,
            },
        )
        self._yazdir(f'Stok delta sync ({stok_aralik} dk)', olusturuldu)

        fatura_interval, _ = IntervalSchedule.objects.get_or_create(
            every=fatura_aralik,
            period=IntervalSchedule.MINUTES,
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Fatura Delta Sync',
            defaults={
                'task': 'dia_integration.sync_fatura_listesi',
                'interval': fatura_interval,
                'crontab': None,
                'kwargs': json.dumps({'delta': True, 'kalem_cek': True}),
                'enabled': True,
            },
        )
        self._yazdir(f'Fatura delta sync ({fatura_aralik} dk)', olusturuldu)

        miktar_interval, _ = IntervalSchedule.objects.get_or_create(
            every=miktar_aralik,
            period=IntervalSchedule.MINUTES,
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Stok Depo Miktar Sync',
            defaults={
                'task': 'dia_integration.sync_stok_depo_miktarlari',
                'interval': miktar_interval,
                'crontab': None,
                'kwargs': json.dumps({}),
                'enabled': True,
            },
        )
        self._yazdir(f'Stok depo miktar sync ({miktar_aralik} dk)', olusturuldu)

        # ── Her gece 02:00'de tam cari sync ─────────────────────
        gece_crontab, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='2',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Cari Tam Sync (gece 02:00)',
            defaults={
                'task': 'dia_integration.sync_cari_listesi',
                'crontab': gece_crontab,
                'kwargs': json.dumps({'delta': False}),
                'enabled': True,
            },
        )
        self._yazdir('Cari tam sync (gece 02:00)', olusturuldu)

        # ── Her gece 03:00'te tam stok sync ─────────────────────
        gece3_crontab, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='3',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Stok Tam Sync (gece 03:00)',
            defaults={
                'task': 'dia_integration.sync_stok_listesi',
                'crontab': gece3_crontab,
                'kwargs': json.dumps({'delta': False}),
                'enabled': True,
            },
        )
        self._yazdir('Stok tam sync (gece 03:00)', olusturuldu)

        # ── Her gece 04:00'te tam fatura sync ───────────────────
        gece4_crontab, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='4',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Fatura Tam Sync (gece 04:00)',
            defaults={
                'task': 'dia_integration.sync_fatura_listesi',
                'crontab': gece4_crontab,
                'kwargs': json.dumps({'delta': False, 'kalem_cek': True}),
                'enabled': True,
            },
        )
        self._yazdir('Fatura tam sync (gece 04:00)', olusturuldu)

        # ── Her gün 08:00'de firma/dönem önbellek güncelle ──────
        sabah_crontab, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='8',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Firma/Dönem Sync (her gün 08:00)',
            defaults={
                'task': 'dia_integration.sync_firma_donem',
                'crontab': sabah_crontab,
                'kwargs': json.dumps({}),
                'enabled': True,
            },
        )
        self._yazdir('Firma/dönem sync (her gün 08:00)', olusturuldu)

        self.stdout.write(self.style.SUCCESS(
            '\n✓ Tüm zamanlamalar ayarlandı.\n'
            '\nCelery worker ve beat\'i başlatmayı unutmayın:\n'
            '  Worker : celery -A metis_admin worker -l info\n'
            '  Beat   : celery -A metis_admin beat -l info\n'
            '\nZamanlamaları admin panelinden yönetebilirsiniz:\n'
            '  /admin/django_celery_beat/periodictask/'
        ))

    def _yazdir(self, ad: str, olusturuldu: bool) -> None:
        durum = '✓ Oluşturuldu' if olusturuldu else '↻ Güncellendi'
        self.stdout.write(f'  {durum}: {ad}')

    def _env_int(self, key: str, default: int) -> int:
        try:
            value = int(os.environ.get(key, default))
        except (TypeError, ValueError):
            value = default
        return max(1, value)
