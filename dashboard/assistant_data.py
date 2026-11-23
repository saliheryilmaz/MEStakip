"""Read-only, bounded ERP queries for the manager assistant."""

from django.db.models import Max, Q, Sum
from django.urls import reverse
from django.utils import timezone

from .ai_tools import _safe, _parse_date
from .assistant_guide import get_project_guide


def _period(qs, field, start_date, end_date):
    today = timezone.localdate()
    start = _parse_date(start_date) or today.replace(day=1)
    end = _parse_date(end_date) or today
    if start > end:
        raise ValueError("Başlangıç tarihi bitişten sonra olamaz.")
    return qs.filter(**{field + "__gte": start, field + "__lte": end}), f"{start} / {end}"


def _result(qs, fields, route, limit, **extra):
    return {"kaynak": reverse(route), "sorgu_zamani": timezone.now().isoformat(),
            "toplam_kayit": qs.count(), "kayitlar": list(qs.values(*fields)[:limit]), **extra}


@_safe
def get_erp_customers(query="", status="", limit=20):
    from erp.models import Cari
    qs = Cari.objects.all()
    if query:
        qs = qs.filter(Q(unvan__icontains=query) | Q(cari_kodu__icontains=query))
    if status:
        qs = qs.filter(durum=status)
    return _result(qs, ("cari_kodu", "unvan", "tip", "durum", "sehir", "bakiye", "sync_durumu", "son_sync_tarihi"),
                   "erp:cari_listesi", limit, notlar="Yerel cari kartları; bakiye son DİA aktarımına aittir.")


@_safe
def get_erp_stock_by_brand(brand=""):
    from erp.models import StokKart
    qs = StokKart.objects.filter(durum="A", gercek_stok__gt=0)
    if brand:
        qs = qs.filter(marka__icontains=brand)
    groups = qs.values("marka", "ana_birim").annotate(miktar=Sum("gercek_stok")).order_by("marka", "ana_birim")
    return {"markalar": list(groups), "son_kart_aktarimi": qs.aggregate(t=Max("son_sync_tarihi"))["t"]}


@_safe
def get_erp_stock(query="", brand="", limit=20):
    from erp.models import StokKart
    qs = StokKart.objects.filter(durum="A")
    if query:
        qs = qs.filter(Q(stok_kodu__icontains=query) | Q(aciklama__icontains=query))
    if brand:
        qs = qs.filter(marka__icontains=brand)
    return _result(qs, ("stok_kodu", "aciklama", "marka", "ana_birim", "gercek_stok", "fiili_stok", "son_sync_tarihi"),
                   "erp:stok_listesi", limit,
                   birim_bazinda=list(qs.values("ana_birim").annotate(gercek=Sum("gercek_stok"), fiili=Sum("fiili_stok"))),
                   notlar="DİA yerel kopyası; anlık stok garantisi yoktur. Farklı birimler toplanmaz.")


@_safe
def get_erp_invoices(start_date="", end_date="", query="", kind="", limit=20):
    from erp.models import Fatura
    qs, period = _period(Fatura.objects.all(), "tarih", start_date, end_date)
    if query:
        qs = qs.filter(Q(cari_unvan__icontains=query) | Q(cari_kodu__icontains=query) |
                       Q(fis_no__icontains=query) | Q(belge_no__icontains=query))
    if kind:
        qs = qs.filter(tur=kind)
    return _result(qs, ("fis_no", "belge_no", "tarih", "tur", "cari_unvan", "toplam", "net", "son_sync_tarihi"),
                   "erp:fatura_listesi", limit, donem=period,
                   tur_bazinda=list(qs.values("tur").annotate(toplam=Sum("toplam"), net=Sum("net"))),
                   notlar="Yerel fatura tutarları tahsilat değildir; döviz ayrımı bu modelde mevcut değil.")


