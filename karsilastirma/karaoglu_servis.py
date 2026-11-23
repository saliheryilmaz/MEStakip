"""
Karaoğlu Lastik XML Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <Products>
      <Product>
        <ManifacturerProductCode>2315600-21</ManifacturerProductCode>
        <InitialStockAmount>4</InitialStockAmount>
        <Price>2775.00</Price>
        <Description>275/45/18 103Y PZERO (N1)</Description>
        <Brand>PİRELLİ</Brand>
        <MinSellingAmount>1</MinSellingAmount>
        <Dot>2021</Dot>
        <Depolar>
          <Depo><Depoadi>...</Depoadi><Adet>4</Adet></Depo>
        </Depolar>
      </Product>
      ...
    </Products>

NOT: InitialStockAmount = 0 olanlar atlanır.
     Description'da ebat "275/45/18" formatında (3 parça slash ile) gelir → "275/45R18"'e dönüştürülür.
     Mevsim Description'dan çıkarılır.
     Brand Türkçe büyük harfli → normalize edilir.
     Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

KARAOGLU_XML_URL = os.getenv("MESBUL_KARAOGLU_XML_URL", "").strip()

CACHE_KEY       = "karaoglu_tum_urunler_v3"
CACHE_KEY_STALE = "karaoglu_tum_urunler_stale_v3"
CACHE_TTL       = 55 * 60
CACHE_TTL_STALE = 24 * 60 * 60

# 275/45/18 veya 275/45R18 gibi formatlar
_EBAT_RAW_RE = re.compile(r'(\d{3})/(\d{2})/(\d{2})', re.IGNORECASE)
_EBAT_STD_RE = re.compile(r'\d{3}/\d{2}R\d{2}', re.IGNORECASE)
_DOT_RE      = re.compile(r'20\d{2}')

# Türkçe marka normalize
_TR_MAP = str.maketrans("İIŞĞÜÖÇ", "iışğüöç")


def _ebat_normalize(desc: str) -> str:
    """275/45/18 → 275/45R18 dönüşümü."""
    m = _EBAT_RAW_RE.search(desc)
    if m:
        return f"{m.group(1)}/{m.group(2)}R{m.group(3)}"
    m2 = _EBAT_STD_RE.search(desc)
    return m2.group() if m2 else ""


def _mevsim_cikar(desc: str) -> str:
    k = desc.lower().translate(_TR_MAP)
    if "kis" in k or "winter" in k or "wint" in k:
        return "Kış"
    if "4 mevsim" in k or "allseason" in k or "all season" in k or "m+s" in k:
        return "4 Mevsim"
    return "Yaz"


def _marka_normalize(marka: str) -> str:
    temiz = " ".join(marka.strip().split())
    return " ".join(w.translate(_TR_MAP).capitalize() for w in temiz.split())


def _txt(el, tag: str) -> str:
    return (el.findtext(tag, "") or "").strip()


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


def karaoglu_verileri_getir() -> list[LastikUrun]:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(KARAOGLU_XML_URL, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Karaoğlu] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Karaoğlu] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    products = root.findall("Product")
    if not products:
        products = root.findall(".//{*}Product")

    for p in products:
        try:
            # Rize şubesi hariç kalan depoların stokunu hesapla
            depolar = p.findall("./Depolar/Depo")
            if depolar:
                rize_olmayan_adet = 0
                for d in depolar:
                    depo_adi = (d.findtext("Depoadi") or "").strip().upper()
                    if "RİZE" in depo_adi:
                        continue
                    try:
                        rize_olmayan_adet += int(float(d.findtext("Adet") or "0"))
                    except (ValueError, TypeError):
                        pass
                miktar = rize_olmayan_adet
            else:
                miktar = int(float(_txt(p, "InitialStockAmount") or "0"))

            if miktar <= 0:
                continue

            fiyat = float((_txt(p, "Price") or "0").replace(",", "."))
            if fiyat < 100:
                continue

            desc  = _txt(p, "Description")
            marka = _txt(p, "Brand")
            sku   = _txt(p, "ManifacturerProductCode")
            dot   = _txt(p, "Dot")

            # Ebat kontrolü
            ebat = _ebat_normalize(desc)
            if not ebat:
                continue

            urunler.append(LastikUrun(
                toptanci  = "Karaoğlu",
                stok_kodu = sku,
                marka     = _marka_normalize(marka),
                urun_adi  = desc,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = _DOT_RE.search(dot).group() if _DOT_RE.search(dot) else "",
                mevsim    = _mevsim_cikar(desc),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Karaoğlu] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def karaoglu_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    if not KARAOGLU_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum = karaoglu_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "").replace("/", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum:
        # Description'daki ebatı normalize et: 205/55/16 ve 205/55R16 → 20555 16
        # R harfini ve slash'ları kaldırarak sadece sayısal kısmı karşılaştır
        desc_norm = re.sub(r'[/R\s]', '', u.urun_adi.upper())
        ebat_norm = re.sub(r'[/R\s]', '', ebat_temiz)

        if ebat_norm and ebat_norm not in desc_norm:
            continue
        if marka_temiz and marka_temiz not in u.marka.upper() and marka_temiz not in u.urun_adi.upper():
            continue
        if mevsim_temiz and mevsim_temiz.lower() not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
