from django.urls import path
from . import views

app_name = 'erp'

urlpatterns = [
    # DİA Sync durumu
    path('dia/durum/', views.dia_durum, name='dia_durum'),
    path('dia/sync/', views.sync_baslat, name='sync_baslat'),

    # Cari
    path('cari/', views.cari_listesi, name='cari_listesi'),
    path('cari/<int:pk>/', views.cari_detay, name='cari_detay'),

    # Stok
    path('stok/', views.stok_listesi, name='stok_listesi'),
    path('stok/<int:pk>/', views.stok_detay, name='stok_detay'),

    # Depo
    path('depo/', views.depo_listesi, name='depo_listesi'),

    # Loglar
    path('sync/loglar/', views.sync_loglar, name='sync_loglar'),

    # Fatura / Malzeme Hareket
    path('fatura/', views.fatura_listesi, name='fatura_listesi'),
    path('fatura/sync/', views.fatura_sync, name='fatura_sync'),

    # Depo Fişi
    path('depo-fisi/', views.depo_fisi_listesi, name='depo_fisi_listesi'),
    path('depo-fisi/istek/<int:stok_pk>/', views.depo_fisi_istek, name='depo_fisi_istek'),
    path('depo-fisi/<int:pk>/', views.depo_fisi_detay, name='depo_fisi_detay'),
    path('depo-fisi/<int:pk>/guncelle/', views.depo_fisi_guncelle, name='depo_fisi_guncelle'),
    path('depo-fisi/<int:pk>/sil/', views.depo_fisi_sil, name='depo_fisi_sil'),
    path('depo-fisi/<int:pk>/onayla/', views.depo_fisi_onayla, name='depo_fisi_onayla'),
    path('depo-fisi/<int:pk>/iptal/', views.depo_fisi_iptal, name='depo_fisi_iptal'),
    path('depo-fisi/kalem/<int:kalem_pk>/sil/', views.depo_fisi_kalem_sil, name='depo_fisi_kalem_sil'),
]