@_safe
def get_erp_material_lines(start_date="", end_date="", query="", brand="", kind="", limit=20):
    from erp.models import FaturaKalemi
    qs, period = _period(FaturaKalemi.objects.all(), "fatura__tarih", start_date, end_date)
    if query:
        qs = qs.filter(Q(stok_kodu__icontains=query) | Q(stok_adi__icontains=query) | Q(fatura__cari_unvan__icontains=query))
    if brand:
        qs = qs.filter(marka__icontains=brand)
    if kind:
        qs = qs.filter(fatura__tur=kind)
    qs = qs.order_by("-fatura__tarih", "-pk")
    return _result(qs, ("fatura__fis_no", "fatura__tarih", "fatura__tur", "fatura__cari_unvan",
                       "stok_kodu", "stok_adi", "marka", "dot", "miktar", "birim", "tutar", "odeme_plani"),
                   "erp:fatura_listesi", limit, donem=period,
                   notlar="DİA fatura kalemleri; Excel malzeme hareketlerinden ayrı veri kaynağı.")


@_safe
def get_dia_sync_status():
    from dia_integration.models import SyncLog
    rows = []
    for module in ("cari", "stok", "fatura", "stok_depo_miktar", "firma_donem"):
        # Do not send raw exception messages or connection credentials to the model.
        latest = SyncLog.objects.filter(modul=module).values(
            "modul", "baslangic", "bitis", "durum", "toplam_kayit", "basarili_kayit", "hatali_kayit"
        ).order_by("-baslangic").first()
        rows.append(latest or {"modul": module, "durum": "hiç çalışmamış"})
    return {"moduller": rows, "kaynak": reverse("erp:dia_durum"),
            "notlar": "Yerel görev kayıtları. Canlı DİA bağlantısı test edilmedi."}


@_safe
def get_warranties(user, query="", limit=20):
    from .models import GarantiBelgesi
    qs = GarantiBelgesi.objects.filter(olusturan=user)
    if query:
        qs = qs.filter(Q(musteri_adi__icontains=query) | Q(arac_plaka__icontains=query) | Q(belge_no__icontains=query))
    return _result(qs, ("belge_no", "musteri_adi", "arac_plaka", "montaj_tarihi"), "dashboard:garanti_belgeleri", limit)


@_safe
def get_tire_storage(query="", status="depoda", limit=12):
    from .models import LastikOteli
    qs = LastikOteli.objects.all()
    if status:
        qs = qs.filter(durum=status)
    if query:
        qs = qs.filter(Q(plaka__icontains=query) | Q(musteri_adi__icontains=query) |
                       Q(depo__ad__icontains=query) | Q(depo__raf__icontains=query))
    return _result(qs, ("plaka", "musteri_adi", "mevsim", "adet", "durum", "depo__ad", "depo__raf"),
                   "dashboard:lastik_saklama", limit,
                   plaka_sayisi=qs.exclude(plaka="").values("plaka").distinct().count(),
                   mevsim_bazinda=list(qs.order_by().values("mevsim").annotate(lastik=Sum("adet"))))


@_safe
def get_fleet(user, query="", limit=12):
    from .models import FiloArac
    qs = FiloArac.objects.filter(user=user)
    if query:
        qs = qs.filter(Q(plaka__icontains=query) | Q(raf__icontains=query) | Q(ebat__icontains=query))
    return _result(qs, ("plaka", "raf", "adet", "durum", "ebat", "mevsim"), "dashboard:filo_yonetimi", limit)


@_safe
def get_calendar(user, start_date="", end_date="", limit=12):
    from .models import Event
    qs, period = _period(Event.objects.filter(created_by=user), "date", start_date, end_date)
    return _result(qs.order_by("date", "time"), ("title", "date", "time", "priority"),
                   "dashboard:calendar", limit, donem=period)


@_safe
def get_deposits(user, start_date="", end_date="", query="", limit=12):
    from .models import SiparisKapora
    qs, period = _period(SiparisKapora.objects.filter(siparis__user=user), "tarih", start_date, end_date)
    if query:
        qs = qs.filter(siparis__musteri_adi__icontains=query)
    return _result(qs.order_by("-tarih", "-pk"), ("siparis_id", "siparis__musteri_adi", "tutar", "yontem", "tarih"),
                   "dashboard:orders", limit, donem=period, toplam_tutar=qs.aggregate(t=Sum("tutar"))["t"] or 0)


