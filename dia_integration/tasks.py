from __future__ import annotations

from celery import shared_task


@shared_task
def test_task():
    print("Celery çalışıyor!")
    return "Merhaba Celery"


@shared_task(name='dia_integration.test_dia_baglantisi')
def test_dia_baglantisi() -> dict:
    from dia_integration.client import DiaClient

    client = DiaClient()
    try:
        session_id = client.login()
        firmalar = client.ozel_cagri(
            modul='sis',
            servis_adi='sis_yetkili_firma_donem_sube_depo',
            data={},
            firma_donem_ekle=False,
        ).get('result', [])
    finally:
        client.logout()

    return {
        'basarili': True,
        'session': session_id[:8],
        'firma_sayisi': len(firmalar),
    }


@shared_task(name='dia_integration.sync_cari_listesi')
def sync_cari_listesi(delta: bool = True) -> dict:
    from dia_integration.models import SyncTetikleyen
    from dia_integration.services import CariService

    sonuc = CariService.dia_dan_senkronize_et(
        delta=delta,
        tetikleyen=SyncTetikleyen.OTOMATIK,
    )
    return sonuc.__dict__


@shared_task(name='dia_integration.sync_stok_listesi')
def sync_stok_listesi(delta: bool = True) -> dict:
    from dia_integration.models import SyncTetikleyen
    from dia_integration.services import StokService

    sonuc = StokService.dia_dan_senkronize_et(
        delta=delta,
        tetikleyen=SyncTetikleyen.OTOMATIK,
    )
    return sonuc.__dict__


@shared_task(name='dia_integration.sync_stok_depo_miktarlari')
def sync_stok_depo_miktarlari() -> dict:
    from dia_integration.services import StokService

    islenen = StokService.depo_miktarlarini_guncelle()
    return {'islenen': islenen}


@shared_task(name='dia_integration.sync_firma_donem')
def sync_firma_donem() -> dict:
    from django.utils import timezone

    from dia_integration.client import DiaClient
    from dia_integration.models import DiaBaglanti
    from dia_integration.services import StokService

    with DiaClient() as client:
        firmalar = client.ozel_cagri(
            modul='sis',
            servis_adi='sis_yetkili_firma_donem_sube_depo',
            data={},
            firma_donem_ekle=False,
        ).get('result', [])

    baglanti = DiaBaglanti.objects.filter(is_aktif=True).first()
    if baglanti:
        baglanti.firma_donem_bilgisi = firmalar
        baglanti.firma_donem_guncellendi = timezone.now()
        baglanti.save(update_fields=['firma_donem_bilgisi', 'firma_donem_guncellendi'])

    depo_sayisi = StokService.depolari_senkronize_et()
    return {'firma_sayisi': len(firmalar), 'depo_sayisi': depo_sayisi}


@shared_task(name='dia_integration.sync_fatura_listesi')
def sync_fatura_listesi(
    delta: bool = True,
    kalem_cek: bool = True,
    baslangic_tarihi: str | None = None,
    bitis_tarihi: str | None = None,
    maksimum_kayit: int | None = None,
) -> dict:
    from dia_integration.models import SyncTetikleyen
    from dia_integration.services import FaturaService

    sonuc = FaturaService.dia_dan_senkronize_et(
        delta=delta,
        kalem_cek=kalem_cek,
        baslangic_tarihi=baslangic_tarihi,
        bitis_tarihi=bitis_tarihi,
        maksimum_kayit=maksimum_kayit,
        tetikleyen=SyncTetikleyen.OTOMATIK,
    )
    return sonuc.__dict__
