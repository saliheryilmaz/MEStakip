import hashlib
import re
import json
import unicodedata
from uuid import uuid4
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse, StreamingHttpResponse
from django.core.cache import cache
from django.views.decorators.gzip import gzip_page
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.http import require_POST

from .uspa_servis        import uspa_ara
from .keskin_servis      import keskin_ara
from .otosemih_servis    import otosemih_ara
from .netlastik_servis   import netlastik_ara
from .lastsis_servis     import lastsis_ara
from .dincbay_servis     import dincbay_ara
from .degeras_servis     import degeras_ara
from .art4_servis        import art4_ara
from .simetri_servis     import simetri_ara
from .yilkarlas_servis   import yilkarlas_ara
from .oltay_servis       import oltay_ara
from .asoto_servis       import asoto_ara
from .karaoglu_servis    import karaoglu_ara
from .cakiroglu_servis   import cakiroglu_ara
from .ayko_servis        import ayko_ara
from .halilyilmaz_servis import halilyilmaz_ara
from .mollaoglu_servis   import mollaoglu_ara
from .onbellek import cache as mesbul_cache
from .models import AramaGecmisi, Abonelik, Odeme, Notlar, ToptanciIskonto


class AbonelikGerekli(LoginRequiredMixin):
    """
    Giriş yapılmamış kullanıcıları ana sayfaya (modal ile) yönlendirir.
    Giriş yapılmış ama aboneliği olmayan veya süresi dolmuş
    kullanıcıları bilgilendirme sayfasına yönlendirir.
    """
    login_url = settings.LOGIN_URL
    redirect_field_name = 'next'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not request.user.is_staff:
            try:
                abonelik = request.user.abonelik
                if not abonelik.erisim_var_mi:
                    return render(request, "karsilastirma/abonelik_bitti.html", {
                        "bitis": abonelik.bitis,
                        "plan":  abonelik.plan,
                    }, status=403)
            except Abonelik.DoesNotExist:
                return render(request, "karsilastirma/abonelik_bitti.html", {
                    "bitis": None,
                    "plan":  None,
                }, status=403)

        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)

# ── Marka normalize ──────────────────────────────────────────────────────────

