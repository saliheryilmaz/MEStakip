"""DİA cari ekstre/hareket sorguları."""
from __future__ import annotations

from datetime import date

from dia_integration.client import DiaClient
from dia_integration.services.rapor_service import RaporService


def cari_hareketlerini_getir(cari, baslangic: date | None = None, bitis: date | None = None) -> list[dict]:
    """Tek bir cari kartın DİA hareketlerini getirir.

    Bu fonksiyon DİA web servisini çağırır; yalnızca kullanıcı ekstresini
    görüntülemeyi istediğinde çalıştırılmalıdır.
    """
    if not cari.dia_key:
        raise ValueError('Bu cari kartın DİA anahtarı yok. Önce cari senkronizasyonu yapın.')

    filters = [{
        'field': '_key_scf_carikart',
        'operator': '=',
        'value': int(cari.dia_key),
    }]
    if baslangic:
        filters.append({
            'field': 'tarih',
            'operator': '>=',
            'value': baslangic.isoformat(),
        })
    if bitis:
        filters.append({
            'field': 'tarih',
            'operator': '<=',
            'value': bitis.isoformat(),
        })

    with DiaClient() as client:
        return client.listele(
            modul='scf',
            servis_adi='scf_carikart_hareket_listele',
            filters=filters,
            sorts=[
                {'field': 'tarih', 'sorttype': 'DESC'},
                {'field': 'saat', 'sorttype': 'DESC'},
            ],
            limit=0,
            offset=0,
        )


def cari_ekstre_pdf_al(cari, baslangic: date, bitis: date):
    """DİA ``scf1110a`` cari hesap ekstresini PDF olarak alır.

    Bu çağrı rapor servisidir ve DİA kontörü tüketebilir. ``_key`` her zaman
    MesDia'daki seçili carinin DİA anahtarından alınır; Tester örneğindeki
    sabit örnek anahtar kullanılmaz.
    """
    if not cari.dia_key:
        raise ValueError('Bu cari kartın DİA anahtarı yok. Önce cari senkronizasyonu yapın.')

    baslangic_iso = baslangic.isoformat()
    bitis_iso = bitis.isoformat()
    param = {
        '_key': str(cari.dia_key),
        'tarihbaslangic': baslangic_iso,
        'tarihbitis': bitis_iso,
        'tarihreferans': date.today().isoformat(),
        'vadeyontem': 'B',
        'vadefarki': '0',
        '__ekparametreler': ['acilisbakiyesi'],
        '__fisturleri': [],
        '_key_sis_sube': 0,
        '_depolar': '',
        '_subeler': [],
        'ustIslemTuruKeys': 0,
        'topluekstre': 'False',
        'tekniksformgoster': 'False',
        'baesitsegosterme': 'False',
        'filtreler': [{
            'filtreadi': 'vadetarihi',
            'filtreturu': 'aralik',
            'ilkdeger': baslangic_iso,
            'sondeger': bitis_iso,
            'serbest': '',
        }],
        'siralama': [{'fieldname': 'vadetarihi', 'sorttype': 'asc'}],
        'gruplama': [{'fieldname': 'turu'}],
    }
    return RaporService.rapor_al(
        'scf1110a',
        tasarim_key=1144,
        param=param,
        format_type='pdf',
    )
