"""
Celery görevleri — DİA senkronizasyon otomasyonu.

Mevcut görevler:
  Faz 1:
    - test_dia_baglantisi   : DİA bağlantı testi
    - sync_firma_donem      : Firma/dönem önbelleği güncelle

  Faz 2:
    - sync_cari_listesi     : Cari delta/tam sync

  Faz 2 (altyapı):
    - isleme_kuyruktaki     : Retry kuyruğu işleyici
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Faz 1 görevleri
# ─────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='dia_integration.test_dia_baglantisi',
)
def test_dia_baglantisi(self) -> dict:
    """
    DİA bağlantısını ve login/logout akışını doğrular.

    Manuel tetikleme veya ilk kurulum doğrulaması için kullanılır.
    Celery Beat'e eklenmez.

    Returns:
        {'basarili': True, 'session_id_prefix': '...', 'sure_ms': ...}
    """
    from dia_integration.client import DiaClient
    from dia_integration.models import SyncLog, SyncDurum, SyncTetikleyen

    log = SyncLog.objects.create(
        modul='baglanti_testi',
        tetikleyen=SyncTetikleyen.SISTEM,
        celery_task_id=self.request.id or '',
    )

    try:
        import time
        baslangic = time.monotonic()

        client = DiaClient()
        session_id = client.login()
        client.logout()

        sure_ms = int((time.monotonic() - baslangic) * 1000)

        log.basarili_kayit = 1
        log.toplam_kayit = 1
        log.tamamla(durum=SyncDurum.BASARILI)

        logger.info('DİA bağlantı testi başarılı. Süre: %dms', sure_ms)
        return {
            'basarili': True,
            'session_id_prefix': session_id[:8] + '...',
            'sure_ms': sure_ms,
        }

    except Exception as exc:
        log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
        logger.error('DİA bağlantı testi başarısız: %s', exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='dia_integration.sync_firma_donem',
)
def sync_firma_donem(self) -> dict:
    """
    DİA firma/dönem/şube/depo hiyerarşisini önbelleğe alır.

    Periyodik çalışma: günde 1 kez yeterli (bu veri nadiren değişir).

    Returns:
        {'firma_sayisi': int, 'donem_sayisi': int}
    """
    from dia_integration.client import DiaClient
    from dia_integration.models import DiaBaglanti, SyncLog, SyncDurum, SyncTetikleyen

    log = SyncLog.objects.create(
        modul='firma_donem',
        tetikleyen=SyncTetikleyen.OTOMATIK,
        celery_task_id=self.request.id or '',
    )

    try:
        baglanti = DiaBaglanti.objects.filter(is_aktif=True).first()

        with DiaClient() as client:
            yanit = client.ozel_cagri(
                modul='sis',
                servis_adi='sis_yetkili_firma_donem_sube_depo',
                data={},
            )

        firmalar = yanit.get('result', [])
        firma_sayisi = len(firmalar)
        donem_sayisi = sum(len(f.get('donemler', [])) for f in firmalar)

        if baglanti:
            baglanti.firma_donem_bilgisi = firmalar
            baglanti.firma_donem_guncellendi = timezone.now()
            baglanti.save(update_fields=['firma_donem_bilgisi', 'firma_donem_guncellendi'])
        else:
            logger.warning('Aktif DiaBaglanti kaydı bulunamadı; firma/dönem verisi kaydedilemedi.')

        log.toplam_kayit = firma_sayisi
        log.basarili_kayit = firma_sayisi
        log.tamamla(durum=SyncDurum.BASARILI)

        logger.info('Firma/dönem sync tamamlandı: %d firma, %d dönem.', firma_sayisi, donem_sayisi)
        return {'firma_sayisi': firma_sayisi, 'donem_sayisi': donem_sayisi}

    except Exception as exc:
        log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
        logger.error('sync_firma_donem başarısız: %s', exc)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────
# Faz 2 görevleri
# ─────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='dia_integration.sync_cari_listesi',
)
def sync_cari_listesi(self, delta: bool = True) -> dict:
    """
    DİA cari listesini MEStakip'e senkronize eder.

    Args:
        delta: True → son sync'ten beri değişenleri çek (varsayılan)
               False → tüm cari listesini çek (tam sync)

    Celery Beat önerisi: her 30 dakikada bir delta=True ile çalıştır.

    Returns:
        {'toplam': int, 'eklenen': int, 'guncellenen': int, 'hatali': int}
    """
    from dia_integration.services import CariService
    from dia_integration.models import SyncTetikleyen
    from dia_integration.exceptions import DiaBaseError

    try:
        sonuc = CariService.dia_dan_senkronize_et(
            delta=delta,
            tetikleyen=SyncTetikleyen.OTOMATIK,
        )
        return {
            'toplam': sonuc.toplam,
            'eklenen': sonuc.eklenen,
            'guncellenen': sonuc.guncellenen,
            'hatali': sonuc.hatali,
        }
    except DiaBaseError as exc:
        logger.error('sync_cari_listesi DİA hatası: %s', exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error('sync_cari_listesi beklenmedik hata: %s', exc)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────
# Altyapı — retry kuyruk işleyici
# ─────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='dia_integration.isleme_kuyruktaki',
)
def isleme_kuyruktaki(self) -> dict:
    """
    SenkronKuyrugu'ndaki bekleyen/hatalı görevleri işler.

    Her döngüde en fazla 50 kayıt işlenir (kontör tasarrufu).
    Celery Beat: her 5 dakikada bir çalıştırılabilir.
    """
    from django.utils import timezone as tz
    from dia_integration.models import SenkronKuyrugu, SenkronKuyrukDurum

    bekleyenler = SenkronKuyrugu.objects.filter(
        durum=SenkronKuyrukDurum.BEKLIYOR,
        sonraki_deneme__lte=tz.now(),
    ).order_by('sonraki_deneme')[:50]

    islendi = 0
    hatali = 0

    for gorev in bekleyenler:
        # Faz 2+ kapsamında modül dispatch mantığı buraya eklenecek.
        gorev.durum = SenkronKuyrukDurum.ISLENIYOR
        gorev.save(update_fields=['durum'])
        islendi += 1

    logger.info('Kuyruk işleme: %d görev ele alındı, %d hata.', islendi, hatali)
    return {'islendi': islendi, 'hatali': hatali}


# ─────────────────────────────────────────────────────────────
# Faz 3 görevleri — Stok
# ─────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='dia_integration.sync_stok_listesi',
)
def sync_stok_listesi(self, delta: bool = True) -> dict:
    """
    DİA stok listesini MEStakip'e senkronize eder.

    Celery Beat önerisi: her 60 dakikada bir delta=True ile çalıştır.
    """
    from dia_integration.services import StokService
    from dia_integration.models import SyncTetikleyen
    from dia_integration.exceptions import DiaBaseError

    try:
        sonuc = StokService.dia_dan_senkronize_et(
            delta=delta,
            tetikleyen=SyncTetikleyen.OTOMATIK,
        )
        return {
            'toplam': sonuc.toplam,
            'eklenen': sonuc.eklenen,
            'guncellenen': sonuc.guncellenen,
            'hatali': sonuc.hatali,
        }
    except DiaBaseError as exc:
        logger.error('sync_stok_listesi DİA hatası: %s', exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error('sync_stok_listesi beklenmedik hata: %s', exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    name='dia_integration.sync_depo_miktarlari',
)
def sync_depo_miktarlari(self) -> dict:
    """
    DİA depo miktarlarını günceller.

    Celery Beat önerisi: her 15 dakikada bir çalıştır.
    """
    from dia_integration.services import StokService
    from dia_integration.exceptions import DiaBaseError

    try:
        n = StokService.depo_miktarlarini_guncelle()
        return {'guncellenen': n}
    except DiaBaseError as exc:
        logger.error('sync_depo_miktarlari DİA hatası: %s', exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error('sync_depo_miktarlari beklenmedik hata: %s', exc)
        raise self.retry(exc=exc)
