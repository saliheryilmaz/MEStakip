"""
DİA Entegrasyon URL'leri.

Faz 2+ kapsamında senkronizasyon tetikleme, durum görüntüleme
ve webhook benzeri endpoint'ler buraya eklenecek.
"""

from django.urls import path

app_name = 'dia_integration'

urlpatterns = [
    # Faz 2+ kapsamında view'lar eklendikçe buraya eklenecek.
    # Örn:
    # path('sync/cari/', views.sync_cari, name='sync_cari'),
    # path('sync/durum/', views.sync_durum, name='sync_durum'),
]
