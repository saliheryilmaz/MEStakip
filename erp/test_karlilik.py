from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Fatura, FaturaKalemi


class KarlilikTest(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('analiz'))
        self.url = reverse('erp:kar_zarar')

    def kalem(self, gun, tur, adet, tutar, ad='', kod='A', maliyet=0):
        fatura = Fatura.objects.create(tarih=date(2026, 11, gun), tur=tur, tur_aciklama=ad)
        return FaturaKalemi.objects.create(fatura=fatura, stok_kodu=kod, stok_adi=kod,
                                          miktar=adet, tutar=tutar, maliyet=maliyet)

    def test_alis_gecmisi_iade_ve_iki_gorunum(self):
        self.kalem(1, 'A', 2, 200)
        self.kalem(2, 'A', 2, 400)
        self.kalem(3, 'S', 2, 500)
        self.kalem(4, 'I', 1, 250, 'Perakende Satış İade')
        self.kalem(6, 'A', 1, 900)
        for mode, count in [('urun', 1), ('fatura', 2)]:
            response = self.client.get(self.url, dict(baslangic='2026-11-03', bitis='2026-11-04', gorunum=mode))
            self.assertEqual(response.status_code, 200)
            summary = response.context['toplam']
            self.assertEqual((summary.alis, summary.satis, summary.kar, summary.marj), (0, 250, 100, 40))
            self.assertEqual(len(response.context['sayfa']), count)

    def test_eksik_maliyet_ve_zarar(self):
        self.kalem(1, 'S', 2, 120, maliyet=80)
        self.kalem(1, 'S', 1, 50, kod='B')
        result = self.client.get(self.url)
        self.assertIsNone(result.context['toplam'].kar)
        self.assertEqual(self.client.get(self.url, {'q': 'A'}).context['toplam'].kar, Decimal('-40'))
