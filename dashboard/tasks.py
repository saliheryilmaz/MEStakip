from celery import shared_task
from .otel_plan import rapor_kaydet


@shared_task
def otel_plan_raporu():
    return rapor_kaydet()
