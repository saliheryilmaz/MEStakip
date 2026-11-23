"""
Simetri Lastik XML Servisi (continentaldas.com)
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <ArrayOfProduct>
      <product>
        <sku>0000000006</sku>
        <name>KARGO BEDELİ</name>
        <brand/>
        <dot>2025</dot>
        <season>-</season>
        <listPrice>0</listPrice>
        <price>0</price>
        <quantity>91</quantity>
        <minSellCount>1</minSellCount>
      </product>
      ...
    </ArrayOfProduct>

NOT: price = 0 veya quantity = 0 olanlar atlanır.
     season "-" veya boşsa name alanından çıkarılır.
     Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

SIMETRI_XML_URL = os.getenv("MESBUL_SIMETRI_XML_URL", "").strip()

CACHE_KEY       = "simetri_tum_urunler_v2"
CACHE_KEY_STALE = "simetri_tum_urunler_stale_v2"
CACHE_TTL       = 55 * 60        # 55 dakika
CACHE_TTL_STALE = 24 * 60 * 60   # 24 saat fallback

_EBAT_RE = re.compile(r'\d{3}/\d{2}R\d{2}[A-Z0-9]?', re.IGNORECASE)
_DOT_RE  = re.compile(r'20\d{2}')


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


def _mevsim_cikar(season_alan: str, name: str) -> str:
    """season alanı "-" veya boşsa name'den çıkar."""
    kaynak = season_alan.strip() if season_alan and season_alan.strip() not in ("-", "") else name
    k = kaynak.lower()
    if "kış" in k or "kis" in k or "winter" in k or "w " in k or k.endswith("w"):
        return "Kış"
    if "4 mevsim" in k or "4mevsim" in k or "all season" in k or "allseason" in k or "m+s" in k or "ms " in k:
        return "4 Mevsim"
    return "Yaz"


def _dot_cikar(dot_alan: str, name: str) -> str:
    """dot alanından veya name'den üretim yılını çek."""
    if dot_alan and dot_alan.strip():
        m = _DOT_RE.search(dot_alan)
        if m:
            return m.group()
    # name'den dene
    m = _DOT_RE.search(name)
    return m.group() if m else ""


def simetri_verileri_getir() -> list[LastikUrun]:
    """Simetri XML'ini çekip tüm ürün listesini döner. Cache'e yazar."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(SIMETRI_XML_URL, timeout=40)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Simetri] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Simetri] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []

    # Namespace tespiti
    ns_match = re.search(r'xmlns=["\']([^"\']+)["\']', resp.text)
    ns = ns_match.group(1) if ns_match else ""
    prefix = f"{{{ns}}}" if ns else ""

    products = root.findall(f"{prefix}product")
    if not products:
        products = root.findall(".//{*}product")

    for urun in products:
        def txt(tag, default=""):
            val = urun.findtext(f"{prefix}{tag}", default)
            return (val or default).strip()

        try:
            fiyat  = float(txt("price", "0") or "0")
            miktar = int(txt("quantity", "0") or "0")

            if fiyat < 100 or miktar <= 0:
                continue

            name   = txt("name")
            marka  = txt("brand")
            sku    = txt("sku")
            dot    = txt("dot")
            season = txt("season")

            # Ebat kontrolü — boşluklu format da kabul et: "255 30 R19" veya "205/55R16"
            ebat_pattern = re.compile(
                r'\d{3}[\s/]\d{2}[\s/]?R\d{2}|\d{3}/\d{2}R\d{2}',
                re.IGNORECASE
            )
            if not ebat_pattern.search(name):
                continue

            if not marka:
                marka = name.split()[0] if name else ""

            urunler.append(LastikUrun(
                toptanci  = "Simetri",
                stok_kodu = sku,
                marka     = marka,
                urun_adi  = name,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = _dot_cikar(dot, name),
                mevsim    = _mevsim_cikar(season, name),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Simetri] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def simetri_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Simetri verilerini filtreler.

    ebat:   "205/55R16" → name içinde arar
    marka:  "Pirelli"   → brand/name içinde arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim" → boşsa hepsi gelir
    """
    if not SIMETRI_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = simetri_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum_urunler:
        # Hem ürün adını hem ebat arama terimini normalize et (boşluk/slash kaldır)
        urun_normalize = u.urun_adi.upper().replace(" ", "").replace("/", "")

        if ebat_temiz and ebat_temiz.replace("/", "") not in urun_normalize:
            continue

        if marka_temiz and (marka_temiz not in u.marka.upper() and marka_temiz not in urun_normalize):
            continue

        if mevsim_temiz and mevsim_temiz.lower() not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
