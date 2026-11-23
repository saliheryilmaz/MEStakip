"""
USPA Lastik XML Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

Django DB cache kullanılır — tüm worker'lar aynı cache'i paylaşır.
"""

import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

USPA_XML_URL = os.getenv("MESBUL_USPA_XML_URL", "").strip()
CACHE_KEY       = "uspa_tum_urunler"
CACHE_KEY_STALE = "uspa_tum_urunler_stale"
CACHE_TTL       = 55 * 60       # 55 dakika
CACHE_TTL_STALE = 24 * 60 * 60  # 24 saat fallback


@dataclass
class LastikUrun:
    toptanci:    str
    stok_kodu:   str
    marka:       str
    urun_adi:    str   # tam ürün adı (ebat + model buradan okunur)
    fiyat:       float
    miktar:      int
    dot:         str
    mevsim:      str

    @property
    def fiyat_str(self) -> str:
        return f"{self.fiyat:,.2f} ₺"

    @property
    def stok_str(self) -> str:
        if self.miktar <= 0:
            return "Yok"
        if self.miktar <= 4:
            return f"Son {self.miktar} adet"
        return f"{self.miktar} adet"


def uspa_verileri_getir() -> list[LastikUrun]:
    """
    USPA XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar — tüm worker'lar aynı cache'i paylaşır.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(USPA_XML_URL, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[USPA] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[USPA] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for urun in root.findall("Urun"):
        try:
            fiyat  = float(urun.findtext("Fiyat", "0"))
            miktar = int(urun.findtext("Miktar", "0"))
            urunler.append(LastikUrun(
                toptanci  = "USPA Lastik",
                stok_kodu = urun.findtext("StokKodu", ""),
                marka     = urun.findtext("Marka", ""),
                urun_adi  = urun.findtext("UrunAdi", ""),
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = urun.findtext("Dot", ""),
                mevsim    = urun.findtext("Mevsim", "Yaz"),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[USPA] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def uspa_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    USPA verilerini filtreler.

    ebat:   "205/55R16"  → UrunAdi içinde arar (büyük/küçük harf yok sayılır)
    marka:  "Continental" → Marka alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim" → boşsa hepsi gelir
    """
    if not USPA_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = uspa_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum_urunler:
        urun_adi_upper = u.urun_adi.upper().replace(" ", "")

        # Ebat eşleşmesi — UrunAdi içinde geçiyor mu?
        if ebat_temiz and ebat_temiz not in urun_adi_upper:
            continue

        # Marka filtresi — Marka alanında VEYA ürün adında ara
        if marka_temiz and (marka_temiz not in u.marka.upper() and marka_temiz not in u.urun_adi.upper()):
            continue

        # Mevsim filtresi
        if mevsim_temiz and mevsim_temiz.lower() not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    # Fiyata göre sırala — en ucuz üstte
    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
