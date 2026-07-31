"""
FaturaService — DİA scf_fatura + scf_fatura_getir → erp.Fatura/FaturaKalemi senkronizasyon servisi.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from dia_integration.client import DiaClient
from dia_integration.exceptions import DiaBaseError
from dia_integration.mappers.fatura_mapper import FaturaMapper
from dia_integration.mixins import SyncDurumSecenekleri
from dia_integration.models import SyncDurum, SyncHataKaydi, SyncLog, SyncTetikleyen
from erp.models import Fatura, FaturaKalemi

logger = logging.getLogger(__name__)


def _dec(v, d='0') -> Decimal:
    try:
        return Decimal(str(v).replace(',', '.')) if v else Decimal(d)
    except InvalidOperation:
        return Decimal(d)


def _str(d, key, default='') -> str:
    val = d.get(key)
    if isinstance(val, dict):
        return val.get('aciklama', '') or val.get('adi', '') or default
    return str(val or default).strip()


@dataclass
class FaturaSyncSonuc:
    toplam: int = 0
    eklenen: int = 0
    guncellenen: int = 0
    hatali: int = 0
    hatalar: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f'T:{self.toplam} E:{self.eklenen} G:{self.guncellenen} H:{self.hatali}'


class FaturaService:

    @staticmethod
    def dia_dan_senkronize_et(
        delta: bool = True,
        sayfa_boyutu: int = 50,
        kalem_cek: bool = True,
        tetikleyen: str = SyncTetikleyen.SISTEM,
        kullanici=None,
    ) -> FaturaSyncSonuc:
        """DİA'dan fatura listesini + kalemlerini çekip yerel modele kaydeder."""
        log = SyncLog.objects.create(
            modul='fatura',
            tetikleyen=tetikleyen,
            tetikleyen_kullanici=kullanici,
        )
        sonuc = FaturaSyncSonuc()

        try:
            filters = FaturaService._delta_filtresi(delta)
            logger.info('Fatura sync başladı. delta=%s kalem_cek=%s', delta, kalem_cek)

            with DiaClient() as client:
                offset = 0
                while True:
                    sayfa = client.listele(
                        modul='scf',
                        servis_adi='scf_fatura_listele',
                        filters=filters,
                        limit=sayfa_boyutu,
                        offset=offset,
                    )
                    if not sayfa:
                        break

                    for d in sayfa:
                        sonuc.toplam += 1
                        try:
                            fatura, eklendi = FaturaService._fatura_isle(d)
                            if eklendi:
                                sonuc.eklenen += 1
                            else:
                                sonuc.guncellenen += 1

                            # Kalem detayını çek
                            if kalem_cek and fatura.dia_key:
                                try:
                                    yanit = client.ozel_cagri(
                                        modul='scf',
                                        servis_adi='scf_fatura_getir',
                                        data={'key': int(fatura.dia_key)},
                                    )
                                    kalemler = yanit.get('result', {})
                                    if isinstance(kalemler, dict):
                                        FaturaService._kalemleri_isle(fatura, kalemler)
                                except Exception as ke:
                                    logger.warning('Kalem çekme hatası fatura %s: %s', fatura.dia_key, ke)

                        except Exception as exc:
                            sonuc.hatali += 1
                            msg = f'{d.get("fisno","?")}: {exc}'
                            sonuc.hatalar.append(msg)
                            SyncHataKaydi.objects.create(
                                sync_log=log, modul='fatura',
                                yerel_model='erp.Fatura',
                                yerel_id=d.get('fisno', '?'),
                                dia_servis='scf_fatura_listele',
                                hata_mesaji=str(exc),
                            )

                    if len(sayfa) < sayfa_boyutu:
                        break
                    offset += sayfa_boyutu

            durum = (SyncDurum.BASARILI if not sonuc.hatali
                     else (SyncDurum.KISMI_BASARILI if sonuc.toplam > sonuc.hatali
                           else SyncDurum.BASARISIZ))
            log.toplam_kayit = sonuc.toplam
            log.basarili_kayit = sonuc.toplam - sonuc.hatali
            log.hatali_kayit = sonuc.hatali
            log.tamamla(durum=durum)
            logger.info('Fatura sync tamamlandı: %s', sonuc)
            return sonuc

        except DiaBaseError as exc:
            log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
            raise
        except Exception as exc:
            log.tamamla(durum=SyncDurum.BASARISIZ, hata=str(exc))
            raise

    @staticmethod
    def _fatura_isle(d: dict):
        """Tek fatura başlığını kaydet. (fatura, olusturuldu_mu) döner."""
        alanlar = FaturaMapper.dia_to_fields(d)
        dia_key = alanlar.pop('dia_key', '')
        dia_son = alanlar.pop('dia_son_degisiklik', None)

        with transaction.atomic():
            if dia_key:
                fatura, ok = Fatura.objects.update_or_create(dia_key=dia_key, defaults=alanlar)
            else:
                fis_no = alanlar.get('fis_no', '')
                fatura, ok = Fatura.objects.update_or_create(fis_no=fis_no, defaults=alanlar)
            fatura.dia_key = dia_key
            fatura.dia_son_degisiklik = dia_son
            fatura.son_sync_tarihi = timezone.now()
            fatura.sync_durumu = SyncDurumSecenekleri.SENKRON
            fatura.save(update_fields=['dia_key', 'dia_son_degisiklik', 'son_sync_tarihi', 'sync_durumu'])
        return fatura, ok

    @staticmethod
    def _kalemleri_isle(fatura: Fatura, getir_yanit: dict) -> None:
        """scf_fatura_getir yanıtından m_kalemler'i işle."""
        kalemler_raw = getir_yanit.get('m_kalemler', [])
        if not kalemler_raw:
            return

        # Mevcut kalemleri sil, yeniden yaz (idempotent)
        FaturaKalemi.objects.filter(fatura=fatura).delete()

        yeni_kalemler = []
        for k in kalemler_raw:
            # Stok bilgisi _key_kalemturu içinde dict olarak geliyor
            stok_info = k.get('_key_kalemturu', {})
            if isinstance(stok_info, dict):
                stok_kodu = stok_info.get('stokkartkodu', '')
                stok_adi  = stok_info.get('aciklama', '')
            else:
                stok_kodu = ''
                stok_adi  = ''

            # Birim
            birim_info = k.get('_key_scf_kalem_birimleri', [])
            birim = ''
            if isinstance(birim_info, list) and len(birim_info) >= 2:
                birim = birim_info[1] if isinstance(birim_info[1], str) else ''

            # Satış temsilcisi
            satisci_info = k.get('_key_scf_satiselemani', {})
            satisci = _str({'v': satisci_info}, 'v') if not isinstance(satisci_info, dict) else (satisci_info.get('aciklama') or '')

            # Ödeme planı
            odeme_info = k.get('_key_scf_odeme_plani', {})
            odeme = _str({'v': odeme_info}, 'v') if not isinstance(odeme_info, dict) else (odeme_info.get('aciklama') or '')

            # Depo
            depo_info = k.get('_key_sis_depo_source', {})
            depo = _str({'v': depo_info}, 'v') if not isinstance(depo_info, dict) else (depo_info.get('depoadi') or '')

            # Stok kartından marka / kategori / dot bilgilerini al
            marka    = ''
            kategori = ''
            dot      = ''
            if stok_kodu:
                from erp.models import StokKart as SK
                sk = SK.objects.filter(stok_kodu=stok_kodu).values('marka', 'ozel_kod1', 'ozel_kod2').first()
                if sk:
                    marka    = sk.get('marka', '')
                    dot      = sk.get('ozel_kod1', '')   # Yıl / DOT
                    kategori = sk.get('ozel_kod2', '')   # Segment / Kategori

            yeni_kalemler.append(FaturaKalemi(
                fatura      = fatura,
                dia_key     = str(k.get('_key', '')),
                sirano      = k.get('sirano', 0),
                stok_kodu   = stok_kodu,
                stok_adi    = stok_adi,
                miktar      = _dec(k.get('miktar')),
                birim       = birim,
                birim_fiyat = _dec(k.get('birimfiyati') or k.get('yerelbirimfiyati')),
                indirim     = _dec(k.get('indirimtoplam')),
                tutar       = _dec(k.get('tutari')),
                satisci     = satisci,
                odeme_plani = odeme,
                depo        = depo,
                marka       = marka,
                kategori    = kategori,
                dot         = dot,
            ))

        FaturaKalemi.objects.bulk_create(yeni_kalemler)
        logger.debug('Fatura %s — %d kalem kaydedildi.', fatura.dia_key, len(yeni_kalemler))

    @staticmethod
    def _delta_filtresi(delta: bool) -> list[dict]:
        if not delta:
            return []
        son = (SyncLog.objects
               .filter(modul='fatura', durum__in=[SyncDurum.BASARILI, SyncDurum.KISMI_BASARILI])
               .order_by('-bitis').first())
        if not son or not son.bitis:
            return []
        return [{'field': '_date', 'operator': '>=', 'value': son.bitis.strftime('%Y-%m-%d %H:%M:%S')}]
