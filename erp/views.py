"""
ERP görünüm katmanı — Cari, Stok, Depo listeleri ve DİA Sync durumu.
"""

from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import CharField, OuterRef, Q, Subquery
from django.db.models.functions import Cast
from django.forms import DecimalField
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from dia_integration.models import ApiIstekLog, SyncLog, SyncDurum
from erp.models import Cari, CariTip, Depo, StokKart, DepoFisi, DepoFisiKalemi, Fatura, FaturaKalemi, FaturaTur


# ─────────────────────────────────────────────────────────────
# Sync Durumu
# ─────────────────────────────────────────────────────────────

@login_required
def dia_durum(request):
    """DİA bağlantı durumu ve son sync özetleri."""
    from dia_integration.models import DiaBaglanti

    baglanti = DiaBaglanti.objects.filter(is_aktif=True).first()
    son_sync_loglar = SyncLog.objects.order_by('-baslangic')[:10]

    son_syncler = {
        'Son DİA Rapor Aktarımı': SyncLog.objects.filter(modul='mes_rapor').order_by('-baslangic').first(),
    }

    # İstatistikler
    istatistik = {
        'cari_sayisi': Cari.objects.count(),
        'stok_sayisi': StokKart.objects.count(),
        'depo_sayisi': Depo.objects.count(),
        'fatura_sayisi': Fatura.objects.count(),
        'fatura_kalem_sayisi': FaturaKalemi.objects.count(),
        'basarili_sync': SyncLog.objects.filter(durum=SyncDurum.BASARILI).count(),
        'hatali_sync': SyncLog.objects.filter(durum=SyncDurum.BASARISIZ).count(),
        'son_api_cagri': ApiIstekLog.objects.order_by('-istek_zamani').first(),
        'bugun_api_cagri': ApiIstekLog.objects.filter(
            istek_zamani__date=__import__('datetime').date.today()
        ).count(),
    }

    return render(request, 'erp/dia_durum.html', {
        'baglanti': baglanti,
        'son_sync_loglar': son_sync_loglar,
        'son_syncler': son_syncler,
        'istatistik': istatistik,
        'aktif_sayfa': 'dia_durum',
    })


@login_required
@require_POST
def sync_baslat(request):
    """
    Sync görevi başlat.
    Celery worker varsa kuyruğa gönderir, yoksa senkron çalıştırır.
    """
    modul = request.POST.get('modul', '')
    tam = request.POST.get('tam', 'false') == 'true'
    rapor = request.POST.get('rapor', 'false') == 'true'

    if rapor and modul != 'cari':
        return JsonResponse({'basarili': False, 'hata': 'Rapor sync şu an yalnızca cari kartları için kullanılabilir.'})
    if rapor and not getattr(settings, 'DIA_CARI_KART_RAPOR_TASARIM_KEY', ''):
        return JsonResponse({
            'basarili': False,
            'hata': (
                'Cari Kart Listesi (scf1100c) rapor tasarım anahtarı ayarlı değil. '
                'DIA_CARI_KART_RAPOR_TASARIM_KEY değerini .env dosyasına ekleyip uygulamayı yeniden başlatın.'
            ),
        })

    try:
        if modul == 'mes_rapor':
            from dia_integration.services.mes_rapor_sync import mes_rapor_senkronize_et

            sayilar = mes_rapor_senkronize_et(request.user)
            ozet = ', '.join(f'{sayi} {ad}' for ad, sayi in sayilar.items())
            return JsonResponse({
                'basarili': True, 'mesaj': f'DİA raporu aktarıldı: {ozet}.', 'mod': 'senkron',
            })

        # Celery worker'ın erişilebilir olup olmadığını kontrol et
        from metis_admin.celery import app as celery_app

        try:
            inspector = celery_app.control.inspect(timeout=1.0)
            aktif_workerlar = inspector.active()
            worker_var = bool(aktif_workerlar)
        except Exception:
            worker_var = False

        if worker_var:
            # Celery worker varsa kuyruğa gönder
            if modul == 'cari' and rapor:
                from dia_integration.tasks import sync_cari_rapor_listesi
                task = sync_cari_rapor_listesi.delay()
            elif modul == 'cari':
                from dia_integration.tasks import sync_cari_listesi
                task = sync_cari_listesi.delay(delta=not tam)
            elif modul == 'stok':
                from dia_integration.tasks import sync_stok_listesi
                task = sync_stok_listesi.delay(delta=not tam)
            elif modul == 'firma_donem':
                from dia_integration.tasks import sync_firma_donem
                task = sync_firma_donem.delay()
            elif modul == 'stok_depo_miktar':
                from dia_integration.tasks import sync_stok_depo_miktarlari
                task = sync_stok_depo_miktarlari.delay()
            elif modul == 'fatura':
                from dia_integration.tasks import sync_fatura_listesi
                task = sync_fatura_listesi.delay(delta=not tam, kalem_cek=True)
            else:
                return JsonResponse({'basarili': False, 'hata': f'Bilinmeyen modül: {modul}'})

            return JsonResponse({
                'basarili': True,
                'task_id': task.id,
                'mesaj': f'{modul} sync görevi Celery kuyruğuna gönderildi.',
                'mod': 'celery',
            })
        else:
            # Worker yoksa direkt çalıştır
            if modul == 'cari' and rapor:
                from dia_integration.services import CariService
                from dia_integration.models import SyncTetikleyen
                sonuc = CariService.rapordan_senkronize_et(
                    tetikleyen=SyncTetikleyen.MANUEL,
                    kullanici=request.user,
                )
                mesaj = f'Cari rapor sync tamamlandı: {sonuc.eklenen} eklendi, {sonuc.guncellenen} güncellendi.'
            elif modul == 'cari':
                from dia_integration.services import CariService
                from dia_integration.models import SyncTetikleyen
                sonuc = CariService.dia_dan_senkronize_et(delta=not tam, tetikleyen=SyncTetikleyen.MANUEL)
                mesaj = f'Cari sync tamamlandı: {sonuc.eklenen} eklendi, {sonuc.guncellenen} güncellendi.'
            elif modul == 'stok':
                from dia_integration.services import StokService
                from dia_integration.models import SyncTetikleyen
                sonuc = StokService.dia_dan_senkronize_et(delta=not tam, tetikleyen=SyncTetikleyen.MANUEL)
                mesaj = f'Stok sync tamamlandı: {sonuc.eklenen} eklendi, {sonuc.guncellenen} güncellendi.'
            elif modul == 'firma_donem':
                from dia_integration.services import StokService
                n = StokService.depolari_senkronize_et()
                mesaj = f'Firma/dönem sync tamamlandı: {n} depo güncellendi.'
            elif modul == 'stok_depo_miktar':
                from dia_integration.services import StokService
                n = StokService.depo_miktarlarini_guncelle()
                mesaj = f'Stok depo miktarları tamamlandı: {n} kayıt güncellendi.'
            elif modul == 'fatura':
                from dia_integration.services import FaturaService
                from dia_integration.models import SyncTetikleyen
                sonuc = FaturaService.dia_dan_senkronize_et(
                    delta=not tam,
                    kalem_cek=True,
                    tetikleyen=SyncTetikleyen.MANUEL,
                    kullanici=request.user,
                )
                mesaj = f'Fatura sync tamamlandı: {sonuc.eklenen} eklendi, {sonuc.guncellenen} güncellendi.'
            else:
                return JsonResponse({'basarili': False, 'hata': f'Bilinmeyen modül: {modul}'})

            return JsonResponse({
                'basarili': True,
                'mesaj': mesaj,
                'mod': 'senkron',
            })

    except Exception as exc:
        return JsonResponse({'basarili': False, 'hata': str(exc)})


