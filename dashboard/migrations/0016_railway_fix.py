# Generated manually for Railway deployment fix

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0015_remove_notification_event'),
    ]

    operations = [
        # Bu migration Railway'deki Event tablosu çakışmasını çözmek için boş
        # Event modeli zaten 0007_event.py'de oluşturulmuş
    ]