# Bilinen yazım varyantlarını canonical forma eşle
# Anahtar: küçük harf + boşluk normalize edilmiş → Değer: gösterilecek isim
MARKA_ESLESME = {
    # ── Continental ──
    "continental":       "Continental",
    "continantal":       "Continental",
    "continenta":        "Continental",
    "contintental":      "Continental",
    "continetal":        "Continental",
    "contiental":        "Continental",
    "conti":             "Continental",
    "contı":             "Continental",

    # ── Bridgestone ──
    "bridgestone":       "Bridgestone",
    "bridgeston":        "Bridgestone",
    "bridgstonne":       "Bridgestone",
    "brigdestone":       "Bridgestone",

    # ── Michelin ──
    "michelin":          "Michelin",
    "michellin":         "Michelin",
    "michlin":           "Michelin",

    # ── Pirelli ──
    "pirelli":           "Pirelli",
    "pirrelli":          "Pirelli",
    "pireli":            "Pirelli",

    # ── Goodyear ──
    "goodyear":          "Goodyear",
    "good year":         "Goodyear",
    "goodyear dunlop":   "Goodyear",

    # ── Dunlop ──
    "dunlop":            "Dunlop",

    # ── Hankook ──
    "hankook":           "Hankook",
    "han kook":          "Hankook",
    "hankuk":            "Hankook",

    # ── Yokohama ──
    "yokohama":          "Yokohama",
    "yokahoma":          "Yokohama",

    # ── Falken ──
    "falken":            "Falken",

    # ── Kumho ──
    "kumho":             "Kumho",

    # ── Lassa ──
    "lassa":             "Lassa",

    # ── Petlas ──
    "petlas":            "Petlas",

    # ── Maxxis ──
    "maxxis":            "Maxxis",

    # ── Toyo ──
    "toyo":              "Toyo",
    "toyo tires":        "Toyo",

    # ── Uniroyal ──
    "uniroyal":          "Uniroyal",

    # ── Nokian ──
    "nokian":            "Nokian",
    "nokian tyres":      "Nokian",

    # ── BFGoodrich ──
    "bfgoodrich":        "BFGoodrich",
    "bf goodrich":       "BFGoodrich",
    "bf-goodrich":       "BFGoodrich",

    # ── Apollo ──
    "apollo":            "Apollo",

    # ── Debica / Dębica ──
    "debica":            "Debica",
    "dębica":            "Debica",
    "debıca":            "Debica",

    # ── Dayton ──
    "dayton":            "Dayton",

    # ── Barum ──
    "barum":             "Barum",

    # ── Firestone ──
    "firestone":         "Firestone",

    # ── Nexen ──
    "nexen":             "Nexen",

    # ── Starmaxx ──
    "starmaxx":          "Starmaxx",

    # ── Linglong ──
    "linglong":          "Linglong",
    "ling long":         "Linglong",

    # ── Triangle ──
    "triangle":          "Triangle",

    # ── Kormoran ──
    "kormoran":          "Kormoran",

    # ── Tigar ──
    "tigar":             "Tigar",

    # ── Fulda ──
    "fulda":             "Fulda",

    # ── Kleber ──
    "kleber":            "Kleber",

    # ── Vredestein ──
    "vredestein":        "Vredestein",

    # ── General ──
    "general":           "General",
    "general tire":      "General",

    # ── Cooper ──
    "cooper":            "Cooper",

    # ── Sailun ──
    "sailun":            "Sailun",

    # ── Sava ──
    "sava":              "Sava",

    # ── Matador ──
    "matador":           "Matador",

    # ── Semperit ──
    "semperit":          "Semperit",

    # ── Riken ──
    "riken":             "Riken",

    # ── Giti ──
    "giti":              "Giti",

    # ── Leao ──
    "leao":              "Leao",

    # ── Westlake ──
    "westlake":          "Westlake",

    # ── Goodride ──
    "goodride":          "Goodride",

    # ── Nankang ──
    "nankang":           "Nankang",

    # ── Accelera ──
    "accelera":          "Accelera",

    # ── Gripmax ──
    "gripmax":           "Gripmax",

    # ── Milestone ──
    "milestone":         "Milestone",

    # ── Minerva ──
    "minerva":           "Minerva",

    # ── Windforce ──
    "windforce":         "Windforce",

    # ── Wintech ──
    "wintech":           "Wintech",

    # ── Doublestar ──
    "doublestar":        "Doublestar",

    # ── Comforser ──
    "comforser":         "Comforser",

    # ── Laufenn ──
    "laufenn":           "Laufenn",

    # ── Zeetex ──
    "zeetex":            "Zeetex",

    # ── Mazzini ──
    "mazzini":           "Mazzini",

    # ── Torque ──
    "torque":            "Torque",

    # ── Haida ──
    "haida":             "Haida",

    # ── Austone ──
    "austone":           "Austone",

    # ── Aplus ──
    "aplus":             "Aplus",

    # ── Cachland ──
    "cachland":          "Cachland",
}

def _normalize_marka(marka: str) -> str:
    """Toptancıların marka varyantlarını tek bir görünen ada dönüştürür."""
    if not marka:
        return marka
    temiz = " ".join(unicodedata.normalize("NFKC", marka).split())
    anahtar = temiz.casefold().replace("i\u0307", "i")
    eslesme = MARKA_ESLESME.get(anahtar) or MARKA_ESLESME.get(anahtar.replace("ı", "i"))
    if eslesme:
        return eslesme
    return " ".join(w.capitalize() for w in temiz.split())


