"""MesRapor01'in tamamlanmış paketini MesDia tablolarına aktarır."""

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from dia_integration.mappers.cari_mapper import CariMapper
from dia_integration.mappers.fatura_mapper import FaturaMapper, _parse_tarih
from dia_integration.mappers.stok_mapper import StokMapper
from dia_integration.mixins import SyncDurumSecenekleri
from dia_integration.models import SyncDurum, SyncLog, SyncTetikleyen
from dia_integration.services.rapor_service import RaporService
from erp.models import Cari, Depo, Fatura, FaturaKalemi, FaturaTur, StokKart, StokDepoRaporMiktari


FATURA_TURLERI = {
    '1': (FaturaTur.ALIS, 'Mal Alım'),
    '2': (FaturaTur.SATIS, 'Perakende Satış'),
    '3': (FaturaTur.SATIS, 'Toptan Satış'),
    '4': (FaturaTur.ALIS, 'Alınan Hizmet'),
    '5': (FaturaTur.SATIS, 'Verilen Hizmet'),
    '6': (FaturaTur.IADE, 'Alım İade'),
    '7': (FaturaTur.IADE, 'Perakende Satış İade'),
    '8': (FaturaTur.IADE, 'Toptan Satış İade'),
    '9': (FaturaTur.DIGER, 'Alınan Fiyat Farkı'),
    '10': (FaturaTur.DIGER, 'Verilen Fiyat Farkı'),
    '15': (FaturaTur.ALIS, 'Müstahsil Makbuzu'),
}


def _anahtar(satir, alan='_key'):
    deger = satir.get(alan)
    return str(deger).strip() if deger not in (None, '', 0, '0') else ''


def _tablo(tablolar, ad):
    satirlar = tablolar.get(ad)
    if not isinstance(satirlar, list) or any(not isinstance(satir, dict) for satir in satirlar):
        raise ValueError(f'MesRapor01 içinde geçerli {ad} listesi bulunamadı.')
    return satirlar


def _dizin(tablolar, ad):
    dizin = {}
    for satir in _tablo(tablolar, ad):
        key = _anahtar(satir)
        if not key or key in dizin:
            raise ValueError(f'{ad} listesinde eksik veya tekrarlanan DİA anahtarı var.')
        dizin[key] = satir
    return dizin


def _sayi(deger):
    try:
        sayi = Decimal(str(deger))
        if sayi.is_finite():
            return sayi
    except InvalidOperation:
        pass
    raise ValueError('MesRapor01 geçersiz bir sayısal alan döndürdü.')


def _kart_kaydet(model, key, kod_alani, alanlar):
    mevcut = model.objects.filter(dia_key=key).first()
    if mevcut is None:
        mevcut = model.objects.filter(**{kod_alani: alanlar[kod_alani]}).first()
        if mevcut and mevcut.dia_key and mevcut.dia_key != key:
            raise ValueError(f'{model.__name__} kodu başka bir DİA kaydına bağlı.')
    if mevcut:
        model.objects.filter(pk=mevcut.pk).update(dia_key=key, **alanlar)
    else:
        model.objects.create(dia_key=key, **alanlar)


