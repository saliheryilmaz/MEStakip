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

## Yönetici Asistanı

`/dashboard/assistant/` proje sayfalarını açıklar ve izin verilen salt okunur
sorgularla sipariş, finans, teklif, garanti, çıkma lastik ve DİA kayıtlarını inceler.
DİA sonuçları canlı API sorgusu değil, son senkronize edilmiş yerel kayıtlardır.
Yanıtlarda kullanılan sorguların kaynak bağlantıları gösterilir.

Coolify uygulamasının **Environment Variables** bölümünde runtime için tanımlayın:

```env
GROQ_API_KEY=<Groq hesabınızın API anahtarı>
GROQ_MODEL=openai/gpt-oss-120b
```

Değişiklikten sonra uygulamayı deploy edin. API anahtarını tarayıcıya veya Git'e koymayın.
Sorular ve yanıt için gerekli sorgu sonuçları Groq'a gönderilir; bağlantı şifreleri gönderilmez.
`groq/compound` ve `groq/compound-mini` yerel araç çağrısı desteklemediğinden asistan
bunların yerine varsayılan modeli kullanır. Anahtar/limit/bağlantı hatası olduğunda
ekranda açık bir durum mesajı gösterilir; yerine yanıltıcı sıfır tutarlar üretilmez.

Kontrol soruları: "Projeyi ve sayfaları açıkla", "DİA carilerinde ... ara",
"Bu ay satış faturalarını göster", "Peki geçen ay?", "Son cari sync ne zaman?".
Yanıtı ilgili kayıt ekranıyla karşılaştırın. Asistan fatura kesmez ve kayıt değiştirmez.

Geliştirici kontrolü: `python manage.py test dashboard.test_assistant --noinput`.
Modül bilgileri `dashboard/assistant_guide.py` içinde sürümlenir.
## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE.md](LICENSE.md) dosyasına bakın.

## 📧 İletişim

Proje Sahibi - [GitHub](https://github.com/saliheryilmaz)

---

⭐ Bu projeyi beğendiyseniz yıldız vermeyi unutmayın!