# Toptancı B2B portal linkleri ve logo bilgileri
B2B_LINKLER = {
    "USPA Lastik":   {"url": "https://www.uspalastik.com",  "logo": "toptancilar/uspa1.png"},
    "Keskin Lastik": {"url": "https://keskinlastik.com",    "logo": "toptancilar/keskin0.png"},
    "OtoSemih":      {"url": "https://www.otosemih.com.tr", "logo": "toptancilar/otosemih.png"},
    "NetLastik":     {"url": "https://www.netlastik.com",   "logo": "toptancilar/eksililogo.avif"},
    "Lastsis":       {"url": "https://panel.lastsis.com",   "logo": "toptancilar/yocar0.png"},
    "Dinçbay":       {"url": "http://95.13.23.154:9015",    "logo": "toptancilar/dincbaylogo.png"},
    "Degeras":       {"url": "https://netclick-apis.degeras.com", "logo": "toptancilar/degeras.png.png"},
    "Art4":          {"url": "https://xml1.xmlbankasi.com",  "logo": "toptancilar/art4.png"},
    "Simetri":       {"url": "https://xml.continentaldas.com", "logo": "toptancilar/simetri.png"},
    "Yılkarlas":     {"url": "https://connect.b2bstore.com",   "logo": "toptancilar/yilkarlas.jpeg"},
    "Oltay":         {"url": "https://www.oltaylastik.com",    "logo": "toptancilar/oltayfoto.jpg"},
    "AS Oto":        {"url": "https://asotolastik.com",        "logo": "toptancilar/asoto.jpg"},
    "Karaoğlu":      {"url": "https://www.b2bkaraoglulastik.com", "logo": "toptancilar/karaoglu-logo.png"},
    "Çakıroğlu":     {"url": "https://next.paflima.com",         "logo": "toptancilar/cakiroglu.png"},
    "Ayko":          {"url": "https://next.paflima.com",         "logo": "toptancilar/ayko.png"},
    "Halil Yılmaz":  {"url": "https://next.paflima.com",         "logo": "toptancilar/halilyilmaz.svg"},
    "Mollaoğlu":     {"url": "https://bayi.mollaoglu.com.tr",     "logo": "toptancilar/mollaoglu.png"},
}


def _toptanci_yanitlari(ebat, marka, mevsim):
    """Tamamlanan her kaynak için (ürünler, hata adı, tamamlanan, toplam) üret."""
    GOREVLER = [
        uspa_ara,
        keskin_ara,
        otosemih_ara,
        netlastik_ara,
        lastsis_ara,
        dincbay_ara,
        degeras_ara,
        art4_ara,
        simetri_ara,
        yilkarlas_ara,
        oltay_ara,
        asoto_ara,
        karaoglu_ara,
        cakiroglu_ara,
        ayko_ara,
        halilyilmaz_ara,
        mollaoglu_ara,
    ]

    # Modül adı → görünen toptancı adı
    MODUL_ISIM = {
        "karsilastirma.uspa_servis":       "USPA Lastik",
        "karsilastirma.keskin_servis":     "Keskin Lastik",
        "karsilastirma.otosemih_servis":   "OtoSemih",
        "karsilastirma.netlastik_servis":  "NetLastik",
        "karsilastirma.lastsis_servis":    "Lastsis",
        "karsilastirma.dincbay_servis":    "Dinçbay",
        "karsilastirma.degeras_servis":    "Degeras",
        "karsilastirma.art4_servis":       "Art4",
        "karsilastirma.simetri_servis":    "Simetri",
        "karsilastirma.yilkarlas_servis":  "Yılkarlas",
        "karsilastirma.oltay_servis":      "Oltay",
        "karsilastirma.asoto_servis":      "AS Oto",
        "karsilastirma.karaoglu_servis":   "Karaoğlu",
        "karsilastirma.cakiroglu_servis":  "Çakıroğlu",
        "karsilastirma.ayko_servis":       "Ayko",
        "karsilastirma.halilyilmaz_servis": "Halil Yılmaz",
        "karsilastirma.mollaoglu_servis":   "Mollaoğlu",
    }

    # Yalnızca ham tedarikçi sonuçları ortaktır. İskontolar ve kullanıcı
    # filtreleri her istekte bu sonuçlardan ayrı uygulanır.
    query = json.dumps([ebat, marka, mevsim], ensure_ascii=False)
    key = "mesbul:ebat:v1:" + hashlib.sha256(query.encode()).hexdigest()
    kayit = cache.get(key)
    sonuclar = {} if kayit is None else kayit
    eksikler = [fn for fn in GOREVLER if fn.__module__ not in sonuclar]
    toplam = len(GOREVLER)
    tamamlanan = len(sonuclar)
    if tamamlanan:
        yield [u for grup in sonuclar.values() for u in grup], None, tamamlanan, toplam

    if eksikler:
        with ThreadPoolExecutor(max_workers=len(eksikler)) as executor:
            futures = {executor.submit(fn, ebat, marka, mevsim): fn.__module__ for fn in eksikler}
            for future in as_completed(futures):
                modul = futures[future]
                tamamlanan += 1
                try:
                    grup = future.result()
                except Exception as e:
                    isim = MODUL_ISIM.get(modul, modul)
                    print(f"[{isim}] Hata: {type(e).__name__}")
                    yield [], isim, tamamlanan, toplam
                else:
                    sonuclar[modul] = grup
                    yield grup, None, tamamlanan, toplam

        # Eksik kaynaklar sonraki aramada yeniden denenir. Tekrar denemeler
        # sırasında önceki fiyatların önbellek süresini uzatma.
        if kayit is None and sonuclar:
            cache.set(key, sonuclar, timeout=120)


