from celery import shared_task

@shared_task
def test_task():
    print("Celery çalışıyor!")
    return "Merhaba Celery"
