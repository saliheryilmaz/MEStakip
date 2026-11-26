from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from erp.models import StokKart
from .models import LastikDepo, LastikOteli, LastikOteliLastik, OtelPlanRaporu, UserProfile
from .otel_plan import degerlendir, plan, rapor_kaydet


class OtelPlanTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("personel")
        self.client.force_login(self.user)
        self.raf = LastikDepo.objects.create(ad="Depo A", raf="B2")
        self.set = self.make_set("yaz")
        self.winter = self.make_set("kis")

    def make_set(self, season):
        item = LastikOteli.objects.create(musteri_adi="Örnek müşteri", plaka="34FL1635", mevsim=season,
                    durum="teslim_edildi", giris_tarihi=date(2026, 12, 1), arac_kilometre=50000,
                    marka="Test", adet=4, ebat="205/55R16", depo=self.raf)
        for i in range(1, 5):
            LastikOteliLastik.objects.create(kayit=item, sira=i, marka="Test", desen="A", dot="2022",
                                            ebat="205/55R16", dis_derinligi=7)
        return item

    def test_duzenle_dis_derinligi_turkce_formda_korunur(self):
        url = reverse("dashboard:lastik_saklama_duzenle", args=[self.set.pk])
        depths = ["5.5", "0.0", "7.0", ""]
        payload = {"adet": "4", "plaka": self.set.plaka, "musteri_adi": self.set.musteri_adi}
        for pos, depth in enumerate(depths, 1):
            self.set.lastikler.filter(sira=pos).update(dis_derinligi=depth or None)
            payload[f"lastik_{pos}_dis"] = depth
            payload[f"lastik_{pos}_marka"] = "Test"

        with translation.override("tr"):
            response = self.client.get(url)
            for pos, depth in enumerate(depths, 1):
                self.assertRegex(response.content.decode(), rf'name="lastik_{pos}_dis"[^>]*value="{depth}"')
            self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(list(self.set.lastikler.order_by("sira").values_list("dis_derinligi", flat=True)),
                         [Decimal("5.5"), Decimal("0"), Decimal("7"), None])

    def submit(self, condition="balon", km="80000"):
        form = dict(previous="0", tarih="2027-12-01", km=km)
        for i in range(1, 5):
            data = dict(marka="Test", model="A", dot="2022", ebat="205/55R16", mm="5",
                        bulgular=[condition if i == 1 else "normal"])
            form.update({f"t{i}-{k}": v for k, v in data.items()})
        with patch("django.utils.timezone.localdate", return_value=date(2027, 12, 1)):
            response = self.client.post(reverse("dashboard:otel_kontrol", args=[self.set.pk]), form)
        self.assertEqual(response.status_code, 302)
        return self.set.kontroller.first()

    def test_full_season_lifecycle(self):
        check = self.submit()
        self.assertEqual(check.oneri, "degistir")
        self.assertEqual(check.hedef, date(2028, 5, 1))
        self.assertEqual(check.lastikler[0]["mm_10000"], 0.67)
        self.assertEqual(self.set.kontroller.count(), 2)
        self.assertEqual(self.set.kontroller.last().lastikler[0]["mm"], 7)
        self.assertEqual(self.set.durum, "teslim_edildi")
        StokKart.objects.create(stok_kodu="Y1", aciklama="Test 205/55 R16 91V", mevsim="Yazlık",
                                gercek_stok=2, ana_birim="Adet")
        StokKart.objects.create(stok_kodu="K1", aciklama="Test 205/55 R16", mevsim="Kışlık",
                                gercek_stok=8, ana_birim="Adet")
        uri = reverse("dashboard:otel_karar", args=[self.set.pk])
        self.client.post(uri, {"kontrol": check.pk, "islem": "degistir"})
        self.set.refresh_from_db()
        self.assertEqual(self.set.durum, "degisim")
        self.assertEqual(self.raf.dolu_adet, 0)
        self.winter.refresh_from_db()
        self.assertEqual(self.winter.durum, "teslim_edildi")
        self.assertEqual(self.client.post(reverse("dashboard:lastik_saklama_cikis", args=[self.set.pk])).status_code, 404)
        report_day = date(2027, 12, 1)
        report = plan(report_day)
        group, = report["alim"]
        self.assertEqual((group["tahmini"], group["onayli"], group["stok"], group["eksik"]), (4, 0, 2, 2))
        self.assertEqual(rapor_kaydet(report_day), rapor_kaydet(report_day))
        self.assertEqual(OtelPlanRaporu.objects.get().icerik["musteri"], 1)
        self.assertEqual(self.client.post(uri, {"kontrol": check.pk, "islem": "karsilandi"}).status_code, 400)
        for action in ("bildirildi", "onaylandi"):
            self.client.post(uri, {"kontrol": check.pk, "islem": action})
        self.assertEqual(plan(report_day)["alim"][0]["onayli"], 4)
        for url in (reverse("dashboard:otel_plan"), reverse("dashboard:otel_kontrol", args=[self.set.pk])):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(uri, {"kontrol": check.pk, "islem": "karsilandi"})
        self.assertFalse(plan(report_day)["ihtiyac"])

    def test_no_km_and_return(self):
        check = self.submit("normal", km="")
        self.assertNotIn("mm_km", check.lastikler[0])
        self.assertIn("düşük güven", check.lastikler[0]["yontem"])
        self.client.post(reverse("dashboard:otel_karar", args=[self.set.pk]),
                         {"kontrol": check.pk, "islem": "sakla", "depo": self.raf.pk})
        self.set.refresh_from_db()
        self.assertEqual(self.set.durum, "depoda")
        self.assertEqual(self.raf.dolu_adet, 1)
        self.assertTrue(self.set.hareketler.filter(hareket_tipi="giris").exists())

    def test_unknown_history_and_guest(self):
        row = dict(mm=None, bulgular=[], dot="")
        self.assertEqual(degerlendir([row], [row], 0, None, date.today(), 6)[0], "eksik")
        UserProfile.objects.update_or_create(user=self.user, defaults={"role":"misafir"})
        self.assertEqual(self.client.get(reverse("dashboard:otel_plan")).status_code, 302)

    def test_plan_panel_omits_storage_list_without_creating_demand(self):
        item = LastikOteli.objects.create(
            musteri_adi="Ölçümü aktarılmamış müşteri", plaka="34ESKI01",
            mevsim="yaz", giris_tarihi=date(2026, 11, 1), adet=4, ebat="205/55R16",
        )
        response = self.client.get(reverse("dashboard:otel_plan"))
        self.assertNotContains(response, item.musteri_adi)
        self.assertNotContains(response, "Lastik Oteli setleri")
        self.assertContains(response, "Satın alma planı")
        self.assertContains(response, "Müşteri ihtiyaçları")
        self.assertNotContains(response, "İlk kontrolü gir")
        self.assertFalse(response.context["data"]["ihtiyac"])
        self.assertFalse(item.kontroller.exists())

    def test_winter_delivery_plans_only_the_removed_worn_summer_set(self):
        self.winter.durum = "depoda"
        self.winter.save(update_fields=["durum"])
        uri = reverse("dashboard:lastik_saklama_cikis", args=[self.winter.pk])
        with patch("django.utils.timezone.localdate", return_value=date(2027, 12, 1)):
            response = self.client.post(uri, {"sonuc": "degisim", "cikan_set": self.set.pk})
        self.assertEqual(response.status_code, 302)
        self.set.refresh_from_db()
        self.winter.refresh_from_db()
        self.assertEqual((self.set.durum, self.winter.durum), ("degisim", "teslim_edildi"))
        row, = plan(date(2027, 12, 1))["ihtiyac"]
        self.assertEqual((row["id"], row["hedef"], row["adet"], row["onay"]), (
            self.set.pk, "2028-05-01", 4, False,
        ))

    def test_vehicle_sale_excludes_prior_risk_without_changing_other_customer(self):
        self.winter.durum = "depoda"
        self.winter.save(update_fields=["durum"])
        unrelated = self.make_set("yaz")
        unrelated.musteri_adi = "Yeni mal sahibi"
        unrelated.save(update_fields=["musteri_adi"])
        self.submit()
        self.assertTrue(plan(date(2027, 12, 1))["ihtiyac"])
        uri = reverse("dashboard:lastik_saklama_cikis", args=[self.winter.pk])
        self.assertEqual(self.client.post(uri, {"sonuc": "arac_satisi"}).status_code, 302)
        self.assertFalse(plan(date(2027, 12, 1))["ihtiyac"])
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.plan_sonucu, "")

    def test_customer_takes_removed_set_without_stock_demand(self):
        self.winter.durum = "depoda"
        self.winter.save(update_fields=["durum"])
        self.submit()
        uri = reverse("dashboard:lastik_saklama_cikis", args=[self.winter.pk])
        self.assertEqual(self.client.post(uri, {"sonuc": "musteri_aldi", "cikan_set": self.set.pk}).status_code, 302)
        self.set.refresh_from_db()
        self.winter.refresh_from_db()
        self.assertEqual(self.set.plan_sonucu, "musteri_aldi")
        self.assertEqual(self.winter.plan_sonucu, "")
        self.assertFalse(plan(date(2027, 12, 1))["ihtiyac"])

    def test_report_combines_sizes_and_allocates_existing_stock_once(self):
        # Twelve customers, four tires each, including legacy single-size records.
        for i in range(12):
            LastikOteli.objects.create(musteri_adi=f"Müşteri {i}", plaka=f"34TEST{i}",
                mevsim="yaz", giris_tarihi=date(2027, 11, 1), adet=4,
                ebat="205/55 R16", dis_derinligi=Decimal("2.5"))
        StokKart.objects.create(stok_kodu="Y2", aciklama="205/55R16 91V", mevsim="Yazlık",
                                ana_birim="Adet", gercek_stok=20)
        row, = plan(date(2027, 12, 1))["alim"]
        self.assertEqual((row["musteri"], row["adet"], row["stok"], row["eksik"]), (12, 48, 20, 28))
        self.assertEqual(row["hedef"], "2028-05-01")