def _onizleme_eslesir(urun, marka, mevsim, min_dot):
    if marka and marka not in (_normalize_marka(urun.marka) or "").casefold():
        return False
    if mevsim:
        ham = (urun.mevsim or "").casefold()
        if re.search(r"4|dört|all.?season", ham):
            sezon = "4 Mevsim"
        elif re.search(r"kış|kıs|kis|winter", ham):
            sezon = "Kış"
        elif re.search(r"yaz|summer", ham):
            sezon = "Yaz"
        else:
            sezon = ""
        if sezon != mevsim:
            return False
    yil = re.search(r"20[0-9]{2}", str(urun.dot))
    return not min_dot or not yil or yil.group() >= min_dot


def _arama_akisi(request, sorgu):
    ebat, marka, mevsim, min_dot = sorgu
    marka = _normalize_marka(marka).casefold() if marka else ""
    demo = not request.user.is_staff and request.user.abonelik.plan == "demo"
    kullanici_id = request.user.pk

    def satir(veri):
        return json.dumps(veri, ensure_ascii=False) + "\n"

    def akit():
        yield satir({"basladi": True})
        urunler, hatalar, en_ucuzlar = [], [], []
        for grup, hata, biten, toplam in _toptanci_yanitlari(ebat, "", ""):
            urunler.extend(grup)
            if hata:
                hatalar.append(hata)
            en_ucuzlar.extend(u for u in grup if _onizleme_eslesir(u, marka, mevsim, min_dot))
            en_ucuzlar = sorted(en_ucuzlar, key=lambda u: u.fiyat)[:5]
            yield satir({"biten": biten, "toplam": toplam, "urunler": [
                {"model": u.urun_adi, "marka": _normalize_marka(u.marka),
                 "fiyat": u.fiyat, "toptanci": "" if demo else u.toptanci}
                for u in en_ucuzlar
            ]})

        # Son sayfa farklı bir web worker'a düşse de aynı aramayı kullanır.
        anahtar = uuid4().hex
        mesbul_cache.set(f"arama-teslim:{kullanici_id}:{anahtar}", (sorgu, urunler, hatalar), 120)
        yield satir({"hazir": anahtar})

    response = StreamingHttpResponse(akit(), content_type="application/x-ndjson")
    response["X-Accel-Buffering"] = "no"
    response["Cache-Control"] = "no-store, no-transform"
    return response


def _dot_yillari(secili=""):
    yil = timezone.localdate().year
    yillar = set(range(yil - 4, yil + 1))
    if re.fullmatch(r"20[0-9]{2}", secili):
        yillar.add(int(secili))
    return sorted(yillar, reverse=True)