# ─────────────────────────────────────────────────────────────
# Cari
# ─────────────────────────────────────────────────────────────

@login_required
@require_GET
def cari_ara_ajax(request):
    """Depo fişi modalı için yerel DİA cari senkronizasyonunda ünvan arar."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'sonuclar': []})

    cariler = Cari.objects.filter(durum='A').filter(
        Q(unvan__icontains=q) | Q(cari_kodu__icontains=q)
    ).order_by('unvan')[:20]
    return JsonResponse({
        'sonuclar': [
            {'unvan': cari.unvan, 'cari_kodu': cari.cari_kodu}
            for cari in cariler
        ]
    })

@login_required
def cari_listesi(request):
    """Cari kartı listesi — arama, filtre, sayfalama."""
    qs = Cari.objects.all().order_by('unvan')

    # Arama
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(cari_kodu__icontains=q) |
            Q(unvan__icontains=q) |
            Q(vergi_no__icontains=q) |
            Q(telefon1__icontains=q) |
            Q(eposta__icontains=q)
        )

    # Filtreler
    tip = request.GET.get('tip', '')
    if tip:
        qs = qs.filter(tip=tip)

    durum = request.GET.get('durum', 'A')
    if durum:
        qs = qs.filter(durum=durum)

    sehir = request.GET.get('sehir', '')
    if sehir:
        qs = qs.filter(sehir__icontains=sehir)

    bakiyeye_gore = request.GET.get('sirala') == 'bakiye'
    if bakiyeye_gore:
        qs = qs.order_by('-bakiye', 'unvan', 'pk')

    # Sayfalama
    paginator = Paginator(qs, 25)
    sayfa = paginator.get_page(request.GET.get('sayfa', 1))

    # Seçenek listeleri
    sehirler = (
        Cari.objects.exclude(sehir='')
        .values_list('sehir', flat=True)
        .distinct()
        .order_by('sehir')[:50]
    )

    return render(request, 'erp/cari_listesi.html', {
        'bakiyeye_gore': bakiyeye_gore,
        'sayfa': sayfa,
        'q': q,
        'tip_secenekleri': CariTip.choices,
        'secili_tip': tip,
        'secili_durum': durum,
        'sehirler': sehirler,
        'secili_sehir': sehir,
        'toplam': qs.count(),
        'aktif_sayfa': 'cari_listesi',
    })


@login_required
def cari_detay(request, pk):
    """Cari detay görünümü."""
    cari = get_object_or_404(Cari, pk=pk)
    return render(request, 'erp/cari_detay.html', {
        'cari': cari,
        'aktif_sayfa': 'cari_listesi',
    })


def _ekstre_degeri(hareket, *alanlar, varsayilan='—'):
    for alan in alanlar:
        deger = hareket.get(alan)
        if isinstance(deger, str):
            deger = deger.strip()
        if deger is not None and deger != '':
            return deger
    return varsayilan


@login_required
def cari_ekstre(request, pk):
    """Seçilen cari için DİA cari hesap hareketlerini canlı olarak gösterir."""
    cari = get_object_or_404(Cari, pk=pk)
    baslangic_str = request.GET.get('baslangic', '').strip()
    bitis_str = request.GET.get('bitis', '').strip()
    getir = request.GET.get('getir') == '1'
    rapor_pdf = request.GET.get('rapor_pdf') == '1'
    hareketler = []
    hata = ''
    borc_toplam = Decimal('0')
    alacak_toplam = Decimal('0')

    try:
        baslangic = datetime.date.fromisoformat(baslangic_str) if baslangic_str else None
        bitis = datetime.date.fromisoformat(bitis_str) if bitis_str else None
        if baslangic and bitis and baslangic > bitis:
            raise ValueError('Başlangıç tarihi bitiş tarihinden sonra olamaz.')

        if rapor_pdf:
            if not baslangic:
                baslangic = datetime.date(datetime.date.today().year, 1, 1)
            if not bitis:
                bitis = datetime.date.today()
            from dia_integration.services.cari_hareket_service import cari_ekstre_pdf_al
            rapor = cari_ekstre_pdf_al(cari, baslangic=baslangic, bitis=bitis)
            response = HttpResponse(rapor.icerik, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="cari-ekstre-{cari.pk}-{baslangic.isoformat()}-{bitis.isoformat()}.pdf"'
            )
            return response

        if getir:
            if cari.rapor_ekstresi is None:
                from dia_integration.services.cari_hareket_service import cari_hareketlerini_getir
                hareketler = cari_hareketlerini_getir(cari, baslangic=baslangic, bitis=bitis)
            else:
                ilk = baslangic.isoformat() if baslangic else ''
                son = bitis.isoformat() if bitis else '9999-12-31'
                hareketler = sorted(
                    (h for h in cari.rapor_ekstresi if ilk <= h['tarih'] <= son),
                    key=lambda h: (h['tarih'], h.get('saat') or ''), reverse=True,
                )
            satirlar = []
            for hareket in hareketler:
                satir = {
                    'tarih': hareket.get('tarih'),
                    'saat': hareket.get('saat'),
                    'tur': _ekstre_degeri(hareket, 'turu_txt', 'turu', 'tip'),
                    'belge': _ekstre_degeri(hareket, 'belgeno', 'fisno'),
                    'aciklama': _ekstre_degeri(hareket, 'aciklama', 'satiraciklamasi', 'bilgi'),
                }
                for ad, alanlar in (
                    ('borc', ('yerelborc', 'borc_yerelborc', 'borc')),
                    ('alacak', ('yerelalacak', 'alacak_yerelalacak', 'alacak')),
                    ('bakiye', ('yerelborcalacakbakiye', 'borcalacakbakiye')),
                ):
                    deger = _ekstre_degeri(hareket, *alanlar, varsayilan=0)
                    try:
                        satir[ad] = Decimal(str(deger).replace(',', '.'))
                    except InvalidOperation:
                        satir[ad] = Decimal('0')
                borc_toplam += satir['borc']
                alacak_toplam += satir['alacak']
                satirlar.append(satir)
            hareketler = satirlar
    except (ValueError, InvalidOperation) as exc:
        hata = str(exc)
    except Exception as exc:
        hata = f'DİA cari ekstresi alınamadı: {exc}'

    return render(request, 'erp/cari_ekstre.html', {
        'cari': cari,
        'hareketler': hareketler,
        'rapordan': cari.rapor_ekstresi is not None,
        'baslangic': baslangic_str,
        'bitis': bitis_str,
        'getirildi': getir and not hata,
        'hata': hata,
        'borc_toplam': borc_toplam,
        'alacak_toplam': alacak_toplam,
        'aktif_sayfa': 'cari_listesi',
    })


# ─────────────────────────────────────────────────────────────
# Stok
# ─────────────────────────────────────────────────────────────

@login_required
def stok_listesi(request):
    """Stok kartı listesi — arama, filtre, sayfalama."""
    qs = StokKart.objects.all()

    # Sıralama
    SIRALAMA_MAP = {
        'uretici_kodu': 'uretici_kodu',
        '-uretici_kodu': '-uretici_kodu',
        'aciklama': 'aciklama',
        '-aciklama': '-aciklama',
        'marka': 'marka',
        '-marka': '-marka',
        'dot': 'ozel_kod1',
        '-dot': '-ozel_kod1',
        'mevsim': 'mevsim',
        '-mevsim': '-mevsim',
    }
    siralama = request.GET.get('siralama', '').strip()
    order_field = SIRALAMA_MAP.get(siralama, 'stok_kodu')
    qs = qs.order_by(order_field)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(stok_kodu__icontains=q) |
            Q(uretici_kodu__icontains=q) |
            Q(aciklama__icontains=q) |
            Q(ana_barkod__icontains=q) |
            Q(marka__icontains=q)
        )

    durum = request.GET.get('durum', 'A')
    if durum:
        qs = qs.filter(durum=durum)

    marka = request.GET.get('marka', '')
    if marka:
        qs = qs.filter(marka__icontains=marka)

    # Ürün türü sekmesi ile DİA araç segmenti (özel kod 2) ayrı kavramlardır.
    # Lastik sekmesi ozel_kod2='Lastik' diye filtrelenemez; bu alan
    # "Otomobil / SUV 4x4 / Hafif Ticari" gibi araç segmentlerini tutar.
    # Senkronize stok kartları mevcut durumda lastik kartları olduğundan
    # Lastik sekmesinde bu alanı filtre olarak kullanma.
    segment = request.GET.get('segment', '').strip()
    if segment and segment != 'Lastik':
        qs = qs.filter(ozel_kod2__iexact=segment)

    # Mevsim filtresi
    mevsim_f = request.GET.get('mevsim', '').strip()
    if mevsim_f:
        qs = qs.filter(mevsim__icontains=mevsim_f)

    # DOT filtresi (ozel_kod1)
    dot_f = request.GET.get('dot', '').strip()
    if dot_f:
        qs = qs.filter(ozel_kod1__icontains=dot_f)

    # Depo filtresi — depo_miktarlari üzerinden
    depo_f = request.GET.get('depo', '').strip()
    if depo_f:
        qs = qs.filter(depo_miktarlari__depo__pk=depo_f)

    # Stok var filtresi
    stok_var = request.GET.get('stok_var', '1').strip()
    if stok_var == '1':
        qs = qs.filter(gercek_stok__gt=0)

    # İkinci arama kutusu (q2) — ozel_kod2 / ozel_kod1 / mevsim üzerinden
    q2 = request.GET.get('q2', '').strip()
    if q2:
        qs = qs.filter(
            Q(ozel_kod1__icontains=q2) |
            Q(ozel_kod2__icontains=q2) |
            Q(mevsim__icontains=q2)
        )

    paginator = Paginator(qs, 25)
    sayfa = paginator.get_page(request.GET.get('sayfa', 1))

    markalar = (
        StokKart.objects.exclude(marka='')
        .values_list('marka', flat=True)
        .distinct()
        .order_by('marka')[:50]
    )

    return render(request, 'erp/stok_listesi.html', {
        'sayfa': sayfa,
        'q': q,
        'secili_durum': durum,
        'markalar': markalar,
        'secili_marka': marka,
        'toplam': qs.count(),
        'aktif_sayfa': 'stok_listesi',
        'segment': segment,
        'mevsim_f': mevsim_f,
        'dot_f': dot_f,
        'depo_f': depo_f,
        'stok_var': stok_var,
        'q2': q2,
        'siralama': siralama,
        'segmentler': StokKart.objects.exclude(ozel_kod2='').values_list('ozel_kod2', flat=True).distinct().order_by('ozel_kod2')[:30],
        'mevsimler': StokKart.objects.exclude(mevsim='').values_list('mevsim', flat=True).distinct().order_by('mevsim')[:20],
        'dot_listesi': StokKart.objects.exclude(ozel_kod1='').values_list('ozel_kod1', flat=True).distinct().order_by('ozel_kod1')[:50],
        'depolar': Depo.objects.filter(aktif=True).order_by('sube_adi', 'ad'),
    })


@login_required
def stok_detay(request, pk):
    """Stok kartı detay görünümü."""
    stok = get_object_or_404(StokKart, pk=pk)
    depo_miktarlari = stok.depo_miktarlari.select_related('depo').all()
    return render(request, 'erp/stok_detay.html', {
        'stok': stok,
        'depo_miktarlari': depo_miktarlari,
        'rapor_depo_miktarlari': stok.rapor_depo_miktarlari.select_related('depo'),
        'aktif_sayfa': 'stok_listesi',
    })


# ─────────────────────────────────────────────────────────────
# Depo
# ─────────────────────────────────────────────────────────────

@login_required
def depo_listesi(request):
    """Depo listesi."""
    depolar = Depo.objects.filter(aktif=True).order_by('sube_adi', 'ad')
    return render(request, 'erp/depo_listesi.html', {
        'depolar': depolar,
        'aktif_sayfa': 'depo_listesi',
    })


# ─────────────────────────────────────────────────────────────
# Sync Logları
# ─────────────────────────────────────────────────────────────

@login_required
def sync_loglar(request):
    """Senkronizasyon log listesi."""
    qs = SyncLog.objects.order_by('-baslangic')

    modul = request.GET.get('modul', '')
    if modul:
        qs = qs.filter(modul=modul)

    durum_filtre = request.GET.get('durum', '')
    if durum_filtre:
        qs = qs.filter(durum=durum_filtre)

    paginator = Paginator(qs, 30)
    sayfa = paginator.get_page(request.GET.get('sayfa', 1))

    return render(request, 'erp/sync_loglar.html', {
        'sayfa': sayfa,
        'secili_modul': modul,
        'secili_durum': durum_filtre,
        'durum_secenekleri': SyncDurum.choices,
        'modul_listesi': ['cari', 'stok', 'firma_donem', 'stok_depo_miktar', 'fatura', 'baglanti_testi'],
        'aktif_sayfa': 'sync_loglar',
    })


# ─────────────────────────────────────────────────────────────
# Depo Fişi
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def depo_fisi_istek(request, stok_pk):
    """
    Stok listesindeki araba ikonuna tıklandığında çağrılır.
    depo_fisi_id POST parametresi varsa o fişe kalem ekler,
    yoksa yeni bir DepoFisi + DepoFisiKalemi oluşturur.
    """
    stok = get_object_or_404(StokKart, pk=stok_pk)
    adet = max(1, int(request.POST.get('adet', 1)))
    fiyat_alani = DecimalField(min_value=Decimal('0'), max_digits=18, decimal_places=4, required=False)
    try:
        birim_fiyat = fiyat_alani.clean(request.POST.get('birim_fiyat'))
    except ValidationError:
        return JsonResponse({'basarili': False, 'hata': 'Geçerli bir birim fiyat girin. En fazla dört ondalık basamak kullanabilirsiniz.'}, status=400)
    cari_post = request.POST.get('cari', '').strip()
    cari = cari_post or request.user.get_full_name() or request.user.username
    aciklama_raw = request.POST.get('aciklama', '').strip()
    aciklama = aciklama_raw

    depo_fisi_id = request.POST.get('depo_fisi_id', '').strip()
    if depo_fisi_id:
        fis = get_object_or_404(DepoFisi, pk=int(depo_fisi_id))
        if fis.durum != 'bekliyor':
            return JsonResponse({'basarili': False, 'hata': 'Bu fiş artık aktif değil, yeni bir fiş açın.'}, status=400)
    else:
        if not Cari.objects.filter(unvan__iexact=cari, durum='A').exists():
            return JsonResponse({
                'basarili': False,
                'hata': 'Listeden aktif bir DİA cari kartı seçin.'
            }, status=400)
        fis = DepoFisi.objects.create(
            islem_yapan=request.user,
            depo=Depo.varsayilan_fatura_deposu(),
            cari=cari,
            plaka=request.POST.get('plaka', '').strip().upper(),
            arac_marka=request.POST.get('arac_marka', '').strip(),
            arac_model=request.POST.get('arac_model', '').strip(),
            aciklama=aciklama,
        )
    DepoFisiKalemi.objects.create(
        fis=fis, stok=stok, adet=adet,
        birim_fiyat=stok.fiyat1 if birim_fiyat is None else birim_fiyat,
    )
    return JsonResponse({
        'basarili': True,
        'fis_no': fis.fis_no,
        'depo_fisi_id': fis.pk,
        'cari': fis.cari,
        'stok_kodu': stok.stok_kodu,
        'aciklama': stok.aciklama,
        'mesaj': f'{stok.stok_kodu} fişe eklendi (Fiş #{fis.fis_no})',
    })


def _fatura_numarali_depo_fisleri():
    fatura = Fatura.objects.filter(
        dia_key=OuterRef('fatura_no'),
        belge_no=Cast(OuterRef('fis_no'), CharField()),
    ).exclude(dia_key='')
    return DepoFisi.objects.annotate(dia_fatura_no=Subquery(fatura.values('fis_no')[:1]))


@login_required
def depo_fisi_listesi(request):
    """Depo fişleri listesi."""
    # Filtreler
    baslangic_str = request.GET.get('baslangic', '')
    bitis_str     = request.GET.get('bitis', '')
    plaka         = request.GET.get('plaka', '').strip()
    cari_filtre   = request.GET.get('cari', '').strip()
    durum_filtre  = request.GET.get('durum', '')

    # Tarih filtresi sadece form gönderilirse uygula
    filtre_aktif = bool(baslangic_str or bitis_str or plaka or cari_filtre or durum_filtre)

    bugun = datetime.date.today()

    try:
        baslangic = datetime.date.fromisoformat(baslangic_str) if baslangic_str else bugun
    except ValueError:
        baslangic = bugun
    try:
        bitis = datetime.date.fromisoformat(bitis_str) if bitis_str else bugun
    except ValueError:
        bitis = bugun

    from django.db.models import Sum
    qs = (_fatura_numarali_depo_fisleri()
          .prefetch_related('kalemler__stok')
          .annotate(toplam_adet=Sum('kalemler__adet'))
          .order_by('-olusturuldu'))

    # Filtre uygulanmışsa tarihe göre daralt, uygulanmamışsa tümünü göster
    if baslangic_str or bitis_str:
        qs = qs.filter(tarih__gte=baslangic, tarih__lte=bitis)

    if plaka:
        qs = qs.filter(plaka__icontains=plaka)
    if cari_filtre:
        qs = qs.filter(cari__icontains=cari_filtre)
    if durum_filtre:
        qs = qs.filter(durum=durum_filtre)

    return render(request, 'erp/depo_fisi_listesi.html', {
        'fisler': qs,
        'baslangic': baslangic,
        'bitis': bitis,
        'plaka': plaka,
        'cari': cari_filtre,
        'durum_filtre': durum_filtre,
        'filtre_aktif': filtre_aktif,
        'aktif_sayfa': 'depo_fisi_listesi',
    })


@login_required
def depo_fisi_detay(request, pk):
    """
    Fiş detayı.
    GET  → görüntüle
    POST → plaka/cari/aciklama güncelle VEYA kalem adeti güncelle VEYA yazıldı işaretle
    """
    fis = get_object_or_404(_fatura_numarali_depo_fisleri(), pk=pk)
    kalemler = fis.kalemler.select_related('stok').all()

    if request.method == 'POST':
        islem = request.POST.get('islem', '')

        if islem == 'dia_fatura_gonder':
            if fis.fatura_no:
                messages.error(request, 'Bu fiş için DİA aktarım kaydı mevcut; yinelenen fatura oluşturmamak için tekrar gönderilmedi.')
            elif fis.durum != 'bekliyor':
                messages.error(request, 'Yalnızca bekleyen fişler DİA’ya gönderilebilir.')
            elif not fis.cari:
                messages.error(request, 'DİA faturası için fişte cari seçilmeli.')
            elif not kalemler.exists():
                messages.error(request, 'DİA faturası için fişte en az bir ürün olmalı.')
            else:
                try:
                    from dia_integration.services.depo_fisi_fatura_service import depo_fisini_dia_faturasi_yap
                    dia_ref = depo_fisini_dia_faturasi_yap(fis)
                    fis.fatura_no = dia_ref or f'ME-DEP-{fis.fis_no}'
                    fis.yazildi = True
                    fis.durum = 'onaylandi'
                    fis.islem_yapan = request.user
                    fis.save(update_fields=['depo', 'fatura_no', 'yazildi', 'durum', 'islem_yapan', 'guncellendi'])
                    messages.success(request, f'Fiş #{fis.fis_no} DİA’ya fatura olarak gönderildi. Fatura numarası rapor güncellendiğinde görünecek.')
                except Exception as exc:
                    messages.error(request, f'DİA’ya gönderilemedi: {exc}')
            return redirect('erp:depo_fisi_detay', pk=pk)

        # Fiş bilgilerini güncelle
        if islem == 'fis_guncelle':
            depo_id = request.POST.get('depo', '').strip()
            if depo_id and fis.durum == 'bekliyor' and not fis.fatura_no:
                depo = Depo.fatura_depolari().filter(pk=int(depo_id)).first() if depo_id.isascii() and depo_id.isdecimal() else None
                if depo is None:
                    messages.error(request, 'DİA şube anahtarı bulunan aktif bir depo seçin.')
                    return redirect('erp:depo_fisi_detay', pk=pk)
                fis.depo = depo
            fis.plaka      = request.POST.get('plaka', fis.plaka).strip().upper()
            fis.kilometre  = request.POST.get('kilometre') or None
            fis.arac_marka = request.POST.get('arac_marka', fis.arac_marka).strip()
            fis.arac_model = request.POST.get('arac_model', fis.arac_model).strip()
            fis.cari       = request.POST.get('cari', fis.cari).strip()
            fis.aciklama   = request.POST.get('aciklama', fis.aciklama).strip()
            fis.save(update_fields=['plaka', 'kilometre', 'arac_marka', 'arac_model', 'cari', 'aciklama', 'depo'])

        # Yazıldı işaretle (fatura kesildi)
        elif islem == 'yazildi_isle':
            fis.yazildi  = True
            fis.durum    = 'onaylandi'
            fis.islem_yapan = request.user
            fis.save(update_fields=['yazildi', 'durum', 'islem_yapan', 'guncellendi'])

        # Kalem adetini güncelle
        elif islem == 'kalem_adet':
            kalem_pk = request.POST.get('kalem_pk')
            yeni_adet = int(request.POST.get('adet', 1))
            if kalem_pk and yeni_adet > 0:
                DepoFisiKalemi.objects.filter(pk=kalem_pk, fis=fis).update(adet=yeni_adet)

        return redirect('erp:depo_fisi_detay', pk=pk)

    return render(request, 'erp/depo_fisi_detay.html', {
        'fis': fis,
        'kalemler': kalemler,
        'fatura_depolari': Depo.fatura_depolari() if fis.durum == 'bekliyor' and not fis.fatura_no else [],
        'aktif_sayfa': 'depo_fisi_listesi',
    })


@login_required
@require_POST
def depo_fisi_onayla(request, pk):
    """Fişi onayla."""
    from django.utils import timezone
    fis = get_object_or_404(DepoFisi, pk=pk)
    if fis.durum == 'bekliyor':
        fis.durum       = 'onaylandi'
        fis.yazildi     = True
        fis.onaylandi   = True
        fis.onay_veren  = request.user
        fis.onay_tarihi = timezone.now()
        fis.fatura_no   = request.POST.get('fatura_no', '').strip()
        fis.islem_yapan = request.user
        fis.save(update_fields=['durum', 'yazildi', 'onaylandi', 'onay_veren', 'onay_tarihi', 'fatura_no', 'islem_yapan'])
    return JsonResponse({'basarili': True, 'mesaj': f'Fiş #{fis.fis_no} onaylandı.'})


@login_required
@require_POST
def depo_fisi_iptal(request, pk):
    """Fişi iptal et."""
    fis = get_object_or_404(DepoFisi, pk=pk)
    fis.durum = 'iptal'
    fis.save(update_fields=['durum'])
    return JsonResponse({'basarili': True, 'mesaj': f'Fiş #{fis.fis_no} iptal edildi.'})


@login_required
@require_POST
def depo_fisi_guncelle(request, pk):
    """Fiş listesinden inline düzenleme — plaka, cari, açıklama."""
    fis = get_object_or_404(DepoFisi, pk=pk)
    if fis.durum == 'bekliyor':
        fis.plaka      = request.POST.get('plaka', fis.plaka).strip().upper()
        fis.kilometre  = request.POST.get('kilometre') or None
        fis.arac_marka = request.POST.get('arac_marka', fis.arac_marka).strip()
        fis.arac_model = request.POST.get('arac_model', fis.arac_model).strip()
        fis.cari       = request.POST.get('cari', fis.cari).strip()
        fis.aciklama   = request.POST.get('aciklama', fis.aciklama).strip()
        fis.save(update_fields=['plaka', 'kilometre', 'arac_marka', 'arac_model', 'cari', 'aciklama'])
        return JsonResponse({'basarili': True, 'mesaj': f'Fiş #{fis.fis_no} güncellendi.'})
    return JsonResponse({'basarili': False, 'hata': 'Fiş düzenlenemez (onaylı/iptal).'})


@login_required
@require_POST
def depo_fisi_sil(request, pk):
    """Fişi tamamen sil (sadece bekliyor durumundakiler)."""
    fis = get_object_or_404(DepoFisi, pk=pk)
    fis_no = fis.fis_no
    fis.delete()
    return JsonResponse({'basarili': True, 'mesaj': f'Fiş #{fis_no} silindi.'})


@login_required
@require_POST
def depo_fisi_kalem_ekle(request, pk):
    """
    Depo fişi detay sayfasından yeni kalem ekle.
    POST: stok_pk veya stok_kodu/uretici_kodu, adet, kalem_notu
    """
    fis = get_object_or_404(DepoFisi, pk=pk)
    if fis.durum != 'bekliyor':
        return JsonResponse({'basarili': False, 'hata': 'Sadece bekliyor durumundaki fişlere kalem eklenebilir.'})

    stok_pk = request.POST.get('stok_pk', '').strip()
    ara_kodu = request.POST.get('ara_kodu', '').strip()
    adet = max(1, int(request.POST.get('adet', 1) or 1))
    kalem_notu = request.POST.get('kalem_notu', '').strip()

    stok = None
    if stok_pk:
        stok = get_object_or_404(StokKart, pk=int(stok_pk))
    elif ara_kodu:
        stok = StokKart.objects.filter(
            Q(uretici_kodu__iexact=ara_kodu) | Q(stok_kodu__iexact=ara_kodu)
        ).first()
        if not stok:
            return JsonResponse({'basarili': False, 'hata': f'Kod bulunamadı: {ara_kodu}'})
    else:
        return JsonResponse({'basarili': False, 'hata': 'Stok kodu veya üretici kodu gerekli.'})

    kalem = DepoFisiKalemi.objects.create(
        fis=fis, stok=stok, adet=adet, kalem_notu=kalem_notu, birim_fiyat=stok.fiyat1,
    )
    return JsonResponse({
        'basarili': True,
        'kalem_pk': kalem.pk,
        'stok_kodu': stok.stok_kodu,
        'uretici_kodu': stok.uretici_kodu,
        'aciklama': stok.aciklama,
        'marka': stok.marka,
        'adet': adet,
        'mesaj': f'{stok.stok_kodu} fişe eklendi.',
    })


@login_required
def stok_ara_ajax(request):
    """Depo fişi kalem ekleme formunda stok arama — AJAX."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'sonuclar': []})
    stoklar = StokKart.objects.filter(
        Q(uretici_kodu__icontains=q) | Q(stok_kodu__icontains=q) | Q(aciklama__icontains=q)
    ).filter(durum='A')[:15]
    sonuclar = [{
        'pk': s.pk,
        'stok_kodu': s.stok_kodu,
        'uretici_kodu': s.uretici_kodu,
        'aciklama': s.aciklama,
        'marka': s.marka,
        'gercek_stok': float(s.gercek_stok),
    } for s in stoklar]
    return JsonResponse({'sonuclar': sonuclar})


