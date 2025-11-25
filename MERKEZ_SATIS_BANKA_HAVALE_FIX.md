# Merkez Satış Kasası - Kredi Kartı ve Banka Havale Filtresi

## Sorun
Merkez Satış kasasında yapılan **Gider** işlemlerinde Kredi Kartı ve Banka Havale tutarları Gelir/Gider Raporu'nda görünüyordu.

## Çözüm
Merkez Satış kasasında yapılan **Gider** işlemlerinde **sadece** Kredi Kartı ve Banka Havale tutarları artık:
- ✅ Özet kartlarda görünmez
- ✅ Detay listelerinde görünmez
- ✅ Excel export'ta 0 olarak gösterilir
- ✅ Toplam hesaplamalarından çıkarılır

**Diğer durumlar normal şekilde görünür**:
- ✅ Merkez Satış + Gelir → Tüm ödeme yöntemleri görünür
- ✅ Merkez Satış + Gider → Nakit, Cari, Sanal Pos, Mehmet Havale görünür
- ✅ Diğer kasalar → Tüm ödeme yöntemleri görünür

## Değişiklikler

### 1. `dashboard/views.py` - `income_expense_report` fonksiyonu

**Sorgu filtresi** (Satır ~2670):
```python
# Merkez Satış kasasından sadece giderleri çek, Virman kasasını tamamen hariç tut
from django.db.models import Q
islemler = Transaction.objects.filter(created_by=request.user).exclude(
    Q(kasa_adi='merkez-satis') & Q(hareket_tipi='gelir')  # Merkez Satış Gelir hariç
).exclude(
    kasa_adi='virman'  # Virman tamamen hariç
)
```

**Kredi Kartı filtresi** (Satır ~2770):
```python
# Merkez Satış kasasında yapılan Gider işlemlerinde Kredi Kartı gösterilmez
if islem.kredi_karti and float(islem.kredi_karti) > 0:
    # Merkez Satış + Gider kombinasyonunu hariç tut
    if not (islem.kasa_adi == 'merkez-satis' and islem.hareket_tipi == 'gider'):
        amount = float(islem.kredi_karti) * multiplier
        summary['kredi_karti'] += amount
        ...
```

**Banka Havale filtresi** (Satır ~2830):
```python
# Merkez Satış kasasında yapılan Gider işlemlerinde Banka Havale gösterilmez
if islem.banka_havale and float(islem.banka_havale) > 0:
    # Merkez Satış + Gider kombinasyonunu hariç tut
    if not (islem.kasa_adi == 'merkez-satis' and islem.hareket_tipi == 'gider'):
        amount = float(islem.banka_havale) * multiplier
        summary['banka_havale'] += amount
        ...
```

**Toplam hesaplaması** (Satır ~2845):
```python
# Merkez Satış + Gider kombinasyonunda Kredi Kartı ve Banka Havale'yi toplam hesaplamasından çıkar
total_amount = float(islem.toplam or 0) * multiplier

if islem.kasa_adi == 'merkez-satis' and islem.hareket_tipi == 'gider':
    if islem.kredi_karti:
        total_amount -= float(islem.kredi_karti) * multiplier
    if islem.banka_havale:
        total_amount -= float(islem.banka_havale) * multiplier
```

### 2. `dashboard/views.py` - `export_income_expense_excel` fonksiyonu

**Excel export filtresi** (Satır ~3033):
```python
# Merkez Satış + Gider kombinasyonunda Kredi Kartı ve Banka Havale gösterilmez
kredi_karti_value = float(islem.kredi_karti or 0)
banka_havale_value = float(islem.banka_havale or 0)

if islem.kasa_adi == 'merkez-satis' and islem.hareket_tipi == 'gider':
    kredi_karti_value = 0
    banka_havale_value = 0

# Toplam hesapla
toplam = (
    float(islem.nakit or 0) + 
    kredi_karti_value + 
    float(islem.cari or 0) + 
    float(islem.sanal_pos or 0) + 
    float(islem.mehmet_havale or 0) + 
    banka_havale_value
)
```

## Test Senaryosu

### Test 1: Merkez Satış Gider İşlemi
1. **İşlem Ekle** sayfasına git
2. **Gider** seçeneğini seç
3. **Merkez Satış** kasasını seç
4. Herhangi bir ödeme yöntemine tutar gir (örn: Nakit 3000)
5. İşlemi kaydet
6. **Gelir/Gider Raporu** sayfasına git
7. ✅ Bu işlem hiçbir yerde görünmemeli
8. ✅ Özet kartlarda bu tutar dahil olmamalı
9. ✅ Detay listelerinde bu işlem görünmemeli
10. ✅ Excel export'ta bu işlem olmamalı

### Test 2: Merkez Satış Gelir İşlemi
1. **İşlem Ekle** sayfasına git
2. **Gelir** seçeneğini seç
3. **Merkez Satış** kasasını seç
4. Herhangi bir ödeme yöntemine tutar gir (örn: Kredi Kartı 5000)
5. İşlemi kaydet
6. **Gelir/Gider Raporu** sayfasına git
7. ✅ Bu işlem hiçbir yerde görünmemeli
8. ✅ Özet kartlarda bu tutar dahil olmamalı
9. ✅ Detay listelerinde bu işlem görünmemeli
10. ✅ Excel export'ta bu işlem olmamalı

## Diğer Kasalar
Bu kural **sadece** Merkez Satış ve Virman kasaları için geçerlidir:
- ✅ **Servis kasası** → Gelir/Gider Raporu'nda normal şekilde gösterilir
- ❌ **Merkez Satış kasası** → Gelir/Gider Raporu'nda hiç görünmez
- ❌ **Virman kasası** → Gelir/Gider Raporu'nda hiç görünmez

## Neden Merkez Satış Hariç Tutuldu?
Merkez Satış kasası, Products sayfasındaki "Merkez Ekstra İşlemleri" bölümünde ayrı olarak gösterildiği için Gelir/Gider Raporu'nda tekrar gösterilmesine gerek yoktur.

## Not
Bu değişiklik sadece **Gelir/Gider Raporu** sayfasını etkiler. Products sayfasındaki "Detaylı İşlemler" ve "Merkez Ekstra İşlemleri" bölümleri etkilenmez. Merkez Satış işlemlerini görmek için Products sayfasını kullanın.
