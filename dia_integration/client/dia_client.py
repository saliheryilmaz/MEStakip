"""
DiaClient — DİA Web Servis API ile ham HTTP iletişim katmanı.

Sorumluluklar:
  - Login / logout / session yenileme (1 saatlik TTL yönetimi)
  - Generic _listele / _getir / _ekle / _guncelle / _sil metodları
  - Her çağrı için ApiIstekLog kaydı (opsiyonel, ayarla kontrol edilir)
  - Hata kodlarını DiaBaseError alt sınıflarına dönüştürme
  - requests.Session ile connection pooling (performans)

DİA API Payload Formatı (v3):
  İstek : {servis_adi: {session_id, firma_kodu, donem_kodu, ...parametreler}}
  Yanıt : {"code": "200", "msg": "...", "result": ..., "warnings": [...]}
  Login : {login: {username, password, disconnect_same_user}} → msg = session_id
  Logout: {logout: {session_id}}

Bu sınıf iş kuralı içermez — sadece DİA'ya HTTP konuşur.
Servis sınıfları (CariService, StokService, ...) bu client'ı kullanır.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

from dia_integration.exceptions import (
    DIA_STATUS_EXCEPTION_MAP,
    DiaBaseError,
    DiaConnectionError,
    DiaSessionTimeoutError,
)

logger = logging.getLogger(__name__)

# DİA API base URL şablonu
_BASE_URL_TEMPLATE = 'https://{server_code}.ws.dia.com.tr/api/v3/{module}/json'

# API loglama modeli — geç import (circular import'u önlemek için)
_ApiIstekLog = None


def _get_api_log_model():
    """ApiIstekLog modelini lazy import ile yükle."""
    global _ApiIstekLog
    if _ApiIstekLog is None:
        from dia_integration.models import ApiIstekLog
        _ApiIstekLog = ApiIstekLog
    return _ApiIstekLog


class DiaClient:
    """
    DİA Web Servis API istemcisi.

    Kullanım:
        client = DiaClient()
        client.login()
        sonuc = client.listele('scf', 'scf_carikart_listele', limit=100)
        client.logout()

    Veya context manager olarak (önerilen):
        with DiaClient() as client:
            sonuc = client.listele('scf', 'scf_carikart_listele')
    """

    def __init__(
        self,
        server_code: str | None = None,
        username: str | None = None,
        password: str | None = None,
        firma_kodu: int | str | None = None,
        donem_kodu: int | str | None = None,
        session_ttl: int | None = None,
    ) -> None:
        self.server_code = server_code or settings.DIA_SERVER_CODE
        self.username = username or settings.DIA_USERNAME
        self.password = password or settings.DIA_PASSWORD
        # firma_kodu ve donem_kodu integer olarak sakla (DİA integer bekliyor)
        _firma = firma_kodu or settings.DIA_FIRMA_KODU
        _donem = donem_kodu or settings.DIA_DONEM_KODU
        self.firma_kodu: int = int(_firma)
        self.donem_kodu: int = int(_donem)
        self.session_ttl = session_ttl or settings.DIA_SESSION_TTL_SECONDS

        self._session_id: str = ''
        self._session_alindi: float = 0.0  # Unix timestamp (monotonic)

        # requests.Session: TCP bağlantılarını yeniden kullanır
        self._http = requests.Session()
        self._http.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    # ──────────────────────────────────────────────────────────
    # Context manager desteği
    # ──────────────────────────────────────────────────────────

    def __enter__(self) -> 'DiaClient':
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.logout()
        except Exception:
            pass  # logout hatası main exception'ı bastırmasın
        self._http.close()

    # ──────────────────────────────────────────────────────────
    # Session yönetimi
    # ──────────────────────────────────────────────────────────

    @property
    def session_gecerli_mi(self) -> bool:
        """Session hâlâ TTL içinde mi?"""
        if not self._session_id:
            return False
        gecen = time.monotonic() - self._session_alindi
        return gecen < self.session_ttl

    def _session_yenile_gerekirse(self) -> None:
        """Session süresi dolmuşsa otomatik yenile."""
        if not self.session_gecerli_mi:
            logger.info('DİA session süresi dolmuş veya yok, yeniden login yapılıyor.')
            self.login()

    def login(self) -> str:
        """
        DİA'ya login ol, session_id al.

        DİA v3 login formatı:
          POST /api/v3/sis/json
          Payload: {"login": {"username": ..., "password": ..., "disconnect_same_user": true}}
          Yanıt  : {"code": "200", "msg": "<session_id>", "warnings": []}

        Returns:
            session_id (str)

        Raises:
            DiaAuthError: Hatalı kullanıcı/şifre (HTTP 401)
            DiaConnectionError: Ağ hatası
        """
        url = _BASE_URL_TEMPLATE.format(server_code=self.server_code, module='sis')
        servis = 'login'
        payload = {
            servis: {
                'username': self.username,
                'password': self.password,
                'disconnect_same_user': True,
            }
        }

        baslangic = time.monotonic()
        try:
            resp = self._http.post(url, json=payload, timeout=30)
        except requests.exceptions.RequestException as exc:
            raise DiaConnectionError(f'DİA bağlantı hatası (login): {exc}') from exc

        sure_ms = int((time.monotonic() - baslangic) * 1000)
        yanit = self._yanit_isle(
            servis, resp, sure_ms,
            istek_ozeti={'username': self.username}
        )

        # Session ID, login yanıtının 'msg' alanında gelir
        session_id: str = yanit.get('msg', '')
        if not session_id:
            raise DiaBaseError('Login yanıtında session_id (msg alanı) bulunamadı.')

        self._session_id = session_id
        self._session_alindi = time.monotonic()
        logger.info('DİA login başarılı. session_id=%s...', session_id[:8])
        return session_id

    def logout(self) -> None:
        """
        DİA oturumunu kapat.

        DİA v3 logout formatı:
          POST /api/v3/sis/json
          Payload: {"logout": {"session_id": ...}}
        """
        if not self._session_id:
            return
        url = _BASE_URL_TEMPLATE.format(server_code=self.server_code, module='sis')
        try:
            self._http.post(
                url,
                json={'logout': {'session_id': self._session_id}},
                timeout=15,
            )
        except Exception:
            pass  # logout başarısız olsa bile session'ı temizle
        finally:
            self._session_id = ''
            self._session_alindi = 0.0
        logger.info('DİA logout yapıldı.')

    # ──────────────────────────────────────────────────────────
    # Generic CRUD metodları
    # ──────────────────────────────────────────────────────────

    def listele(
        self,
        modul: str,
        servis_adi: str,
        filters: list[dict] | None = None,
        sorts: list[dict] | None = None,
        params: dict | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        DİA _listele servisi.

        Args:
            modul: DİA modül kodu (örn: 'scf', 'bcs', 'muh')
            servis_adi: Tam servis adı (örn: 'scf_carikart_listele')
            filters: [{"field": "...", "operator": ">=", "value": "..."}]
            sorts: [{"field": "...", "direction": "asc"}]
            params: Modüle özgü ek parametreler
            limit: Sayfa boyutu
            offset: Sayfalama başlangıcı

        Returns:
            Kayıt listesi (her kayıt bir dict)
        """
        data: dict[str, Any] = {
            'limit': limit,
            'offset': offset,
        }
        if filters:
            data['filters'] = filters
        if sorts:
            data['sorts'] = sorts
        if params:
            data['params'] = params

        yanit = self._cagir(modul, servis_adi, data)
        return yanit.get('result', [])

    def getir(self, modul: str, servis_adi: str, key: str | int) -> dict:
        """
        DİA _getir servisi — tek kayıt getirir.

        Args:
            modul: DİA modül kodu
            servis_adi: Tam servis adı (örn: 'scf_carikart_getir')
            key: DİA kayıt _key değeri

        Returns:
            Kayıt dict'i (bağlı alt modeller dahil)
        """
        yanit = self._cagir(modul, servis_adi, {'key': key})
        return yanit.get('result', {})

    def ekle(self, modul: str, servis_adi: str, kart: dict) -> str:
        """
        DİA _ekle servisi — yeni kayıt oluşturur.

        Args:
            modul: DİA modül kodu
            servis_adi: Tam servis adı (örn: 'scf_carikart_ekle')
            kart: Oluşturulacak kayıt verisi

        Returns:
            Oluşturulan kaydın DİA _key değeri (str)
        """
        yanit = self._cagir(modul, servis_adi, {'kart': kart})
        return str(yanit.get('msg', ''))

    def guncelle(self, modul: str, servis_adi: str, kart: dict) -> str:
        """
        DİA _guncelle servisi — var olan kaydı günceller.

        Args:
            modul: DİA modül kodu
            servis_adi: Tam servis adı (örn: 'scf_carikart_guncelle')
            kart: Güncellenecek kayıt verisi (_key içermeli)

        Returns:
            Güncellenen kaydın DİA _key değeri (str)
        """
        if '_key' not in kart:
            raise ValueError(f'guncelle çağrısında kart içinde _key zorunlu: {servis_adi}')
        yanit = self._cagir(modul, servis_adi, {'kart': kart})
        return str(yanit.get('msg', kart.get('_key', '')))

    def sil(self, modul: str, servis_adi: str, key: str | int) -> str:
        """
        DİA _sil servisi.

        Returns:
            DİA'dan dönen mesaj (str)
        """
        yanit = self._cagir(modul, servis_adi, {'key': key})
        return yanit.get('msg', '')

    def ozel_cagri(
        self,
        modul: str,
        servis_adi: str,
        data: dict,
        firma_donem_ekle: bool = True,
    ) -> dict:
        """
        Standart CRUD dışına çıkan özel servisler için.
        Örn: scf_barkod_okut, scf_carikart_hesapdurumu_getir,
             sis_yetkili_firma_donem_sube_depo
        """
        return self._cagir(modul, servis_adi, data, firma_donem_ekle=firma_donem_ekle)

    # ──────────────────────────────────────────────────────────
    # Yardımcı metodlar
    # ──────────────────────────────────────────────────────────

    def _cagir(
        self,
        modul: str,
        servis_adi: str,
        data: dict,
        firma_donem_ekle: bool = True,
    ) -> dict:
        """
        Tüm API çağrılarının geçtiği merkezi metod.

        DİA v3 payload formatı:
          {servis_adi: {session_id, firma_kodu, donem_kodu, ...parametreler}}

        Session yenileme, auth header ekleme, loglama ve
        hata dönüşümü burada yapılır.
        """
        self._session_yenile_gerekirse()

        data.setdefault('session_id', self._session_id)
        if firma_donem_ekle:
            data.setdefault('firma_kodu', self.firma_kodu)
            data.setdefault('donem_kodu', self.donem_kodu)

        url = _BASE_URL_TEMPLATE.format(server_code=self.server_code, module=modul)
        # DİA payload formatı: {servis_adi: data_dict}
        payload = {servis_adi: data}

        # Hassas alanları özet için maskele
        istek_ozeti = {
            k: v for k, v in data.items()
            if k not in ('session_id', 'password', 'sifre')
        }

        baslangic = time.monotonic()
        try:
            resp = self._http.post(url, json=payload, timeout=60)
        except requests.exceptions.Timeout as exc:
            self._log_yaz(
                servis_adi, None, None,
                int((time.monotonic() - baslangic) * 1000),
                False, str(exc), istek_ozeti
            )
            raise DiaConnectionError(f'DİA istek zaman aşımı: {servis_adi}') from exc
        except requests.exceptions.RequestException as exc:
            self._log_yaz(
                servis_adi, None, None,
                int((time.monotonic() - baslangic) * 1000),
                False, str(exc), istek_ozeti
            )
            raise DiaConnectionError(f'DİA bağlantı hatası: {servis_adi}: {exc}') from exc

        sure_ms = int((time.monotonic() - baslangic) * 1000)

        # 419 → session timeout → otomatik yenile ve bir kez daha dene
        if resp.status_code == 419:
            logger.warning('DİA 419 Session Timeout, yeniden login yapılıyor.')
            self.login()
            data['session_id'] = self._session_id
            payload[servis_adi] = data
            try:
                resp = self._http.post(url, json=payload, timeout=60)
            except requests.exceptions.RequestException as exc:
                raise DiaConnectionError(f'DİA yeniden bağlantı hatası: {exc}') from exc
            sure_ms = int((time.monotonic() - baslangic) * 1000)

        return self._yanit_isle(servis_adi, resp, sure_ms, istek_ozeti)

    def _yanit_isle(
        self,
        servis_adi: str,
        resp: requests.Response,
        sure_ms: int,
        istek_ozeti: dict,
    ) -> dict:
        """
        HTTP yanıtını işle, hata varsa uygun exception fırlat.

        DİA v3 başarı yanıt yapısı:
          {"code": "200", "msg": "...", "result": ..., "warnings": [...]}

        Başarılıysa yanıt dict'ini döndür.
        """
        try:
            yanit: dict = resp.json()
        except ValueError:
            self._log_yaz(
                servis_adi, resp.status_code, None, sure_ms,
                False, f'JSON parse hatası: {resp.text[:200]}', istek_ozeti
            )
            raise DiaBaseError(f'DİA yanıtı JSON değil: {resp.text[:200]}')

        # DİA kod alanı string olarak gelebilir ("200") veya int olarak (200)
        raw_kod = yanit.get('code') or yanit.get('status')
        try:
            dia_kod = int(raw_kod) if raw_kod is not None else resp.status_code
        except (ValueError, TypeError):
            dia_kod = resp.status_code

        # faultcode varsa kesinlikle hata
        if 'faultcode' in yanit:
            dia_kod = resp.status_code if resp.status_code != 200 else 400

        basarili = (resp.status_code == 200 and dia_kod == 200 and 'faultcode' not in yanit)

        sonuc_sayisi: int | None = None
        if isinstance(yanit.get('result'), list):
            sonuc_sayisi = len(yanit['result'])

        hata_mesaji = ''
        if not basarili:
            hata_mesaji = yanit.get('faultstring') or yanit.get('msg', '') or f'Hata kodu: {dia_kod}'

        self._log_yaz(
            servis_adi,
            resp.status_code,
            dia_kod,
            sure_ms,
            basarili,
            hata_mesaji if not basarili else '',
            istek_ozeti,
            sonuc_sayisi,
        )

        if not basarili:
            hata_sinifi = DIA_STATUS_EXCEPTION_MAP.get(dia_kod, DiaBaseError)
            raise hata_sinifi(hata_mesaji, status_code=dia_kod)

        return yanit

    def _log_yaz(
        self,
        servis_adi: str,
        http_kod: int | None,
        dia_kod: int | None,
        sure_ms: int,
        basarili: bool,
        hata: str,
        istek_ozeti: dict,
        sonuc_sayisi: int | None = None,
    ) -> None:
        """ApiIstekLog kaydını veritabanına yazar (ayar aktifse)."""
        if not getattr(settings, 'DIA_LOG_API_REQUESTS', True):
            return
        try:
            Model = _get_api_log_model()
            Model.objects.create(
                servis_adi=servis_adi,
                istek_zamani=timezone.now(),
                sure_ms=sure_ms,
                http_durum_kodu=http_kod,
                dia_durum_kodu=dia_kod,
                basarili=basarili,
                hata_mesaji=hata[:2000] if hata else '',
                istek_ozeti=istek_ozeti,
                sonuc_sayisi=sonuc_sayisi,
            )
        except Exception as exc:
            # Loglama hatası ana akışı durdurmamalı
            logger.warning('ApiIstekLog yazılamadı: %s', exc)
