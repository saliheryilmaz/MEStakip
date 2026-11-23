from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    # createcachetable safely skips an existing table on established installs.
    call_command('createcachetable', database=schema_editor.connection.alias)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('karsilastirma', '0010_notlar_musteri')]
    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
