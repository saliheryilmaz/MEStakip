"""
ERP görünüm katmanı — Cari, Stok, Depo listeleri ve DİA Sync durumu.
"""

from __future__ import annotations

import datetime

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

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

    # Modül bazında son sync
    moduller = ['cari', 'stok', 'firma_donem', 'stok_depo_miktar', 'fatura']
    son_syncler = {}
    for modul in moduller:
        log = SyncLog.objects.filter(modul=modul).order_by('-baslangic').first()
        son_syncler[modul] = log

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

    try:
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
            if modul == 'cari':
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
            if modul == 'cari':
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


# ─────────────────────────────────────────────────────────────
# Stok
# ─────────────────────────────────────────────────────────────

@login_required
def stok_listesi(request):
    """Stok kartı listesi — arama, filtre, sayfalama."""
    qs = StokKart.objects.all().order_by('stok_kodu')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(stok_kodu__icontains=q) |
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
    })


@login_required
def stok_detay(request, pk):
    """Stok kartı detay görünümü."""
    stok = get_object_or_404(StokKart, pk=pk)
    depo_miktarlari = stok.depo_miktarlari.select_related('depo').all()
    return render(request, 'erp/stok_detay.html', {
        'stok': stok,
        'depo_miktarlari': depo_miktarlari,
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
def depo_fisi_istek(request, stok_pk):
    """
    Stok listesindeki araba ikonuna tıklandığında çağrılır.
    Yeni bir DepoFisi + DepoFisiKalemi oluşturur.
    """
    stok = get_object_or_404(StokKart, pk=stok_pk)

    # Her istek için her zaman yeni fiş oluştur
    adet = max(1, int(request.POST.get('adet', 1)))
    fis = DepoFisi.objects.create(
        islem_yapan=request.user,
        cari=request.user.get_full_name() or request.user.username,
        plaka=request.POST.get('plaka', '').strip().upper(),
        arac_marka=request.POST.get('arac_marka', '').strip(),
        arac_model=request.POST.get('arac_model', '').strip(),
    )
    DepoFisiKalemi.objects.create(fis=fis, stok=stok, adet=adet)

    return JsonResponse({
        'basarili': True,
        'fis_no': fis.fis_no,
        'stok_kodu': stok.stok_kodu,
        'aciklama': stok.aciklama,
        'mesaj': f'{stok.stok_kodu} fişe eklendi (Fiş #{fis.fis_no})',
    })


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
    qs = (DepoFisi.objects
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
    fis = get_object_or_404(DepoFisi, pk=pk)
    kalemler = fis.kalemler.select_related('stok').all()

    if request.method == 'POST':
        islem = request.POST.get('islem', '')

        # Fiş bilgilerini güncelle
        if islem == 'fis_guncelle':
            fis.plaka      = request.POST.get('plaka', fis.plaka).strip().upper()
            fis.kilometre  = request.POST.get('kilometre') or None
            fis.arac_marka = request.POST.get('arac_marka', fis.arac_marka).strip()
            fis.arac_model = request.POST.get('arac_model', fis.arac_model).strip()
            fis.cari       = request.POST.get('cari', fis.cari).strip()
            fis.aciklama   = request.POST.get('aciklama', fis.aciklama).strip()
            fis.save(update_fields=['plaka', 'kilometre', 'arac_marka', 'arac_model', 'cari', 'aciklama'])

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

        from django.shortcuts import redirect
        return redirect('erp:depo_fisi_detay', pk=pk)

    return render(request, 'erp/depo_fisi_detay.html', {
        'fis': fis,
        'kalemler': kalemler,
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
    qs = FaturaKalemi.objects.select_related('fatura').order_by('-fatura__tarih', 'fatura__fis_no', 'sirano')

    q             = request.GET.get('q', '').strip()
    tur_filtre    = request.GET.get('tur', '')
    kategori      = request.GET.get('kategori', '').strip()
    marka         = request.GET.get('marka', '').strip()
    kanal         = request.GET.get('kanal', '').strip()
    baslangic_str = request.GET.get('baslangic', '')
    bitis_str     = request.GET.get('bitis', '')

    if q:
        qs = qs.filter(
            Q(stok_kodu__icontains=q) | Q(stok_adi__icontains=q) |
            Q(fatura__fis_no__icontains=q) | Q(fatura__cari_unvan__icontains=q) |
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
