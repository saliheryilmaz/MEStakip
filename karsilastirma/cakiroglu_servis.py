"""
Çakıroğlu XML Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <Urunler>
      <Urun>
        <StokKodu>BRD-511248</StokKodu>
        <Marka>BRIDGESTONE</Marka>
        <Miktar>19</Miktar>
        <Aciklama/>
        <UrunAdi>255/40R18 99Y XL TURANZA T005 EXT MOE</UrunAdi>
        <Fiyat>11750.00</Fiyat>
        <Dot>2025</Dot>
        <Mevsim>Yaz</Mevsim>
      </Urun>
      ...
    </Urunler>

Ebat bilgisi UrunAdi alanının başında yer alır (ör. "255/40R18 99Y XL ...").
Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

CAKIROGLU_XML_URL = os.getenv("MESBUL_CAKIROGLU_XML_URL", "").strip()
CACHE_KEY       = "cakiroglu_tum_urunler"
CACHE_KEY_STALE = "cakiroglu_tum_urunler_stale"
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


def _mevsim_cikar(mevsim_alan: str, urun_adi: str) -> str:
    """
    Önce Mevsim alanına bak, boşsa UrunAdi'ndan çıkar.
    Döndürülen değer: "Yaz" | "Kış" | "4 Mevsim"
    """
    kaynak = mevsim_alan.strip() if mevsim_alan else ""
    if not kaynak:
        kaynak = urun_adi

    k = kaynak.lower()
    if "kış" in k or "kis" in k or "winter" in k or "ice" in k or "snow" in k or "blizzak" in k or "iceways" in k:
        return "Kış"
    if "4 mevsim" in k or "4mevsim" in k or "all season" in k or "allseason" in k or "all-season" in k or "multiways" in k or "m+s" in k or "allseason" in k:
        return "4 Mevsim"
    return "Yaz"


def cakiroglu_verileri_getir() -> list[LastikUrun]:
    """
    Çakıroğlu XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar — tüm worker'lar aynı cache'i paylaşır.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(CAKIROGLU_XML_URL, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Çakıroğlu] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Çakıroğlu] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for urun in root.findall("Urun"):
        try:
            miktar_raw = (urun.findtext("Miktar", "0") or "0").strip()
            # "8+" veya "8 +" gibi değerleri de handle et
            miktar = int(miktar_raw.rstrip("+").strip() or "0")
            if miktar <= 0:
                continue

            fiyat = float(urun.findtext("Fiyat", "0") or "0")
            if fiyat < 100:
                continue

            mevsim_raw = (urun.findtext("Mevsim", "") or "").strip()
            dot_raw    = (urun.findtext("Dot", "") or "").strip()

            # Dot: "2025" gibi geliyor, 4 haneli yıl değilse boş bırak
            dot = dot_raw if re.fullmatch(r"20\d{2}", dot_raw) else ""

            urun_adi   = (urun.findtext("UrunAdi", "") or "").strip()

            urunler.append(LastikUrun(
                toptanci  = "Çakıroğlu",
                stok_kodu = (urun.findtext("StokKodu", "") or "").strip(),
                marka     = (urun.findtext("Marka", "") or "").strip(),
                urun_adi  = urun_adi,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = dot,
                mevsim    = _mevsim_cikar(mevsim_raw, urun_adi),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Çakıroğlu] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def cakiroglu_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Çakıroğlu verilerini filtreler.

    ebat:   "205/55R16"  → UrunAdi içinde arar
    marka:  "Bridgestone" → Marka alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim" → boşsa hepsi gelir
    """
    if not CAKIROGLU_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = cakiroglu_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum_urunler:
        urun_adi_upper = u.urun_adi.upper().replace(" ", "")

        # Ebat eşleşmesi — UrunAdi içinde geçiyor mu?
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
