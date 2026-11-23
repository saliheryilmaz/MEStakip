import json
from contextlib import ExitStack
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from . import views
from .uspa_servis import LastikUrun


class AramaAkisiTest(SimpleTestCase):
    def test_ilk_teklif_yavas_kaynaktan_once_gelir(self):
        request_factory = RequestFactory()
        form = {"ebat": "205/55R16", "mevsim": "Yaz", "min_dot": "2026"}
        request = request_factory.post("/", form, HTTP_ACCEPT="application/x-ndjson")
        request.user = SimpleNamespace(pk=1, is_authenticated=True, is_staff=True)
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
                self.assertTrue(json.loads(next(stream))["basladi"])
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
                gecmis.assert_called_once()
