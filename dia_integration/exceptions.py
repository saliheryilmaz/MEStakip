"""
DİA API'ye özgü istisna (exception) sınıfları.

Kullanım:
    from dia_integration.exceptions import DiaAuthError, DiaTimeoutError

Her exception sınıfı, üst katmanlarda (view, task, servis) yakalanıp
kullanıcıya veya log sistemine anlamlı mesaj iletmek için kullanılır.
"""


class DiaBaseError(Exception):
    """Tüm DİA hatalarının ortak atası."""

    def __init__(self, message: str = '', status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class DiaAuthError(DiaBaseError):
    """
    Kimlik doğrulama hatası.
    DİA HTTP 401: hatalı kullanıcı adı/şifre.
    """


class DiaSessionTimeoutError(DiaBaseError):
    """
    Oturum zaman aşımı.
    DİA HTTP 419: session süresi dolmuş, yeniden login gerekli.
    """


class DiaValidationError(DiaBaseError):
    """
    Geçersiz parametre veya iş kuralı hatası.
    DİA HTTP 400: msg alanında detay gelir.
    """


class DiaPermissionError(DiaBaseError):
    """
    Yetki hatası.
    DİA HTTP 401 (yanlış işlem yetkisi) veya 402/405 (lisans).
    """


class DiaCreditError(DiaBaseError):
    """
    Yetersiz kontör.
    DİA HTTP 406.
    """


class DiaServerError(DiaBaseError):
    """
    DİA sunucu / işlem hatası.
    DİA HTTP 500/501.
    """


class DiaConnectionError(DiaBaseError):
    """
    Ağ bağlantısı veya timeout hatası (requests.exceptions.* sarmalayıcısı).
    """


# HTTP durum kodu → exception sınıfı eşlemesi
# DiaClient bu tabloyu kullanarak doğru exception'ı fırlatır.
DIA_STATUS_EXCEPTION_MAP: dict[int, type[DiaBaseError]] = {
    400: DiaValidationError,
    401: DiaAuthError,
    402: DiaPermissionError,
    405: DiaPermissionError,
    406: DiaCreditError,
    419: DiaSessionTimeoutError,
    500: DiaServerError,
    501: DiaServerError,
}
