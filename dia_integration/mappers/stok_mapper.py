"""
StokMapper — DİA scf_stokkart JSON ↔ erp.StokKart modeli dönüştürücü.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from erp.models import StokDurum, StokKart, StokKartTur
from dia_integration.mappers.cari_mapper import _parse_datetime


def _to_decimal(value, varsayilan: str = '0') -> Decimal:
    try:
        return Decimal(str(value).replace(',', '.')) if value else Decimal(varsayilan)
    except InvalidOperation:
        return Decimal(varsayilan)


def _dia_tur_to_model(dia_tur: str) -> str:
    mapping = {
        'TCR': StokKartTur.TICARI_MAL,
        'HMM': StokKartTur.HAMMADDE,
        'YRM': StokKartTur.YARI_MAMUL,
        'MAM': StokKartTur.MAMUL,
        'HZM': StokKartTur.HIZMET,
    }
    return mapping.get(dia_tur, StokKartTur.DIGER)


def _model_tur_to_dia(tur: str) -> str:
    mapping = {
        StokKartTur.TICARI_MAL: 'TCR',
        StokKartTur.HAMMADDE:   'HMM',
        StokKartTur.YARI_MAMUL: 'YRM',
        StokKartTur.MAMUL:      'MAM',
        StokKartTur.HIZMET:     'HZM',
        StokKartTur.DIGER:      'TCR',
    }
    return mapping.get(tur, 'TCR')


def _ozelkod_aciklamasi(deger, kod) -> str:
    """DİA'nın "Açıklama (Kod)" birleşik değerinden açıklamayı ayıklar."""
    metin = str(deger or '').strip()
    kod = str(kod or '').strip()
    ek = f' ({kod})' if kod else ''
    return metin[:-len(ek)].strip() if ek and metin.endswith(ek) else metin


class StokMapper:
    """
    DİA stok kart verisi ile erp.StokKart modeli arasında dönüşüm.

    Kullanım:
        alanlar = StokMapper.dia_to_fields(dia_dict)
        kart    = StokMapper.model_to_dia(stok)
    """

    @staticmethod
    def dia_to_fields(d: dict) -> dict:
        """
        DİA scf_stokkart dict'ini erp.StokKart alan sözlüğüne çevirir.
        update_or_create(defaults=...) ile kullanılmak üzere tasarlanmıştır.
        """
        return {
            'stok_kodu':          d.get('stokkartkodu', ''),
            'uretici_kodu':      d.get('ekalan1') or d.get('tedarikcistokkodlari') or d.get('tedarikcistokkodu') or d.get('uretici_kodu') or d.get('ureticikodu', ''),
            'aciklama':           d.get('aciklama', ''),
            'tur':                _dia_tur_to_model(d.get('stokkartturu', 'TCR')),
            'durum':              StokDurum.AKTIF if d.get('durum') == 'A' else StokDurum.PASIF,
            'ana_birim':          d.get('birimadi', ''),
            'ana_birim_dia_key':  str(d.get('anabirimkey', '')),
            'ana_barkod':         d.get('anabarkod') or d.get('barkodu', ''),
            'marka':              d.get('markaack') or d.get('marka', ''),
            'ozel_kod1':          d.get('ozelkod1', ''),
            # DİA M3 = Stok Özel Kod 2; stok listesi bunu
            # `ozelkod3`: "Yazlık (1001)" biçiminde döndürüyor.
            'mevsim':             (
                _ozelkod_aciklamasi(d.get('ozelkod3'), d.get('ozelkod3kodu'))
                or d.get('ozelkod3aciklama')
                or d.get('ozelkod3ack')
                or ''
            ),
            # DİA stok listesi M4 (Stok Özel Kod 3) değerini `ozelkod4`
            # alanında "Açıklama (Kod)" biçiminde döndürüyor. Kullanıcının
            # Segment alanı için gösterdiği DİA kartı M4 olduğundan bunu
            # önceliklendir; eski M2 alias'ları eski kayıtlar için yedek kalsın.
            'ozel_kod2':          (
                _ozelkod_aciklamasi(d.get('ozelkod4'), d.get('ozelkod4kodu'))
                or d.get('ozelkod4aciklama')
                or d.get('ozelkod4ack')
                or d.get('ozelkod2aciklama')
                or d.get('ozelkod2ack')
                or d.get('ozelkod2')
                or d.get('ozelkod2kodu')
                or d.get('altgrup2ack')
                or d.get('altgrup2')
                or ''
            ),
            'kdv_alis':           _to_decimal(d.get('kdvalis'), '18'),
            'kdv_satis':          _to_decimal(d.get('kdvsatis'), '18'),
            'fiyat1':             _to_decimal(d.get('fiyat1')),
            'fiyat2':             _to_decimal(d.get('fiyat2')),
            'gercek_stok':        _to_decimal(d.get('gercek_stok')),
            'fiili_stok':         _to_decimal(d.get('fiili_stok')),
            'notlar':             d.get('note', ''),
            # DiaSyncMixin
            'dia_key':            str(d.get('_key', '')),
            'dia_son_degisiklik': _parse_datetime(d.get('_date')),
        }

    @staticmethod
    def model_to_dia(stok: 'StokKart') -> dict:
        """
        erp.StokKart modelini DİA scf_stokkart_ekle/guncelle 'kart' formatına çevirir.

        DİA zorunlu alanları:
          - stokkartkodu (benzersiz, max 30 karakter)
          - aciklama
          - stokkartturu (TCR, HMM, vb.)
        """
        kart: dict = {
            'stokkartkodu':  stok.stok_kodu,
            'aciklama':      stok.aciklama,
            'stokkartturu':  _model_tur_to_dia(stok.tur),
            'durum':         'A' if stok.aktif_mi else 'P',
            'note':          stok.notlar or '',
        }
        if stok.dia_key:
            kart['_key'] = stok.dia_key
        return kart
