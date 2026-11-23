"""
Ayko XML Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <Urunler>
      <Urun>
        <StokKodu>212028-24</StokKodu>
        <Marka>LASSA</Marka>
        <Miktar>8</Miktar>
        <Aciklama/>
        <UrunAdi>175/70R14 84T ICEWAYS 2</UrunAdi>
        <Fiyat>3555.00</Fiyat>
        <Dot>2024</Dot>
        <Mevsim>Kış</Mevsim>
      </Urun>
      ...
    </Urunler>

Ebat bilgisi UrunAdi alanının başında yer alır.
Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

AYKO_XML_URL = os.getenv("MESBUL_AYKO_XML_URL", "").strip()
CACHE_KEY       = "ayko_tum_urunler"
CACHE_KEY_STALE = "ayko_tum_urunler_stale"
CACHE_TTL       = 55 * 60        # 55 dakika
CACHE_TTL_STALE = 24 * 60 * 60   # 24 saat fallback


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


def _mevsim_normalize(mevsim_raw: str) -> str:
    m = mevsim_raw.strip().lower()
    if "kış" in m or "kis" in m or "winter" in m:
        return "Kış"
    if "4 mevsim" in m or "4mevsim" in m or "all" in m:
        return "4 Mevsim"
    return "Yaz"


def ayko_verileri_getir() -> list[LastikUrun]:
    """
    Ayko XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar — tüm worker'lar aynı cache'i paylaşır.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(AYKO_XML_URL, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Ayko] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Ayko] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for urun in root.findall("Urun"):
        try:
            miktar = int(urun.findtext("Miktar", "0") or "0")
            if miktar <= 0:
                continue

            fiyat = float(urun.findtext("Fiyat", "0") or "0")
            if fiyat < 100:
                continue

            mevsim_raw = (urun.findtext("Mevsim", "") or "").strip()
            dot_raw    = (urun.findtext("Dot", "") or "").strip()

            dot = dot_raw if re.fullmatch(r"20\d{2}", dot_raw) else ""

            urunler.append(LastikUrun(
                toptanci  = "Ayko",
                stok_kodu = (urun.findtext("StokKodu", "") or "").strip(),
                marka     = (urun.findtext("Marka", "") or "").strip(),
                urun_adi  = (urun.findtext("UrunAdi", "") or "").strip(),
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = dot,
                mevsim    = _mevsim_normalize(mevsim_raw),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Ayko] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def ayko_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Ayko verilerini filtreler.

    ebat:   "205/55R16"  → UrunAdi içinde arar
    marka:  "Lassa"      → Marka alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim" → boşsa hepsi gelir
    """
    if not AYKO_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = ayko_verileri_getir()

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
