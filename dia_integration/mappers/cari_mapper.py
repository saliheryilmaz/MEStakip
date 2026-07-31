"""
CariMapper — DİA scf_carikart JSON ↔ erp.Cari modeli dönüştürücü.

Sorumluluk:
  - DİA'dan gelen ham dict → Cari model alanlarına eşleme
  - Cari modeli → DİA'ya gönderilecek 'kart' dict'ine eşleme
  - Tip dönüşümleri (string → Decimal, DİA kodu → seçenek sabiti)
  - DİA'ya özgü alan adlarını sistemin geri kalanından izole etmek

Bu sınıf yan etkisi olmayan saf dönüşüm fonksiyonları içerir —
hiçbir veritabanı işlemi, API çağrısı veya iş kuralı yoktur.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from erp.models import Cari, CariDurum, CariTip

if TYPE_CHECKING:
    pass


def _to_decimal(value: str | None, varsayilan: str = '0') -> Decimal:
    """DİA'dan gelen sayısal string'i Decimal'e çevirir."""
    try:
        return Decimal(str(value).replace(',', '.')) if value else Decimal(varsayilan)
    except InvalidOperation:
        return Decimal(varsayilan)


def _dia_tip_to_model(dia_tip: str) -> str:
    """DİA carikarttipi → CariTip seçeneği."""
    mapping = {
        'AL': CariTip.ALICI,
        'SA': CariTip.SATICI,
        'AS': CariTip.ALICI_SATICI,
    }
    return mapping.get(dia_tip, CariTip.DIGER)


def _model_tip_to_dia(tip: str) -> str:
    """CariTip → DİA carikarttipi."""
    mapping = {
        CariTip.ALICI: 'AL',
        CariTip.SATICI: 'SA',
        CariTip.ALICI_SATICI: 'AS',
        CariTip.DIGER: 'AL',
    }
    return mapping.get(tip, 'AL')


def _dia_durum_to_model(dia_durum: str) -> str:
    """DİA durum ('A'/'P') → CariDurum."""
    return CariDurum.AKTIF if dia_durum == 'A' else CariDurum.PASIF


class CariMapper:
    """
    DİA cari kart verisi ile erp.Cari modeli arasında dönüşüm.

    Kullanım:
        cari = CariMapper.dia_to_model(dia_dict)          # yeni nesne, kaydedilmemiş
        alan_dict = CariMapper.dia_to_fields(dia_dict)    # update_or_create için
        kart = CariMapper.model_to_dia(cari)              # DİA'ya gönderilecek kart
    """

    # ── DİA → Model ──────────────────────────────────────────

    @staticmethod
    def dia_to_fields(d: dict) -> dict:
        """
        DİA scf_carikart dict'ini erp.Cari alan sözlüğüne çevirir.

        Sadece değer dönüşümü — veritabanı işlemi yok.
        update_or_create(defaults=...) ile kullanılmak üzere tasarlanmıştır.

        Args:
            d: DİA'dan gelen scf_carikart_listele/getir kaydı

        Returns:
            Cari model alanlarına karşılık gelen dict
        """
        return {
            'cari_kodu': d.get('carikartkodu', ''),
            'unvan': d.get('unvan', ''),
            'kisa_aciklama': d.get('kisaaciklama', ''),
            'tip': _dia_tip_to_model(d.get('carikarttipi', 'AL')),
            'durum': _dia_durum_to_model(d.get('durum', 'A')),
            'vergi_no': d.get('verginumarasi', ''),
            'tc_kimlik_no': d.get('tckimlikno', ''),
            'vergi_dairesi': d.get('vergidairesi', ''),
            'daire_kodu': d.get('dairekodu', ''),
            'telefon1': d.get('telefon1', ''),
            'telefon2': d.get('telefon2', ''),
            'cep_tel': d.get('ceptel', ''),
            'fax': d.get('fax', ''),
            'eposta': d.get('eposta', ''),
            'web_url': d.get('weburl', ''),
            'adres1': d.get('adres1', ''),
            'adres2': d.get('adres2', ''),
            'ilce': d.get('ilce', ''),
            'sehir': d.get('sehir', ''),
            'posta_kodu': d.get('postakodu', ''),
            'ulke': d.get('ulke', 'TÜRKİYE'),
            'risk_limiti': _to_decimal(d.get('risklimiti')),
            'indirim_orani': _to_decimal(d.get('indirimorani')),
            'bakiye': _to_decimal(d.get('bakiye')),
            'borc_toplam': _to_decimal(d.get('borctoplam')),
            'alacak_toplam': _to_decimal(d.get('alacaktoplam')),
            'efatura_senaryosu': str(d.get('efaturasenaryosu', '')),
            'notlar': d.get('note', ''),
            # DiaSyncMixin alanları
            'dia_key': str(d.get('_key', '')),
            'dia_son_degisiklik': _parse_datetime(d.get('_date')),
        }

    @staticmethod
    def dia_to_model(d: dict) -> Cari:
        """
        DİA dict'inden kaydedilmemiş bir Cari nesnesi oluşturur.
        Sadece yeni kayıt oluşturmada kullanılır; güncellemede
        dia_to_fields + update_or_create tercih edilir.
        """
        return Cari(**CariMapper.dia_to_fields(d))

    # ── Model → DİA ──────────────────────────────────────────

    @staticmethod
    def model_to_dia(cari: 'Cari') -> dict:
        """
        erp.Cari modelini DİA scf_carikart_ekle/guncelle 'kart' formatına çevirir.

        DİA zorunlu alanları:
          - carikartkodu (benzersiz, max 30 karakter)
          - unvan
          - carikarttipi (AL/SA/AS)

        Returns:
            DİA 'kart' parametresi olarak kullanılacak dict
        """
        kart: dict = {
            'carikartkodu': cari.cari_kodu,
            'unvan': cari.unvan,
            'kisaaciklama': cari.kisa_aciklama or cari.unvan,
            'carikarttipi': _model_tip_to_dia(cari.tip),
            'durum': 'A' if cari.aktif_mi else 'P',
            'verginumarasi': cari.vergi_no or '',
            'tckimlikno': cari.tc_kimlik_no or '',
            'telefon1': cari.telefon1 or '',
            'telefon2': cari.telefon2 or '',
            'ceptel': cari.cep_tel or '',
            'fax': cari.fax or '',
            'eposta': cari.eposta or '',
            'weburl': cari.web_url or '',
            'adres1': cari.adres1 or '',
            'adres2': cari.adres2 or '',
            'ilce': cari.ilce or '',
            'postakodu': cari.posta_kodu or '',
            'risklimiti': str(cari.risk_limiti),
            'indirimorani': str(cari.indirim_orani),
            'note': cari.notlar or '',
        }
        # Güncelleme için _key ekle
        if cari.dia_key:
            kart['_key'] = cari.dia_key
        return kart


# ── Yardımcı: datetime parse ──────────────────────────────────

def _parse_datetime(value: str | None):
    """
    DİA _date alanını ('2026-04-01 10:29:41') Django aware datetime'a çevirir.
    Hata durumunda None döner.
    """
    if not value:
        return None
    from django.utils import timezone
    import datetime
    try:
        naive = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return timezone.make_aware(naive)
    except (ValueError, TypeError):
        return None