def _arama_baglam(request):
    ebatlar = AramaGecmisi.objects.filter(kullanici=request.user).values_list("ebat", flat=True)[:32]
    return {
        "gecmis": list(dict.fromkeys(ebatlar))[:8],
        "markalar": sorted(set(MARKA_ESLESME.values())),
        "dot_yillari": _dot_yillari(),
        "b2b_linkler": B2B_LINKLER,
        "demo_mod": (
            not request.user.is_staff
            and hasattr(request.user, "abonelik")
            and request.user.abonelik.plan == "demo"
        ),
    }


class AramaView(AbonelikGerekli, View):
    template_name = "karsilastirma/arama.html"

    def get(self, request):
        return render(request, self.template_name, _arama_baglam(request))


class SonuclarView(AbonelikGerekli, View):
    template_name = "karsilastirma/sonuclar.html"

    def get(self, request):
        return redirect("mesbul:index")

    def post(self, request):
        ebat    = request.POST.get("ebat",    "").strip()
        marka   = request.POST.get("marka",   "").strip()
        mevsim  = request.POST.get("mevsim",  "").strip()
        min_dot = request.POST.get("min_dot", "").strip()

        if not ebat:
            return render(request, AramaView.template_name, {
                **_arama_baglam(request),
                "hata": "Lütfen lastik ebatını girin.",
            })

        sorgu = (ebat, marka, mevsim, min_dot)
        if request.headers.get("Accept") == "application/x-ndjson":
            return _arama_akisi(request, sorgu)
        return self._sonuc_sayfasi(request, sorgu)

    @method_decorator(gzip_page)
    def _sonuc_sayfasi(self, request, sorgu):
        ebat, marka, mevsim, min_dot = sorgu
        anahtar = request.POST.get("arama_teslim", "")
        teslim = None
        if re.fullmatch(r"[0-9a-f]{32}", anahtar):
            teslim = mesbul_cache.get(f"arama-teslim:{request.user.pk}:{anahtar}")
        if teslim and teslim[0] == sorgu:
            _, sonuclar, hatali_toptancilar = teslim
        else:
            sonuclar, hatali_toptancilar = [], []
            for grup, hata, _, _ in _toptanci_yanitlari(ebat, "", ""):
                sonuclar.extend(grup)
                if hata:
                    hatali_toptancilar.append(hata)
        sonuclar.sort(key=lambda u: u.fiyat)

        # Marka adlarını normalize et (CONTINENTAL, Continenta → Continental)
        for u in sonuclar:
            u.marka = _normalize_marka(u.marka)

        # Marka filtresi (case-insensitive)
        if marka:
            marka_lower = _normalize_marka(marka).casefold()
            sonuclar = [u for u in sonuclar if marka_lower in (u.marka or "").casefold()]

        AramaGecmisi.objects.create(
            kullanici=request.user if request.user.is_authenticated else None,
            ebat=ebat,
            marka=marka,
            mevsim=mevsim,
            sonuc_sayisi=len(sonuclar),
        )

        en_ucuz_fiyat = sonuclar[0].fiyat if sonuclar else None

        toptanci_sayilari = dict(Counter(s.toptanci for s in sonuclar))

        # Marka listesi: normalize edilmiş, case-insensitive unique, sıralı
        # lower() → canonical form dict ile duplicate'ları kesin engelle
        _marka_dict: dict[str, str] = {}
        for s in sonuclar:
            if s.marka and s.marka not in ("—", "Diğer", "Diger", ""):
                key = s.marka.lower().strip()
                if key not in _marka_dict:
                    _marka_dict[key] = s.marka
        marka_listesi = sorted(_marka_dict.values())

        # İskonto bilgilerini dict olarak hazırla: {toptanci_adi: iskonto_metni}
        iskontolar = {
            i.toptanci_adi: i.iskonto_metni
            for i in ToptanciIskonto.objects.filter(kullanici=request.user)
            if i.iskonto_metni
        }

        return render(request, self.template_name, {
            "sonuclar":           sonuclar,
            "ebat":               ebat,
            "marka":              marka,
            "mevsim":             mevsim,
            "min_dot":            min_dot,
            "dot_yillari":        _dot_yillari(min_dot),
            "en_ucuz_fiyat":      en_ucuz_fiyat,
            "sonuc_sayisi":       len(sonuclar),
            "toptanci_sayilari":  toptanci_sayilari,
            "marka_listesi":      marka_listesi,
            "b2b_linkler":        B2B_LINKLER,
            "hatali_toptancilar": hatali_toptancilar,
            "iskontolar":         iskontolar,
            "demo_mod":           (
                hasattr(request.user, 'abonelik') and
                request.user.abonelik.plan == "demo"
            ) if not request.user.is_staff else False,
        })


