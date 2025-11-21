# Mestakip CRM

Modern ve kullanıcı dostu bir işletme yönetim sistemi. Lastik satış ve servis işletmeleri için özel olarak tasarlanmış kapsamlı bir CRM çözümü.

## 🚀 Özellikler

### 📊 Dashboard & Analitik
- Gerçek zamanlı iş takibi ve raporlama
- Gelir/gider analizi ve grafikler
- Marka bazlı satış dağılımı
- Özelleştirilebilir metrikler

### 💰 Finansal Yönetim
- Detaylı gelir/gider takibi
- Çoklu kasa yönetimi (Servis, Merkez Satış)
- Ödeme yöntemleri: Nakit, Kredi Kartı, Cari, Sanal Pos, Havale
- Kategori bazlı harcama takibi
- Excel entegrasyonu ile toplu veri yükleme
- Gelir/Gider raporlama sistemi

### 📦 Envanter Yönetimi
- Sipariş takip sistemi
- Stok ve satış durumu kontrolü
- Marka ve ürün bazlı filtreleme
- Toplu Excel export/import
- İptal edilen siparişler raporu

### 📅 Takvim & Etkinlikler
- Randevu ve hatırlatma sistemi
- Görsel takvim arayüzü
- Etkinlik kategorileri

### 👥 Kullanıcı Yönetimi
- Rol bazlı yetkilendirme (Admin, Yönetici, Kullanıcı)
- Çoklu kullanıcı desteği
- Bildirim sistemi

## 🛠️ Teknolojiler

- **Backend:** Django 5.1.3
- **Frontend:** Bootstrap 5, JavaScript
- **Veritabanı:** PostgreSQL (Production), SQLite (Development)
- **Deployment:** Railway
- **Excel İşleme:** openpyxl

## 📋 Gereksinimler

- Python 3.11+
- PostgreSQL (Production için)
- Node.js (Frontend build için - opsiyonel)

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

## 🤝 Katkıda Bulunma

1. Fork edin
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

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
