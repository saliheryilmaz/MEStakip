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


def _to_text(value, max_length: int | None = None, default: str = '') -> str:
    """DİA'dan gelen değeri veritabanı alanına güvenli metin olarak hazırlar."""
    if value is None:
        value = default
    text = str(value).strip()
    if max_length is not None:
        return text[:max_length]
    return text


def _to_tc_kimlik_no(value) -> str:
    """Sadece geçerli uzunluktaki TCKN değerini saklar."""
    digits = ''.join(ch for ch in _to_text(value) if ch.isdigit())
    return digits if len(digits) == 11 else ''


def _dia_tip_to_model(dia_tip: str) -> str:
    """DİA carikarttipi → CariTip seçeneği."""
    mapping = {
        'AL': CariTip.ALICI,
        'ST': CariTip.SATICI,
        # Eski/özel DIA kurulumlarından gelebilecek kodu da geriye dönük destekle.
        'SA': CariTip.SATICI,
        'AS': CariTip.ALICI_SATICI,
    }
    return mapping.get(dia_tip, CariTip.DIGER)


def _model_tip_to_dia(tip: str) -> str:
    """CariTip → DİA carikarttipi."""
    mapping = {
        CariTip.ALICI: 'AL',
        CariTip.SATICI: 'ST',
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
            'cari_kodu': _to_text(d.get('carikartkodu'), 30),
            'unvan': _to_text(d.get('unvan'), 200),
            'kisa_aciklama': _to_text(d.get('kisaaciklama'), 100),
            'tip': _dia_tip_to_model(d.get('carikarttipi', 'AL')),
            'durum': _dia_durum_to_model(d.get('durum', 'A')),
            'vergi_no': _to_text(d.get('verginumarasi'), 20),
            'tc_kimlik_no': _to_tc_kimlik_no(d.get('tckimlikno')),
            'vergi_dairesi': _to_text(d.get('vergidairesi'), 100),
            'daire_kodu': _to_text(d.get('dairekodu'), 20),
            'telefon1': _to_text(d.get('telefon1'), 30),
            'telefon2': _to_text(d.get('telefon2'), 30),
            'cep_tel': _to_text(d.get('ceptel'), 30),
            'fax': _to_text(d.get('fax'), 30),
            'eposta': _to_text(d.get('eposta'), 254),
            'web_url': _to_text(d.get('weburl'), 300),
            'adres1': _to_text(d.get('adres1'), 200),
            'adres2': _to_text(d.get('adres2'), 200),
            'ilce': _to_text(d.get('ilce'), 100),
            # ScfCarikartModel şehir bilgisini `il` alanında döndürür.
            'sehir': _to_text(d.get('il') or d.get('sehir'), 100),
            'posta_kodu': _to_text(d.get('postakodu'), 10),
            'ulke': _to_text(d.get('ulke'), 100, default='TÜRKİYE'),
            'risk_limiti': _to_decimal(d.get('risklimiti')),
            'indirim_orani': _to_decimal(d.get('indirimorani')),
            'bakiye': _to_decimal(d.get('bakiye')),
            'borc_toplam': _to_decimal(d.get('borctoplam')),
            'alacak_toplam': _to_decimal(d.get('alacaktoplam')),
            'efatura_senaryosu': _to_text(d.get('efaturasenaryosu'), 10),
            'notlar': _to_text(d.get('note')),
            # DiaSyncMixin alanları
            'dia_key': _to_text(d.get('_key')),
            'dia_son_degisiklik': _parse_datetime(d.get('_date')),
        }

    @staticmethod
    def rapor_to_fields(d: dict) -> dict:
        """scf1100c rapor satırını, raporda gerçekten bulunan alanlarla eşler.

        Cari kart listesi raporunun sütun tasarımı değişebildiği için raporda
        dönmeyen alanları boş değerle ezmez. Kod ve ünvan olmadan satır kabul
        edilmez; ``_key`` varsa DİA bağlantısı korunur.
        """
        alan_eslemeleri = {
            'carikartkodu': ('carikartkodu', 'cari_kodu', 'carikodu'),
            'unvan': ('unvan', 'carikartunvani'),
            'kisaaciklama': ('kisaaciklama', 'kisa_aciklama'),
            'carikarttipi': ('carikarttipi', 'cari_tipi', 'tip'),
            'durum': ('durum',),
            'verginumarasi': ('verginumarasi', 'vergi_no', 'vergino'),
            'tckimlikno': ('tckimlikno', 'tc_kimlik_no'),
            'vergidairesi': ('vergidairesi', 'vergi_dairesi'),
            'dairekodu': ('dairekodu', 'daire_kodu'),
            'telefon1': ('telefon1',),
            'telefon2': ('telefon2',),
            'ceptel': ('ceptel', 'cep_tel'),
            'fax': ('fax',),
            'eposta': ('eposta',),
            'weburl': ('weburl', 'web_url'),
            'adres1': ('adres1',),
            'adres2': ('adres2',),
            'ilce': ('ilce',),
            'il': ('il', 'sehir'),
            'postakodu': ('postakodu', 'posta_kodu'),
            'ulke': ('ulke',),
            'risklimiti': ('risklimiti', 'risk_limiti'),
            'indirimorani': ('indirimorani', 'indirim_orani'),
            'bakiye': ('bakiye',),
            'borctoplam': ('borctoplam', 'borc_toplam'),
            'alacaktoplam': ('alacaktoplam', 'alacak_toplam'),
            'efaturasenaryosu': ('efaturasenaryosu', 'efatura_senaryosu'),
            'note': ('note', 'notlar'),
            '_key': ('_key', 'dia_key'),
            '_date': ('_date', 'dia_son_degisiklik'),
        }
        normalize = {}
        for target, aliases in alan_eslemeleri.items():
            for alias in aliases:
                if alias in d and d[alias] is not None:
                    normalize[target] = d[alias]
                    break

        if not normalize.get('carikartkodu') or not normalize.get('unvan'):
            raise ValueError('Cari rapor satırında cari kodu veya ünvan bulunamadı.')

        alanlar = CariMapper.dia_to_fields(normalize)
        # Bu rapor tasarımı bazı sütunları dışarıda bırakabilir; yalnızca raporda
        # yer alan alanları güncelle, var olan yerel bilgileri boşaltma.
        alan_esleme_model = {
            'kisaaciklama': 'kisa_aciklama', 'carikarttipi': 'tip',
            'durum': 'durum', 'verginumarasi': 'vergi_no', 'tckimlikno': 'tc_kimlik_no',
            'vergidairesi': 'vergi_dairesi', 'dairekodu': 'daire_kodu',
            'telefon1': 'telefon1', 'telefon2': 'telefon2', 'ceptel': 'cep_tel',
            'fax': 'fax', 'eposta': 'eposta', 'weburl': 'web_url',
            'adres1': 'adres1', 'adres2': 'adres2', 'ilce': 'ilce', 'il': 'sehir',
            'postakodu': 'posta_kodu', 'ulke': 'ulke', 'risklimiti': 'risk_limiti',
            'indirimorani': 'indirim_orani', 'bakiye': 'bakiye',
            'borctoplam': 'borc_toplam', 'alacaktoplam': 'alacak_toplam',
            'efaturasenaryosu': 'efatura_senaryosu', 'note': 'notlar',
        }
        for source, model_field in alan_esleme_model.items():
            if source not in normalize:
                alanlar.pop(model_field, None)
        if '_key' in normalize:
            alanlar['dia_key'] = _to_text(normalize.get('_key'))
        if '_date' in normalize:
            alanlar['dia_son_degisiklik'] = _parse_datetime(normalize.get('_date'))
        return alanlar

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
