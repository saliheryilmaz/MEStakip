"""
Celery uygulama yapılandırması.

PythonAnywhere'de Always-On Task olarak çalıştırmak için:
    celery -A metis_admin worker -l info
Periyodik görevler için beat scheduler:
    celery -A metis_admin beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""

import os
from celery import Celery

# Django ayarları için ortam değişkeni
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metis_admin.settings')

app = Celery('metis_admin')

# Django settings.py içindeki CELERY_ önekli tüm ayarları yükle
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tüm INSTALLED_APPS içindeki tasks.py dosyalarını otomatik keşfet
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:
    """Celery bağlantısını doğrulamak için test görevi."""
    print(f'Request: {self.request!r}')
