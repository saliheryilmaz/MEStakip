<<<<<<< HEAD
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0060_add_marka_to_malzemehareketi'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='ic_not',
            field=models.TextField(blank=True, null=True, verbose_name='İç Not'),
        ),
    ]
=======
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0060_add_marka_to_malzemehareketi'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='ic_not',
            field=models.TextField(blank=True, null=True, verbose_name='İç Not'),
        ),
    ]
>>>>>>> a1c5e77f71df14e5bfa36b6fc1593c31ab3147a5
