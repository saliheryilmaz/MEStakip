# Mestakip CRM

[![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

Mestakip CRM, lastik satış ve servis işletmeleri için özel olarak tasarlanmış, kapsamlı bir işletme yönetim sistemidir. Finansal yönetim, stok takibi, müşteri ilişkileri ve raporlama gibi temel iş süreçlerinizi tek bir platformda birleştirir.

## 🚀 Öne Çıkan Özellikler

### 📊 Kapsamlı Dashboard
- Gerçek zamanlı iş takibi ve özelleştirilebilir metrikler
- Görsel veri analizleri ve detaylı raporlama
- Marka ve ürün bazlı satış analizleri

### 💰 Finansal Çözümler
- Çoklu kasa ve şube yönetimi
- Kapsamlı gelir/gider takip sistemi
- Excel entegrasyonu ile veri yönetimi

### 📦 Stok ve Envanter
- Detaylı ürün ve stok takibi
- Otomatik stok uyarıları
- Toplu ürün giriş/çıkış işlemleri

## 🛠️ Teknik Özellikler

| Bileşen | Teknoloji |
|---------|-----------|
| Backend | Django 5.1.4 |
| Frontend | Bootstrap 5, JavaScript |
| Veritabanı | MySQL / SQLite |
| Deployment | PythonAnywhere |

## 🚀 Hızlı Başlangıç

### Gereksinimler
- Python 3.11+
- MySQL 5.7+ (Production için)
- Node.js 16+ (Frontend build için)

### Kurulum

1. Depoyu klonlayın:
   ```bash
   git clone https://github.com/username/mestakip-crm.git
   cd mestakip-crm
   ```

2. Sanal ortam oluşturup etkinleştirin:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   .\venv\Scripts\activate  # Windows
   ```

3. Gerekli paketleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

4. Ortam değişkenlerini ayarlayın:
   `.env` dosyası oluşturun ve aşağıdaki değişkenleri ekleyin:
   ```env
   DEBUG=False
   SECRET_KEY=your-secret-key-here
   DB_NAME=your_database_name
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_HOST=your_database_host
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

5. Veritabanı ayarlarını yapılandırın ve migrate işlemlerini çalıştırın:
   ```bash
   python manage.py migrate
   ```

6. Süper kullanıcı oluşturun:
   ```bash
   python manage.py createsuperuser
   ```

7. Statik dosyaları toplayın:
   ```bash
   python manage.py collectstatic --noinput
   ```

8. Geliştirme sunucusunu başlatın:
   ```bash
   python manage.py runserver
   ```

9. Tarayıcınızda `http://127.0.0.1:8000` adresini ziyaret edin.

## 🚀 Production Deployment

### PythonAnywhere ile Deploy

1. PythonAnywhere hesabı oluşturun: https://www.pythonanywhere.com
2. Web App oluşturun ve Python versiyonunu seçin (3.11 önerilir)
3. MySQL veritabanı oluşturun
4. Kodu yükleyin (GitHub'dan clone veya Files sekmesinden upload)
5. Virtual environment oluşturun ve bağımlılıkları yükleyin
6. Web App ayarlarında:
   - **Source code**: Projenizin ana dizini
   - **Working directory**: Projenizin ana dizini
   - **WSGI configuration file**: `metis_admin/wsgi.py` dosyasını düzenleyin
7. Environment variables'ı ayarlayın (Files > .env dosyası oluşturun)
8. Static files ayarlarını yapılandırın
9. Web App'i reload edin

### WSGI Configuration (PythonAnywhere)

`/var/www/yourusername_pythonanywhere_com_wsgi.py` dosyasını düzenleyin:

```python
import os
import sys

path = '/home/yourusername/path/to/mestakip-crm'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'metis_admin.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Gunicorn ile Çalıştırma (Opsiyonel)

```bash
gunicorn metis_admin.wsgi:application --bind 0.0.0.0:8000
```

## 📁 Proje Yapısı

```
mestakip-crm/
├── dashboard/              # Ana uygulama
│   ├── models.py          # Veritabanı modelleri
│   ├── views.py           # View fonksiyonları
│   ├── forms.py           # Form tanımlamaları
│   ├── urls.py            # URL yönlendirmeleri
│   └── migrations/        # Veritabanı migrasyonları
├── templates/             # HTML şablonları
│   ├── base.html         # Ana şablon
│   └── dashboard/        # Dashboard şablonları
├── static/               # Statik dosyalar (CSS, JS, images)
├── metis_admin/          # Django proje ayarları
├── requirements.txt      # Python bağımlılıkları
└── manage.py            # Django yönetim scripti
```

## 🔐 Güvenlik

- CSRF koruması aktif
- SQL injection koruması
- XSS koruması
- Güvenli şifre hashleme
- Session yönetimi
- Environment variables ile hassas bilgilerin korunması

**Önemli:** Production ortamında mutlaka:
- `DEBUG=False` ayarlayın
- Güçlü bir `SECRET_KEY` kullanın
- Database credentials'ı environment variables'da saklayın
- HTTPS kullanın

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE.md](LICENSE.md) dosyasına bakın.

## 📧 İletişim

Proje Sahibi - [GitHub](https://github.com/saliheryilmaz)

---

⭐ Bu projeyi beğendiyseniz yıldız vermeyi unutmayın!
