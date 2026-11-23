from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from dia_integration.services.depo_fisi_fatura_service import depo_fisini_dia_faturasi_yap
from erp.models import Cari, Depo, DepoFisi, DepoFisiKalemi, StokKart


class DiaFaturaTest(TestCase):
    def setUp(self):
        depo = Depo.objects.create(ad='Merkez', dia_key='10', sube_dia_key='20')
        cari = Cari.objects.create(unvan='Test Cari', cari_kodu='C1', dia_key='30')
        self.fis = DepoFisi.objects.create(depo=depo, cari=cari.unvan)
        stok = StokKart.objects.create(stok_kodu='S1', dia_key='40', ana_birim_dia_key='50')
        self.satir = DepoFisiKalemi.objects.create(
            fis=self.fis, stok=stok, adet=2, birim_fiyat=Decimal('1500'),
        )

    @patch('dia_integration.services.depo_fisi_fatura_service.DiaClient')
    def test_tl_fatura(self, client_class):
        servis = client_class.return_value.__enter__.return_value.ozel_cagri
        servis.return_value = {'key': '60'}
        self.assertEqual(depo_fisini_dia_faturasi_yap(self.fis), '60')
        servis.assert_called_once()
        modul, islem, veri = servis.call_args.args
        self.assertEqual((modul, islem), ('scf', 'scf_fatura_ekle'))
        kart = veri['kart']
        for alan in ('dovizkuru', 'raporlamadovizkuru'):
            self.assertEqual(Decimal(kart[alan]), 1)
        for alan in ('_key_sis_doviz', '_key_sis_doviz_raporlama'):
            self.assertEqual(kart[alan], {'adi': 'TL'})
        self.assertEqual(kart['_key_sis_sube_source'], 20)
        satir, = kart['m_kalemler']
        self.assertEqual(satir['_key_sis_depo_source'], kart['_key_sis_depo_source'])
        self.assertEqual(satir['_key_sis_doviz'], kart['_key_sis_doviz'])
        self.assertEqual(satir['kdvdurumu'], 'D')
        self.assertEqual(Decimal(satir['birimfiyati']) * Decimal(satir['miktar']), 3000)

    @patch('dia_integration.services.depo_fisi_fatura_service.DiaClient')
    def test_gecersiz_adet_gonderimi_durdurur(self, client_class):
        self.satir.adet = 0
        self.satir.save()
        with self.assertRaisesMessage(ValueError, 'Adet sıfırdan büyük olmalı'):
            depo_fisini_dia_faturasi_yap(self.fis)
        client_class.assert_not_called()
