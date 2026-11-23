"""
Art4 XML Servisi (xmlbankasi.com)
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <Products>
      <Product>
        <Product_code><![CDATA[ 2323700-24 ]]></Product_code>
        <Brand><![CDATA[ Pirelli ]]></Brand>
        <Name><![CDATA[ Pirelli Cinturato P7 215/55R17 ... Yaz Lastiği (Üretim Yılı: 2024) ]]></Name>
        <urun_stok>1</urun_stok>
        <mevsim>Yaz</mevsim>          ← bazen boş
        <üretim_tarihi>2024</üretim_tarihi>  ← bazen boş
        <Fiyat>5000.00</Fiyat>
      </Product>
      ...
    </Products>

NOT: mevsim ve üretim_tarihi boşsa Name alanından çıkarılır.
     urun_stok = 0 olanlar atlanır.
     Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

ART4_XML_URL = os.getenv("MESBUL_ART4_XML_URL", "").strip()
CACHE_KEY       = "art4_tum_urunler"
CACHE_KEY_STALE = "art4_tum_urunler_stale"
CACHE_TTL       = 55 * 60        # 55 dakika
CACHE_TTL_STALE = 24 * 60 * 60   # 24 saat fallback

# Name alanındaki üretim yılı pattern'i: "(Üretim Yılı: 2024)" veya "(Üretim Yılı:2024)"
_DOT_RE     = re.compile(r'[Üü]retim\s*[Yy]ıl[ıi]\s*:?\s*(20\d{2})', re.IGNORECASE)
# Ebat pattern: 205/55R16 veya 205/55R16C tarzı
_EBAT_RE    = re.compile(r'\d{3}/\d{2}R\d{2}[A-Z]?', re.IGNORECASE)


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


def _mevsim_cikar(mevsim_alan: str, name: str) -> str:
    """
    Önce mevsim alanına bak, boşsa Name'den çıkar.
    Döndürülen değer: "Yaz" | "Kış" | "4 Mevsim"
    """
    kaynak = mevsim_alan.strip() if mevsim_alan else ""
    if not kaynak:
        kaynak = name

    k = kaynak.lower()
    if "kış" in k or "kis" in k or "winter" in k or "kış lastiği" in k:
        return "Kış"
    if "4 mevsim" in k or "4mevsim" in k or "all season" in k or "all-season" in k or "allseason" in k or "m+s" in k:
        return "4 Mevsim"
    return "Yaz"  # default — "Yaz Lastiği" veya belirsiz


def _dot_cikar(tarihi_alan: str, name: str) -> str:
    """
    Önce üretim_tarihi alanına bak, boşsa Name içindeki '(Üretim Yılı: 2024)' pattern'ini çek.
    """
    if tarihi_alan and tarihi_alan.strip():
        m = re.search(r'20\d{2}', tarihi_alan)
        if m:
            return m.group()

    m = _DOT_RE.search(name)
    return m.group(1) if m else ""


def art4_verileri_getir() -> list[LastikUrun]:
    """
    Art4 XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(ART4_XML_URL, timeout=20)
        resp.raise_for_status()
        # XML encoding sorunu olmaması için bytes üzerinden parse
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Art4] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Art4] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for urun in root.findall("Product"):
        try:
            miktar = int(urun.findtext("urun_stok", "0") or "0")
            if miktar <= 0:
                continue

            fiyat = float(urun.findtext("Fiyat", "0") or "0")
            if fiyat < 100:
                continue

            name          = (urun.findtext("Name", "") or "").strip()
            mevsim_alan   = (urun.findtext("mevsim", "") or "").strip()
            tarih_alan    = (urun.findtext("üretim_tarihi", "") or "").strip()

            urunler.append(LastikUrun(
                toptanci  = "Art4",
                stok_kodu = (urun.findtext("Product_code", "") or "").strip(),
                marka     = (urun.findtext("Brand", "") or "").strip(),
                urun_adi  = name,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = _dot_cikar(tarih_alan, name),
                mevsim    = _mevsim_cikar(mevsim_alan, name),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Art4] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def art4_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Art4 verilerini filtreler.

    ebat:   "205/55R16"  → Name içinde arar
    marka:  "Continental" → Brand alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim" → boşsa hepsi gelir
    """
    tum_urunler = art4_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum_urunler:
        urun_adi_upper = u.urun_adi.upper().replace(" ", "")

        if ebat_temiz and ebat_temiz not in urun_adi_upper:
            continue

        if marka_temiz and (marka_temiz not in u.marka.upper() and marka_temiz not in u.urun_adi.upper()):
            continue

        if mevsim_temiz and mevsim_temiz.lower() not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
