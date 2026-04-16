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
