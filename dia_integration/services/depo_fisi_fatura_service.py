"""Create a retail sales invoice in DİA from a MesDia depot ticket.

This is a real write operation. It is called only from the explicit user action;
it is deliberately never invoked by sync jobs or tests.
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from dia_integration.client import DiaClient
from erp.models import Cari, Depo


def pozitif_anahtar(deger):
    return str(deger).isascii() and str(deger).isdecimal() and int(deger) > 0


def depo_fisini_dia_faturasi_yap(fis) -> str:
    if fis.depo_id:
        depo = Depo.fatura_depolari().filter(pk=fis.depo_id).first()
    else:
        depo = Depo.varsayilan_fatura_deposu()
    if depo is None:
        raise ValueError('Fiş Bilgileri bölümünden DİA şube anahtarı bulunan aktif bir depo seçin.')

    cari_adi = (fis.cari or '').strip()
    eslesen = Cari.objects.filter(Q(unvan__iexact=cari_adi) | Q(cari_kodu__iexact=cari_adi))
    if eslesen.count() != 1:
        raise ValueError('Cari, DİA ile eşleşen tek bir MesDia cari kartı olmalı.')
    cari = eslesen.first()
    if not pozitif_anahtar(cari.dia_key):
        raise ValueError('Cari kartın DİA anahtarı yok; önce cari senkronizasyonu yapın.')

    kalemler = []
    for satir in fis.kalemler.select_related('stok').all():
        stok = satir.stok
        if not pozitif_anahtar(stok.dia_key) or not pozitif_anahtar(stok.ana_birim_dia_key):
            raise ValueError(f'{stok.stok_kodu}: DİA stok/birim anahtarı eksik.')
        if satir.adet <= 0:
            raise ValueError(f'{stok.stok_kodu}: Adet sıfırdan büyük olmalı.')
        if not 0 <= stok.kdv_satis <= 100:
            raise ValueError(f'{stok.stok_kodu}: KDV oranı 0 ile 100 arasında olmalı.')
        birim_fiyat = satir.kullanilan_birim_fiyat
        if birim_fiyat <= 0:
            raise ValueError(f'{stok.stok_kodu}: Birim fiyat sıfırdan büyük olmalı; fatura gönderilmedi.')
        kalemler.append({
            '_key_kalemturu': int(stok.dia_key),
            '_key_scf_kalem_birimleri': int(stok.ana_birim_dia_key),
            '_key_sis_depo_source': int(depo.dia_key),
            '_key_sis_doviz': {'adi': 'TL'},
            'kalemturu': 'MLZM',
            'miktar': str(satir.adet),
            'anamiktar': str(satir.adet),
            'birimfiyati': str(birim_fiyat),
            'yerelbirimfiyati': str(birim_fiyat),
            'dovizkuru': '1',
            'kdv': str(stok.kdv_satis),
            'kdvdurumu': 'D',
            'sirano': len(kalemler) + 1,
        })
    if not kalemler:
        raise ValueError('Fişte aktarılacak kalem yok.')

    aciklama = f'MesDia depo fişi #{fis.fis_no}'
    plaka = (fis.plaka or '').strip()
    if plaka:
        aciklama = f'{aciklama} · Plaka: {plaka}'

    kart = {
        'turu': 2,  # Perakende Satış
        '_key_scf_carikart': int(cari.dia_key),
        '_key_sis_depo_source': int(depo.dia_key),
        '_key_sis_sube_source': int(depo.sube_dia_key),
        '_key_sis_doviz': {'adi': 'TL'},
        '_key_sis_doviz_raporlama': {'adi': 'TL'},
        'dovizkuru': '1',
        'raporlamadovizkuru': '1.000000',
        'tarih': timezone.localdate().isoformat(),
        'saat': timezone.localtime().strftime('%H:%M:%S'),
        'belgeno': str(fis.fis_no),
        'aciklama1': aciklama,
        'istemcitipi': 'W',
        'm_kalemler': kalemler,
    }
    with DiaClient() as client:
        response = client.ozel_cagri('scf', 'scf_fatura_ekle', {'kart': kart})
    fis.depo = depo
    return str(response.get('key') or response.get('msg') or '')
