"""
Django settings for metis_admin project.
Local, Docker and Coolify/Hetzner deployment configuration.
"""

from pathlib import Path
import os

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Yardımcı: .env'de tanımsız zorunlu değişken varsa açık hata ver
# ---------------------------------------------------------------------------
def _require_env(key: str) -> str:
    value = os.environ.get(key, '').strip()
    if not value:
        raise RuntimeError(
            f"Zorunlu ortam değişkeni eksik: {key}\n"
            f".env dosyanıza {key}=<değer> satırını ekleyin."
        )
    return value


def _bool_env(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def _csv_env(key: str, default: str = '') -> list[str]:
    return [item.strip() for item in os.environ.get(key, default).split(',') if item.strip()]


# ============================================================
# GENERAL SETTINGS
# ============================================================

# DEBUG: .env'de yoksa False (güvenli varsayılan — production'da asla True kalmasın)
DEBUG = _bool_env('DEBUG', False)

# SECRET_KEY zorunlu — fallback/gömülü değer yok
SECRET_KEY = _require_env('SECRET_KEY')


# ALLOWED_HOSTS environment variable'dan alınabilir (virgülle ayrılmış)
ALLOWED_HOSTS = _csv_env(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1,wadmory.pythonanywhere.com,takip.meslas.com',
)


# ============================================================
# CSRF / SECURITY SETTINGS
# ============================================================

# CSRF_TRUSTED_ORIGINS environment variable'dan alınabilir (virgülle ayrılmış)
CSRF_TRUSTED_ORIGINS = _csv_env(
    'CSRF_TRUSTED_ORIGINS',
    'https://wadmory.pythonanywhere.com,https://takip.meslas.com',
)

SESSION_COOKIE_SECURE = _bool_env('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = _bool_env('CSRF_COOKIE_SECURE', not DEBUG)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = _bool_env('SECURE_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _bool_env('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = _bool_env('SECURE_HSTS_PRELOAD', False)


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dashboard',
    # DİA ERP entegrasyon app'leri
    'erp',
    'dia_integration',
    # Celery periyodik görevler
    'django_celery_beat',
    'django_celery_results',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'metis_admin.urls'


# ============================================================
# TEMPLATES
# ============================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'metis_admin.wsgi.application'


# ============================================================
# DATABASE
# ============================================================

# Coolify için önerilen format: DATABASE_URL=postgres://...
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

# Alternatif olarak DB_* değişkenleri verilirse MySQL kullanılır, yoksa SQLite (development)
DB_NAME = os.environ.get('DB_NAME', '').strip()
DB_USER = os.environ.get('DB_USER', '').strip()
DB_PASSWORD = os.environ.get('DB_PASSWORD', '').strip()
DB_HOST = os.environ.get('DB_HOST', '').strip()
DB_PORT = os.environ.get('DB_PORT', '').strip()

if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.environ.get('DB_CONN_MAX_AGE', '600')),
        )
    }
elif DB_NAME and DB_USER and DB_PASSWORD and DB_HOST:
    # Production - MySQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT or '3306',
            'OPTIONS': {
                'charset': 'utf8mb4',
            },
        }
    }
else:
    # Development - SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }




# ============================================================
# AUTH
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = 'tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True


# ============================================================
# STATIC & MEDIA
# ============================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = []
if (BASE_DIR / 'static').exists():
    STATICFILES_DIRS.append(BASE_DIR / 'static')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================
# AUTH REDIRECTS
# ============================================================

LOGIN_URL = '/dashboard/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/dashboard/login/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ============================================================
# EMAIL SETTINGS
# ============================================================

# Email backend seçimi (.env'den)
EMAIL_BACKEND_TYPE = os.environ.get('EMAIL_BACKEND', 'smtp').lower()
if EMAIL_BACKEND_TYPE == 'console':
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# SMTP settings
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'mail.meslas.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'info@meslas.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_TIMEOUT = 30

DEFAULT_FROM_EMAIL = 'MESLAS OTOMOTİV <info@meslas.com>'
SERVER_EMAIL = 'info@meslas.com'

# Development için console backend kullanmak isterseniz:
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# ============================================================
# CELERY (Görev kuyruğu ve periyodik senkronizasyon)
# ============================================================

# Broker: Redis (Coolify production) veya DB (local geliştirme)
# Local'de Redis yoksa CELERY_BROKER_URL'yi .env'den boş bırakın → DB broker kullanılır
_celery_broker = os.environ.get('CELERY_BROKER_URL', '').strip() or os.environ.get('REDIS_URL', '').strip()
if _celery_broker:
    CELERY_BROKER_URL = _celery_broker
else:
    # Redis yoksa veritabanı broker kullan (geliştirme için)
    # Windows'ta SQLite path için forward slash kullanılmalı
    _broker_db_path = str(BASE_DIR / 'celery_broker.sqlite3').replace('\\', '/')
    CELERY_BROKER_URL = f'sqla+sqlite:///{_broker_db_path}'

# Sonuçlar Django veritabanında (django-celery-results)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', '').strip() or 'django-db'
CELERY_RESULT_EXTENDED = True

# Seri/zaman biçimleri
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Istanbul'
CELERY_ENABLE_UTC = True

# Periyodik görevler için django-celery-beat
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Görev yeniden deneme varsayılanları
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_DEFAULT_RETRY_DELAY = 60  # saniye

# Uzun süren görevlerin zaman aşımı (DİA senkronu için 10 dk yeterli)
CELERY_TASK_SOFT_TIME_LIMIT = 600   # 10 dakika — SoftTimeLimitExceeded fırlatır
CELERY_TASK_TIME_LIMIT = 660        # 11 dakika — zorla öldürür

# ============================================================
# DİA ERP BAĞLANTI AYARLARI
# ============================================================

DIA_SERVER_CODE = os.environ.get('DIA_SERVER_CODE', 'diademo')
DIA_USERNAME = os.environ.get('DIA_USERNAME', 'ws')
DIA_PASSWORD = os.environ.get('DIA_PASSWORD', 'ws')
DIA_FIRMA_KODU = os.environ.get('DIA_FIRMA_KODU', '1')
DIA_DONEM_KODU = os.environ.get('DIA_DONEM_KODU', '1')

# Session timeout: DİA 1 saat, biz 50 dakika ile yeniliyoruz (güvenlik payı)
DIA_SESSION_TTL_SECONDS = int(os.environ.get('DIA_SESSION_TTL_SECONDS', '3000'))

# API loglama: production'da False yapılabilir (kontör tasarrufu için)
DIA_LOG_API_REQUESTS = os.environ.get('DIA_LOG_API_REQUESTS', 'True').lower() == 'true'
