from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Cari, TahsilatAylikRapor
from .tahsilat import analiz, aylik_rapor_kaydet, DUZENLI, KAPATAN, YETERSIZ


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class TahsilatTests(TestCase):
    def setUp(self):
        self.cari = Cari.objects.create(cari_kodu="TEST", unvan="Test Ticaret", tip="AL",
                                        bakiye=100, son_sync_tarihi=timezone.now(), rapor_ekstresi=[])
        self.today = timezone.localdate()

    def add(self, day, kind, debit, credit, balance):
        self.cari.rapor_ekstresi.append(dict(tarih=day.isoformat(), turu_txt=kind,
                                            yerelborc=debit, yerelalacak=credit,
                                            yerelborcalacakbakiye=balance))

    def test_cycle_and_reminder_survive_new_sales(self):
        for offset in (60, 45, 30, 15):
            self.add(self.today-timedelta(days=offset), "Gelen Havale", 0, 25, 100)
        self.add(self.today, "Perakende Satış", 26, 0, 126)
        self.cari.bakiye = Decimal(126)
        profile = analiz(self.cari, self.today)
        self.assertEqual(profile["model"], DUZENLI)
        self.assertEqual(profile["beklenti"], self.today.isoformat())
        self.assertEqual(profile["durum"], "Ödeme bekleniyor")
        self.cari.son_sync_tarihi = timezone.now() - timedelta(days=6)
        self.assertEqual(analiz(self.cari, self.today)["durum"], "Güncel ekstre gerekli")

    def test_closed_cycles_and_non_cash_movements(self):
        for i in (60, 40, 20, 0):
            start = self.today - timedelta(days=i)
            self.add(start, "Perakende Satış", 100, 0, 100)
            if i:
                self.add(start + timedelta(days=8), "Tahsilat", 0, 100, 0)
        self.add(self.today, "Satış İade", 0, 10, 90)
        profile = analiz(self.cari, self.today)
        self.assertEqual(profile["model"], KAPATAN)
        self.assertEqual(profile["odeme_gunu"], 3)
        self.assertEqual(profile["kapatma_gunu"], 8)
        self.assertEqual(profile["beklenti"], (self.today + timedelta(days=8)).isoformat())

    def test_report_is_repeatable_and_pages_work(self):
        self.assertEqual(analiz(self.cari, self.today)["model"], YETERSIZ)
        report = aylik_rapor_kaydet()
        aylik_rapor_kaydet()
        self.assertEqual(TahsilatAylikRapor.objects.count(), 1)
        self.client.force_login(User.objects.create_user("tahsilat-test"))
        url = reverse("erp:tahsilat_merkezi")
        self.assertContains(self.client.get(url), self.cari.unvan)
        self.assertContains(self.client.get(url, {"ay": report.ay.strftime("%Y-%m")}), self.cari.unvan)
        profile = reverse("erp:tahsilat_profil", args=[self.cari.pk])
        self.assertRedirects(self.client.post(profile, {"not_metni": "Yeniden aranacak", "tekrar_ara": self.today}), profile)
        self.assertContains(self.client.get(url, {"takip": "1"}), self.cari.unvan)
        self.cari.bakiye = Decimal(0)
        self.cari.save()
        self.assertNotContains(self.client.get(url), self.cari.unvan)