@login_required
@require_POST
def depo_fisi_kalem_sil(request, kalem_pk):
    """Fişten kalem çıkar."""
    kalem = get_object_or_404(DepoFisiKalemi, pk=kalem_pk)
    fis_no = kalem.fis.fis_no
    kalem.delete()
    return JsonResponse({'basarili': True, 'mesaj': f'Kalem silindi (Fiş #{fis_no})'})


# ─────────────────────────────────────────────────────────────
# Malzeme Hareket (Fatura Alış/Satış)
# ─────────────────────────────────────────────────────────────

@login_required
def fatura_listesi(request):
    """Fatura kalemleri — kalem bazlı malzeme hareket görünümü."""
    if request.method == 'POST':
        kalem = get_object_or_404(FaturaKalemi, pk=request.POST.get('kalem_id'))
        kalem.manuel_aciklama = request.POST['manuel_aciklama'].strip()
        kalem.save(update_fields=['manuel_aciklama'])
        messages.success(request, 'Satır açıklaması kaydedildi.')
        return redirect(request.get_full_path())

    stok_uretici_kodu = StokKart.objects.filter(
        stok_kodu=OuterRef('stok_kodu'),
    ).exclude(stok_kodu='').values('uretici_kodu')[:1]
    qs = (
        FaturaKalemi.objects.select_related('fatura')
        .annotate(uretici_kodu=Subquery(stok_uretici_kodu))
        .order_by('-fatura__tarih', 'fatura__fis_no', 'sirano')
    )

    q             = request.GET.get('q', '').strip()
    tur_filtre    = request.GET.get('tur', '')
    kategori      = request.GET.get('kategori', '').strip()
    marka         = request.GET.get('marka', '').strip()
    kanal         = request.GET.get('kanal', '').strip()
    baslangic_str = request.GET.get('baslangic', '')
    bitis_str     = request.GET.get('bitis', '')

    if q:
        qs = qs.filter(
            Q(uretici_kodu__icontains=q) | Q(stok_kodu__icontains=q) | Q(stok_adi__icontains=q) |
            Q(fatura__fis_no__icontains=q) | Q(fatura__belge_no__icontains=q) |
            Q(fatura__cari_unvan__icontains=q) |
            Q(fatura__cari_kodu__icontains=q)
        )
    if tur_filtre:
        qs = qs.filter(fatura__tur=tur_filtre)
    if kategori:
        qs = qs.filter(kategori=kategori)
    if marka:
        qs = qs.filter(marka=marka)
    if kanal:
        qs = qs.filter(kanal=kanal)
    if baslangic_str:
        try:
            qs = qs.filter(fatura__tarih__gte=datetime.date.fromisoformat(baslangic_str))
        except ValueError:
            pass
    if bitis_str:
        try:
            qs = qs.filter(fatura__tarih__lte=datetime.date.fromisoformat(bitis_str))
        except ValueError:
            pass

    from django.db.models import Sum
    istatistik = {
        'toplam_kayit': qs.count(),
        'satis_toplam': qs.filter(fatura__tur=FaturaTur.SATIS).aggregate(t=Sum('tutar'))['t'] or 0,
        'alis_toplam':  qs.filter(fatura__tur=FaturaTur.ALIS).aggregate(t=Sum('tutar'))['t'] or 0,
        'toplam_adet':  qs.aggregate(t=Sum('miktar'))['t'] or 0,
        'maliyet_toplam': qs.aggregate(t=Sum('maliyet'))['t'] or 0,
    }

    paginator = Paginator(qs, 50)
    sayfa = paginator.get_page(request.GET.get('sayfa', 1))
    belge_numaralari = {kalem.fatura.belge_no for kalem in sayfa}
    fis_numaralari = {
        int(numara) for numara in belge_numaralari
        if numara.isascii() and numara.isdecimal() and len(numara) <= 10
    }
    depo_fisleri = DepoFisi.objects.only(
        'fatura_no', 'plaka', 'arac_marka', 'arac_model', 'kilometre',
    ).in_bulk(fis_numaralari)
    arac_bilgileri = {(str(fis.pk), fis.fatura_no): fis for fis in depo_fisleri.values() if fis.fatura_no}
    for kalem in sayfa:
        kalem.depo_fisi = arac_bilgileri.get((kalem.fatura.belge_no, kalem.fatura.dia_key))
    filtre_kaynagi = FaturaKalemi.objects.all()
    sayfa_query = request.GET.copy()
    sayfa_query.pop('sayfa', None)

    return render(request, 'erp/fatura_listesi.html', {
        'sayfa': sayfa,
        'q': q,
        'tur_filtre': tur_filtre,
        'kategori': kategori,
        'marka': marka,
        'kanal': kanal,
        'tur_secenekleri': FaturaTur.choices,
        'kategoriler': filtre_kaynagi.exclude(kategori='').values_list('kategori', flat=True).distinct().order_by('kategori')[:100],
        'markalar': filtre_kaynagi.exclude(marka='').values_list('marka', flat=True).distinct().order_by('marka')[:100],
        'kanallar': filtre_kaynagi.exclude(kanal='').values_list('kanal', flat=True).distinct().order_by('kanal')[:50],
        'baslangic': baslangic_str,
        'bitis': bitis_str,
        'sayfa_query': sayfa_query.urlencode(),
        'istatistik': istatistik,
        'aktif_sayfa': 'fatura_listesi',
    })


