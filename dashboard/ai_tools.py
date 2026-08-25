"""
MEStakip Yönetici Asistanı — Tool Katmanı
==========================================
Her tool fonksiyonu:
  - Sadece izin verilen Django ORM sorgularını çalıştırır
  - Sonucu dict olarak döndürür
  - Hata durumunda {"hata": "..."} döndürür
  - Raw SQL veya dosya sistemi erişimi YOKTUR
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum, Q
from django.utils import timezone

from .models import (
    CikmaLastik,
    GarantiBelgesi,
    JokerSatisHareketi,
    MalzemeHareketi,
    Quotation,
    Siparis,
    Transaction,
    TransactionCategory,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────

def _parse_date(s: str) -> date | None:
    """YYYY-MM-DD formatını date nesnesine çevirir."""
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    """Ayın son gününü döndürür."""
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    return d.replace(month=d.month + 1, day=1) - timedelta(days=1)


def _tx_total(tx) -> Decimal:
    """Transaction veya ExcelTransaction'ın toplam tutarını hesaplar."""
    fields = ["nakit", "kredi_karti", "cari", "sanal_pos",
              "mehmet_havale", "banka_havale", "pafgo", "canta_cikis"]
    return sum(Decimal(str(getattr(tx, f, 0) or 0)) for f in fields)