@_safe
def get_warehouse_slips(query="", start_date="", end_date="", limit=12):
    from erp.models import DepoFisi
    qs, period = _period(DepoFisi.objects.all(), "tarih", start_date, end_date)
    if query:
        qs = qs.filter(Q(cari__icontains=query) | Q(plaka__icontains=query) | Q(fis_no__icontains=query))
    return _result(qs.order_by("-tarih", "-pk"), ("fis_no", "tarih", "cari", "plaka", "adet", "onaylandi", "fatura_no"),
                   "erp:depo_fisi_listesi", limit, donem=period)


def _definition(name, description, **properties):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "additionalProperties": False}}}


TEXT = {"type": "string"}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 30}
DATE = {"type": "string", "description": "YYYY-MM-DD; boş ise bu ay"}
KIND = {"type": "string", "enum": ["", "S", "A", "I", "D"]}
DEFINITIONS = [
    _definition("get_erp_stock_by_brand", "Mevcut DİA sıfır lastik stoklarını marka ve birime göre topla. Son stok kartı aktarım zamanını da verir.", brand=TEXT),
    _definition("get_tire_storage", "Lastik saklama otelinde müşteri, plaka veya raf ara. Mevsimlere göre adet ve plaka sayısı.", query=TEXT, status={"type":"string","enum":["depoda","teslim_edildi",""]}, limit=LIMIT),
    _definition("get_fleet", "Kullanıcının filo araçları, plaka, raf ve lastik ebadı.", query=TEXT, limit=LIMIT),
    _definition("get_deposits", "Sipariş kaporaları, nakit ve havale tutarları. Müşteri adıyla filtrelenebilir.", start_date=DATE, end_date=DATE, query=TEXT, limit=LIMIT),
    _definition("get_calendar", "Kullanıcının belirtilen tarih aralığındaki takvim etkinlikleri.", start_date=DATE, end_date=DATE, limit=LIMIT),
    _definition("get_warehouse_slips", "Depo fişleri, fiş numarası, müşteri, plaka ve onay durumu.", start_date=DATE, end_date=DATE, query=TEXT, limit=LIMIT),
    _definition("get_project_guide", "MesDia sayfaları ve kullanım adımları. Genel proje anlatımı için topic boş bırak.", topic=TEXT),
    _definition("get_erp_customers", "DİA cari kartlarını ünvan/kodla ara; varsayılan aktif ve pasif birlikte.", query=TEXT, status={"type": "string", "enum": ["", "A", "P"]}, limit=LIMIT),
    _definition("get_erp_stock", "DİA sıfır lastik stok kartları ve gerçek/fiili miktarlar. Sipariş stoğu değildir.", query=TEXT, brand=TEXT, limit=LIMIT),
    _definition("get_erp_invoices", "DİA alış/satış/iade faturaları; cari veya fatura numarasıyla arama.", start_date=DATE, end_date=DATE, query=TEXT, kind=KIND, limit=LIMIT),
    _definition("get_erp_material_lines", "DİA fatura ürün satırları; DOT, marka, miktar ve ödeme planı.", start_date=DATE, end_date=DATE, query=TEXT, brand=TEXT, kind=KIND, limit=LIMIT),
    _definition("get_dia_sync_status", "Cari/stok/fatura verisi neden gelmiyor? Son aktarım durumları ve hatalı kayıt sayıları."),
    _definition("get_warranties", "Kullanıcının garanti belgeleri; müşteri, plaka veya belge numarasıyla arama.", query=TEXT, limit=LIMIT),
]
REGISTRY = {fn.__name__: fn for fn in (get_tire_storage, get_fleet, get_deposits, get_calendar, get_warehouse_slips, get_project_guide, get_erp_customers, get_erp_stock, get_erp_stock_by_brand,
            get_erp_invoices, get_erp_material_lines, get_dia_sync_status, get_warranties)}
