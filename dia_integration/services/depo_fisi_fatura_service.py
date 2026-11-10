"""Create a retail sales invoice in DİA from a MEStakip depot ticket.

This is a real write operation. It is called only from the explicit user action;
it is deliberately never invoked by sync jobs or tests.
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from dia_integration.client import DiaClient
from erp.models import Cari


def depo_fisini_dia_faturasi_yap(fis) -> str:
    cari_adi = (fis.cari or '').strip()
    eslesen = Cari.objects.filter(Q(unvan__iexact=cari_adi) | Q(cari_kodu__iexact=cari_adi))
    if eslesen.count() != 1:
        raise ValueError('Cari, DİA ile eşleşen tek bir MEStakip cari kartı olmalı.')
    cari = eslesen.first()
    if not cari.dia_key:
        raise ValueError('Cari kartın DİA anahtarı yok; önce cari senkronizasyonu yapın.')

    kalemler = []
    for satir in fis.kalemler.select_related('stok').all():
        stok = satir.stok
        if not stok.dia_key or not stok.ana_birim_dia_key:
            raise ValueError(f'{stok.stok_kodu}: DİA stok/birim anahtarı eksik.')
        if stok.fiyat1 <= 0:
            raise ValueError(f'{stok.stok_kodu}: DİA Fiyat 1 sıfır; fatura gönderilmedi.')
        kalemler.append({
            '_key_kalemturu': int(stok.dia_key),
            '_key_scf_kalem_birimleri': int(stok.ana_birim_dia_key),
            'kalemturu': 'MLZM',
            'miktar': str(satir.adet),
            'anamiktar': str(satir.adet),
            'birimfiyati': str(stok.fiyat1),
            'yerelbirimfiyati': str(stok.fiyat1),
            'dovizkuru': '1',
            'kdv': str(stok.kdv_satis),
            'kdvdurumu': 'H',
            'sirano': len(kalemler) + 1,
        })
    if not kalemler:
        raise ValueError('Fişte aktarılacak kalem yok.')

    kart = {
        'turu': 2,  # Perakende Satış
        '_key_scf_carikart': int(cari.dia_key),
        '_key_sis_doviz': {'adi': 'TL'},
        '_key_sis_doviz_raporlama': {'adi': 'TL'},
        'dovizkuru': '1',
        'tarih': timezone.localdate().isoformat(),
        'saat': timezone.localtime().strftime('%H:%M:%S'),
        'belgeno': f'ME-DEP-{fis.fis_no}',
        'aciklama1': f'MEStakip depo fişi #{fis.fis_no}',
        'istemcitipi': 'W',
        'm_kalemler': kalemler,
    }
    if fis.depo and fis.depo.dia_key:
        kart['_key_sis_depo_source'] = int(fis.depo.dia_key)
        if fis.depo.sube_dia_key:
            kart['_key_sis_sube_source'] = int(fis.depo.sube_dia_key)

    with DiaClient() as client:
        response = client.ozel_cagri('scf', 'scf_fatura_ekle', {'kart': kart})
    return str(response.get('key') or response.get('msg') or '')
