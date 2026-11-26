"""DİA fatura kalemlerinden ürün ve fatura bazında brüt kârlılık."""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby
from operator import attrgetter

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .models import FaturaKalemi, FaturaTur


class AnalizFiltresi(forms.Form):
    baslangic = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    bitis = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    q = forms.CharField(required=False, max_length=200)
    gorunum = forms.ChoiceField(required=False, choices=[('urun', 'Ürün'), ('fatura', 'Fatura')])

    def clean(self):
        data = super().clean()
        if data.get('baslangic') and data.get('bitis') and data['baslangic'] > data['bitis']:
            raise forms.ValidationError('Başlangıç tarihi bitiş tarihinden sonra olamaz.')
        return data


@dataclass
class Ozet:
    ad: str = ''
    detay: str = ''
    alis: Decimal = Decimal(0)
    satis: Decimal = Decimal(0)
    maliyet: Decimal = Decimal(0)
    eksik: int = 0
    tahmini: int = 0
    satis_satiri: int = 0

    @property
    def kar(self):
        if self.satis_satiri and not self.eksik:
            return self.satis - self.maliyet

    @property
    def marj(self):
        if self.kar is not None and self.satis > 0:
            return self.kar * 100 / self.satis


def hareket(tur, aciklama):
    ad = aciklama.lower().replace('i\u0307', 'i')
    if tur == FaturaTur.IADE or 'iade' in ad:
        if 'sat' in ad:
            return 'satis', -1
        if 'alım' in ad or 'alış' in ad or 'alim' in ad or 'alis' in ad:
            return 'alis', -1
    elif tur == FaturaTur.ALIS:
        return 'alis', 1
    elif tur == FaturaTur.SATIS:
        return 'satis', 1
    return '', 0


def analiz(filtre):
    toplam = Ozet()
    gruplar = {}
    haric = 0
    gecmis = defaultdict(lambda: [Decimal(0), Decimal(0)])
    qs = FaturaKalemi.objects.select_related('fatura').filter(fatura__tarih__isnull=False)
    if filtre['bitis']:
        qs = qs.filter(fatura__tarih__lte=filtre['bitis'])
    arama = filtre['q'].casefold()
    for tarih, gun in groupby(qs.order_by('fatura__tarih', 'fatura_id', 'pk').iterator(),
                              key=attrgetter('fatura.tarih')):
        gunluk = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for k in gun:
            f = k.fatura
            yon, isaret = hareket(f.tur, f.tur_aciklama)
            urun = (k.stok_kodu, k.birim, k.kategori == 'HİZMET')
            miktar = abs(k.miktar) if isaret < 0 else k.miktar
            tutar = abs(k.tutar) if isaret < 0 else k.tutar
            if yon == 'alis' and k.stok_kodu and miktar > 0 and tutar > 0:
                gunluk[urun][0] += isaret * miktar
                gunluk[urun][1] += isaret * tutar
            if filtre['baslangic'] and tarih < filtre['baslangic']:
                continue
            if arama and not any(arama in s.casefold() for s in
                                 (k.stok_kodu, k.stok_adi, f.fis_no, f.belge_no, f.cari_unvan)):
                continue
            if not yon:
                haric += 1
                continue
            if filtre['gorunum'] == 'fatura':
                key = f.pk
                ad = f.belge_no or f.fis_no or f'Fatura #{f.pk}'
                detay = f'{tarih:%d.%m.%Y} · {f.cari_unvan} · {f.tur_aciklama or f.get_tur_display()}'
            else:
                key = (urun, k.stok_adi if not k.stok_kodu else '')
                ad = k.stok_adi or k.stok_kodu or 'Tanımsız ürün'
                detay = ' · '.join(filter(None, (k.stok_kodu, k.birim)))
            if key not in gruplar:
                gruplar[key] = Ozet(ad, detay)
            maliyet = k.maliyet
            tahmin = False
            if yon == 'satis' and maliyet <= 0 and k.stok_kodu:
                adet, bedel = gecmis[urun]
                if adet > 0 and bedel > 0:
                    maliyet = bedel / adet
                    tahmin = True
            for satir in (toplam, gruplar[key]):
                if yon == 'alis':
                    satir.alis += isaret * tutar
                else:
                    satir.satis_satiri += 1
                    satir.satis += isaret * tutar
                    if maliyet <= 0 or miktar == 0:
                        satir.eksik += 1
                    else:
                        satir.maliyet += isaret * miktar * maliyet
                        satir.tahmini += int(tahmin)
        for urun, (adet, bedel) in gunluk.items():
            gecmis[urun][0] += adet
            gecmis[urun][1] += bedel
    rows = list(gruplar.values())
    if filtre['gorunum'] == 'fatura':
        rows.reverse()
    else:
        rows.sort(key=lambda row: (-row.satis, row.ad))
    return toplam, rows, haric


@login_required
def kar_zarar(request):
    form = AnalizFiltresi(request.GET)
    toplam, rows, haric = (None, [], 0)
    if form.is_valid():
        toplam, rows, haric = analiz(form.cleaned_data)
    params = request.GET.copy()
    params.pop('sayfa', None)
    return render(request, 'erp/kar_zarar.html', {
        'form': form, 'toplam': toplam, 'haric': haric,
        'fatura': request.GET.get('gorunum') == 'fatura',
        'sayfa': Paginator(rows, 50).get_page(request.GET.get('sayfa')), 'params': params.urlencode(),
    })
