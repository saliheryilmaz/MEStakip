from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = 'mesbul'

urlpatterns = [
    path('', views.AramaView.as_view(), name='index'),
    path('api/stok/', views.stok_api, name='stok_api'),
    path('arama/', views.AramaView.as_view(), name='arama'),
    path('sonuclar/', views.SonuclarView.as_view(), name='sonuclar'),
    path('abonelikler/', views.AbonelikYonetimView.as_view(), name='abonelik_yonetim'),
    path('abonelikler/<int:kullanici_id>/kaydet/', views.AbonelikKaydetView.as_view(), name='abonelik_kaydet'),
    path('abonelikler/kullanici-ekle/', views.KullaniciEkleView.as_view(), name='kullanici_ekle'),
    path('abonelikler/odeme-ekle/', views.OdemeEkleView.as_view(), name='odeme_ekle'),
    path('odeme-gecmisim/', views.OdemeGecmisiView.as_view(), name='odeme_gecmisi'),
    path('notlar/', views.NotlarView.as_view(), name='notlar'),
    path('notlar/ekle/', views.NotEkleView.as_view(), name='not_ekle'),
    path('notlar/<int:not_id>/sil/', views.NotSilView.as_view(), name='not_sil'),
    path('uyelik-talep/', login_required(views.UyelikTalepView.as_view()), name='uyelik_talep'),
    path('iskonto/', views.IskontoYonetimView.as_view(), name='iskonto_yonetim'),
]