@method_decorator(staff_member_required(login_url=settings.LOGIN_URL), name='dispatch')
class KullaniciEkleView(View):
    """Yeni kullanıcı oluştur + abonelik ata. Sadece staff."""

    def post(self, request):
        from .models import Abonelik
        from datetime import date

        username = request.POST.get("username", "").strip()
        email    = request.POST.get("email", "").strip()
        sifre    = request.POST.get("sifre", "").strip()
        plan     = request.POST.get("plan", "demo")
        bitis    = request.POST.get("bitis", "")

        hata = None

        if not username or not sifre or not bitis:
            hata = "Kullanıcı adı, şifre ve bitiş tarihi zorunludur."
        elif User.objects.filter(username=username).exists():
            hata = f'"{username}" kullanıcı adı zaten kullanımda.'
        else:
            try:
                bitis_tarihi = date.fromisoformat(bitis)
            except ValueError:
                hata = "Geçersiz tarih formatı."

        if hata:
            kullanicilar = User.objects.filter(is_staff=False).prefetch_related('abonelik').order_by('username')
            from django.utils import timezone
            return render(request, "karsilastirma/abonelik_yonetim.html", {
                "kullanicilar": kullanicilar,
                "bugun":        timezone.localdate(),
                "form_hata":    hata,
                "form_data":    request.POST,
            })

        yeni = User.objects.create_user(username=username, email=email, password=sifre)
        Abonelik.objects.create(kullanici=yeni, plan=plan, bitis=bitis_tarihi, aktif=True)
        return redirect('mesbul:abonelik_yonetim')


@method_decorator(staff_member_required(login_url=settings.LOGIN_URL), name='dispatch')
class OdemeEkleView(View):
    """Admin tarafından kullanıcıya ödeme kaydı ekler."""

    def post(self, request):
        from datetime import date
        kullanici_id = request.POST.get("kullanici_id")
        tutar        = request.POST.get("tutar", "").strip()
        tarih        = request.POST.get("tarih", "").strip()
        yontem       = request.POST.get("yontem", "havale")
        aciklama     = request.POST.get("aciklama", "").strip()

        kullanici = get_object_or_404(User, pk=kullanici_id, is_staff=False)

        try:
            tutar_dec   = float(tutar.replace(",", "."))
            tarih_obj   = date.fromisoformat(tarih)
        except (ValueError, TypeError):
            return redirect('mesbul:abonelik_yonetim')

        Odeme.objects.create(
            kullanici = kullanici,
            tutar     = tutar_dec,
            tarih     = tarih_obj,
            yontem    = yontem,
            aciklama  = aciklama,
        )
        return redirect('mesbul:abonelik_yonetim')


class OdemeGecmisiView(AbonelikGerekli, View):
    """Kullanıcının kendi ödeme geçmişini görür."""
    template_name = "karsilastirma/odeme_gecmisi.html"

    def get(self, request):
        odemeler = Odeme.objects.filter(kullanici=request.user).order_by("-tarih")
        toplam   = sum(o.tutar for o in odemeler)
        return render(request, self.template_name, {
            "odemeler": odemeler,
            "toplam":   toplam,
        })


