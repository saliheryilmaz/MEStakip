import json
import io
import ssl
import urllib.error
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse, resolve
from django.utils import timezone

from . import assistant_service as service
from .assistant_guide import get_project_guide
from .groq_client import GroqError, groq_chat_completion
from .models import Quotation, UserProfile, GarantiBelgesi


def completion(content=None, calls=None):
    return {"choices": [{"message": {"role": "assistant", "content": content,
                                     "tool_calls": calls or []}, "finish_reason": "stop"}]}


def call(name, arguments="{}", key="call-1"):
    return {"id": key, "type": "function", "function": {"name": name, "arguments": arguments}}


class AssistantServiceTests(SimpleTestCase):
    @patch("dashboard.groq_client.urllib.request.urlopen")
    def test_transport_errors_have_safe_categories(self, urlopen):
        for reason, code in ((PermissionError(13, "private detail"), "network_blocked"),
                             (TimeoutError("private detail"), "timeout"),
                             (ssl.SSLError("private detail"), "tls_error")):
            urlopen.side_effect = urllib.error.URLError(reason)
            with self.assertRaises(GroqError) as caught:
                groq_chat_completion(api_key="test", messages=[])
            self.assertEqual(caught.exception.error_code, code)
            self.assertNotIn("private detail", str(caught.exception))

    @patch("dashboard.groq_client.urllib.request.urlopen")
    def test_model_error_code_does_not_expose_response_body(self, urlopen):
        body = json.dumps({"error": {"code": "model_not_found", "message": "PRIVATE"}}).encode()
        urlopen.side_effect = urllib.error.HTTPError("https://api.groq.com", 404, "Not found", {}, io.BytesIO(body))
        with self.assertRaises(GroqError) as caught:
            groq_chat_completion(api_key="test", messages=[])
        self.assertEqual(caught.exception.error_code, "model_not_found")
        self.assertNotIn("PRIVATE", str(caught.exception))

    @patch("dashboard.groq_client.urllib.request.urlopen")
    def test_tools_use_sequential_calls(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(completion("OK")).encode()
        groq_chat_completion(api_key="test", messages=[], tools=[{"type": "function"}])
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertFalse(payload["parallel_tool_calls"])

    @patch.object(service, "configuration", return_value=("test-key", service.DEFAULT_MODEL))
    @patch.object(service, "groq_chat_completion")
    def test_specific_failures_reach_the_ui(self, client, config):
        for error, expected in ((GroqError("safe", status_code=404), "model_unavailable"),
                                (GroqError("safe", error_code="network_blocked"), "network_blocked")):
            client.side_effect = error
            self.assertEqual(service.answer_question(None, "Merhaba", [])["status"], expected)

    def test_all_guide_links_resolve(self):
        for item in get_project_guide()["moduller"]:
            self.assertTrue(resolve(item["url"]))

    def test_optional_null_filters_use_function_defaults(self):
        def inventory(brand="", size="", season="", limit=20):
            return {"brand": brand, "size": size, "season": season, "limit": limit}
        with patch.dict(service.REGISTRY, {"get_used_tire_inventory": inventory}):
            result = service.execute_tool("get_used_tire_inventory",
                                          '{"brand":null,"size":null,"season":null,"limit":null}', None)
            self.assertEqual(result, inventory())
            result = service.execute_tool("get_used_tire_inventory", '{"brand":"Test","limit":null}', None)
            self.assertEqual(result, inventory(brand="Test"))
            for args in ('{"limit":"20"}', '{"brand":[]}', '{"user":null}'):
                self.assertIn("hata", service.execute_tool("get_used_tire_inventory", args, None))

    def test_provider_nullable_schema_preserves_local_validation(self):
        for item in service.PROVIDER_DEFINITIONS:
            schema = item["function"]["parameters"]
            original = service.SCHEMAS[item["function"]["name"]]
            for name, spec in schema.get("properties", {}).items():
                if name not in original.get("required", []):
                    self.assertEqual(spec, {"anyOf": [original["properties"][name], {"type": "null"}]})
                    self.assertNotIn("anyOf", original["properties"][name])

    def test_required_null_filter_and_invalid_enum_are_rejected(self):
        schema = {"properties": {"query": {"type": "string"}}, "required": ["query"]}
        with patch.dict(service.SCHEMAS, {"get_erp_stock": schema}):
            for args in ('{}', '{"query":null}'):
                self.assertIn("hata", service.execute_tool("get_erp_stock", args, None))
        self.assertIn("hata", service.execute_tool("get_erp_invoices", '{"kind":"INVALID"}', None))

    @patch.object(service, "configuration", return_value=("test-key", service.DEFAULT_MODEL))
    @patch.object(service, "groq_chat_completion")
    def test_tool_generation_failure_is_not_a_connection_error(self, client, config):
        client.side_effect = GroqError("PRIVATE BODY", status_code=400, error_code="tool_use_failed")
        with self.assertLogs(service.logger, level="WARNING") as logs:
            result = service.answer_question(None, "Stok?", [])
        self.assertEqual(result["status"], "tool_use_failed")
        self.assertNotIn("PRIVATE", result["text"] + str(logs.output))
        self.assertIn("tool_use_failed", str(logs.output))

    def test_rejects_unknown_tools_and_unsafe_arguments(self):
        with patch.dict(service.REGISTRY, {"get_erp_stock": lambda **kw: self.fail("must not run")}):
            for args in ('{"user": 2}', '{"limit": -1}', '{"limit": 100000}',
                         '{"limit": true}', '{"query": []}', '[]', '{broken'):
                self.assertIn("hata", service.execute_tool("get_erp_stock", args, None))
        self.assertIn("hata", service.execute_tool("delete_invoice", "{}", None))
        self.assertIn("hata", service.execute_tool("get_erp_invoices", '{"start_date":"bad"}', None))

    @patch.object(service, "configuration", return_value=("test-key", service.DEFAULT_MODEL))
    @patch.object(service, "groq_chat_completion")
    def test_multistep_tools_and_followup_context(self, client, config):
        client.side_effect = [completion(calls=[call("get_project_guide")]),
                              completion(calls=[call("get_project_guide", '{"topic":"cari"}', "call-2")]),
                              completion("Cari ekranını açın.")]
        history = [{"role": "user", "content": "DİA cari kartları"},
                   {"role": "assistant", "content": "Hangi firma?"}]
        result = service.answer_question(None, "Nasıl bulurum?", history)
        self.assertTrue(result["used_groq"])
        self.assertEqual(client.call_count, 3)
        self.assertEqual(len(result["sources"]), 2)
        sent = client.call_args.kwargs["messages"]
        self.assertIn(history[0], sent)
        self.assertEqual(len([msg for msg in sent if msg["role"] == "tool"]), 2)

    @patch.object(service, "configuration", return_value=("test-key", service.DEFAULT_MODEL))
    @patch.object(service, "groq_chat_completion")
    def test_errors_are_explicit_and_do_not_echo_provider_body(self, client, config):
        for status, expected in ((401, "authentication"), (429, "rate_limit"), (500, "provider_error")):
            client.side_effect = GroqError("SECRET AND CUSTOMER DATA", status_code=status)
            result = service.answer_question(None, "Gelir?", [])
            self.assertEqual(result["status"], expected)
            self.assertFalse(result["used_groq"])
            self.assertNotIn("SECRET", result["text"])
            self.assertNotIn("0 ₺", result["text"])

    @patch.object(service, "configuration", return_value=("", service.DEFAULT_MODEL))
    @patch.object(service, "groq_chat_completion")
    def test_no_key_never_calls_provider(self, client, config):
        self.assertEqual(service.answer_question(None, "Merhaba", [])["status"], "not_configured")
        client.assert_not_called()

    @patch.object(service, "configuration", return_value=("test-key", service.DEFAULT_MODEL))
    @patch.object(service, "groq_chat_completion")
    def test_tool_loop_is_bounded(self, client, config):
        client.return_value = completion(calls=[call("get_project_guide")])
        self.assertEqual(service.answer_question(None, "İncele", [])["status"], "budget")
        self.assertEqual(client.call_count, 5)
        self.assertEqual(client.call_args.kwargs["tool_choice"], "none")

    @patch.dict("os.environ", {"GROQ_MODEL": "groq/compound-mini", "GROQ_API_KEY": "test"})
    def test_compound_model_migrates(self):
        self.assertEqual(service.configuration()[1], service.DEFAULT_MODEL)


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False,
                   STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class AssistantDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="assistant-test")
        cls.other = User.objects.create_user(username="other-test")
        for owner, amount in ((cls.user, 50), (cls.other, 900)):
            Quotation.objects.create(olusturan=owner, teklif_no=owner.username,
                                     teklif_tarihi=timezone.localdate(), cari=owner.username,
                                     genel_toplam=amount)
            GarantiBelgesi.objects.create(olusturan=owner, belge_no=owner.username,
                                         musteri_adi=owner.username, montaj_tarihi=timezone.localdate())

    def setUp(self):
        self.client.force_login(self.user)

    def test_quotes_and_warranties_are_scoped(self):
        result = service.execute_tool("get_quotes_summary", "{}", self.user)
        self.assertEqual(result["toplam_teklif"], 1)
        self.assertEqual(result["toplam_tutar_tl"], 50)
        result = service.execute_tool("get_warranties", "{}", self.user)
        self.assertEqual(result["toplam_kayit"], 1)
        self.assertEqual(result["kayitlar"][0]["musteri_adi"], self.user.username)

    def test_erp_queries_and_sync_metadata(self):
        from erp.models import Cari, StokKart, Fatura, FaturaKalemi
        from dia_integration.models import SyncLog
        Cari.objects.create(cari_kodu="T1", unvan="Test Cari", durum="P")
        StokKart.objects.create(stok_kodu="L1", aciklama="205/55R16", marka="Test", gercek_stok=4)
        invoice = Fatura.objects.create(fis_no="INV1", cari_unvan="Test Cari",
                                        tarih=timezone.localdate(), toplam=500, tur="S")
        FaturaKalemi.objects.create(fatura=invoice, stok_kodu="L1", stok_adi="205/55R16", miktar=4)
        SyncLog.objects.create(modul="cari", durum="basarili", toplam_kayit=1, basarili_kayit=1,
                               hata_mesaji="DO NOT SEND RAW ERROR")
        self.assertEqual(service.execute_tool("get_erp_customers", '{"query":"Test"}', self.user)["toplam_kayit"], 1)
        stock = service.execute_tool("get_erp_stock", '{"query":"205"}', self.user)
        self.assertEqual(stock["kayitlar"][0]["gercek_stok"], Decimal(4))
        self.assertEqual(service.execute_tool("get_erp_invoices", '{"kind":"S"}', self.user)["toplam_kayit"], 1)
        self.assertEqual(service.execute_tool("get_erp_material_lines", '{}', self.user)["toplam_kayit"], 1)
        status = service.execute_tool("get_dia_sync_status", '{}', self.user)
        self.assertNotIn("DO NOT SEND", str(status))
        self.assertEqual(status["moduller"][0]["toplam_kayit"], 1)

    def test_input_validation_and_guest_access(self):
        url = reverse("dashboard:manager_assistant_query")
        for payload in ([], {"q": []}, {"q": " "}, {"q": "a" * 4001}):
            self.assertEqual(self.client.post(url, data=json.dumps(payload), content_type="application/json").status_code, 400)
        UserProfile.objects.update_or_create(user=self.user, defaults={"role": "misafir"})
        self.assertEqual(self.client.post(url, data='{"q":"Merhaba"}', content_type="application/json").status_code, 302)

    @patch.object(service, "answer_question")
    def test_history_restores_and_clear_requires_post(self, answer):
        answer.return_value = {"text": "Yanıt", "used_groq": True, "sources": [], "status": "ready"}
        response = self.client.post(reverse("dashboard:manager_assistant_query"),
                                    data='{"q":"Soru"}', content_type="application/json")
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("dashboard:manager_assistant"))
        self.assertContains(response, 'assistant-history')
        self.assertEqual(response.context["assistant_history"][0]["content"], "Soru")
        url = reverse("dashboard:clear_chat_history")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertNotIn("ai_chat_history", self.client.session)