@transaction.atomic
def raporu_aktar(veri):
    rapor = veri.get('rapor_json') if isinstance(veri, dict) else None
    if not isinstance(rapor, dict) or rapor.get('basarili') is not True:
        raise ValueError('MesRapor01 başarılı bir rapor paketi döndürmedi.')
    if rapor.get('son_paket') is not True:
        raise ValueError('MesRapor01 paketi tamamlanmadı. Aktarım yapılmadı.')
    if (rapor.get('firma_kodu'), rapor.get('donem_kodu')) != (1, 1):
        raise ValueError('Rapor firma veya dönem bilgisi beklenen değerle eşleşmiyor.')
    tablolar = rapor.get('veriler')
    if not isinstance(tablolar, dict):
        raise ValueError('MesRapor01 veriler bölümü bulunamadı.')

    cariler = _dizin(tablolar, 'cariler')
    stoklar = _dizin(tablolar, 'stoklar')
    depolar = _dizin(tablolar, 'depolar')
    subeler = _dizin(tablolar, 'subeler')
    markalar = _dizin(tablolar, 'markalar')
    ozel_kodlar = _dizin(tablolar, 'ozel_kodlar')
    birim_tanimlari = _dizin(tablolar, 'birim_tanimlari')
    hizmetler = _dizin(tablolar, 'hizmetler')
    odeme_planlari = _dizin(tablolar, 'odeme_planlari')
    faturalar = _dizin(tablolar, 'faturalar')
    kalemler = _dizin(tablolar, 'fatura_kalemleri')
    stok_birimleri = _dizin(tablolar, 'stok_birimleri')
    ekstre = _tablo(tablolar, 'cari_ekstre')
    envanter = _tablo(tablolar, 'depo_envanteri')
    sync = {'son_sync_tarihi': timezone.now(), 'sync_durumu': SyncDurumSecenekleri.SENKRON}

    cari_hareketleri = defaultdict(list)
    ekstre_alanlari = (
        'tarih', 'saat', 'turu', 'turu_txt', 'tip', 'belgeno', 'fisno', 'aciklama', 'bilgi',
        'yerelborc', 'yerelalacak', 'borc', 'alacak', 'yerelborcalacakbakiye', 'borcalacakbakiye',
    )
    for satir in ekstre:
        cari_key = _anahtar(satir, '_key_scf_carikart')
        if cari_key not in cariler or not _parse_tarih(satir.get('tarih')):
            raise ValueError('Cari ekstre satırında geçerli cari veya tarih bulunamadı.')
        hareket = {alan: satir[alan] for alan in ekstre_alanlari if alan in satir}
        hareket['tarih'] = _parse_tarih(satir['tarih']).isoformat()
        cari_hareketleri[cari_key].append(hareket)

    for key, satir in cariler.items():
        alanlar = CariMapper.rapor_to_fields(satir)
        alanlar.pop('dia_key', None)
        if not alanlar['cari_kodu'] or not alanlar['unvan']:
            raise ValueError('Cari kartta kod veya ünvan eksik.')
        _kart_kaydet(Cari, key, 'cari_kodu', {
            **alanlar, **sync, 'rapor_ekstresi': cari_hareketleri[key],
        })

    for key, satir in depolar.items():
        ad = satir.get('depoadi') or satir.get('ad')
        if not ad:
            raise ValueError('Rapor depo adı içermiyor.')
        sube_key = _anahtar(satir, '_key_sis_sube')
        Depo.objects.update_or_create(dia_key=key, defaults={
            'ad': ad, 'sube_dia_key': sube_key,
            'sube_adi': subeler.get(sube_key, {}).get('subeadi', ''),
            'aktif': satir.get('durum') != 'P' and satir.get('aktif') not in (False, 'f'),
        })

    ana_birimler = {}
    for key, satir in stok_birimleri.items():
        if str(satir.get('anabirim')) == '1':
            stok_key = _anahtar(satir, '_key_scf_stokkart')
            if stok_key in ana_birimler:
                raise ValueError('Bir stok kartında birden fazla ana birim var.')
            ana_birimler[stok_key] = (key, satir)

    stok_alanlari = {
        'stokkartturu': 'tur', 'durum': 'durum', 'ekalan1': 'uretici_kodu',
        'kdvalis': 'kdv_alis', 'kdvsatis': 'kdv_satis', 'note': 'notlar',
        'marka': 'marka', 'ozelkod1': 'ozel_kod1', 'ozelkodaciklama3': 'mevsim',
        'ozelkodaciklama4': 'ozel_kod2', 'fiyat1': 'fiyat1', 'fiyat2': 'fiyat2',
        'anabirimkey': 'ana_birim_dia_key', 'anabirimadi': 'ana_birim',
    }
    for key, satir in stoklar.items():
        ham = dict(satir)
        marka = markalar.get(_anahtar(ham, '_key_scf_marka'), {})
        if marka.get('marka') is not None:
            ham['marka'] = str(marka['marka'])[:100]
        for no, alan in ((1, 'ozelkod1'), (3, 'ozelkodaciklama3'), (4, 'ozelkodaciklama4')):
            kod = ozel_kodlar.get(_anahtar(ham, f'_key_sis_ozelkod{no}'), {})
            if kod.get('aciklama') is not None:
                ham[alan] = kod['aciklama']
        if key in ana_birimler:
            birim_key, birim = ana_birimler[key]
            ham['anabirimkey'] = birim_key
            tanim = birim_tanimlari.get(_anahtar(birim, '_key_sis_stok_birim_listesi'), {})
            if tanim.get('birimadi') is not None:
                ham['anabirimadi'] = tanim['birimadi']
            for alan in ('fiyat1', 'fiyat2'):
                if birim.get(alan) is not None:
                    ham[alan] = birim[alan]
        esleme = StokMapper.dia_to_fields(ham)
        if not str(esleme['stok_kodu'] or '').strip() or not esleme['aciklama']:
            raise ValueError('Stok kartında kod veya açıklama eksik.')
        alanlar = {hedef: esleme[hedef] for kaynak, hedef in stok_alanlari.items()
                   if ham.get(kaynak) is not None}
        _kart_kaydet(StokKart, key, 'stok_kodu', {
            **alanlar, **sync, 'stok_kodu': esleme['stok_kodu'],
            'aciklama': esleme['aciklama'], 'dia_son_degisiklik': esleme['dia_son_degisiklik'],
        })

    yerel_stok = StokKart.objects.in_bulk(stoklar, field_name='dia_key')
    yerel_depo = Depo.objects.in_bulk(depolar, field_name='dia_key')
    miktarlar = {}
    for satir in envanter:
        stok_key = _anahtar(satir, '_key_scf_stokkart')
        depo_key = _anahtar(satir, '_key_sis_depo')
        if stok_key not in yerel_stok or depo_key not in yerel_depo or (stok_key, depo_key) in miktarlar:
            raise ValueError('Depo envanterinde eksik bağlantı veya tekrarlanan stok/depo çifti var.')
        miktarlar[stok_key, depo_key] = _sayi(satir.get('net_hareket_miktari'))
    StokDepoRaporMiktari.objects.filter(depo_id__in=[depo.pk for depo in yerel_depo.values()]).delete()
    StokDepoRaporMiktari.objects.bulk_create([
        StokDepoRaporMiktari(stok=yerel_stok[stok_key], depo=yerel_depo[depo_key],
                            net_hareket_miktari=miktar)
        for (stok_key, depo_key), miktar in miktarlar.items()
    ])

    yerel_faturalar = {}
    for key, satir in faturalar.items():
        alanlar = FaturaMapper.dia_to_fields(satir)
        alanlar.pop('dia_key')
        if not alanlar['fis_no'] or not alanlar['tarih']:
            raise ValueError('Fatura başlığında fiş numarası veya tarih eksik.')
        alanlar['tur'], alanlar['tur_aciklama'] = FATURA_TURLERI.get(
            str(satir.get('turu')), (alanlar['tur'], alanlar['tur_aciklama']),
        )
        cari_key = _anahtar(satir, '_key_scf_carikart')
        if cari_key and cari_key not in cariler:
            raise ValueError('Faturanın cari kartı raporda bulunamadı.')
        if cari_key:
            alanlar['cari_kodu'] = cariler[cari_key]['carikartkodu']
            alanlar['cari_unvan'] = cariler[cari_key]['unvan']
        depo = yerel_depo.get(_anahtar(satir, '_key_sis_depo_source'))
        if depo:
            alanlar['depo_adi'] = depo.ad
            alanlar['sube_adi'] = depo.sube_adi
        alanlar['aciklama'] = alanlar['aciklama'] or satir.get('aciklama1') or ''
        yerel_faturalar[key], _ = Fatura.objects.update_or_create(dia_key=key, defaults={**alanlar, **sync})

    for key, satir in kalemler.items():
        fatura = yerel_faturalar.get(_anahtar(satir, '_key_scf_fatura'))
        if fatura is None:
            raise ValueError('Fatura kaleminin başlığı raporda bulunamadı.')
        urun_key = _anahtar(satir, '_key_kalemturu')
        tur = satir.get('kalemturu')
        stok = yerel_stok.get(urun_key) if tur == 'MLZM' else None
        hizmet = hizmetler.get(urun_key, {}) if tur == 'HZMT' else {}
        if (tur == 'MLZM' and stok is None) or (tur == 'HZMT' and not hizmet):
            raise ValueError('Fatura kaleminin stok veya hizmet kartı raporda bulunamadı.')
        depo = yerel_depo.get(_anahtar(satir, '_key_sis_depo_source'))
        plan = odeme_planlari.get(_anahtar(satir, '_key_scf_odeme_plani'), {})
        alanlar = {
            'sirano': satir['sirano'], 'miktar': _sayi(satir['miktar']),
            'birim_fiyat': _sayi(satir['birimfiyati']),
            'tutar': _sayi(satir['tutari']),
            'depo': depo.ad if depo else fatura.depo_adi,
            'odeme_plani': plan.get('aciklama', ''),
        }
        if stok:
            alanlar.update(stok_kodu=stok.stok_kodu, stok_adi=stok.aciklama, marka=stok.marka,
                           mevsim=stok.mevsim, kategori=stok.ozel_kod2, dot=stok.ozel_kod1)
        elif hizmet:
            alanlar.update(stok_kodu=hizmet['hizmetkartkodu'], stok_adi=hizmet['aciklama'], kategori='HİZMET')
        FaturaKalemi.objects.update_or_create(fatura=fatura, dia_key=key, defaults=alanlar)

    from erp.tahsilat import aylik_rapor_kaydet
    aylik_rapor_kaydet()

    return {
        'cari': len(cariler), 'stok': len(stoklar), 'depo': len(depolar),
        'net depo miktarı': len(miktarlar), 'ekstre satırı': len(ekstre),
        'fatura': len(faturalar), 'fatura kalemi': len(kalemler),
    }


def mes_rapor_senkronize_et(kullanici):
    log = SyncLog.objects.create(modul='mes_rapor', tetikleyen=SyncTetikleyen.MANUEL,
                                 tetikleyen_kullanici=kullanici)
    try:
        sayilar = raporu_aktar(RaporService.mes_raporu_json_al().json_verisi)
    except Exception as exc:
        log.tamamla(SyncDurum.BASARISIZ, str(exc))
        raise
    toplam = sum(sayilar.values())
    SyncLog.objects.filter(pk=log.pk).update(toplam_kayit=toplam, basarili_kayit=toplam)
    log.tamamla()
    return sayilar
