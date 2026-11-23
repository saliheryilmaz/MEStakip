"""
AS Otomotiv XML Servisi (b2bstore.com)
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <Node>
      <Product>
        <ProductName>185/60 R15 84T MP93 NORDİCCA MATADOR TL</ProductName>
        <Brand>matador</Brand>
        <ProductCode>L-MAT15854600000</ProductCode>
        <pricePlusTax>2251.85</pricePlusTax>
        <Price>1876.55</Price>
        <TaxRatio>20</TaxRatio>
        <StockNumber>4</StockNumber>
        <Season>Winter</Season>
        <ProductionDate>2021</ProductionDate>
        <ProductTypeCode>Lastik</ProductTypeCode>
        <Category1>KIŞ LASTİK</Category1>
      </Product>
      ...
    </Node>

NOT: StockNumber = 0 olanlar atlanır.
     pricePlusTax (KDV dahil) kullanılır.
     ProductTypeCode != Lastik olanlar atlanır.
     Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

ASOTO_XML_URL = os.getenv("MESBUL_ASOTO_XML_URL", "").strip()

CACHE_KEY       = "asoto_tum_urunler_v4"
CACHE_KEY_STALE = "asoto_tum_urunler_stale_v4"
CACHE_TTL       = 55 * 60
CACHE_TTL_STALE = 24 * 60 * 60

# 205/55R16 veya 205/55 R16 veya 155/ R12
_EBAT_RE = re.compile(
    r'\d{3}/\d{2}\s*R\d{2}'
    r'|\d{3}/\s*R\d{2}',
    re.IGNORECASE
)
_DOT_RE = re.compile(r'20\d{2}')

_MEVSIM_MAP = {
    "summer":     "Yaz",
    "yaz":        "Yaz",
    "winter":     "Kış",
    "kış":        "Kış",
    "kis":        "Kış",
    "allseason":  "4 Mevsim",
    "all season": "4 Mevsim",
    "4 mevsim":   "4 Mevsim",
    "fourseason":  "4 Mevsim",
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


def _txt(el, tag: str) -> str:
    return (el.findtext(tag, "") or "").strip()


def _mevsim_cikar(season: str, name: str, category: str) -> str:
    # Önce Season alanından çıkar
    s = season.strip().lower().replace("-", "").replace(" ", "")
    if s in _MEVSIM_MAP:
        return _MEVSIM_MAP[s]
    # Category1 alanından çıkar (KIŞ LASTİK, YAZ LASTİK, 4 MEVSİM LASTİK)
    cat = category.lower()
    if "kış" in cat or "kis" in cat:
        return "Kış"
    if "4 mevsim" in cat or "dört mevsim" in cat:
        return "4 Mevsim"
    if "yaz" in cat:
        return "Yaz"
    # Son çare: ürün adından çıkar
    k = name.lower()
    if "kış" in k or "kis" in k or "winter" in k:
        return "Kış"
    if "4 mevsim" in k or "allseason" in k or "all season" in k or "m+s" in k:
        return "4 Mevsim"
    return "Yaz"


def asoto_verileri_getir() -> list[LastikUrun]:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(ASOTO_XML_URL, timeout=40)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[AS Oto] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[AS Oto] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    products = root.findall("Product")
    if not products:
        products = root.findall(".//{*}Product")

    for p in products:
        try:
            # Sadece lastik ürünleri al
            tip = _txt(p, "ProductTypeCode").lower()
            if tip and "lastik" not in tip:
                continue

            miktar = int(float(_txt(p, "StockNumber") or "0"))
            if miktar <= 0:
                continue

            # KDV dahil fiyat tercih edilir
            fiyat_str = _txt(p, "pricePlusTax") or _txt(p, "Price") or "0"
            fiyat = float(fiyat_str.replace(",", "."))
            if fiyat < 100:
                continue

            name     = _txt(p, "ProductName")
            marka    = _txt(p, "Brand")
            sku      = _txt(p, "ProductCode")
            season   = _txt(p, "Season")
            dot      = _txt(p, "ProductionDate")
            category = _txt(p, "Category1")

            # Ebat kontrolü
            if not _EBAT_RE.search(name):
                continue

            # Marka capitalize
            if marka:
                marka = " ".join(w.capitalize() for w in marka.split())

            urunler.append(LastikUrun(
                toptanci  = "AS Oto",
                stok_kodu = sku,
                marka     = marka,
                urun_adi  = name,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = _DOT_RE.search(dot).group() if _DOT_RE.search(dot) else "",
                mevsim    = _mevsim_cikar(season, name, category),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[AS Oto] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def asoto_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    if not ASOTO_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum = asoto_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "").replace("/", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum:
        urun_norm = u.urun_adi.upper().replace(" ", "").replace("/", "")

        if ebat_temiz and ebat_temiz not in urun_norm:
            continue
        if marka_temiz and marka_temiz not in u.marka.upper() and marka_temiz not in u.urun_adi.upper():
            continue
        if mevsim_temiz and mevsim_temiz.lower() not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
