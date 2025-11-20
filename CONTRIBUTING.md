# Katkıda Bulunma Rehberi

Mestakip CRM projesine katkıda bulunmak istediğiniz için teşekkür ederiz! 🎉

## 🤝 Nasıl Katkıda Bulunabilirsiniz?

### 1. Issue Bildirimi
- Hata bulduysanız veya yeni özellik öneriniz varsa, önce [Issues](https://github.com/yourusername/mestakip-crm/issues) bölümünde benzer bir konu olup olmadığını kontrol edin
- Yoksa yeni bir issue açın ve detaylı açıklama yapın

### 2. Pull Request Süreci

#### Adım 1: Fork ve Clone
```bash
# Projeyi fork edin (GitHub'da Fork butonuna tıklayın)
# Sonra kendi fork'unuzu klonlayın
git clone https://github.com/YOUR-USERNAME/mestakip-crm.git
cd mestakip-crm
```

#### Adım 2: Branch Oluşturun
```bash
# Ana branch'ten yeni bir branch oluşturun
git checkout -b feature/amazing-feature
# veya
git checkout -b fix/bug-fix
```

#### Adım 3: Geliştirme Yapın
- Kodunuzu yazın
- Test edin
- Commit mesajlarınızı anlamlı yazın

```bash
git add .
git commit -m "feat: Add amazing feature"
# veya
git commit -m "fix: Fix critical bug"
```

#### Adım 4: Push ve PR
```bash
git push origin feature/amazing-feature
```
GitHub'da Pull Request oluşturun.

## 📝 Commit Mesaj Formatı

Commit mesajlarınızı şu formatta yazın:

```
<type>: <subject>

<body> (opsiyonel)
```

### Type'lar:
- `feat`: Yeni özellik
- `fix`: Hata düzeltmesi
- `docs`: Dokümantasyon değişikliği
- `style`: Kod formatı (boşluk, noktalama vb.)
- `refactor`: Kod yeniden yapılandırma
- `test`: Test ekleme/düzeltme
- `chore`: Build, konfigürasyon vb.

### Örnekler:
```
feat: Add user authentication system
fix: Resolve database connection timeout
docs: Update installation instructions
style: Format code according to PEP 8
refactor: Simplify transaction calculation logic
test: Add unit tests for payment methods
chore: Update dependencies
```

## 🎨 Kod Standartları

### Python
- PEP 8 standartlarına uyun
- Fonksiyonlara docstring ekleyin
- Değişken isimleri açıklayıcı olsun
- Type hints kullanın (mümkünse)

```python
def calculate_total(amount: float, tax_rate: float = 0.18) -> float:
    """
    Vergi dahil toplam tutarı hesaplar.
    
    Args:
        amount: Ana tutar
        tax_rate: Vergi oranı (varsayılan: 0.18)
    
    Returns:
        Vergi dahil toplam tutar
    """
    return amount * (1 + tax_rate)
```

### JavaScript
- ES6+ syntax kullanın
- Fonksiyon isimleri camelCase olsun
- Yorumlar ekleyin

```javascript
/**
 * Kullanıcı bilgilerini getirir
 * @param {number} userId - Kullanıcı ID'si
 * @returns {Promise<Object>} Kullanıcı bilgileri
 */
async function getUserInfo(userId) {
    // Implementation
}
```

### HTML/CSS
- Semantic HTML kullanın
- Bootstrap class'larını tercih edin
- Responsive tasarım yapın

## 🧪 Test

Değişikliklerinizi test edin:

```bash
# Django testleri
python manage.py test

# Belirli bir app'i test et
python manage.py test dashboard

# Coverage raporu
coverage run --source='.' manage.py test
coverage report
```

## 📋 Pull Request Checklist

PR göndermeden önce kontrol edin:

- [ ] Kod PEP 8 standartlarına uygun
- [ ] Testler yazıldı ve geçiyor
- [ ] Dokümantasyon güncellendi
- [ ] Commit mesajları anlamlı
- [ ] Conflict yok
- [ ] CHANGELOG.md güncellendi (major değişiklikler için)

## 🐛 Hata Bildirimi

Hata bildirirken şunları ekleyin:

1. **Açıklama**: Hatanın ne olduğu
2. **Adımlar**: Hatayı nasıl tekrar oluşturabiliriz?
3. **Beklenen Davranış**: Ne olması gerekiyordu?
4. **Gerçek Davranış**: Ne oldu?
5. **Ekran Görüntüsü**: Varsa ekleyin
6. **Ortam**: OS, Python versiyonu, Django versiyonu

## 💡 Özellik Önerisi

Yeni özellik önerirken:

1. **Kullanım Senaryosu**: Bu özellik neden gerekli?
2. **Çözüm Önerisi**: Nasıl çalışmalı?
3. **Alternatifler**: Başka çözümler düşündünüz mü?
4. **Ek Bilgi**: Mockup, örnek kod vb.

## 📞 İletişim

Sorularınız için:
- GitHub Issues
- Email: your-email@example.com

## 🙏 Teşekkürler

Katkılarınız için teşekkür ederiz! Her katkı, projeyi daha iyi hale getirir. 🚀
