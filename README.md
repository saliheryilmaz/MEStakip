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
| Deployment | Docker / Coolify / Hetzner |

## 🚀 Hızlı Başlangıç

### Gereksinimler
- Python 3.11+
- MySQL 5.7+ (Production için)
- Node.js 16+ (Frontend build için)

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

## Coolify + Hetzner Deploy

1. Hetzner sunucuda Coolify kurulu olsun ve GitHub repo erişimi tanımlansın.
2. Coolify içinde yeni kaynak oluşturun: Git Repository -> Docker Compose.
3. Compose dosyası olarak `docker-compose.coolify.yml` seçin.
4. Web servisine domain bağlayın ve internal port olarak `8000` kullanın.
5. Environment Variables bölümünde `.env.coolify.example` içindeki değerleri girin.
6. İlk deploy sonrası web container loglarında migration ve healthcheck sonucunu kontrol edin.
7. Uygulamada `/erp/dia/durum/` ekranından DİA bağlantı testini çalıştırın.

Gerekli DİA env değerleri:

```env
DIA_SERVER_CODE=diademo
DIA_USERNAME=ws
DIA_PASSWORD=ws
DIA_FIRMA_KODU=1
DIA_DONEM_KODU=1
DIA_SYNC_INTERVAL_MINUTES=1
```

Canlı DİA'ya geçince sadece bu DİA değerlerini gerçek hesap bilgilerinizle değiştirmeniz yeterli olur.

Dockerfile build pack ile tek container kullanıyorsanız ve ayrı `worker`/`beat`
servisi açmadıysanız şunu da ekleyin:

```env
RUN_CELERY_IN_WEB=True
```

Bu ayar DİA cari, stok, fatura ve stok miktarı sync görevlerini aynı container
içinde her dakika çalıştırır. Docker Compose kullanımında önerilen yapı ayrı
`web`, `worker` ve `beat` servisleridir.

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE.md](LICENSE.md) dosyasına bakın.

## 📧 İletişim

Proje Sahibi - [GitHub](https://github.com/saliheryilmaz)

---

⭐ Bu projeyi beğendiyseniz yıldız vermeyi unutmayın!
