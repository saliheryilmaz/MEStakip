"""
Yılkarlas XML Servisi (b2bstore.com)
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <ProductShared>
      <ProductName>7.50-16 ROCKSTONE TR76 İÇ LASTİK</ProductName>
      <BrandName>ROCKSTONE</BrandName>
      <ProductCode>ROCK-75076</ProductCode>
      <Price>925</Price>
      <TaxRatio>20</TaxRatio>
      <StockNumberSort>2</StockNumberSort>
      <Season/>
      <ProductionDate/>
      ...
    </ProductShared>

NOT: StockNumberSort = 0 ve Price = 0 olanlar atlanır.
     Season boşsa ProductName'den çıkarılır.
     KDV dahil fiyat: Price * (1 + TaxRatio/100)
     Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

YILKARLAS_XML_URL = os.getenv("MESBUL_YILKARLAS_XML_URL", "").strip()

CACHE_KEY       = "yilkarlas_tum_urunler_v3"
CACHE_KEY_STALE = "yilkarlas_tum_urunler_stale_v3"
CACHE_TTL       = 55 * 60        # 55 dakika
CACHE_TTL_STALE = 24 * 60 * 60   # 24 saat fallback

_EBAT_RE = re.compile(
    r'\d{3}/\d{2}\s*R\d{2}'    # 205/55R16 veya 205/55 R16
    r'|\d{3}/\d{2}R\d{2}'      # 205/55R16
    r'|\d{2,3}[.]\d{2}[-]\d{2}' # 7.50-16
    r'|\d{2,3}/\d{2}[.]\d{1}'  # 295/80R22.5
    , re.IGNORECASE
)
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


def _mevsim_cikar(season: str, name: str) -> str:
    kaynak = season.strip() if season and season.strip() else name
    k = kaynak.lower()
    if "kış" in k or "kis" in k or "winter" in k or "wint" in k:
        return "Kış"
    if "4 mevsim" in k or "4mevsim" in k or "all season" in k or "m+s" in k or "allseason" in k:
        return "4 Mevsim"
    return "Yaz"


def _dot_cikar(prod_date: str, name: str) -> str:
    if prod_date and prod_date.strip():
        m = _DOT_RE.search(prod_date)
        if m:
            return m.group()
    m = _DOT_RE.search(name)
    return m.group() if m else ""


def _txt(el, tag: str) -> str:
    val = el.findtext(tag, "") or ""
    return val.strip()


def yilkarlas_verileri_getir() -> list[LastikUrun]:
    """Yılkarlas XML'ini çekip tüm ürün listesini döner. Cache'e yazar."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(YILKARLAS_XML_URL, timeout=40)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Yılkarlas] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Yılkarlas] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []

    # ProductShared'ler ProductList içinde
    products = root.findall("ProductList/ProductShared")
    if not products:
        products = root.findall("ProductShared")
    if not products:
        products = root.findall(".//{*}ProductShared")

    for urun in products:
        try:
            fiyat_ham_str = _txt(urun, "Price") or "0"
            # Binlik nokta ayracını kaldır: "5.750" → "5750"
            # Ondalık virgülü noktaya çevir: "5,75" → "5.75"
            # Eğer son kısım 3 haneli ise binlik ayraç, 2 haneli ise ondalık
            fiyat_ham_str = fiyat_ham_str.replace(",", ".")
            parts = fiyat_ham_str.split(".")
            if len(parts) == 2 and len(parts[1]) == 3:
                # binlik nokta: 5.750 → 5750
                fiyat_ham_str = "".join(parts)
            fiyat_ham = float(fiyat_ham_str or "0")
            if fiyat_ham < 1:
                continue

            # KDV dahil fiyat
            try:
                kdv = float(_txt(urun, "TaxRatio") or "0")
                fiyat = round(fiyat_ham * (1 + kdv / 100), 2)
            except ValueError:
                fiyat = fiyat_ham

            if fiyat < 100:
                continue

            miktar = int(_txt(urun, "StockNumberSort") or "0")
            if miktar <= 0:
                continue

            name   = _txt(urun, "ProductName")
            marka  = _txt(urun, "BrandName")
            sku    = _txt(urun, "ProductCode")
            season = _txt(urun, "Season")
            dot    = _txt(urun, "ProductionDate")

            # Lastik mi? Ebat pattern'i içermeli
            if not _EBAT_RE.search(name):
                continue

            urunler.append(LastikUrun(
                toptanci  = "Yılkarlas",
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
    print(f"[Yılkarlas] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def yilkarlas_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """Yılkarlas verilerini filtreler."""
    if not YILKARLAS_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = yilkarlas_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "").replace("/", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum_urunler:
        urun_normalize = u.urun_adi.upper().replace(" ", "").replace("/", "")

        if ebat_temiz and ebat_temiz not in urun_normalize:
            continue

        if marka_temiz and (marka_temiz not in u.marka.upper() and marka_temiz not in u.urun_adi.upper()):
            continue

        if mevsim_temiz and mevsim_temiz.lower() not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
