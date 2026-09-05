"""
FaturaService — DİA scf_fatura + scf_fatura_getir → erp.Fatura/FaturaKalemi senkronizasyon servisi.
"""
from __future__ import annotations
import datetime
import logging
import os
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
_DELTA_LOOKBACK_MINUTES = int(os.environ.get('DIA_DELTA_LOOKBACK_MINUTES', '15'))


def _dec(v, d='0') -> Decimal:
    try:
        if v is None or v == '':
            return Decimal(d)
        raw = str(v).strip()
        if ',' in raw:
            raw = raw.replace('.', '').replace(',', '.')
        return Decimal(raw)
    except InvalidOperation:
        return Decimal(d)


def _str(d, key, default='') -> str:
    val = d.get(key)
    if isinstance(val, dict):
        return val.get('aciklama', '') or val.get('adi', '') or default
    return str(val or default).strip()


def _ilk_metin(d: dict, keys: tuple[str, ...], default: str = '') -> str:
    for key in keys:
        val = d.get(key)
        if isinstance(val, dict):
            val = (
                val.get('aciklama') or val.get('adi') or val.get('ad')
                or val.get('depoadi') or val.get('subeadi')
            )
        if val not in (None, ''):
            return str(val).strip()
    return default


def _kanal_belirle(fatura: Fatura, kalem: dict) -> str:
    kanal = _ilk_metin(kalem, ('kanal', '__kanal', 'satis_kanali', '__satis_kanali'))
    if kanal:
        return kanal.upper()
    if fatura.tur == 'A':
        return 'TEDARİKÇİ'
    if fatura.tur == 'S':
        return 'PERAKENDE'
    if fatura.tur == 'I':
        return 'İADE'
    return (fatura.tur_aciklama or fatura.get_tur_display() or '').upper()


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
        baslangic_tarihi: datetime.date | str | None = None,
        bitis_tarihi: datetime.date | str | None = None,
        maksimum_kayit: int | None = None,
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
            filters = FaturaService._filtreleri_olustur(
                delta=delta,
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi,
            )
            logger.info(
                'Fatura sync başladı. delta=%s kalem_cek=%s filtreler=%s',
                delta,
                kalem_cek,
                filters,
            )

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

                    if maksimum_kayit is not None:
                        kalan = maksimum_kayit - sonuc.toplam
                        if kalan <= 0:
                            break
                        sayfa = sayfa[:kalan]

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
                    if maksimum_kayit is not None and sonuc.toplam >= maksimum_kayit:
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
                stok_kodu = stok_info.get('stokkartkodu', '') or stok_info.get('kod', '')
                stok_adi  = stok_info.get('aciklama', '') or stok_info.get('adi', '')
            else:
                stok_kodu = k.get('__stokkartkodu', '') or k.get('stokkartkodu', '')
                stok_adi  = k.get('__stokaciklama', '') or k.get('aciklama', '')

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
            bolge = _ilk_metin(
                k,
                ('bolge', '__bolge', 'subeadi', '__sourcesubeadi', '_key_sis_sube_source'),
                default=fatura.sube_adi or depo or fatura.depo_adi,
            )

            # Stok kartından marka / kategori / dot bilgilerini al
            marka    = _ilk_metin(k, ('marka', 'markaack', '__marka'))
            kategori = _ilk_metin(k, ('kategori', 'kategoriack', 'ozelkod2ack', '__kategori'))
            dot      = _ilk_metin(k, ('dot', 'uretimyili', 'yil', 'ozelkod1'))
            if stok_kodu:
                from erp.models import StokKart as SK
                sk = SK.objects.filter(stok_kodu=stok_kodu).values('marka', 'ozel_kod1', 'ozel_kod2').first()
                if sk:
                    marka    = marka or sk.get('marka', '')
                    dot      = dot or sk.get('ozel_kod1', '')   # Yıl / DOT
                    kategori = kategori or sk.get('ozel_kod2', '')   # Segment / Kategori

            yeni_kalemler.append(FaturaKalemi(
                fatura      = fatura,
                dia_key     = str(k.get('_key', '')),
                sirano      = k.get('sirano', 0),
                stok_kodu   = stok_kodu,
                stok_adi    = stok_adi,
                miktar      = _dec(k.get('miktar')),
                kanal       = _kanal_belirle(fatura, k),
                birim       = birim,
                prim        = _dec(k.get('prim') or k.get('primtutari') or k.get('komisyon')),
                maliyet     = _dec(k.get('maliyet') or k.get('maliyetfiyati') or k.get('alisfiyati') or k.get('sonalisfiyati')),
                birim_fiyat = _dec(k.get('birimfiyati') or k.get('yerelbirimfiyati') or k.get('sonbirimfiyati')),
                indirim     = _dec(k.get('indirimtoplam') or k.get('indirimorani')),
                tutar       = _dec(k.get('tutari') or k.get('nettutar') or k.get('yereltutari')),
                satisci     = satisci,
                odeme_plani = odeme,
                depo        = depo,
                marka       = marka,
                kategori    = kategori,
                dot         = dot,
                bolge       = bolge,
            ))

        FaturaKalemi.objects.bulk_create(yeni_kalemler)
        logger.debug('Fatura %s — %d kalem kaydedildi.', fatura.dia_key, len(yeni_kalemler))

    @staticmethod
    def _filtreleri_olustur(
        delta: bool,
        baslangic_tarihi: datetime.date | str | None = None,
        bitis_tarihi: datetime.date | str | None = None,
    ) -> list[dict]:
        filters = FaturaService._delta_filtresi(delta)
        baslangic = _tarih_filtre_degeri(baslangic_tarihi)
        bitis = _tarih_filtre_degeri(bitis_tarihi)
        if baslangic:
            filters.append({'field': 'tarih', 'operator': '>=', 'value': baslangic})
        if bitis:
            filters.append({'field': 'tarih', 'operator': '<=', 'value': bitis})
        return filters

    @staticmethod
    def _delta_filtresi(delta: bool) -> list[dict]:
        if not delta:
            return []
        son = (SyncLog.objects
               .filter(modul='fatura', durum__in=[SyncDurum.BASARILI, SyncDurum.KISMI_BASARILI])
               .order_by('-bitis').first())
        if not son or not son.bitis:
            return []
        filtre_zamani = timezone.localtime(son.bitis) - datetime.timedelta(minutes=_DELTA_LOOKBACK_MINUTES)
        return [{'field': '_date', 'operator': '>=', 'value': filtre_zamani.strftime('%Y-%m-%d %H:%M:%S')}]


def _tarih_filtre_degeri(value: datetime.date | str | None) -> str:
    if not value:
        return ''
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    try:
        return datetime.date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return ''