@method_decorator(login_required(login_url=settings.LOGIN_URL), name='dispatch')
class IskontoYonetimView(View):
    """Her kullanıcı kendi iskonto bilgilerini AJAX ile kaydeder/listeler."""

    def get(self, request):
        iskontolar = list(
            ToptanciIskonto.objects.filter(kullanici=request.user)
            .values('toptanci_adi', 'iskonto_metni')
        )
        return JsonResponse({"iskontolar": iskontolar})

    def post(self, request):
        try:
            body = json.loads(request.body)
        except (ValueError, json.JSONDecodeError):
            return JsonResponse({"hata": "Geçersiz istek"}, status=400)

        toptanci_adi   = body.get("toptanci_adi", "").strip()
        iskonto_metni  = body.get("iskonto_metni", "").strip()

        if not toptanci_adi:
            return JsonResponse({"hata": "Toptancı adı zorunlu"}, status=400)

        obj, _ = ToptanciIskonto.objects.update_or_create(
            kullanici=request.user,
            toptanci_adi=toptanci_adi,
            defaults={"iskonto_metni": iskonto_metni},
        )
        return JsonResponse({"ok": True, "toptanci_adi": obj.toptanci_adi})


class UyelikTalepView(View):
    """Üyelik talep formunu işler, siteye mail gönderir."""

    def post(self, request):
        import json as _json
        from django.core.mail import send_mail
        from django.conf import settings as conf

        try:
            body = _json.loads(request.body)
        except (ValueError, _json.JSONDecodeError):
            return JsonResponse({"hata": "Geçersiz istek"}, status=400)

        ad_soyad = body.get("ad_soyad", "").strip()
        telefon  = body.get("telefon",  "").strip()
        email    = body.get("email",    "").strip()
        plan     = body.get("plan",     "").strip()
        mesaj    = body.get("mesaj",    "").strip()

        if not ad_soyad or not telefon:
            return JsonResponse({"hata": "Ad soyad ve telefon zorunludur"}, status=400)
        if not email:
            return JsonResponse({"hata": "E-posta zorunludur"}, status=400)

        plan_label = {
            "aylik":  "Aylık — 1.000 ₺/ay (KDV hariç)",
            "yillik": "Yıllık — 10.000 ₺/yıl (KDV hariç, 2 ay bedava)",
            "demo":   "Demo",
        }.get(plan, plan)

        konu = f"[MesBul] Yeni Üyelik Talebi — {ad_soyad} ({plan_label})"
        icerik = (
            f"Yeni üyelik talebi geldi:\n\n"
            f"Ad Soyad : {ad_soyad}\n"
            f"Telefon  : {telefon}\n"
            f"E-posta  : {email or '—'}\n"
            f"Plan     : {plan_label}\n"
            f"Mesaj    : {mesaj or '—'}\n"
        )

        alici = getattr(conf, 'ILETISIM_ALICI_EMAIL', '') or conf.EMAIL_HOST_USER
        try:
            from django.core.mail import EmailMessage
            msg = EmailMessage(
                subject=konu,
                body=icerik,
                from_email=conf.DEFAULT_FROM_EMAIL,
                to=[alici],
                reply_to=[email],   # "Yanıtla" tuşu müşteriye gider
            )
            msg.send(fail_silently=False)
        except Exception as e:
            print(f"[UyelikTalep] Mail gönderilemedi: {e}")
            return JsonResponse({"hata": "Mail gönderilemedi, lütfen tekrar deneyin."}, status=500)

        return JsonResponse({"ok": True})


@method_decorator(staff_member_required(login_url=settings.LOGIN_URL), name='dispatch')
class AbonelikYonetimView(View):
    """Sadece staff kullanıcılar erişebilir. Tüm kullanıcıları ve abonelik durumlarını listeler."""
    template_name = "karsilastirma/abonelik_yonetim.html"

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        from .models import Abonelik

        bugun = timezone.localdate()
        hafta_sonu = bugun + timedelta(days=7)

        kullanicilar = User.objects.filter(is_staff=False).prefetch_related('abonelik').order_by('username')

        aktif_sayisi = sum(1 for u in kullanicilar if hasattr(u, 'abonelik') and u.abonelik.erisim_var_mi)
        bu_hafta_biten = Abonelik.objects.filter(bitis__gte=bugun, bitis__lte=hafta_sonu, aktif=True).count()

        return render(request, self.template_name, {
            "kullanicilar":    kullanicilar,
            "bugun":           bugun,
            "aktif_sayisi":    aktif_sayisi,
            "bu_hafta_biten":  bu_hafta_biten,
        })


