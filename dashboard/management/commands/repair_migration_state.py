"""
Repair migration history for databases that already contain legacy tables.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = 'Mevcut tablolar varsa eksik migration kayıtlarını güvenli şekilde tamamlar.'

    MIGRATIONS = [
        (
            'django_celery_beat',
            '0001_initial',
            {
                'django_celery_beat_intervalschedule',
                'django_celery_beat_crontabschedule',
                'django_celery_beat_periodictask',
                'django_celery_beat_periodictasks',
            },
        ),
        (
            'django_celery_beat',
            '0002_auto_20161118_0346',
            {'django_celery_beat_solarschedule'},
        ),
        (
            'django_celery_results',
            '0001_initial',
            {'django_celery_results_taskresult'},
        ),
        (
            'django_celery_results',
            '0008_chordcounter',
            {'django_celery_results_chordcounter'},
        ),
        (
            'django_celery_results',
            '0009_groupresult',
            {'django_celery_results_groupresult'},
        ),
        (
            'dia_integration',
            '0001_initial',
            {'dia_integration_diabaglanti'},
        ),
    ]

    def handle(self, *args, **options):
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()
        tables = set(connection.introspection.table_names())
        repaired = 0

        for app_label, migration_name, required_tables in self.MIGRATIONS:
            key = (app_label, migration_name)
            if key in applied:
                continue
            if required_tables.issubset(tables):
                recorder.record_applied(app_label, migration_name)
                repaired += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'↻ Migration kaydı tamamlandı: {app_label}.{migration_name}'
                    )
                )

        if repaired:
            self.stdout.write(self.style.SUCCESS(f'✓ {repaired} migration kaydı onarıldı.'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Onarılacak migration kaydı bulunmadı.'))
