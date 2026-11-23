from celery import shared_task

from .tahsilat import aylik_rapor_kaydet


@shared_task
def tahsilat_raporunu_guncelle():
    return aylik_rapor_kaydet().ay.isoformat()
