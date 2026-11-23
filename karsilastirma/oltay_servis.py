"""
Oltay Lastik XML Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <Stoklar>
      <Stok>
        <Urun_Kodu>BF008206</Urun_Kodu>
        <Urun_Adi>265/70R16 117/114S ALL-TERRAIN BF GOODRICH</Urun_Adi>
        <Marka>BFGOODRICH</Marka>
        <Fiyat>15000,000000</Fiyat>      ← virgüllü ondalık
        <Adet>0,00</Adet>               ← virgüllü, stok
        <DOT>2025</DOT>
        <Aktiflik_Durumu>1</Aktiflik_Durumu>  ← 0 = pasif, atla
      </Stok>
      ...
    </Stoklar>

NOT: Adet = 0 veya Aktiflik_Durumu = 0 olanlar atlanır.
     Mevsim Urun_Adi'ndan çıkarılır.
     Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

OLTAY_XML_URL = os.getenv("MESBUL_OLTAY_XML_URL", "").strip()

CACHE_KEY       = "oltay_tum_urunler"
CACHE_KEY_STALE = "oltay_tum_urunler_stale"
CACHE_TTL       = 55 * 60
CACHE_TTL_STALE = 24 * 60 * 60

_EBAT_RE = re.compile(r'\d{3}/\d{2}R\d{2}', re.IGNORECASE)
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


def _para(s: str) -> float:
    """'15000,000000' veya '15000.00' → float"""
    return float((s or "0").strip().replace(".", "").replace(",", "."))


def _adet(s: str) -> int:
    """'4,00' veya '4' → int"""
    try:
        return int(float((s or "0").strip().replace(",", ".")))
    except ValueError:
        return 0


def _mevsim_cikar(name: str) -> str:
    k = name.lower()
    if "kış" in k or "kis" in k or "winter" in k or "wint" in k or "w " in k or k.endswith("w"):
        return "Kış"
    if "4 mevsim" in k or "4mevsim" in k or "all season" in k or "allseason" in k or "m+s" in k or "all-terrain" in k:
        return "4 Mevsim"
    return "Yaz"


def oltay_verileri_getir() -> list[LastikUrun]:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(OLTAY_XML_URL, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Oltay] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Oltay] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    # Rate limit kontrolü
    hata_el = root.find(".//HataMi")
    if hata_el is not None and hata_el.text == "True":
        mesaj = root.findtext(".//HataMesaj", "")
        sonraki = root.findtext(".//SonrakiXmlTarihi", "")
        print(f"[Oltay] Rate limit: {mesaj} — Sonraki: {sonraki}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    products = root.findall("Stok")
    if not products:
        products = root.findall(".//{*}Stok")

    for stok in products:
        try:
            aktif = (stok.findtext("Aktiflik_Durumu", "1") or "1").strip()
            if aktif == "0":
                continue

            miktar = _adet(stok.findtext("Adet", "0"))
            if miktar <= 0:
                continue

            fiyat = _para(stok.findtext("Fiyat", "0"))
            if fiyat < 100:
                continue

            name  = (stok.findtext("Urun_Adi", "") or "").strip()
            marka = (stok.findtext("Marka", "") or "").strip()
            sku   = (stok.findtext("Urun_Kodu", "") or "").strip()
            dot   = (stok.findtext("DOT", "") or "").strip()

            if not _EBAT_RE.search(name):
                continue

            urunler.append(LastikUrun(
                toptanci  = "Oltay",
                stok_kodu = sku,
                marka     = marka,
                urun_adi  = name,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = _DOT_RE.search(dot).group() if _DOT_RE.search(dot) else "",
                mevsim    = _mevsim_cikar(name),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Oltay] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def oltay_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    if not OLTAY_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum = oltay_verileri_getir()

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
