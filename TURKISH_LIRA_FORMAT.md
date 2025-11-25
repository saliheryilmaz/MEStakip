# Türk Lirası Formatı Kullanım Kılavuzu

## Özet
Fiyat değerleri artık Türk Lirası formatında gösteriliyor: **20.000 TL**

## Kullanım

### Django Template'lerinde

```django
{% load turkish_format %}

<!-- Eski format -->
₺{{ fiyat|floatformat:2 }}  <!-- Örnek: ₺20000.00 -->

<!-- Yeni format -->
{{ fiyat|turkish_lira }}  <!-- Örnek: 20.000 TL -->
```

### Özellikler

1. **Binlik Ayırıcı**: Nokta (.) kullanılır
   - Örnek: 20.000 TL

2. **Kuruş Gösterilmez**: Tam sayıya yuvarlanır
   - 20.000,50 → 20.001 TL

3. **Negatif Sayılar**: Eksi işareti ile gösterilir
   - -5.000 TL

4. **Sıfır Değerler**: "0 TL" olarak gösterilir

## Güncellenen Dosyalar

### Template Dosyaları
- ✅ `templates/dashboard/products.html` - Tüm fiyat gösterimleri güncellendi
- ✅ `templates/dashboard/partials/finance-modal.html` - Modal içindeki tutarlar güncellendi
- ✅ `templates/dashboard/index.html` - Dashboard istatistikleri güncellendi

### Backend Dosyaları
- ✅ `dashboard/templatetags/turkish_format.py` - `turkish_lira` filter'ı eklendi
- ✅ `dashboard/templatetags/__init__.py` - Template tags package oluşturuldu

## Diğer Dosyalar İçin Güncelleme

Eğer başka sayfalarda da fiyat gösterimi varsa, aşağıdaki adımları izleyin:

1. Template dosyasının başına ekleyin:
```django
{% load turkish_format %}
```

2. Fiyat gösterimlerini güncelleyin:
```django
<!-- Eski -->
₺{{ tutar|floatformat:2 }}

<!-- Yeni -->
{{ tutar|turkish_lira }}
```

## Örnek Çıktılar

| Girdi | Çıktı |
|-------|-------|
| 20000 | 20.000 TL |
| 1234.56 | 1.235 TL |
| 999999 | 999.999 TL |
| 0 | 0 TL |
| -5000 | -5.000 TL |

## Not

Eğer kuruşları da göstermek isterseniz, mevcut `turkish_format` filter'ını kullanabilirsiniz:
```django
{{ fiyat|turkish_format }}  <!-- Örnek: 20.000,00 -->
```
