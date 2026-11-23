"""
Mollaoğlu XML Servisi (b2bstore.com)
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <GetProductSharedQueryResult>
      <ProductList>
        <ProductShared>
          <ProductCode>580360-23</ProductCode>
          <BrandName>Goodyear</BrandName>
          <ProductName>255/40R20 101Y Eagle F1 Asymmetric 2 Ao XL</ProductName>
          <ProductShortCode>255/40R20 101Y</ProductShortCode>
          <Price>10.507,56</Price>          ← nokta=binlik, virgül=ondalık
          <ProductionDate>2023</ProductionDate>
          <Season>0</Season>               ← 0=Yaz, 1=Kış, 2=4 Mevsim
          <StockNumberSort>1</StockNumberSort>  ← 0=yok, 1+=var
          <ProductDescription><![CDATA[...]]></ProductDescription>
        </ProductShared>
      </ProductList>
    </GetProductSharedQueryResult>

Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

MOLLAOGLU_XML_URL = os.getenv("MESBUL_MOLLAOGLU_XML_URL", "").strip()
CACHE_KEY       = "mollaoglu_tum_urunler"
CACHE_KEY_STALE = "mollaoglu_tum_urunler_stale"
CACHE_TTL       = 55 * 60        # 55 dakika
CACHE_TTL_STALE = 24 * 60 * 60   # 24 saat fallback

_SEASON_MAP = {
    "0": "Yaz",
    "1": "Kış",
    "2": "4 Mevsim",
}


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


def _fiyat_parse(fiyat_raw: str) -> float:
    """
    "10.507,56" → 10507.56
    "8.611"     → 8611.0
    Nokta binlik ayraç, virgül ondalık.
    """
    if not fiyat_raw:
        return 0.0
    temiz = fiyat_raw.strip().replace(".", "").replace(",", ".")
    try:
        return float(temiz)
    except ValueError:
        return 0.0


def mollaoglu_verileri_getir() -> list[LastikUrun]:
    """
    Mollaoğlu XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar — tüm worker'lar aynı cache'i paylaşır.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(MOLLAOGLU_XML_URL, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Mollaoğlu] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Mollaoğlu] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for urun in root.findall(".//ProductShared"):
        try:
            # Stok kontrolü — "20+" gibi değerleri de handle et
            stok_raw = (urun.findtext("StockNumberSort", "0") or "0").strip()
            stok = int(stok_raw.rstrip("+").strip() or "0")
            if stok <= 0:
                continue

            # Fiyat
            fiyat = _fiyat_parse(urun.findtext("Price", "") or "")
            if fiyat < 100:
                continue

            # Mevsim
            season_raw = (urun.findtext("Season", "") or "").strip()
            mevsim = _SEASON_MAP.get(season_raw, "Yaz")

            # DOT
            dot_raw = (urun.findtext("ProductionDate", "") or "").strip()
            dot = dot_raw if re.fullmatch(r"20\d{2}", dot_raw) else ""

            # Ürün adı — ProductName ebat içeriyor
            urun_adi = (urun.findtext("ProductName", "") or "").strip()

            urunler.append(LastikUrun(
                toptanci  = "Mollaoğlu",
                stok_kodu = (urun.findtext("ProductCode", "") or "").strip(),
                marka     = (urun.findtext("BrandName", "") or "").strip(),
                urun_adi  = urun_adi,
                fiyat     = fiyat,
                miktar    = stok,
                dot       = dot,
                mevsim    = mevsim,
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Mollaoğlu] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def mollaoglu_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Mollaoğlu verilerini filtreler.

    ebat:   "205/55R16"  → ProductName içinde arar
    marka:  "Goodyear"   → BrandName alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim" → boşsa hepsi gelir
    """
    if not MOLLAOGLU_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = mollaoglu_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum_urunler:
        urun_adi_upper = u.urun_adi.upper().replace(" ", "")

        # Ebat eşleşmesi — ProductName içinde geçiyor mu?
        if ebat_temiz and ebat_temiz not in urun_adi_upper:
            continue

        # Marka filtresi
        if marka_temiz and (marka_temiz not in u.marka.upper() and marka_temiz not in u.urun_adi.upper()):
            continue

        # Mevsim filtresi
        if mevsim_temiz and mevsim_temiz.lower() not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
