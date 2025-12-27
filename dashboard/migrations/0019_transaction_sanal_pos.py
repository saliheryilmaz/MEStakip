from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0018_malzemedosya_malzemehareketi_dosya'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='sanal_pos',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Sanal Pos',
            ),
        ),
    ]