@login_required
@require_POST
def fatura_sync(request):
    """AJAX: Fatura sync başlat ve Malzeme Hareket tablosu için kalemleri doldur."""
    tam = request.POST.get('tam', 'false') == 'true'
    baslangic = request.POST.get('baslangic', '').strip() or None
    bitis = request.POST.get('bitis', '').strip() or None
    kalem_cek = request.POST.get('kalem_cek', 'true') == 'true'
    try:
        from dia_integration.services.fatura_service import FaturaService
        from dia_integration.models import SyncTetikleyen
        sonuc = FaturaService.dia_dan_senkronize_et(
            delta=not tam,
            kalem_cek=kalem_cek,
            baslangic_tarihi=baslangic,
            bitis_tarihi=bitis,
            tetikleyen=SyncTetikleyen.MANUEL,
            kullanici=request.user,
        )
        return JsonResponse({
            'basarili': True,
            'mesaj': (
                f'Fatura sync tamamlandı: {sonuc.eklenen} yeni, '
                f'{sonuc.guncellenen} güncellendi, {sonuc.hatali} hata.'
            ),
        })
    except Exception as exc:
        return JsonResponse({'basarili': False, 'hata': str(exc)})


@login_required
@require_GET
def tahsilat_merkezi(request):
    from django.utils import timezone
    from .models import TahsilatAylikRapor, TahsilatGorusme
    from .tahsilat import takip_listesi
    today = timezone.localdate()
    ay = request.GET.get("ay", "")
    rapor = None
    if ay:
        try:
            donem = datetime.date.fromisoformat(ay + "-01")
        except ValueError:
            return HttpResponse("Geçersiz rapor ayı.", status=400)
        rapor = get_object_or_404(TahsilatAylikRapor, ay=donem)
    rows = rapor.satirlar if rapor else takip_listesi(today)
    previous = TahsilatAylikRapor.objects.filter(ay__lt=(rapor.ay if rapor else today.replace(day=1))).first()
    balances = {r["pk"]: Decimal(r["bakiye"]) for r in previous.satirlar} if previous else {}
    callbacks = {}
    if not rapor:
        for pk, followup in TahsilatGorusme.objects.values_list("cari_id", "tekrar_ara"):
            callbacks.setdefault(pk, followup)
    for row in rows:
        row["fark"] = Decimal(row["bakiye"]) - balances[row["pk"]] if row["pk"] in balances else None
        followup = callbacks.get(row["pk"])
        row["arama"] = followup
        row["takip"] = bool(row["limit_asildi"] or row["durum"] in ("Ödeme bekleniyor", "Ödeme aralığı aşıldı", "Bakiye mutabakatı gerekli", "Güncel ekstre gerekli") or (followup and followup <= today))
    toplam = sum(Decimal(r["bakiye"]) for r in rows)
    takip = sum(r["takip"] for r in rows)
    q = request.GET.get("q", "").strip()
    if q:
        rows = [r for r in rows if q.casefold() in (r["kod"] + " " + r["unvan"]).casefold()]
    if request.GET.get("takip"):
        rows = [r for r in rows if r["takip"]]
    rows.sort(key=lambda r: (not r["takip"], -Decimal(r["bakiye"])))
    return render(request, "erp/tahsilat.html", {
        "rows": rows, "toplam": toplam, "takip_sayisi": takip, "q": q,
        "aylar": TahsilatAylikRapor.objects.values_list("ay", flat=True),
        "rapor": rapor, "previous": previous, "aktif_sayfa": "cari_listesi",
    })


@login_required
def tahsilat_profil(request, pk):
    from django import forms
    from django.utils import timezone
    from .models import TahsilatGorusme
    from .tahsilat import analiz

    class GorusmeForm(forms.Form):
        not_metni = forms.CharField(max_length=500, label="Görüşme notu",
                                    widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
        tekrar_ara = forms.DateField(required=False, label="Tekrar aranacak tarih",
                                     widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    cari = get_object_or_404(Cari, pk=pk, tip__in=(CariTip.ALICI, CariTip.ALICI_SATICI))
    form = GorusmeForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        TahsilatGorusme.objects.create(cari=cari, kullanici=request.user, **form.cleaned_data)
        return redirect("erp:tahsilat_profil", pk=pk)
    return render(request, "erp/tahsilat_profil.html", {
        "cari": cari, "profil": analiz(cari, timezone.localdate()), "form": form,
        "faturalar": Fatura.objects.filter(cari_kodu=cari.cari_kodu, tur="S").order_by("-tarih", "-pk")[:12],
        "gorusmeler": cari.tahsilat_gorusmeleri.select_related("kullanici")[:50],
        "aktif_sayfa": "cari_listesi",
    })
