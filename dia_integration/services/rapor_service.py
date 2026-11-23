"""DİA raporlama servisi.

Rapor sonuçları DİA'dan base64 kodlu dosya içeriği olarak gelir. Bu katman
çıktıyı çözer; rapor satırlarını Cari/Stok/Fatura modellerine yazmaz. Rapor
tasarımlarının alanları ve JSON şeması doğrulanmadan mevcut senkronizasyon
akışlarının yerine kullanılmamalıdır.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from dia_integration.client import DiaClient
from dia_integration.exceptions import DiaBaseError


@dataclass(frozen=True)
class RaporSonucu:
    """DİA raporunun çözümlenmiş dosya içeriği."""

    report_code: str
    format_type: str
    icerik: bytes
    json_verisi: Any = None


class RaporService:
    """DİA ``rpr_raporsonuc_getir`` çağrılarını yapar ve sonucu decode eder."""

    DESTEKLENEN_FORMATLAR = frozenset({'dia', 'html', 'excel', 'pdf', 'json'})

    @classmethod
    def rapor_al(
        cls,
        report_code: str,
        *,
        param: dict[str, Any] | None = None,
        tasarim_key: str | int = '',
        format_type: str = 'json',
        client: DiaClient | None = None,
    ) -> RaporSonucu:
        """Bir DİA raporunu alır.

        ``client`` verilirse mevcut oturumu kullanır; verilmezse bu metot kendi
        DİA oturumunu açıp kapatır. Çağrı DİA kontörü tüketebilir.
        """
        report_code = str(report_code or '').strip()
        format_type = str(format_type or '').strip().lower()
        if not report_code:
            raise ValueError('report_code boş olamaz.')
        if format_type not in cls.DESTEKLENEN_FORMATLAR:
            raise ValueError(
                'format_type şu değerlerden biri olmalı: '
                + ', '.join(sorted(cls.DESTEKLENEN_FORMATLAR))
            )

        data = {
            'report_code': report_code,
            # DİA örneklerinde tasarim_key hem boş metin hem sayısal key
            # olarak geçiyor. Sayısal key'i metne çevirmek validasyon hatası
            # oluşturabildiği için çağıranın verdiği türü koruyoruz.
            'tasarim_key': tasarim_key if tasarim_key != '' else '',
            'format_type': format_type,
            'param': param or {},
        }
        if client is not None:
            yanit = cls._cagir(client, data)
        else:
            with DiaClient() as dia_client:
                yanit = cls._cagir(dia_client, data)

        encoded_result = yanit.get('result')
        if not isinstance(encoded_result, (str, bytes)):
            raise DiaBaseError(
                f'DİA {report_code} rapor yanıtında base64 result bulunamadı.'
            )

        icerik = cls._base64_coz(encoded_result)
        json_verisi = None
        if format_type == 'json':
            try:
                json_verisi = json.loads(icerik.decode('utf-8-sig'))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DiaBaseError(
                    f'DİA {report_code} rapor sonucu JSON olarak çözümlenemedi.'
                ) from exc

        return RaporSonucu(
            report_code=report_code,
            format_type=format_type,
            icerik=icerik,
            json_verisi=json_verisi,
        )

    @staticmethod
    def _cagir(client: DiaClient, data: dict[str, Any]) -> dict:
        return client.ozel_cagri(
            modul='rpr',
            servis_adi='rpr_raporsonuc_getir',
            data=data,
        )

    @staticmethod
    def _base64_coz(deger: str | bytes) -> bytes:
        if isinstance(deger, str):
            deger = deger.encode('ascii')
        try:
            return base64.b64decode(deger, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise DiaBaseError('DİA rapor sonucu geçerli base64 değil.') from exc

    @classmethod
    def mes_raporu_json_al(cls) -> RaporSonucu:
        """Meslas Otomotiv'in MesDia için hazırladığı özel raporu alır."""
        if settings.DIA_SERVER_CODE.strip().lower() != 'meslasotomotiv':
            raise ValueError('MesRapor01 için DIA_SERVER_CODE=meslasotomotiv olmalı.')
        with DiaClient(firma_kodu=1, donem_kodu=1) as client:
            return cls.rapor_al(
                'MesRapor01',
                tasarim_key=45305,
                param={},
                format_type='json',
                client=client,
            )

    @classmethod
    def stok_karti_json_al(
        cls,
        *,
        stok_kodu: str = '',
        tasarim_key: str | int = '',
        client: DiaClient | None = None,
    ) -> RaporSonucu:
        """Stok Kart Listesi (scf2300b) raporunu JSON biçiminde alır.

        Belirli bir kod verilirse aralığın iki ucuna da aynı kod yazılarak
        rapor kapsamı o stok kartıyla sınırlandırılır.
        """
        stok_kodu = str(stok_kodu or '').strip()
        param = {
            '_key_sis_ozelkod1': '',
            '_key_sis_ozelkod2': '',
            '_key_sis_ozelkod3': '',
            '_key_sis_ozelkod4': '',
            '_key_sis_ozelkod5': '',
            '_key_sis_ozelkod6': '',
            'pasiflerigoster': 'False',
            'recetegoster': 'False',
            'stokbirimlerinigoster': 'False',
            'stokkartkodu1': stok_kodu,
            'stokkartkodu2': stok_kodu,
            'stokkartturleri': [],
            'tasarim_key': tasarim_key if tasarim_key != '' else '',
        }
        return cls.rapor_al(
            'scf2300b',
            param=param,
            tasarim_key=tasarim_key,
            format_type='json',
            client=client,
        )

    @classmethod
    def cari_kart_json_al(
        cls,
        *,
        tasarim_key: str | int,
        client: DiaClient | None = None,
    ) -> RaporSonucu:
        """Cari Kart Listesi (scf1100c) raporunu JSON biçiminde alır."""
        if tasarim_key in ('', None):
            raise ValueError('Cari Kart Listesi raporunun tasarim_key değeri gerekli.')

        param = {
            'cariKeyList': '',
            'cariadreslerigoster': 'True',
            'cariyetkililerigoster': 'False',
            'grupkodu': '',
            'ozelkodu1': '',
            'ozelkodu3': '',
            'ozelkodu4': '',
            'ozelkodu5': '',
            'ozelkodu6': '',
            'ozelkodu7': '',
            'ozelkodu8': '',
            'ozelkodu9': '',
            'ozelkodu10': '',
            'ozelkodu11': '',
            'tasarim_key': tasarim_key,
        }
        return cls.rapor_al(
            'scf1100c',
            param=param,
            tasarim_key=tasarim_key,
            format_type='json',
            client=client,
        )
