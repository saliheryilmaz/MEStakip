# Mestakip CRM

[![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)

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
| Backend | Django 5.1.3 |
| Frontend | Bootstrap 5, JavaScript |
| Veritabanı | PostgreSQL / SQLite |
| Deployment | Railway, Docker |
| API | Django REST Framework |

## 🚀 Hızlı Başlangıç

### Gereksinimler
- Python 3.11+
- PostgreSQL 13+
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

4. Veritabanı ayarlarını yapılandırın ve migrate işlemlerini çalıştırın:
   ```bash
   python manage.py migrate
   ```

5. Geliştirme sunucusunu başlatın:
   ```bash
   python manage.py runserver
   ```

6. Tarayıcınızda `http://127.0.0.1:8000` adresini ziyaret edin.

## 📝 Lisans

Bu proje [MIT Lisansı](LICENSE.md) altında lisanslanmıştır.

## 📞 İletişim

Proje hakkında sorularınız için [e-posta gönderebilirsiniz](mailto:your.email@example.com).

## 🔧 Kurulum

### 1. Projeyi Klonlayın
```bash
git clone https://github.com/yourusername/mestakip-crm.git
cd mestakip-crm
```

### 2. Virtual Environment Oluşturun
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Ayarlayın
`.env.example` dosyasını `.env` olarak kopyalayın ve düzenleyin:
```bash
cp .env.example .env
```

### 5. Veritabanı Migrasyonlarını Çalıştırın
```bash
python manage.py migrate
```

### 6. Süper Kullanıcı Oluşturun
```bash
python manage.py createsuperuser
```

### 7. Statik Dosyaları Toplayın
```bash
python manage.py collectstatic --noinput
```

### 8. Sunucuyu Başlatın
```bash
python manage.py runserver
```

Tarayıcınızda `http://localhost:8000` adresine gidin.

## 🚀 Production Deployment

### Railway ile Deploy

1. Railway hesabı oluşturun: https://railway.app
2. Yeni proje oluşturun ve GitHub repo'nuzu bağlayın
3. PostgreSQL eklentisi ekleyin
4. Ortam değişkenlerini ayarlayın:
   - `DATABASE_URL` (Otomatik eklenir)
   - `SECRET_KEY` (Güvenli bir key)
   - `DEBUG=False`
   - `DJANGO_SUPERUSER_USERNAME=admin` (Opsiyonel)
   - `DJANGO_SUPERUSER_EMAIL=admin@example.com` (Opsiyonel)
   - `DJANGO_SUPERUSER_PASSWORD=güvenli_şifre` (Opsiyonel)

**Not:** Superuser environment variables ayarlanmazsa varsayılan değerler kullanılır:
- Username: `admin`
- Email: `admin@mestakip.com`
- Password: `admin123` (İlk girişten sonra mutlaka değiştirin!)

### Gunicorn ile Çalıştırma
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

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE.md](LICENSE.md) dosyasına bakın.


## 📧 İletişim

Proje Sahibi - [GitHub](https://github.com/saliheryilmaz)

Proje Linki: [https://github.com/yourusername/mestakip-crm](https://github.com/yourusername/mestakip-crm)

## 🙏 Teşekkürler

- [Django](https://www.djangoproject.com/)
- [Bootstrap](https://getbootstrap.com/)
- [Bootstrap Icons](https://icons.getbootstrap.com/)
- [Railway](https://railway.app/)

---

⭐ Bu projeyi beğendiyseniz yıldız vermeyi unutmayın!
