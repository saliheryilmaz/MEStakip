"""
NetLastik Partner API Servisi
Docs: [tedarikçi adresi ortam ayarından alınır]
Base: [tedarikçi adresi ortam ayarından alınır]

Kimlik doğrulama: EKS header'ı
Endpoint: GET /api/v1/partner/products
  - tireSize: "205/55R16"
  - brand: "Continental"
  - season: "Summer" | "Winter" | "AllSeason"
  - pageSize: max 500
  - pageNumber: 1, 2, ...

Yanıt alanları:
  sku, name, brandName, modelName, tireSize, seasonType,
  dotYear, price, stock, currency, tax
"""

import os
import time
import logging
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NETLASTIK_API_URL = os.getenv("MESBUL_NETLASTIK_API_URL", "").strip()
NETLASTIK_API_KEY = os.getenv("MESBUL_NETLASTIK_API_KEY", "").strip()
NETLASTIK_SITE_URL = "https://www.netlastik.com"

# Bellek cache — 30 dk (API rate limit'e göre)
_cache: dict = {}          # ebat+marka+mevsim → (timestamp, list)
_CACHE_TTL = 30 * 60

# Mevsim dönüşüm tabloları
_MEVSIM_TO_API = {
    "yaz":      "Summer",
    "summer":   "Summer",
    "kış":      "Winter",
    "kis":      "Winter",
    "winter":   "Winter",
    "4 mevsim": "AllSeason",
    "allseason":"AllSeason",
    "all season":"AllSeason",
}
_API_TO_MEVSIM = {
    "Summer":    "Yaz",
    "Winter":    "Kış",
    "AllSeason": "4 Mevsim",
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


def _mevsim_api_kodu(mevsim: str) -> str | None:
    """Kullanıcı mevsim değerini API koduna çevirir. Boşsa None döner."""
    if not mevsim:
        return None
    return _MEVSIM_TO_API.get(mevsim.strip().lower())


def netlastik_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    NetLastik API'sinden ürün arar.
    ebat:   "205/55R16"
    marka:  "Continental"
    mevsim: "Yaz" / "Kış" / "4 Mevsim"
    """
    if not NETLASTIK_API_URL or not NETLASTIK_API_KEY:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")

    # Cache kontrolü
    cache_key = f"{ebat}|{marka}|{mevsim}"
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if time.time() - ts < _CACHE_TTL:
            logger.info(f"[NetLastik] Cache'den {len(data)} ürün döndürüldü")
            return data

    season_api = _mevsim_api_kodu(mevsim)

    params = {
        "tireSize": ebat.strip(),
        "pageSize": 500,
        "pageNumber": 1,
        "sortBy": "price_asc",
    }
    if marka:
        params["brand"] = marka.strip()
    if season_api:
        params["season"] = season_api

    headers = {"EKS": NETLASTIK_API_KEY}

    tum_urunler: list[LastikUrun] = []

    try:
        while True:
            resp = requests.get(NETLASTIK_API_URL, params=params, headers=headers, timeout=20)

            if resp.status_code == 401:
                logger.error("[NetLastik] Geçersiz API key (401)")
                break
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "?")
                logger.warning(f"[NetLastik] Rate limit (429) — Retry-After: {retry_after}s")
                break
            resp.raise_for_status()

            data = resp.json()
            urunler = data.get("products", [])

            for u in urunler:
                try:
                    fiyat  = float(u.get("price", 0) or 0)
                    miktar = int(u.get("stock", 0) or 0)
                    if fiyat < 100:
                        continue

                    mevsim_api = u.get("seasonType", "")
                    mevsim_tr  = _API_TO_MEVSIM.get(mevsim_api, "Yaz")

                    dot = str(u.get("dotYear", "") or "")
                    if dot == "0":
                        dot = ""

                    tum_urunler.append(LastikUrun(
                        toptanci  = "NetLastik",
                        stok_kodu = u.get("sku", "") or "",
                        marka     = u.get("brandName", "") or "",
                        urun_adi  = u.get("name", "") or "",
                        fiyat     = fiyat,
                        miktar    = miktar,
                        dot       = dot,
                        mevsim    = mevsim_tr,
                    ))
                except (ValueError, TypeError):
                    continue

            # Sayfalama
            if data.get("hasNextPage"):
                params["pageNumber"] += 1
            else:
                break

    except requests.RequestException as e:
        logger.error(f"[NetLastik] Bağlantı hatası: {type(e).__name__}")

    tum_urunler.sort(key=lambda x: x.fiyat)
    logger.info(f"[NetLastik] {len(tum_urunler)} ürün döndürüldü (ebat={ebat})")

    # Cache'e yaz
    _cache[cache_key] = (time.time(), tum_urunler)
    return tum_urunler
