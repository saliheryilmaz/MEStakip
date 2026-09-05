from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0008_faturakalemi_dot'),
    ]

    operations = [
        migrations.AddField(
            model_name='faturakalemi',
            name='kanal',
            field=models.CharField(blank=True, max_length=50, verbose_name='Kanal'),
        ),
        migrations.AddField(
            model_name='faturakalemi',
            name='prim',
            field=models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=18, verbose_name='Prim'),
        ),
        migrations.AddField(
            model_name='faturakalemi',
            name='maliyet',
            field=models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=18, verbose_name='Maliyet'),
        ),
        migrations.AddField(
            model_name='faturakalemi',
            name='bolge',
            field=models.CharField(blank=True, max_length=100, verbose_name='Bölge'),
        ),
    ]