@method_decorator(staff_member_required(login_url=settings.LOGIN_URL), name='dispatch')
class AbonelikKaydetView(View):
    """Yeni abonelik ekle veya mevcut aboneliği güncelle."""

    def post(self, request, kullanici_id):
        from datetime import date
        from .models import Abonelik

        kullanici = get_object_or_404(User, pk=kullanici_id, is_staff=False)

        plan    = request.POST.get("plan", "demo")
        bitis   = request.POST.get("bitis", "")
        aktif   = request.POST.get("aktif") == "on"

        if not bitis:
            return redirect('mesbul:abonelik_yonetim')

        try:
            bitis_tarihi = date.fromisoformat(bitis)
        except ValueError:
            return redirect('mesbul:abonelik_yonetim')

        Abonelik.objects.update_or_create(
            kullanici=kullanici,
            defaults={
                "plan":   plan,
                "bitis":  bitis_tarihi,
                "aktif":  aktif,
            }
        )
        return redirect('mesbul:abonelik_yonetim')


# ── Not Yönetimi ─────────────────────────────────────────────────────────────

class NotlarView(LoginRequiredMixin, View):
    """Kullanıcının notlarını JSON olarak döner (AJAX)."""
    login_url = settings.LOGIN_URL

    def get(self, request):
        # Süresi dolmuş notları sil
        Notlar.objects.filter(kullanici=request.user, silinme__lt=timezone.now()).delete()

        notlar = Notlar.objects.filter(kullanici=request.user)
        data = [
            {
                "id":         n.pk,
                "ebat":       n.ebat,
                "marka":      n.marka,
                "musteri":    n.musteri,
                "icerik":     n.icerik,
                "tarih":      n.olusturulma.strftime("%d.%m.%Y %H:%M"),
                "kalan_gun":  n.kalan_gun,
            }
            for n in notlar
        ]
        return JsonResponse({"notlar": data})


class NotEkleView(LoginRequiredMixin, View):
    """Yeni not ekle (AJAX POST)."""
    login_url = settings.LOGIN_URL

    def post(self, request):
        try:
            body  = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"hata": "Geçersiz istek"}, status=400)

        icerik  = body.get("icerik",   "").strip()
        ebat    = body.get("ebat",     "").strip()
        marka   = body.get("marka",    "").strip()
        musteri = body.get("musteri",  "").strip()

        if not icerik:
            return JsonResponse({"hata": "Not boş olamaz"}, status=400)

        # Süresi dolmuş notları temizle
        Notlar.objects.filter(kullanici=request.user, silinme__lt=timezone.now()).delete()

        not_obj = Notlar.objects.create(
            kullanici=request.user,
            ebat=ebat,
            marka=marka,
            musteri=musteri,
            icerik=icerik,
        )
        return JsonResponse({
            "id":         not_obj.pk,
            "ebat":       not_obj.ebat,
            "marka":      not_obj.marka,
            "musteri":    not_obj.musteri,
            "icerik":     not_obj.icerik,
            "tarih":      not_obj.olusturulma.strftime("%d.%m.%Y %H:%M"),
            "kalan_gun":  not_obj.kalan_gun,
        }, status=201)


class NotSilView(LoginRequiredMixin, View):
    """Notu sil (AJAX DELETE)."""
    login_url = settings.LOGIN_URL

    def delete(self, request, not_id):
        not_obj = get_object_or_404(Notlar, pk=not_id, kullanici=request.user)
        not_obj.delete()
        return JsonResponse({"ok": True})
