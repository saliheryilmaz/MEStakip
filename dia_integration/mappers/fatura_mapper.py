"""
FaturaMapper — DİA scf_fatura JSON ↔ erp.Fatura modeli dönüştürücü.
"""
from __future__ import annotations
import datetime
from decimal import Decimal, InvalidOperation
from erp.models import Fatura, FaturaTur
from dia_integration.mappers.cari_mapper import _parse_datetime


def _dec(val, default='0') -> Decimal:
    try:
        if val is None or val == '':
            return Decimal(default)
        raw = str(val).strip()
        if ',' in raw:
            raw = raw.replace('.', '').replace(',', '.')
        return Decimal(raw)
    except InvalidOperation:
        return Decimal(default)


def _tur(d: dict) -> str:
    """DİA fatura turukisa → FaturaTur."""
    tur_kisa = (d.get('turukisa') or '').upper().strip()

    alis_kodlari = {'MA', 'AH', 'MI', 'AI', 'GA', 'HA'}   # Mal Alım, Alınan Hizmet, vb.
    iade_kodlari = {'SI', 'RI', 'AI', 'IAD', 'RET'}        # İadeler
    satis_kodlari = {'PS', 'TS', 'SH', 'GS', 'ES', 'FS'}  # Perakende/Toptan/Hizmet Satış

    if tur_kisa in iade_kodlari:
        return FaturaTur.IADE
    if tur_kisa in alis_kodlari:
        return FaturaTur.ALIS
    if tur_kisa in satis_kodlari:
        return FaturaTur.SATIS

    # Fallback: turuack içinde anahtar kelime ara
    turuack = (d.get('turuack') or '').upper()
    if 'ALIM' in turuack or 'ALIŞ' in turuack or 'ALIS' in turuack:
        return FaturaTur.ALIS
    if 'İADE' in turuack or 'IADE' in turuack or 'RET' in turuack:
        return FaturaTur.IADE
    if 'SATIŞ' in turuack or 'SATIS' in turuack:
        return FaturaTur.SATIS

    return FaturaTur.DIGER


class FaturaMapper:
    @staticmethod
    def dia_to_fields(d: dict) -> dict:
        return {
            'fis_no':       d.get('fisno', ''),
            'belge_no':     d.get('belgeno2', '') or d.get('belgeno', ''),
            'tarih':        _parse_tarih(d.get('tarih')),
            'saat':         d.get('saat', ''),
            'tur':          _tur(d),
            'tur_aciklama': d.get('turuack', '') or d.get('turu_kisa', ''),
            'cari_kodu':    d.get('__carikartkodu', '') or d.get('carikartkodu', ''),
            'cari_unvan':   d.get('__cariunvan', '') or d.get('cariunvan', ''),
            'toplam':       _dec(d.get('toplamara') or d.get('toplam')),
            'net':          _dec(d.get('net') or d.get('netdvz')),
            'indirim':      _dec(d.get('toplamindirim')),
            'depo_adi':     d.get('__sourcedepoadi', ''),
            'sube_adi':     d.get('__sourcesubeadi', ''),
            'aciklama':     (d.get('aciklama') or '').strip(),
            # DiaSyncMixin
            'dia_key':             str(d.get('_key', '')),
            'dia_son_degisiklik':  _parse_datetime(d.get('_date')),
        }


def _parse_tarih(val):
    if not val:
        return None
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    raw = str(val).strip()
    try:
        return datetime.date.fromisoformat(raw[:10])
    except (ValueError, TypeError):
        pass
    for fmt in ('%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.datetime.strptime(raw[:10], fmt).date()
        except (ValueError, TypeError):
            continue
    return None
