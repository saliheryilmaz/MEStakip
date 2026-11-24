import json
from contextlib import ExitStack
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, TestCase

from . import views
from .uspa_servis import LastikUrun


class AramaAkisiTest(TestCase):
    def test_stok_api_nakit_fiyati_ve_yetki(self):
        views.StokKart.objects.create(stok_kodu="M1", aciklama="205/55R16", gercek_stok=2,
                                      fiyat1=1800, fiyat2=2475.50)
        url = "/mesbul/api/stok/"
        with self.settings(MESBUL_STOK_TOKEN="integration-test"):
            self.assertEqual(self.client.get(url, {"ebat": "2055516"}).status_code, 401)
            result = self.client.get(url, {"ebat": "2055516"}, HTTP_AUTHORIZATION="Bearer integration-test")
            product, = result.json()["urunler"]
            self.assertEqual(product["satis_fiyati"], "2475.5000")
            self.assertNotIn("1800", result.content.decode())
            self.assertEqual(product["adet"], "2.0000")

    def test_ilk_teklif_yavas_kaynaktan_once_gelir(self):
        request_factory = RequestFactory()
        form = {"ebat": "205/55R16", "mevsim": "Yaz", "min_dot": "2026"}
        request = request_factory.post("/", form, HTTP_ACCEPT="application/x-ndjson")
        request.user = SimpleNamespace(pk=1, is_authenticated=True, is_staff=True)
        for code, desc, qty, status in [
            ("own", "Eldeki model 205/55 R16", 4, "A"),
            ("empty", "Tükenen 205/55R16", 0, "A"),
            ("inactive", "Pasif 205/55R16", 5, "P"),
            ("other", "Farklı jant 205/55R16.5", 4, "A"),
        ]:
            views.StokKart.objects.create(stok_kodu=code, aciklama=desc, gercek_stok=qty,
                                          durum=status, mevsim="Yazlık", ozel_kod1="2026")
        self.assertEqual([u.adet for u in views._yerel_stok("2055516", "")], [4])
        bekle = Event()
        self.addCleanup(bekle.set)
        urun = LastikUrun("Test", "1", "Marka", "Test model", 1000, 2, "2026", "Yaz")

        def hizli(*args):
            return [urun]

        def yavas(*args):
            if not bekle.wait(5):
                raise AssertionError("İlk teklif yavaş kaynağı bekledi")
            return []

        funcs = [key for key in vars(views) if key.endswith("_ara")]
        with patch.object(views.cache, "get", return_value=None), patch.object(views.cache, "set"), \
             patch.object(views, "mesbul_cache") as teslim_cache, \
             patch.object(views.AramaGecmisi.objects, "create") as gecmis, \
             patch.object(views.ToptanciIskonto.objects, "filter", return_value=[]):
            with ExitStack() as stack:
                for key in funcs:
                    mock = stack.enter_context(patch.object(views, key, side_effect=hizli if key == "uspa_ara" else yavas))
                    mock.__module__ = key
                stream = views.SonuclarView().post(request).streaming_content
                start = json.loads(next(stream))
                self.assertTrue(start["basladi"])
                self.assertIn("Eldeki model", start["yerel_html"])
                self.assertIn("4 adet", start["yerel_html"])
                self.assertIn("Fiyat girilmemiş", start["yerel_html"])
                first = json.loads(next(stream))
                self.assertEqual(first["biten"], 1)
                self.assertEqual(first["urunler"][0]["model"], "Test model")
                bekle.set()
                updates = [json.loads(line) for line in stream]
                self.assertEqual(updates[-2]["biten"], 17)
                teslim_cache.get.return_value = teslim_cache.set.call_args.args[1]
                final = request_factory.post("/", {**form, "arama_teslim": updates[-1]["hazir"]})
                final.user = request.user
                with patch.object(views, "_toptanci_yanitlari", side_effect=AssertionError("Tekrar arandı")):
                    result = views.SonuclarView().post(final)
                self.assertContains(result, "Test model")
                self.assertContains(result, "Meslas Otomotiv")
                self.assertContains(result, "Eldeki model")
                gecmis.assert_called_once()
