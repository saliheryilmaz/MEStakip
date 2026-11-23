"""
Lastsis XML Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <product>
        <id>118332</id>
        <category_name>Binek-Hafif Ticari Lastik</category_name>
        <title>Ultracontact 195/45R16 84H XL FR</title>
        <reference_code>313105</reference_code>
        <barcode>4019238078466</barcode>
        <brand>CONTINENTAL</brand>
        <description/>
        <price>6184,8</price>         ← virgüllü Türk formatı
        <dot>2024</dot>
        <quantity>0</quantity>
        <pictures/>
    </product>

NOT: Mevsim alanı yok, title'dan çıkarılır.
     Fiyat virgüllü gelir → noktalıya çevrilir.
     Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

LASTSIS_XML_URL = os.getenv("MESBUL_LASTSIS_XML_URL", "").strip()
CACHE_KEY        = "lastsis_tum_urunler"
CACHE_KEY_STALE  = "lastsis_tum_urunler_stale"
CACHE_TTL        = 55 * 60       # 55 dakika
CACHE_TTL_STALE  = 24 * 60 * 60  # 24 saat fallback


@dataclass
class LastikUrun:
    toptanci:  str
    stok_kodu: str
    marka:     str
    urun_adi:  str
    fiyat:     float
    miktar:    int
    dot:       str
    mevsim:    str
    kategori:  str = ""

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


def _fiyat_parse(raw: str) -> float:
    """'6184,8' veya '6184.8' → 6184.8"""
    return float(raw.strip().replace(",", "."))


def _mevsim_cikar(title: str) -> str:
    """Title'dan mevsim bilgisini çıkarır."""
    t = title.upper()
    if "4 MEVSIM" in t or "4MEVSIM" in t or "ALL SEASON" in t or "ALLSEASON" in t or "ALL-SEASON" in t:
        return "4 Mevsim"
    if "KISLIK" in t or "WINTER" in t or "KISH" in t or "KIŞ" in t:
        return "Kış"
    return "Yaz"


def lastsis_verileri_getir() -> list[LastikUrun]:
    """
    Lastsis XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar — tüm worker'lar aynı cache'i paylaşır.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(LASTSIS_XML_URL, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Lastsis] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Lastsis] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for urun in root.findall("product"):
        try:
            fiyat_raw = urun.findtext("price", "0") or "0"
            fiyat = _fiyat_parse(fiyat_raw)
            if fiyat <= 0:
                continue

            miktar = int(urun.findtext("quantity", "0") or "0")
            if miktar <= 0:
                continue
            title  = (urun.findtext("title", "") or "").strip()
            brand  = (urun.findtext("brand",  "") or "").strip().title()  # CONTINENTAL → Continental

            urunler.append(LastikUrun(
                toptanci  = "Lastsis",
                stok_kodu = urun.findtext("reference_code", "") or "",
                marka     = brand,
                urun_adi  = title,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = urun.findtext("dot", "") or "",
                mevsim    = _mevsim_cikar(title),
                kategori  = urun.findtext("category_name", "") or "",
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Lastsis] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def lastsis_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Lastsis verilerini filtreler.
    ebat:   "205/55R16" → title içinde arar
    marka:  "Continental" → brand alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim"
    """
    if not LASTSIS_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = lastsis_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "")
    marka_upper  = marka.strip().upper()
    mevsim_temiz = mevsim.strip().lower()

    sonuclar = []
    for u in tum_urunler:
        urun_upper = u.urun_adi.upper().replace(" ", "")

        # Ebat eşleşmesi
        if ebat_temiz and ebat_temiz not in urun_upper:
            continue

        # Marka filtresi
        if marka_upper and (marka_upper not in u.marka.upper() and marka_upper not in u.urun_adi.upper()):
            continue

        # Mevsim filtresi
        if mevsim_temiz and mevsim_temiz not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
