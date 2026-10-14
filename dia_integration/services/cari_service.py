"""
CariService — DİA ↔ MEStakip cari senkronizasyon servisi.

Sorumluluklar:
  - DİA'dan cari listesini çekip yerel Cari modelini güncelleme (delta sync)
  - Yerel Cari kaydını DİA'ya oluşturma / güncelleme
  - Bakiye ve hesap durumu sorgulama
  - SyncLog / SyncHataKaydi yönetimi

Bu servis DiaClient'ı ve CariMapper'ı kullanır;
view/task katmanı bu servisi çağırır, doğrudan DiaClient'ı çağırmaz.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from dia_integration.client import DiaClient
from dia_integration.exceptions import DiaBaseError
from dia_integration.mappers.cari_mapper import CariMapper
from dia_integration.models import (
    SyncDurum,
    SyncHataKaydi,
    SyncLog,
    SyncTetikleyen,
)
from erp.models import Cari

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Delta sync için kullanılan DİA filtre operatörü
_DATE_FILTER_OP = '>='
_DELTA_LOOKBACK_MINUTES = int(os.environ.get('DIA_DELTA_LOOKBACK_MINUTES', '15'))


@dataclass
class SyncSonuc:
    """Senkronizasyon çalıştırmasının özeti."""
    toplam: int = 0
    eklenen: int = 0
    guncellenen: int = 0
    atlanan: int = 0
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


class CariService:
    """
    DİA ↔ MEStakip cari senkronizasyon servisi.

    Kullanım:
        # Tüm carileri senkronize et (ilk kurulum veya tam sync)
        sonuc = CariService.dia_dan_senkronize_et()

        # Sadece son sync'ten beri değişenleri çek (delta)
        sonuc = CariService.dia_dan_senkronize_et(delta=True)

        # MEStakip'te oluşturulan yeni cariyi DİA'ya yaz
        dia_key = CariService.dia_ya_gonder(cari)
    """

    # ── DİA → MEStakip ────────────────────────────────────────

    @staticmethod
    def dia_dan_senkronize_et(
        delta: bool = True,
        sayfa_boyutu: int = 100,
        tetikleyen: str = SyncTetikleyen.SISTEM,
        kullanici=None,
    ) -> SyncSonuc:
        """
        DİA'dan cari listesini çekip yerel Cari modelini günceller.

        Args:
            delta: True → son sync'ten beri değişenleri çek (_date filtresi)
                   False → tüm cari listesini çek (tam sync, yavaş)
            sayfa_boyutu: Tek API çağrısında çekilecek kayıt sayısı
            tetikleyen: SyncTetikleyen seçeneği
            kullanici: Tetikleyen Django kullanıcı (manuel çalıştırmada)

        Returns:
            SyncSonuc — eklenen/güncellenen/hatalı sayıları
        """
        log = SyncLog.objects.create(
            modul='cari',
            tetikleyen=tetikleyen,
            tetikleyen_kullanici=kullanici,
        )
        sonuc = SyncSonuc()

        try:
            filters = CariService._delta_filtresi_olustur(delta)
            logger.info('Cari sync başladı. delta=%s, filtreler=%s', delta, filters)

            with DiaClient() as client:
                offset = 0
                while True:
                    sayfa = client.listele(
                        modul='scf',
                        servis_adi='scf_carikart_listele',
                        filters=filters,
                        limit=sayfa_boyutu,
                        offset=offset,
                    )
                    if not sayfa:
                        break

                    for dia_kayit in sayfa:
                        sonuc.toplam += 1
                        try:
                            eklendi = CariService._kaydi_isle(dia_kayit, log)
                            if eklendi:
                                sonuc.eklenen += 1
                            else:
                                sonuc.guncellenen += 1
                        except Exception as exc:
                            sonuc.hatali += 1
                            hata_msg = f'{dia_kayit.get("carikartkodu","?")}: {exc}'
                            sonuc.hatalar.append(hata_msg)
                            logger.warning('Cari işleme hatası: %s', hata_msg)
                            SyncHataKaydi.objects.create(
                                sync_log=log,
                                modul='cari',
                                yerel_model='erp.Cari',
                                yerel_id=dia_kayit.get('carikartkodu', '?'),
                                dia_servis='scf_carikart_listele',
                                hata_kodu='',
                                hata_mesaji=str(exc),
                            )

                    if len(sayfa) < sayfa_boyutu:
                        break
                    offset += sayfa_boyutu

            # Son sync zamanını güncelle
            CariService._son_sync_guncelle()

            durum = (
                SyncDurum.BASARILI if sonuc.basarili_mi
                else (SyncDurum.KISMI_BASARILI if sonuc.toplam > sonuc.hatali else SyncDurum.BASARISIZ)
            )
            log.toplam_kayit = sonuc.toplam
            log.basarili_kayit = sonuc.toplam - sonuc.hatali
            log.hatali_kayit = sonuc.hatali
            log.tamamla(durum=durum)

            logger.info('Cari sync tamamlandı: %s', sonuc)
            return sonuc

        except DiaBaseError as exc:
            log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
            logger.error('Cari sync DİA hatası: %s', exc)
            raise
        except Exception as exc:
            log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
            logger.error('Cari sync beklenmedik hata: %s', exc)
            raise

    @staticmethod
    def _kaydi_isle(dia_kayit: dict, log: SyncLog) -> bool:
        """
        Tek bir DİA cari kaydını işler — oluşturur veya günceller.

        Returns:
            True → yeni oluşturuldu, False → güncellendi
        """
        alanlar = CariMapper.dia_to_fields(dia_kayit)
        dia_key = alanlar.pop('dia_key', '')
        dia_son_degisiklik = alanlar.pop('dia_son_degisiklik', None)
        cari_kodu = alanlar.get('cari_kodu', '')

        if not cari_kodu:
            raise ValueError('carikartkodu boş geldi')

        with transaction.atomic():
            cari, olusturuldu = Cari.objects.update_or_create(
                cari_kodu=cari_kodu,
                defaults=alanlar,
            )
            # Sync alanlarını güncelle
            cari.dia_key = dia_key
            cari.dia_son_degisiklik = dia_son_degisiklik
            cari.son_sync_tarihi = timezone.now()
            from dia_integration.mixins import SyncDurumSecenekleri
            cari.sync_durumu = SyncDurumSecenekleri.SENKRON
            cari.save(update_fields=[
                'dia_key', 'dia_son_degisiklik',
                'son_sync_tarihi', 'sync_durumu',
            ])

        return olusturuldu

    @staticmethod
    def _delta_filtresi_olustur(delta: bool) -> list[dict]:
        """Delta sync için _date filtresi oluşturur."""
        if not delta:
            return []
        son_sync = CariService._son_sync_tarihi_al()
        if not son_sync:
            return []
        filtre_zamani = timezone.localtime(son_sync) - timedelta(minutes=_DELTA_LOOKBACK_MINUTES)
        return [{
            'field': '_date',
            'operator': _DATE_FILTER_OP,
            'value': filtre_zamani.strftime('%Y-%m-%d %H:%M:%S'),
        }]

    @staticmethod
    def _son_sync_tarihi_al():
        """En son başarılı cari sync zamanını döner."""
        son_log = (
            SyncLog.objects
            .filter(modul='cari', durum__in=[SyncDurum.BASARILI, SyncDurum.KISMI_BASARILI])
            .order_by('-bitis')
            .first()
        )
        return son_log.bitis if son_log and son_log.bitis else None

    @staticmethod
    def _son_sync_guncelle() -> None:
        """DiaBaglanti.firma_donem_guncellendi'yi değil, SyncLog'u kullanıyoruz.
        Bu metod şimdilik placeholder — gerekirse ileride genişletilir."""
        pass

    # ── MEStakip → DİA ────────────────────────────────────────

    @staticmethod
    def dia_ya_gonder(cari: Cari) -> str:
        """
        Yerel Cari kaydını DİA'ya oluşturur veya günceller.

        Idempotency: cari.dia_key varsa güncelleme, yoksa oluşturma yapılır.

        Args:
            cari: Gönderilecek Cari modeli

        Returns:
            DİA _key değeri (str)

        Raises:
            DiaBaseError ve alt sınıfları
        """
        kart = CariMapper.model_to_dia(cari)

        with DiaClient() as client:
            if cari.dia_da_var_mi:
                # Güncelleme
                logger.info('DİA cari güncelleniyor: %s (key=%s)', cari.cari_kodu, cari.dia_key)
                dia_key = client.guncelle(
                    modul='scf',
                    servis_adi='scf_carikart_guncelle',
                    kart=kart,
                )
            else:
                # Yeni oluşturma
                logger.info('DİA\'da yeni cari oluşturuluyor: %s', cari.cari_kodu)
                dia_key = client.ekle(
                    modul='scf',
                    servis_adi='scf_carikart_ekle',
                    kart=kart,
                )

        # Başarılı — sync durumunu güncelle
        cari.sync_basarili_isle(dia_key=dia_key)
        logger.info('DİA cari gönderim başarılı: %s → key=%s', cari.cari_kodu, dia_key)
        return dia_key

    # ── Bakiye sorgu ──────────────────────────────────────────

    @staticmethod
    def bakiye_guncelle(cari: Cari) -> dict:
        """
        DİA'dan tek bir carinin güncel bakiyesini çekip modeli günceller.

        Args:
            cari: dia_key alanı dolu olan Cari modeli

        Returns:
            {'bakiye': Decimal, 'borc': Decimal, 'alacak': Decimal}
        """
        if not cari.dia_da_var_mi:
            raise ValueError(f'Cari DİA\'da kayıtlı değil: {cari.cari_kodu}')

        with DiaClient() as client:
            # Tek cari listele (_key filtresiyle) — en güncel bakiye bilgisi dahil
            sonuc = client.listele(
                modul='scf',
                servis_adi='scf_carikart_listele',
                filters=[{'field': '_key', 'operator': '=', 'value': cari.dia_key}],
                limit=1,
            )

        if not sonuc:
            raise ValueError(f'DİA\'dan cari bulunamadı: key={cari.dia_key}')

        d = sonuc[0]
        from dia_integration.mappers.cari_mapper import _to_decimal
        bakiye = _to_decimal(d.get('bakiye'))
        borc = _to_decimal(d.get('borctoplam'))
        alacak = _to_decimal(d.get('alacaktoplam'))

        Cari.objects.filter(pk=cari.pk).update(
            bakiye=bakiye,
            borc_toplam=borc,
            alacak_toplam=alacak,
        )
        logger.info('Bakiye güncellendi: %s → %s', cari.cari_kodu, bakiye)
        return {'bakiye': bakiye, 'borc': borc, 'alacak': alacak}
