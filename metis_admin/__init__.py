# Django başlarken Celery uygulamasını yükle.
# Bu, shared_task dekoratörünün doğru çalışması için gereklidir.
from .celery import app as celery_app

__all__ = ('celery_app',)
