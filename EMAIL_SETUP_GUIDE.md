# Email Gönderme Kurulumu

## Adımlar

### 1. Email Şifresini Bulun
Hosting panelinizde (cPanel, Plesk, vb.) email hesaplarınızı yönettiğiniz bölüme gidin ve `info@meslas.com` hesabının şifresini bulun veya yeni bir şifre oluşturun.

### 2. .env Dosyasını Güncelleyin
`.env` dosyasını açın ve `EMAIL_HOST_PASSWORD` satırına şifrenizi yazın:

```
EMAIL_HOST_PASSWORD=buraya-email-sifrenizi-yazin
```

**Örnek:**
```
EMAIL_HOST_PASSWORD=MySecurePassword123!
```

### 3. Sunucuyu Yeniden Başlatın
Değişikliklerin geçerli olması için Django sunucusunu yeniden başlatın:

```bash
# Development ortamında
python manage.py runserver

# Production ortamında (PythonAnywhere)
# Web app'i reload edin
```

### 4. Test Edin
1. Teklif listesine gidin
2. Bir teklifi görüntüleyin
3. "Email Gönder" butonuna tıklayın
4. Email adresini girin ve gönderin

## Hosting Email Ayarları

Mevcut ayarlarınız:
- **SMTP Sunucu:** mail.meslas.com
- **Port:** 587
- **Güvenlik:** TLS
- **Email:** info@meslas.com
- **Şifre:** `.env` dosyasında tanımlanmalı

## Sorun Giderme

### Email Gönderilmiyor
1. `.env` dosyasında şifrenin doğru olduğundan emin olun
2. Hosting panelinizde email hesabının aktif olduğunu kontrol edin
3. SMTP ayarlarının doğru olduğunu hosting sağlayıcınızla doğrulayın

### SMTP Bağlantı Hatası
- Port 587'nin açık olduğundan emin olun
- Firewall kurallarını kontrol edin
- Hosting sağlayıcınızın SMTP ayarlarını doğrulayın

### Şifre Hatası
- Hosting panelinden şifreyi sıfırlayın
- Özel karakterler varsa tırnak içine alın: `EMAIL_HOST_PASSWORD="My!Pass@123"`

## Güvenlik Notları

⚠️ **ÖNEMLİ:**
- `.env` dosyasını asla Git'e commit etmeyin
- `.gitignore` dosyasında `.env` olduğundan emin olun
- Şifreleri güvenli tutun
- Production ortamında güçlü şifreler kullanın

## Email Gönderme Özellikleri

✅ HTML formatında email
✅ Teklif detayları email içeriğinde
✅ Özelleştirilebilir konu ve mesaj
✅ Otomatik "MESLAS OTOMOTİV" imzası
✅ info@meslas.com adresinden gönderim
