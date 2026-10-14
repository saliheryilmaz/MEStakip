"""
StokService — DİA ↔ MEStakip stok + depo senkronizasyon servisi.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from dia_integration.client import DiaClient
from dia_integration.exceptions import DiaBaseError
from dia_integration.mappers.stok_mapper import StokMapper, _to_decimal
from dia_integration.mixins import SyncDurumSecenekleri
from dia_integration.models import (
    SyncDurum,
    SyncHataKaydi,
    SyncLog,
    SyncTetikleyen,
)
from erp.models import Depo, StokDepoMiktari, StokKart

logger = logging.getLogger(__name__)
_DELTA_LOOKBACK_MINUTES = int(os.environ.get('DIA_DELTA_LOOKBACK_MINUTES', '15'))


@dataclass
class StokSyncSonuc:
    toplam: int = 0
    eklenen: int = 0
    guncellenen: int = 0
    hatali: int = 0
    hatalar: list[str] = field(default_factory=list)

    @property
    def basarili_mi(self) -> bool:
        return self.hatali == 0

    def __str__(self) -> str:
        return (
            f'Toplam:{self.toplam} Eklenen:{self.eklenen} '
            f'Güncellenen:{self.guncellenen} Hatalı:{self.hatali}'
        )


class StokService:
    """
    DİA ↔ MEStakip stok ve depo senkronizasyon servisi.

    Kullanım:
        sonuc = StokService.dia_dan_senkronize_et(delta=True)
        StokService.depolari_senkronize_et()
        StokService.depo_miktarlarini_guncelle()
    """

    # ── DİA → MEStakip: Stok kartları ────────────────────────

    @staticmethod
    def dia_dan_senkronize_et(
        delta: bool = True,
        sayfa_boyutu: int = 100,
        tetikleyen: str = SyncTetikleyen.SISTEM,
        kullanici=None,
    ) -> StokSyncSonuc:
        """DİA'dan stok listesini çekip yerel StokKart modelini günceller."""
        log = SyncLog.objects.create(
            modul='stok',
            tetikleyen=tetikleyen,
            tetikleyen_kullanici=kullanici,
        )
        sonuc = StokSyncSonuc()

        try:
            filters = StokService._delta_filtresi_olustur(delta)
            logger.info('Stok sync başladı. delta=%s', delta)

            with DiaClient() as client:
                offset = 0
                while True:
                    sayfa = client.listele(
                        modul='scf',
                        servis_adi='scf_stokkart_listele',
                        filters=filters,
                        limit=sayfa_boyutu,
                        offset=offset,
                    )
                    if not sayfa:
                        break

                    for dia_kayit in sayfa:
                        sonuc.toplam += 1
                        try:
                            eklendi = StokService._kaydi_isle(dia_kayit)
                            if eklendi:
                                sonuc.eklenen += 1
                            else:
                                sonuc.guncellenen += 1
                        except Exception as exc:
                            sonuc.hatali += 1
                            hata_msg = f'{dia_kayit.get("stokkartkodu","?")}: {exc}'
                            sonuc.hatalar.append(hata_msg)
                            logger.warning('Stok işleme hatası: %s', hata_msg)
                            SyncHataKaydi.objects.create(
                                sync_log=log,
                                modul='stok',
                                yerel_model='erp.StokKart',
                                yerel_id=dia_kayit.get('stokkartkodu', '?'),
                                dia_servis='scf_stokkart_listele',
                                hata_mesaji=str(exc),
                            )

                    if len(sayfa) < sayfa_boyutu:
                        break
                    offset += sayfa_boyutu

            durum = (
                SyncDurum.BASARILI if sonuc.basarili_mi
                else (SyncDurum.KISMI_BASARILI if sonuc.toplam > sonuc.hatali else SyncDurum.BASARISIZ)
            )
            log.toplam_kayit = sonuc.toplam
            log.basarili_kayit = sonuc.toplam - sonuc.hatali
            log.hatali_kayit = sonuc.hatali
            log.tamamla(durum=durum)

            logger.info('Stok sync tamamlandı: %s', sonuc)
            return sonuc

        except DiaBaseError as exc:
            log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
            raise
        except Exception as exc:
            log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
            raise

    @staticmethod
    def _kaydi_isle(dia_kayit: dict) -> bool:
        """Tek bir DİA stok kaydını işler. True → yeni, False → güncellendi."""
        alanlar = StokMapper.dia_to_fields(dia_kayit)
        dia_key = alanlar.pop('dia_key', '')
        dia_son_degisiklik = alanlar.pop('dia_son_degisiklik', None)
        stok_kodu = alanlar.get('stok_kodu', '')

        if not stok_kodu:
            raise ValueError('stokkartkodu boş geldi')

        with transaction.atomic():
            stok, olusturuldu = StokKart.objects.update_or_create(
                stok_kodu=stok_kodu,
                defaults=alanlar,
            )
            stok.dia_key = dia_key
            stok.dia_son_degisiklik = dia_son_degisiklik
            stok.son_sync_tarihi = timezone.now()
            stok.sync_durumu = SyncDurumSecenekleri.SENKRON
            stok.save(update_fields=[
                'dia_key', 'dia_son_degisiklik',
                'son_sync_tarihi', 'sync_durumu',
            ])

        return olusturuldu

    @staticmethod
    def _delta_filtresi_olustur(delta: bool) -> list[dict]:
        if not delta:
            return []
        son_sync = StokService._son_sync_tarihi_al()
        if not son_sync:
            return []
        filtre_zamani = timezone.localtime(son_sync) - timedelta(minutes=_DELTA_LOOKBACK_MINUTES)
        return [{'field': '_date', 'operator': '>=', 'value': filtre_zamani.strftime('%Y-%m-%d %H:%M:%S')}]

    @staticmethod
    def _son_sync_tarihi_al():
        son_log = (
            SyncLog.objects
            .filter(modul='stok', durum__in=[SyncDurum.BASARILI, SyncDurum.KISMI_BASARILI])
            .order_by('-bitis').first()
        )
        return son_log.bitis if son_log and son_log.bitis else None

    # ── DİA → MEStakip: Depolar ───────────────────────────────

    @staticmethod
    def depolari_senkronize_et() -> int:
        """
        DiaBaglanti.firma_donem_bilgisi içindeki şube/depo hiyerarşisini
        Depo modeline yazar.
        """
        from dia_integration.models import DiaBaglanti

        baglanti = DiaBaglanti.objects.filter(is_aktif=True).first()
        if not baglanti or not baglanti.firma_donem_bilgisi:
            with DiaClient() as client:
                yanit = client.ozel_cagri(
                    modul='sis',
                    servis_adi='sis_yetkili_firma_donem_sube_depo',
                    data={},
                    firma_donem_ekle=False,
                )
            firmalar = yanit.get('result', [])
        else:
            firmalar = baglanti.firma_donem_bilgisi

        islenen = 0
        for firma in firmalar:
            for sube in firma.get('subeler', []):
                sube_key = str(sube.get('_key', ''))
                sube_adi = sube.get('subeadi', '')
                for depo in sube.get('depolar', []):
                    depo_key = str(depo.get('_key', ''))
                    depo_adi = depo.get('depoadi', depo.get('ad', ''))
                    if not depo_key:
                        continue
                    Depo.objects.update_or_create(
                        dia_key=depo_key,
                        defaults={
                            'ad': depo_adi,
                            'sube_adi': sube_adi,
                            'sube_dia_key': sube_key,
                            'aktif': True,
                        },
                    )
                    islenen += 1

        logger.info('Depo sync tamamlandı: %d depo.', islenen)
        return islenen

    # ── DİA → MEStakip: Depo miktarları ──────────────────────

    @staticmethod
    def depo_miktarlarini_guncelle(sayfa_boyutu: int = 50) -> int:
        """
        Tüm StokKart kayıtları için DİA'dan depo bazlı miktarları çeker.

        DİA bu serviste stok key filtresi gerektirir,
        bu nedenle her stok için ayrı çağrı yapılır.
        """
        log = SyncLog.objects.create(
            modul='stok_depo_miktar',
            tetikleyen=SyncTetikleyen.SISTEM,
        )

        stoklar = list(
            StokKart.objects
            .filter(dia_key__isnull=False)
            .exclude(dia_key='')
            .values_list('pk', 'dia_key', 'stok_kodu')
        )
        log.toplam_kayit = len(stoklar)
        toplam_islenen = 0

        try:
            with DiaClient() as client:
                for stok_pk, stok_dia_key, stok_kodu in stoklar:
                    try:
                        # DİA bu serviste stok anahtarını params._key içinde bekliyor.
                        yanit = client.ozel_cagri(
                            modul='scf',
                            servis_adi='scf_stok_depo_miktarlari_listele',
                            data={'params': {'_key': int(stok_dia_key)}},
                        )
                        sayfa = yanit.get('result', [])
                        if not isinstance(sayfa, list):
                            sayfa = [sayfa] if sayfa else []
                        for kayit in sayfa:
                            depo_key   = str(kayit.get('_key_sis_depo') or kayit.get('_key') or '')
                            gercek_mik = _to_decimal(kayit.get('gercek_stok') or kayit.get('miktar'))
                            fiili_mik  = _to_decimal(kayit.get('fiili_stok'))
                            stok_obj = StokKart.objects.filter(pk=stok_pk).first()
                            depo_obj = Depo.objects.filter(dia_key=depo_key).first()
                            if stok_obj and depo_obj:
                                StokDepoMiktari.objects.update_or_create(
                                    stok=stok_obj,
                                    depo=depo_obj,
                                    defaults={
                                        'gercek_miktar': gercek_mik,
                                        'fiili_miktar': fiili_mik,
                                    },
                                )
                                toplam_islenen += 1
                    except Exception as exc:
                        logger.warning('Stok %s depo miktar hatası: %s', stok_kodu, exc)

            log.basarili_kayit = len(stoklar)
            log.tamamla(durum=SyncDurum.BASARILI)
            logger.info('Depo miktarları güncellendi: %d stok × depo kaydı.', toplam_islenen)
            return toplam_islenen

        except Exception as exc:
            log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
            raise

    # ── MEStakip → DİA ────────────────────────────────────────

    @staticmethod
    def dia_ya_gonder(stok: StokKart) -> str:
        """
        Yerel StokKart kaydını DİA'ya oluşturur veya günceller.
        """
        kart = StokMapper.model_to_dia(stok)

        with DiaClient() as client:
            if stok.dia_da_var_mi:
                logger.info('DİA stok güncelleniyor: %s (key=%s)', stok.stok_kodu, stok.dia_key)
                dia_key = client.guncelle('scf', 'scf_stokkart_guncelle', kart)
            else:
                logger.info("DİA'da yeni stok oluşturuluyor: %s", stok.stok_kodu)
                dia_key = client.ekle('scf', 'scf_stokkart_ekle', kart)

        stok.sync_basarili_isle(dia_key=dia_key)
        logger.info('DİA stok gönderim başarılı: %s → key=%s', stok.stok_kodu, dia_key)
        return dia_key
