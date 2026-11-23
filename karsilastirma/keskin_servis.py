"""
Keskin Lastik XML Servisi
URL: [tedarikçi adresi ortam ayarından alınır]

XML 60 dakikada bir çekilebilir (rate limit).
Django DB cache kullanılır — tüm worker'lar aynı cache'i paylaşır.

XML yapısı:
    <Stoklar>
      <Stok>
        <PrcCode>CONTI-13010</PrcCode>
        <ACIKLAMA>175/70/13 82T ECO CONTACT 6</ACIKLAMA>
        <Brand>CONTINENTAL</Brand>
        <KATEGORİ>BİNEK</KATEGORİ>
        <MEVSIM>YAZ</MEVSIM>          ← YAZ | KIŞ | 4 MEVSİM
        <DOT>2026</DOT>
        <BAYI>3322</BAYI>
        <ADET>4.00</ADET>             ← veya "20+"
        <SEARCHKEYWORDS>175/70/13,1757013</SEARCHKEYWORDS>
      </Stok>
    </Stoklar>

Ebat formatı: "175/70/13" (R yok, eğik çizgili)
"""

import re
import os
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .onbellek import cache

KESKIN_XML_URL = os.getenv("MESBUL_KESKIN_XML_URL", "").strip()

CACHE_KEY       = "keskin_tum_urunler"
CACHE_KEY_STALE = "keskin_tum_urunler_stale"
CACHE_TTL       = 55 * 60
CACHE_TTL_STALE = 24 * 60 * 60

SUBE_ALANLARI = [
    "MERKEZ_ADET", "MASLAK_ADET", "BOSTANCI_ADET", "LEVENT_ADET",
    "ANKARA_ADET", "BURSA_ADET", "SEYRANTEPE_ADET", "İZMİR_ADET",
    "HADIMKOY_ADET", "SEKERPINAR_ADET",
]


@dataclass
class LastikUrun:
    toptanci:       str
    stok_kodu:      str
    marka:          str
    urun_adi:       str
    fiyat:          float
    miktar:         int
    dot:            str
    mevsim:         str
    kategori:       str = ""
    searchkeywords: str = ""

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


def _adet_parse(deger: str) -> float:
    """'20+', '1.00', '0.00' → float."""
    return float((deger or "0").replace("+", "").strip() or "0")


def _mevsim_duzenle(ham: str) -> str:
    """YAZ → Yaz | KIŞ → Kış | 4 MEVSİM / 4 MEVSIM → 4 Mevsim"""
    # Türkçe İ/I normalize et
    tr_map = str.maketrans("İIŞĞÜÖÇ", "iışğüöç")
    h = ham.strip().translate(tr_map).lower()
    if "4" in h or "all" in h:
        return "4 Mevsim"
    if "kış" in h or "kiş" in h or "kis" in h or "win" in h or "kıs" in h:
        return "Kış"
    return "Yaz"


def _ebat_normalize(ebat: str) -> tuple[str, str]:
    """
    "205/55R16" → slash="205/55/16", rakam="2055516"
    "205/55/16" → slash="205/55/16", rakam="2055516"
    """
    temiz = ebat.strip().upper()
    slash = re.sub(r'R(\d)', r'/\1', temiz)
    rakam = re.sub(r'[^0-9]', '', slash)
    return slash, rakam


def keskin_verileri_getir() -> list[LastikUrun]:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(KESKIN_XML_URL, timeout=60)
        resp.raise_for_status()
        content = resp.content.lstrip(b'\xef\xbb\xbf')
        root = ET.fromstring(content)
    except requests.RequestException as e:
        print(f"[Keskin Lastik] Bağlantı hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Keskin Lastik] XML parse hatası: {type(e).__name__}")
        return cache.get(CACHE_KEY_STALE) or []

    # Rate limit kontrolü
    if root.tag != "Stoklar":
        mesaj   = root.findtext(".//HataMesaj", "") or root.text or ""
        sonraki = root.findtext(".//SonrakiXmlTarihi", "")
        print(f"[Keskin Lastik] Rate limit: {mesaj} — Sonraki: {sonraki}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for stok in root.findall("Stok"):
        try:
            fiyat = float(stok.findtext("BAYI", "0") or "0")
            if fiyat < 100:
                continue

            # Stok: önce ADET, 0 ise şubeleri topla
            adet = _adet_parse(stok.findtext("ADET", "0") or "0")
            if adet <= 0:
                for sube in SUBE_ALANLARI:
                    adet += _adet_parse(stok.findtext(sube, "0") or "0")
            if adet <= 0:
                continue

            urunler.append(LastikUrun(
                toptanci       = "Keskin Lastik",
                stok_kodu      = (stok.findtext("PrcCode",       "") or "").strip(),
                marka          = (stok.findtext("Brand",         "") or "").strip(),
                urun_adi       = (stok.findtext("ACIKLAMA",      "") or "").strip(),
                fiyat          = fiyat,
                miktar         = int(adet),
                dot            = (stok.findtext("DOT",           "") or "").strip(),
                mevsim         = _mevsim_duzenle(stok.findtext("MEVSIM", "YAZ") or "YAZ"),
                kategori       = (stok.findtext("KATEGORİ",      "") or "").strip(),
                searchkeywords = (stok.findtext("SEARCHKEYWORDS","") or "").upper(),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Keskin Lastik] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def keskin_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    if not KESKIN_XML_URL:
        raise ValueError("Tedarikçi bağlantısı yapılandırılmamış.")
    tum_urunler = keskin_verileri_getir()

    ebat_slash, ebat_rakam = _ebat_normalize(ebat)
    marka_upper  = marka.strip().upper()
    mevsim_temiz = mevsim.strip().lower()

    sonuclar = []
    for u in tum_urunler:
        if ebat.strip():
            urun_upper    = u.urun_adi.upper()
            urun_no_slash = urun_upper.replace("/", "").replace(" ", "")

            eslesti = (
                ebat_slash in urun_upper       or  # "205/55/16" in ACIKLAMA
                ebat_rakam in urun_no_slash    or  # "2055516"   in ACIKLAMA
                ebat_rakam in u.searchkeywords     # "2055516"   in SEARCHKEYWORDS
            )
            if not eslesti:
                continue

        if marka_upper and (marka_upper not in u.marka.upper() and marka_upper not in u.urun_adi.upper()):
            continue

        if mevsim_temiz and mevsim_temiz not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
