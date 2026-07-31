"""
Management command: Celery Beat periyodik sync zamanlamalarını veritabanına yazar.

Kullanım:
    python manage.py dia_sync_zamanlama_kur

Bu komut, PythonAnywhere'e deploy ettikten sonra bir kez çalıştırılır.
Django admin panelinden de görüntülenip düzenlenebilir:
  /admin/django_celery_beat/periodictask/
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Celery Beat periyodik DİA sync zamanlamalarını kurar'

    def handle(self, *args, **options) -> None:
        from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
        import json

        self.stdout.write('Periyodik sync zamanlamaları kuruluyor...\n')

        # ── Her 30 dakikada bir cari delta sync ─────────────────
        interval_30dk, _ = IntervalSchedule.objects.get_or_create(
            every=30,
            period=IntervalSchedule.MINUTES,
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Cari Delta Sync (30 dk)',
            defaults={
                'task': 'dia_integration.sync_cari_listesi',
                'interval': interval_30dk,
                'kwargs': json.dumps({'delta': True}),
                'enabled': True,
            },
        )
        self._yazdir('Cari delta sync (30dk)', olusturuldu)

        # ── Her 60 dakikada bir stok delta sync ─────────────────
        interval_60dk, _ = IntervalSchedule.objects.get_or_create(
            every=60,
            period=IntervalSchedule.MINUTES,
        )
        gorev, olusturuldu = PeriodicTask.objects.update_or_create(
            name='DİA Stok Delta Sync (60 dk)',
            defaults={
                'task': 'dia_integration.sync_stok_listesi',
                'interval': interval_60dk,
                'kwargs': json.dumps({'delta': True}),
                'enabled': True,
            },
        )
        self._yazdir('Stok delta sync (60dk)', olusturuldu)

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
