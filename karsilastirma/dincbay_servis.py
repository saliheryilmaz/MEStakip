"""
Dinçbay B2B XML Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

XML yapısı:
    <Product>
        <Kod>518920</Kod>
        <UrunAdi>215/50 16 RE 710 (V) TB.</UrunAdi>
        <Kategori>L</Kategori>
        <Marka>BRIDGESTON</Marka>
        <Mevsim>YAZ</Mevsim>
        <Dot>2003</Dot>
        <FiyatKdvDahil>0.55</FiyatKdvDahil>   ← 100 TL altı = geçersiz fiyat, atla
        <Stok>4</Stok>
        <Depo>Merkez</Depo>
        <MinimumSatisAdedi>2</MinimumSatisAdedi>
    </Product>

NOT: BOM (\xef\xbb\xbf) içerebilir, parse öncesi temizlenir.
     FiyatKdvDahil < 100 olan ürünler (fiyat sorulacak) atlanır.
     Stok = 0 olan ürünler atlanır.
     Django DB cache kullanılır.
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

DINCBAY_XML_URL = os.getenv("MESBUL_DINCBAY_XML_URL", "").strip()
CACHE_KEY        = "dincbay_tum_urunler"
CACHE_KEY_STALE  = "dincbay_tum_urunler_stale"
CACHE_TTL        = 55 * 60       # 55 dakika
CACHE_TTL_STALE  = 24 * 60 * 60  # 24 saat fallback

MIN_FIYAT = 100.0  # Altındaki fiyatlar "fiyat sor" anlamına gelir, atlanır


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


def _mevsim_duzenle(ham: str) -> str:
    ham = ham.strip().upper()
    if "4" in ham or "ALL" in ham or "HER" in ham:
        return "4 Mevsim"
    if "KI" in ham or "WIN" in ham:
        return "Kış"
    return "Yaz"


def dincbay_verileri_getir() -> list[LastikUrun]:
    """
    Dinçbay XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar — tüm worker'lar aynı cache'i paylaşır.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(DINCBAY_XML_URL, timeout=20)
        resp.raise_for_status()
        # BOM karakterini temizle
        content = resp.content.lstrip(b'\xef\xbb\xbf')
        root = ET.fromstring(content)
    except requests.RequestException as e:
        print(f"[Dinçbay] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Dinçbay] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for urun in root.findall("Product"):
        try:
            fiyat = float(urun.findtext("FiyatKdvDahil", "0") or "0")
            # Geçersiz / "fiyat sor" ürünleri atla
            if fiyat < MIN_FIYAT:
                continue

            miktar = int(float(urun.findtext("Stok", "0") or "0"))
            if miktar <= 0:
                continue

            marka = (urun.findtext("Marka", "") or "").strip().title()
            urun_adi = (urun.findtext("UrunAdi", "") or "").strip()

            urunler.append(LastikUrun(
                toptanci  = "Dinçbay",
                stok_kodu = urun.findtext("Kod", "") or "",
                marka     = marka,
                urun_adi  = urun_adi,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = (urun.findtext("Dot", "") or "").strip(),
                mevsim    = _mevsim_duzenle(urun.findtext("Mevsim", "YAZ") or "YAZ"),
                kategori  = urun.findtext("Kategori", "") or "",
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Dinçbay] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def dincbay_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Dinçbay verilerini filtreler.
    ebat:   "205/55R16" → UrunAdi içinde arar
            Dinçbay formatı "215/50 16" (R yok, boşluklu) — her iki formatta da eşleşir
    marka:  "Continental" → Marka alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim"
    """
    if not DINCBAY_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = dincbay_verileri_getir()

    # Ebat normalizasyon: "205/55R16" → "205/55 16" ve "205/5516" → her ikisi için de ara
    ebat_temiz = ebat.strip().upper().replace(" ", "")
    # R'yi boşlukla değiştir: "20555R16" → "205/55 16" benzeri match için
    ebat_no_r  = re.sub(r'R(\d)', r' \1', ebat.strip().upper())  # "205/55R16" → "205/55 16"
    ebat_no_r2 = re.sub(r'R(\d)', r'/\1', ebat.strip().upper())  # "205/55R16" → "205/55/16"

    marka_upper  = marka.strip().upper()
    mevsim_temiz = mevsim.strip().lower()

    sonuclar = []
    for u in tum_urunler:
        urun_upper = u.urun_adi.upper()
        urun_no_space = urun_upper.replace(" ", "")

        # Ebat eşleşmesi — orijinal, R→boşluk veya rakam formatında
        if ebat.strip():
            eslesti = (
                ebat_temiz    in urun_no_space or
                ebat_no_r.replace(" ", "") in urun_no_space or
                ebat_no_r2.replace("/", "").replace(" ", "") in urun_no_space
            )
            if not eslesti:
                continue

        # Marka filtresi
        if marka_upper and (marka_upper not in u.marka.upper() and marka_upper not in urun_upper):
            continue

        # Mevsim filtresi
        if mevsim_temiz and mevsim_temiz not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