def _safe(fn):
    """Tool fonksiyonlarını sarmalayan hata yönetimi."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.error("AI tool hatası [%s]: %s", fn.__name__, exc, exc_info=True)
            return {"hata": f"Veri alınamadı: {exc}"}
    wrapper.__name__ = fn.__name__
    return wrapper


# ─────────────────────────────────────────────
# SİPARİŞ TOOL'LARI
# ─────────────────────────────────────────────

@_safe
def get_orders_summary(user, start_date: str = "", end_date: str = "",
                       status: str = "", limit: int = 10) -> dict:
    """
    Sipariş özetini döndürür.
    start_date / end_date: YYYY-MM-DD (boş = bu ay başından bugüne)
    status: yolda / teslim / kontrol / iptal / (boş = hepsi)
    """
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    qs = Siparis.objects.filter(user=user, olusturma_tarihi__date__gte=start,
                                olusturma_tarihi__date__lte=end)
    if status:
        qs = qs.filter(durum=status)

    toplam     = qs.count()
    ciro       = float(qs.aggregate(t=Sum("toplam_fiyat"))["t"] or 0)
    top_markalar = list(
        qs.values("marka").annotate(sayi=Count("id"), ciro=Sum("toplam_fiyat"))
          .order_by("-sayi")[:limit]
    )
    durum_dagilim = list(
        qs.values("durum").annotate(sayi=Count("id")).order_by("-sayi")
    )
    return {
        "donem": f"{start} – {end}",
        "filtre_durum": status or "tümü",
        "toplam_siparis": toplam,
        "toplam_ciro_tl": ciro,
        "durum_dagilimi": durum_dagilim,
        "top_markalar": top_markalar,
    }


@_safe
def get_pending_orders(user, limit: int = 20) -> dict:
    """Yolda ve işlemdeki siparişleri listeler."""
    bekleyen_durumlar = [
        "yolda", "islemde",
        "yolda-fatura-islendi", "takilacak-faturasi-islendi",
        "islemde-faturasi-islendi", "takildi-ft-islendi-islem-devam",
    ]
    qs = Siparis.objects.filter(user=user, durum__in=bekleyen_durumlar).order_by("-olusturma_tarihi")
    rows = list(qs.values("id", "cari_firma", "marka", "urun", "adet",
                           "toplam_fiyat", "durum", "olusturma_tarihi")[:limit])
    for r in rows:
        r["toplam_fiyat"] = float(r["toplam_fiyat"])
        r["olusturma_tarihi"] = str(r["olusturma_tarihi"])[:10]
    return {"toplam_bekleyen": qs.count(), "siparisler": rows}


@_safe
def get_cancelled_orders(user, start_date: str = "", end_date: str = "",
                         limit: int = 20) -> dict:
    """İptal edilen siparişleri ve iptal nedenlerini döndürür."""
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    qs = Siparis.objects.filter(user=user, durum="iptal",
                                olusturma_tarihi__date__gte=start,
                                olusturma_tarihi__date__lte=end)
    rows = list(qs.values("id", "cari_firma", "marka", "urun", "adet",
                           "toplam_fiyat", "iptal_sebebi", "olusturma_tarihi")[:limit])
    for r in rows:
        r["toplam_fiyat"] = float(r["toplam_fiyat"])
        r["olusturma_tarihi"] = str(r["olusturma_tarihi"])[:10]
    return {
        "donem": f"{start} – {end}",
        "toplam_iptal": qs.count(),
        "iptal_siparisler": rows,
    }


@_safe
def get_brand_analysis(user, start_date: str = "", end_date: str = "",
                       limit: int = 10) -> dict:
    """Marka bazlı sipariş ve ciro analizini döndürür."""
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    qs = Siparis.objects.filter(user=user, olusturma_tarihi__date__gte=start,
                                olusturma_tarihi__date__lte=end)
    rows = list(
        qs.values("marka")
          .annotate(siparis_sayisi=Count("id"), toplam_adet=Sum("adet"),
                    toplam_ciro=Sum("toplam_fiyat"))
          .order_by("-toplam_ciro")[:limit]
    )
    for r in rows:
        r["toplam_ciro"] = float(r.get("toplam_ciro") or 0)
    return {
        "donem": f"{start} – {end}",
        "marka_analizi": rows,
    }


@_safe
def get_stock_summary(user, brand: str = "", size: str = "",
                      season: str = "", limit: int = 20) -> dict:
    """
    Stok (ambar=stok durumundaki siparişler) özetini döndürür.
    brand: marka adı (kısmi eşleşme)
    size: ebat (örn: 205/55R16)
    season: kis / yaz / dort-mevsim
    """
    qs = Siparis.objects.filter(user=user, ambar="stok").exclude(
        durum__in=["iptal", "kontrol"]
    )
    if brand:
        qs = qs.filter(marka__icontains=brand)
    if size:
        qs = qs.filter(urun__icontains=size)
    if season:
        qs = qs.filter(mevsim=season)

    toplam_kayit = qs.count()
    toplam_adet  = int(qs.aggregate(t=Sum("adet"))["t"] or 0)

    top_urunler = list(
        qs.values("marka", "urun", "mevsim")
          .annotate(adet=Sum("adet"))
          .order_by("-adet")[:limit]
    )
    return {
        "filtreler": {"marka": brand, "ebat": size, "mevsim": season},
        "toplam_stok_kayit": toplam_kayit,
        "toplam_stok_adet": toplam_adet,
        "top_urunler": top_urunler,
    }


@_safe
def get_slow_moving_stock(user, days: int = 90, limit: int = 20) -> dict:
    """
    Son `days` günde hiç satılmayan (kontrol / teslim olmayan) stok ürünlerini listeler.
    """
    since = date.today() - timedelta(days=days)
    qs = Siparis.objects.filter(
        user=user,
        ambar="stok",
        olusturma_tarihi__date__lte=since,
    ).exclude(durum__in=["iptal", "kontrol", "teslim"])

    rows = list(
        qs.values("marka", "urun", "mevsim", "durum")
          .annotate(adet=Sum("adet"), en_eski_tarih=Sum("id"))
          .order_by("olusturma_tarihi")[:limit]
    )
    return {
        "kriter": f"Son {days} günde hareketsiz stok",
        "toplam_kayit": qs.count(),
        "toplam_adet": int(qs.aggregate(t=Sum("adet"))["t"] or 0),
        "urunler": list(
            qs.values("id", "marka", "urun", "mevsim", "adet", "durum",
                      "olusturma_tarihi")
              .order_by("olusturma_tarihi")[:limit]
        ),
    }


# ─────────────────────────────────────────────
# FİNANS TOOL'LARI
# ─────────────────────────────────────────────

def _calc_finance_period(user, start: date, end: date) -> dict:
    """
    Belirli bir dönem için gelir/gider/net hesaplar.
    get_filtered_transactions mantığını kullanır.
    """
    from .views import get_filtered_transactions, get_excel_hizmet_transactions

    f_gelir = {
        "hareket_tipi": "gelir",
        "baslangic_tarih": str(start),
        "bitis_tarih": str(end),
    }
    f_gider = {
        "hareket_tipi": "gider",
        "baslangic_tarih": str(start),
        "bitis_tarih": str(end),
    }

    gelir_islemler = list(get_filtered_transactions(user, **f_gelir)) + \
                     get_excel_hizmet_transactions(user, **f_gelir)
    gider_islemler = list(get_filtered_transactions(user, **f_gider)) + \
                     get_excel_hizmet_transactions(user, **f_gider)

    # Gelir hesabı (kredi/kart/cari/sanal pos için %20 KDV düşümü)
    gelir = Decimal("0")
    for tx in gelir_islemler:
        gelir += Decimal(str(getattr(tx, "nakit", 0) or 0))
        gelir += Decimal(str(getattr(tx, "pafgo", 0) or 0))
        gelir += Decimal(str(getattr(tx, "mehmet_havale", 0) or 0))
        gelir += Decimal(str(getattr(tx, "canta_cikis", 0) or 0))
        gelir += Decimal(str(getattr(tx, "kredi_karti", 0) or 0)) / Decimal("1.20")
        gelir += Decimal(str(getattr(tx, "cari", 0) or 0)) / Decimal("1.20")
        gelir += Decimal(str(getattr(tx, "sanal_pos", 0) or 0)) / Decimal("1.20")
        gelir += Decimal(str(getattr(tx, "banka_havale", 0) or 0)) / Decimal("1.20")

    gider = Decimal("0")
    for tx in gider_islemler:
        gider += _tx_total(tx)

    return {
        "gelir_tl": float(gelir),
        "gider_tl": float(gider),
        "net_tl": float(gelir - gider),
    }


@_safe
def get_financial_summary(user, start_date: str = "", end_date: str = "") -> dict:
    """Belirli dönem için gelir, gider ve net bakiyeyi döndürür."""
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    result = _calc_finance_period(user, start, end)
    result["donem"] = f"{start} – {end}"
    return result


@_safe
def get_financial_comparison(user, current_start: str = "", current_end: str = "",
                             prev_start: str = "", prev_end: str = "") -> dict:
    """
    İki dönemin finansal karşılaştırmasını yapar.
    Varsayılan: bu ay vs geçen ay
    """
    today = date.today()
    cur_start = _parse_date(current_start) or _month_start(today)
    cur_end   = _parse_date(current_end)   or today

    # Bir önceki ay
    prev_month_end   = cur_start - timedelta(days=1)
    prev_month_start = _month_start(prev_month_end)
    pre_start = _parse_date(prev_start) or prev_month_start
    pre_end   = _parse_date(prev_end)   or prev_month_end

    current = _calc_finance_period(user, cur_start, cur_end)
    previous = _calc_finance_period(user, pre_start, pre_end)

    def pct(new_val, old_val):
        if old_val == 0:
            return None
        return round((new_val - old_val) / abs(old_val) * 100, 1)

    return {
        "mevcut_donem": f"{cur_start} – {cur_end}",
        "onceki_donem": f"{pre_start} – {pre_end}",
        "mevcut": current,
        "onceki": previous,
        "degisim": {
            "gelir_pct": pct(current["gelir_tl"], previous["gelir_tl"]),
            "gider_pct": pct(current["gider_tl"], previous["gider_tl"]),
            "net_pct":   pct(current["net_tl"],   previous["net_tl"]),
        },
    }


@_safe
def get_cash_distribution(user, start_date: str = "", end_date: str = "") -> dict:
    """Kasa bazlı işlem dağılımını döndürür."""
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    qs = Transaction.objects.filter(
        created_by=user, tarih__gte=start, tarih__lte=end
    )
    kasalar = list(
        qs.values("kasa_adi", "hareket_tipi")
          .annotate(islem_sayisi=Count("id"),
                    nakit=Sum("nakit"), kredi_karti=Sum("kredi_karti"),
                    cari=Sum("cari"), sanal_pos=Sum("sanal_pos"),
                    mehmet_havale=Sum("mehmet_havale"),
                    banka_havale=Sum("banka_havale"))
          .order_by("kasa_adi", "hareket_tipi")
    )
    return {"donem": f"{start} – {end}", "kasalar": kasalar}


@_safe
def get_expense_by_category(user, start_date: str = "", end_date: str = "",
                            limit: int = 10) -> dict:
    """Giderleri kategoriye göre gruplar."""
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    qs = Transaction.objects.filter(
        created_by=user, hareket_tipi="gider",
        tarih__gte=start, tarih__lte=end
    )
    rows = []
    for tx in qs.select_related("kategori1", "kategori1__parent"):
        cat = ""
        if tx.kategori1:
            cat = (tx.kategori1.parent.name + " / " + tx.kategori1.name
                   if tx.kategori1.parent else tx.kategori1.name)
        rows.append({"kategori": cat or "Kategorisiz", "tutar": float(_tx_total(tx))})

    # Gruplama
    from collections import defaultdict
    grouped: dict[str, float] = defaultdict(float)
    for r in rows:
        grouped[r["kategori"]] += r["tutar"]
    sorted_rows = sorted(grouped.items(), key=lambda x: x[1], reverse=True)[:limit]
    return {
        "donem": f"{start} – {end}",
        "gider_kategorileri": [{"kategori": k, "tutar_tl": round(v, 2)}
                                for k, v in sorted_rows],
    }


# ─────────────────────────────────────────────
# ÇIKMA LASTİK TOOL'LARI
# ─────────────────────────────────────────────

@_safe
def get_used_tire_inventory(brand: str = "", size: str = "",
                            season: str = "", limit: int = 30) -> dict:
    """Depodaki (satılmamış) çıkma lastikleri listeler."""
    qs = CikmaLastik.objects.exclude(durum="satildi")
    if brand:
        qs = qs.filter(marka__icontains=brand)
    if size:
        qs = qs.filter(ebat__icontains=size)
    if season:
        qs = qs.filter(mevsim=season)

    toplam_adet = int(qs.aggregate(t=Sum("adet"))["t"] or 0)
    top_ebatlar = list(
        qs.values("ebat").annotate(adet=Sum("adet")).order_by("-adet")[:10]
    )
    top_markalar = list(
        qs.values("marka").annotate(adet=Sum("adet")).order_by("-adet")[:10]
    )
    rows = list(
        qs.values("id", "marka", "model", "ebat", "mevsim", "adet",
                  "durum", "kalite_notu", "depo_konumu", "cikis_tarihi")
          .order_by("-cikis_tarihi")[:limit]
    )
    return {
        "filtreler": {"marka": brand, "ebat": size, "mevsim": season},
        "toplam_kayit": qs.count(),
        "toplam_adet": toplam_adet,
        "top_ebatlar": top_ebatlar,
        "top_markalar": top_markalar,
        "kayitlar": rows,
    }


@_safe
def get_used_tire_sales(start_date: str = "", end_date: str = "",
                        limit: int = 20) -> dict:
    """Satılan çıkma lastiklerini ve cirosunu döndürür."""
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    qs = CikmaLastik.objects.filter(durum="satildi",
                                    satis_tarihi__gte=start, satis_tarihi__lte=end)
    toplam_adet = int(qs.aggregate(t=Sum("adet"))["t"] or 0)
    ciro = sum(
        float((r.satis_fiyati or 0) * (r.adet or 0))
        for r in qs.only("satis_fiyati", "adet")
    )
    top_ebatlar = list(
        qs.values("ebat").annotate(adet=Sum("adet")).order_by("-adet")[:10]
    )
    return {
        "donem": f"{start} – {end}",
        "toplam_satis_kayit": qs.count(),
        "toplam_satis_adet": toplam_adet,
        "toplam_ciro_tl": round(ciro, 2),
        "top_ebatlar": top_ebatlar,
    }


@_safe
def get_used_tire_waiting_long(days: int = 60, limit: int = 20) -> dict:
    """Uzun süredir depoda bekleyen çıkma lastikleri listeler."""
    since = date.today() - timedelta(days=days)
    qs = CikmaLastik.objects.filter(
        durum__in=["cikti", "depolandi"],
        cikis_tarihi__lte=since,
    ).order_by("cikis_tarihi")

    rows = list(
        qs.values("id", "marka", "model", "ebat", "mevsim", "adet",
                  "kalite_notu", "depo_konumu", "cikis_tarihi")[:limit]
    )
    return {
        "kriter": f"Son {days} günden fazla bekleyen",
        "toplam_kayit": qs.count(),
        "toplam_adet": int(qs.aggregate(t=Sum("adet"))["t"] or 0),
        "lastikler": rows,
    }


# ─────────────────────────────────────────────
# TEKLİF TOOL'LARI
# ─────────────────────────────────────────────

@_safe
def get_quotes_summary(status: str = "", start_date: str = "",
                       end_date: str = "", limit: int = 10) -> dict:
    """Teklifleri özetler."""
    qs = Quotation.objects.all()
    if status:
        qs = qs.filter(durum=status)
    if start_date:
        qs = qs.filter(teklif_tarihi__gte=_parse_date(start_date))
    if end_date:
        qs = qs.filter(teklif_tarihi__lte=_parse_date(end_date))

    toplam = qs.count()
    toplam_tutar = float(qs.aggregate(t=Sum("genel_toplam"))["t"] or 0)
    durum_dagilim = list(
        qs.values("durum").annotate(sayi=Count("id"), tutar=Sum("genel_toplam"))
          .order_by("-sayi")
    )
    en_yuksek = list(
        qs.values("id", "teklif_no", "cari", "durum",
                  "teklif_tarihi", "genel_toplam")
          .order_by("-genel_toplam")[:limit]
    )
    for r in en_yuksek:
        r["genel_toplam"] = float(r.get("genel_toplam") or 0)
    return {
        "filtre_durum": status or "tümü",
        "toplam_teklif": toplam,
        "toplam_tutar_tl": toplam_tutar,
        "durum_dagilimi": durum_dagilim,
        "en_yuksek_teklifler": en_yuksek,
    }


# ─────────────────────────────────────────────
# MALZEME / JOKER TOOL'LARI
# ─────────────────────────────────────────────

@_safe
def get_material_movements(user, start_date: str = "", end_date: str = "",
                           category: str = "", limit: int = 20) -> dict:
    """Malzeme hareketlerini özetler."""
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    qs = MalzemeHareketi.objects.filter(kullanici=user,
                                        tarih__gte=start, tarih__lte=end)
    if category:
        qs = qs.filter(kategori__icontains=category)

    toplam_tutar = float(qs.aggregate(t=Sum("tutar"))["t"] or 0)
    top_kategoriler = list(
        qs.values("kategori").annotate(sayi=Count("id"), tutar=Sum("tutar"))
          .order_by("-tutar")[:10]
    )
    top_urunler = list(
        qs.values("urun").annotate(sayi=Count("id"), tutar=Sum("tutar"))
          .order_by("-tutar")[:limit]
    )
    return {
        "donem": f"{start} – {end}",
        "toplam_satir": qs.count(),
        "toplam_tutar_tl": toplam_tutar,
        "top_kategoriler": top_kategoriler,
        "top_urunler": top_urunler,
    }


@_safe
def get_joker_sales(start_date: str = "", end_date: str = "",
                    limit: int = 10) -> dict:
    """Joker satış analizini döndürür."""
    today = date.today()
    start = _parse_date(start_date) or _month_start(today)
    end   = _parse_date(end_date)   or today

    qs = JokerSatisHareketi.objects.filter(tarih__gte=start, tarih__lte=end)
    toplam_satis = float(qs.aggregate(t=Sum("satis_fiyati"))["t"] or 0)
    toplam_kar   = float(qs.aggregate(t=Sum("kar_tutari"))["t"] or 0)
    top_urunler  = list(
        qs.values("urun", "marka")
          .annotate(miktar=Sum("miktar"), kar=Sum("kar_tutari"))
          .order_by("-kar")[:limit]
    )
    return {
        "donem": f"{start} – {end}",
        "toplam_satir": qs.count(),
        "toplam_satis_tl": round(toplam_satis, 2),
        "toplam_kar_tl": round(toplam_kar, 2),
        "top_urunler": top_urunler,
    }


# ─────────────────────────────────────────────
# GENEL ÖZET TOOL'U
# ─────────────────────────────────────────────

@_safe
def get_proactive_summary(user) -> dict:
    """
    Dashboard açılışında gösterilecek proaktif özet.
    Kritik uyarıları, pozitif gelişmeleri ve bekleyen işlemleri döndürür.
    """
    today = date.today()
    start_month = _month_start(today)
    start_30 = today - timedelta(days=30)

    # Siparişler
    yolda = Siparis.objects.filter(user=user, durum__in=[
        "yolda", "islemde", "yolda-fatura-islendi",
        "takilacak-faturasi-islendi", "islemde-faturasi-islendi",
        "takildi-ft-islendi-islem-devam",
    ]).count()

    bu_ay_siparis = Siparis.objects.filter(
        user=user, olusturma_tarihi__date__gte=start_month
    ).count()
    bu_ay_ciro = float(
        Siparis.objects.filter(user=user, olusturma_tarihi__date__gte=start_month)
               .aggregate(t=Sum("toplam_fiyat"))["t"] or 0
    )

    # Teklifler
    acik_teklif = Quotation.objects.filter(durum="acik").count()
    acik_teklif_tutar = float(
        Quotation.objects.filter(durum="acik")
                 .aggregate(t=Sum("genel_toplam"))["t"] or 0
    )

    # Çıkma lastik
    depoda_adet = int(
        CikmaLastik.objects.filter(durum__in=["cikti", "depolandi"])
                   .aggregate(t=Sum("adet"))["t"] or 0
    )

    # Uzun süredir bekleyen çıkma lastik
    uzun_bekleyen = CikmaLastik.objects.filter(
        durum__in=["cikti", "depolandi"],
        cikis_tarihi__lte=today - timedelta(days=60),
    ).count()

    # Finans özeti (bu ay)
    finans = _calc_finance_period(user, start_month, today)

    uyarilar = []
    pozitifler = []
    bilgiler = []

    if yolda > 0:
        bilgiler.append(f"🚚 {yolda} sipariş yolda / işlemde")
    if acik_teklif > 0:
        bilgiler.append(f"📋 {acik_teklif} açık teklif — toplam {acik_teklif_tutar:,.0f} ₺")
    if depoda_adet > 0:
        bilgiler.append(f"🔧 Depoda {depoda_adet} adet çıkma lastik")
    if uzun_bekleyen > 0:
        uyarilar.append(f"⚠️ {uzun_bekleyen} çıkma lastik kaydı 60+ gündür depoda bekliyor")
    if finans["net_tl"] > 0:
        pozitifler.append(f"📈 Bu ay net: +{finans['net_tl']:,.0f} ₺ (gelir: {finans['gelir_tl']:,.0f} ₺)")
    elif finans["net_tl"] < 0:
        uyarilar.append(f"📉 Bu ay net zarar: {finans['net_tl']:,.0f} ₺")

    return {
        "tarih": str(today),
        "bu_ay_siparis": bu_ay_siparis,
        "bu_ay_ciro_tl": bu_ay_ciro,
        "finans_bu_ay": finans,
        "yolda_siparis": yolda,
        "acik_teklif": acik_teklif,
        "acik_teklif_tutar_tl": acik_teklif_tutar,
        "depoda_cikma_lastik_adet": depoda_adet,
        "uyarilar": uyarilar,
        "pozitifler": pozitifler,
        "bilgiler": bilgiler,
    }


# ─────────────────────────────────────────────
# TOOL REGISTRY — Groq'a gönderilecek tanımlar
# ─────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_orders_summary",
            "description": "Belirli tarih aralığında sipariş sayısı, ciro, durum dağılımı ve marka analizini döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Başlangıç tarihi YYYY-MM-DD"},
                    "end_date":   {"type": "string", "description": "Bitiş tarihi YYYY-MM-DD"},
                    "status":     {"type": "string", "description": "yolda | teslim | kontrol | iptal (boş=hepsi)"},
                    "limit":      {"type": "integer", "description": "Kaç marka gösterilsin (varsayılan 10)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_orders",
            "description": "Yolda veya işlemdeki bekleyen siparişleri listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Kaç sipariş gösterilsin"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cancelled_orders",
            "description": "İptal edilen siparişleri ve iptal nedenlerini döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                    "limit":      {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_brand_analysis",
            "description": "Marka bazlı sipariş sayısı ve ciro analizini döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                    "limit":      {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_summary",
            "description": "Depodaki stok durumunu döndürür. Marka, ebat veya mevsim filtresiyle aranabilir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand":  {"type": "string", "description": "Marka adı (kısmi)"},
                    "size":   {"type": "string", "description": "Ebat (örn: 205/55R16)"},
                    "season": {"type": "string", "description": "kis | yaz | dort-mevsim"},
                    "limit":  {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_slow_moving_stock",
            "description": "Uzun süredir satılmayan (hareketsiz) stok ürünlerini listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days":  {"type": "integer", "description": "Kaç günden beri hareketsiz (varsayılan 90)"},
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_summary",
            "description": "Belirli dönem için gelir, gider ve net bakiyeyi döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_comparison",
            "description": "İki dönemin finansal karşılaştırmasını yapar. Varsayılan: bu ay vs geçen ay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_start": {"type": "string"},
                    "current_end":   {"type": "string"},
                    "prev_start":    {"type": "string"},
                    "prev_end":      {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cash_distribution",
            "description": "Kasa (servis, merkez-satis, joker-satis) bazlı işlem dağılımını döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expense_by_category",
            "description": "Giderleri kategoriye göre gruplar ve sıralar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                    "limit":      {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_used_tire_inventory",
            "description": "Depodaki (satılmamış) çıkma lastiklerini listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand":  {"type": "string"},
                    "size":   {"type": "string"},
                    "season": {"type": "string"},
                    "limit":  {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_used_tire_sales",
            "description": "Satılan çıkma lastiklerini ve cirosunu döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                    "limit":      {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_used_tire_waiting_long",
            "description": "Uzun süredir depoda bekleyen çıkma lastiklerini listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days":  {"type": "integer", "description": "Kaç günden fazla bekleyen (varsayılan 60)"},
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quotes_summary",
            "description": "Teklifleri özetler. Durum filtresi: acik | onaylandi | reddedildi",
            "parameters": {
                "type": "object",
                "properties": {
                    "status":     {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                    "limit":      {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_material_movements",
            "description": "Malzeme hareketleri özetini döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                    "category":   {"type": "string"},
                    "limit":      {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_joker_sales",
            "description": "Joker satış analizini döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date":   {"type": "string"},
                    "limit":      {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_proactive_summary",
            "description": "İşletmenin genel durumunu, uyarıları ve önemli bilgileri özetler.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

# Tool adı → fonksiyon eşlemesi
TOOL_REGISTRY = {
    "get_orders_summary":        get_orders_summary,
    "get_pending_orders":        get_pending_orders,
    "get_cancelled_orders":      get_cancelled_orders,
    "get_brand_analysis":        get_brand_analysis,
    "get_stock_summary":         get_stock_summary,
    "get_slow_moving_stock":     get_slow_moving_stock,
    "get_financial_summary":     get_financial_summary,
    "get_financial_comparison":  get_financial_comparison,
    "get_cash_distribution":     get_cash_distribution,
    "get_expense_by_category":   get_expense_by_category,
    "get_used_tire_inventory":   get_used_tire_inventory,
    "get_used_tire_sales":       get_used_tire_sales,
    "get_used_tire_waiting_long": get_used_tire_waiting_long,
    "get_quotes_summary":        get_quotes_summary,
    "get_material_movements":    get_material_movements,
    "get_joker_sales":           get_joker_sales,
    "get_proactive_summary":     get_proactive_summary,
}

# user parametresi gerektiren tool'lar
USER_REQUIRED_TOOLS = {
    "get_orders_summary", "get_pending_orders", "get_cancelled_orders",
    "get_brand_analysis", "get_stock_summary", "get_slow_moving_stock",
    "get_financial_summary", "get_financial_comparison", "get_cash_distribution",
    "get_expense_by_category", "get_material_movements", "get_proactive_summary",
}
