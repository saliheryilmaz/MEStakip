import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('karsilastirma', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Abonelik',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan', models.CharField(choices=[('aylik', 'Aylık'), ('yillik', 'Yıllık'), ('demo', 'Demo')], default='demo', max_length=10)),
                ('baslangic', models.DateField(default=django.utils.timezone.localdate)),
                ('bitis', models.DateField()),
                ('aktif', models.BooleanField(default=True)),
                ('not_alani', models.TextField(blank=True, help_text='Müşteri notları')),
                ('kullanici', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='abonelik', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Abonelik',
                'verbose_name_plural': 'Abonelikler',
                'ordering': ['-bitis'],
            },
        ),
    ]
