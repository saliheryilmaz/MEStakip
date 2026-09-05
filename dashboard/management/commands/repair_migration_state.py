"""
Repair migration history for databases that already contain legacy tables.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = 'Mevcut tablolar varsa eksik migration kayıtlarını güvenli şekilde tamamlar.'

    MIGRATION_CHAINS = {
        'django_celery_results': [
            '0001_initial',
            '0002_add_task_name_args_kwargs',
            '0003_auto_20181106_1101',
            '0004_auto_20190516_0412',
            '0005_taskresult_worker',
            '0006_taskresult_date_created',
            '0007_remove_taskresult_hidden',
            '0008_chordcounter',
            '0009_groupresult',
            '0010_remove_duplicate_indices',
            '0011_taskresult_periodic_task_name',
        ],
        'django_celery_beat': [
            '0001_initial',
            '0002_auto_20161118_0346',
            '0003_auto_20161209_0049',
            '0004_auto_20170221_0000',
            '0005_add_solarschedule_events_choices',
            '0006_auto_20180210_1226',
            '0006_auto_20180322_0932',
            '0006_periodictask_priority',
            '0007_auto_20180521_0826',
            '0008_auto_20180914_1922',
            '0009_periodictask_headers',
            '0010_auto_20190429_0326',
            '0011_auto_20190508_0153',
            '0012_periodictask_expire_seconds',
            '0013_auto_20200609_0727',
            '0014_remove_clockedschedule_enabled',
            '0015_edit_solarschedule_events_choices',
            '0016_alter_crontabschedule_timezone',
            '0017_alter_crontabschedule_month_of_year',
            '0018_improve_crontab_helptext',
            '0019_alter_periodictasks_options',
        ],
    }

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

        repaired += self._repair_missing_ancestors(recorder, applied)
        repaired += self._repair_known_schema_changes(recorder, applied, tables)

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

    def _repair_missing_ancestors(self, recorder, applied: set[tuple[str, str]]) -> int:
        repaired = 0
        for app_label, chain in self.MIGRATION_CHAINS.items():
            applied_indexes = [
                index for index, migration_name in enumerate(chain)
                if (app_label, migration_name) in applied
            ]
            if not applied_indexes:
                continue

            for migration_name in chain[:max(applied_indexes)]:
                key = (app_label, migration_name)
                if key in applied:
                    continue
                recorder.record_applied(app_label, migration_name)
                applied.add(key)
                repaired += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'↻ Eksik önceki migration kaydı tamamlandı: {app_label}.{migration_name}'
                    )
                )
        return repaired

    def _repair_known_schema_changes(
        self,
        recorder,
        applied: set[tuple[str, str]],
        tables: set[str],
    ) -> int:
        repaired = 0

        key = ('django_celery_beat', '0003_auto_20161209_0049')
        if key not in applied and 'django_celery_beat_solarschedule' in tables:
            with connection.cursor() as cursor:
                constraints = connection.introspection.get_constraints(
                    cursor,
                    'django_celery_beat_solarschedule',
                )
            unique_exists = any(
                constraint.get('unique')
                and set(constraint.get('columns', [])) == {'event', 'latitude', 'longitude'}
                for constraint in constraints.values()
            )
            if unique_exists:
                recorder.record_applied(*key)
                applied.add(key)
                repaired += 1
                self.stdout.write(
                    self.style.WARNING(
                        '↻ Mevcut unique index için migration kaydı tamamlandı: '
                        'django_celery_beat.0003_auto_20161209_0049'
                    )
                )

        beat_checks = [
            (
                ('django_celery_beat', '0006_auto_20180322_0932'),
                'django_celery_beat_crontabschedule',
                {'timezone'},
            ),
            (
                ('django_celery_beat', '0007_auto_20180521_0826'),
                'django_celery_beat_periodictask',
                {'one_off', 'start_time'},
            ),
            (
                ('django_celery_beat', '0006_periodictask_priority'),
                'django_celery_beat_periodictask',
                {'priority'},
            ),
            (
                ('django_celery_beat', '0009_periodictask_headers'),
                'django_celery_beat_periodictask',
                {'headers'},
            ),
            (
                ('django_celery_beat', '0011_auto_20190508_0153'),
                'django_celery_beat_periodictask',
                {'clocked_id'},
            ),
            (
                ('django_celery_beat', '0012_periodictask_expire_seconds'),
                'django_celery_beat_periodictask',
                {'expire_seconds'},
            ),
        ]
        for key, table_name, columns in beat_checks:
            repaired += self._record_if_columns_exist(
                recorder,
                applied,
                tables,
                key,
                table_name,
                columns,
            )

        results_checks = [
            (
                ('django_celery_results', '0002_add_task_name_args_kwargs'),
                'django_celery_results_taskresult',
                {'task_name', 'task_args', 'task_kwargs'},
            ),
            (
                ('django_celery_results', '0005_taskresult_worker'),
                'django_celery_results_taskresult',
                {'worker'},
            ),
            (
                ('django_celery_results', '0006_taskresult_date_created'),
                'django_celery_results_taskresult',
                {'date_created'},
            ),
            (
                ('django_celery_results', '0011_taskresult_periodic_task_name'),
                'django_celery_results_taskresult',
                {'periodic_task_name'},
            ),
        ]
        for key, table_name, columns in results_checks:
            repaired += self._record_if_columns_exist(
                recorder,
                applied,
                tables,
                key,
                table_name,
                columns,
            )

        key = ('django_celery_results', '0007_remove_taskresult_hidden')
        if (
            key not in applied
            and 'django_celery_results_taskresult' in tables
            and 'hidden' not in self._columns('django_celery_results_taskresult')
        ):
            recorder.record_applied(*key)
            applied.add(key)
            repaired += 1
            self.stdout.write(
                self.style.WARNING(
                    '↻ Mevcut kolon kaldırma için migration kaydı tamamlandı: '
                    'django_celery_results.0007_remove_taskresult_hidden'
                )
            )

        key = ('django_celery_beat', '0014_remove_clockedschedule_enabled')
        if (
            key not in applied
            and 'django_celery_beat_clockedschedule' in tables
            and 'enabled' not in self._columns('django_celery_beat_clockedschedule')
        ):
            recorder.record_applied(*key)
            applied.add(key)
            repaired += 1
            self.stdout.write(
                self.style.WARNING(
                    '↻ Mevcut kolon kaldırma için migration kaydı tamamlandı: '
                    'django_celery_beat.0014_remove_clockedschedule_enabled'
                )
            )

        return repaired

    def _record_if_columns_exist(
        self,
        recorder,
        applied: set[tuple[str, str]],
        tables: set[str],
        key: tuple[str, str],
        table_name: str,
        columns: set[str],
    ) -> int:
        if key in applied or table_name not in tables:
            return 0
        existing_columns = self._columns(table_name)
        if not columns.issubset(existing_columns):
            return 0
        recorder.record_applied(*key)
        applied.add(key)
        self.stdout.write(
            self.style.WARNING(
                f'↻ Mevcut kolonlar için migration kaydı tamamlandı: {key[0]}.{key[1]}'
            )
        )
        return 1

    def _columns(self, table_name: str) -> set[str]:
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
        return {column.name for column in description}
