"""
Degeras Lastik JSON API Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

Response: { "data": [ { "title": "205/55R16 91H ...", "brandTitle": "...", ... } ] }
"""

import requests
from dataclasses import dataclass

from .onbellek import cache

import os

DEGERAS_API_URL = os.getenv("MESBUL_DEGERAS_API_URL", "").strip()

CACHE_KEY       = "degeras_tum_urunler_v2"
CACHE_KEY_STALE = "degeras_tum_urunler_stale_v2"
CACHE_TTL       = 55 * 60        # 55 dakika
CACHE_TTL_STALE = 24 * 60 * 60   # 24 saat fallback


@dataclass
class LastikUrun:
    toptanci:  str
    stok_kodu: str
    marka:     str
    urun_adi:  str   # title → ebat + model
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
    """API'den gelen mevsim değerini standart forma çevirir."""
    m = mevsim_raw.strip().lower()
    if "kış" in m or "kis" in m or "winter" in m:
        return "Kış"
    if "4mevsim" in m or "4 mevsim" in m or "all" in m or "allseason" in m:
        return "4 Mevsim"
    return "Yaz"


def _dot_normalize(dot_raw: str) -> str:
    """
    'productionDate' veya includedProperties DOT değeri:
    '2019 ve Öncesi' → '2019'  |  '2023' → '2023'  |  None → ''
    """
    if not dot_raw:
        return ""
    # 4 haneli yıl bul
    import re
    m = re.search(r'(20\d{2})', dot_raw)
    return m.group(1) if m else dot_raw.strip()


def degeras_verileri_getir() -> list[LastikUrun]:
    """
    Degeras API'sinden tüm ürün listesini çekip döner.
    Django DB cache'e yazar — tüm worker'lar aynı cache'i paylaşır.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(DEGERAS_API_URL, timeout=20)
        resp.raise_for_status()
        json_data = resp.json()
    except requests.RequestException as e:
        print(f"[Degeras] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ValueError as e:
        print(f"[Degeras] JSON parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    items = json_data.get("data", [])
    urunler = []

    for item in items:
        try:
            fiyat  = float(item.get("currentPrice", 0) or 0)
            miktar = int(item.get("amount", 0) or 0)

            # Mevsim ve DOT → includedProperties içinden al
            mevsim_raw = ""
            dot_raw    = item.get("productionDate", "") or ""

            for prop in item.get("includedProperties", []):
                ad = prop.get("includedPropertyName", "")
                deger = prop.get("includedPropertyValueName", "") or ""
                if "Mevsim" in ad:
                    mevsim_raw = deger
                elif "DOT" in ad or "Üretim" in ad:
                    dot_raw = deger  # includedProperties'teki değer daha detaylı olabilir

            if fiyat < 100 or miktar <= 0:
                continue

            urunler.append(LastikUrun(
                toptanci  = "Degeras",
                stok_kodu = item.get("erpCode", ""),
                marka     = item.get("brandTitle", ""),
                urun_adi  = item.get("title", ""),
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = _dot_normalize(dot_raw),
                mevsim    = _mevsim_normalize(mevsim_raw),
            ))
        except (ValueError, TypeError, KeyError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Degeras] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def degeras_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Degeras verilerini filtreler.

    ebat:   "205/55R16"  → title içinde arar (büyük/küçük harf yok sayılır)
    marka:  "Continental" → brandTitle alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim" → boşsa hepsi gelir
    """
    if not DEGERAS_API_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = degeras_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum_urunler:
        urun_adi_upper = u.urun_adi.upper().replace(" ", "")

        # Ebat eşleşmesi — title içinde geçiyor mu?
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
