# Merkez Satış Kasası - Test Kılavuzu

## Yapılan Değişiklik
Merkez Satış kasasındaki **tüm işlemler** (hem Gelir hem Gider) artık **Gelir/Gider Raporu** sayfasında görünmüyor.

## Test Adımları

### 1. Merkez Satış İşlemi Oluştur
1. **İşlem Ekle** sayfasına git (`/dashboard/finance/`)
2. Bir işlem oluştur:
   - Hareket Tipi: **Gider** (veya Gelir)
   - Tarih: Bugün
   - Kasa Adı: **Merkez Satış**
   - Herhangi bir ödeme yöntemine tutar gir (örn: Nakit 5000)
   - Açıklama: "Test - Merkez Satış"
3. **Kaydet** butonuna tıkla

### 2. Gelir/Gider Raporu'nu Kontrol Et
1. **Gelir/Gider Raporu** sayfasına git (`/dashboard/income-expense-report/`)
2. Tarih filtrelerini bugünü kapsayacak şekilde ayarla
3. **ÇALIŞTIR** butonuna tıkla

### 3. Beklenen Sonuçlar ✅

#### Özet Kartlar
- ✅ Nakit kartında 5000 TL **görünmemeli**
- ✅ Diğer kartlarda da bu işlem **görünmemeli**
- ✅ Toplam kartında bu işlem **dahil olmamalı**

#### İşlem Listesi Tablosu
- ✅ "Test - Merkez Satış" açıklamalı işlem **görünmemeli**
- ✅ Merkez Satış kasası **hiçbir satırda görünmemeli**

#### Excel Export
1. **Excel İndir** butonuna tıkla
2. Excel dosyasını aç
3. ✅ "Test - Merkez Satış" işlemi **Excel'de olmamalı**

### 4. Merkez Satış İşlemlerini Nerede Görebilirim?

Merkez Satış işlemleri **Products** sayfasında görüntülenir:
1. **Products** sayfasına git (`/dashboard/products/`)
2. Aşağı kaydır
3. **"Merkez Ekstra İşlemleri"** bölümünü bul
4. ✅ Burada Merkez Satış işlemlerini görebilirsiniz

### 5. Diğer Kasaları Test Et

#### Servis Kasası (Normal Görünmeli)
1. **İşlem Ekle** → Gider → **Servis** → Nakit 3000 → Kaydet
2. **Gelir/Gider Raporu** → Bugün
3. ✅ Bu işlem **görünmeli**

#### Virman Kasası (Görünmemeli)
1. **İşlem Ekle** → Gider → **Virman** → Nakit 2000 → Kaydet
2. **Gelir/Gider Raporu** → Bugün
3. ✅ Bu işlem **görünmemeli** (Virman zaten hariç tutulur)

## Sorun Giderme

### Eğer Merkez Satış İşlemleri Hala Görünüyorsa:

1. **Tarayıcı Cache'ini Temizle**:
   - Chrome: Ctrl + Shift + Delete
   - Sayfayı yenile: Ctrl + F5

2. **Django Sunucusunu Yeniden Başlat**:
   ```bash
   # Sunucuyu durdur (Ctrl + C)
   # Tekrar başlat
   python manage.py runserver
   ```

3. **Veritabanını Kontrol Et**:
   ```python
   # Django shell'de
   python manage.py shell
   
   from dashboard.models import Transaction
   from django.contrib.auth.models import User
   
   user = User.objects.get(username='your_username')
   merkez_satis = Transaction.objects.filter(
       created_by=user,
       kasa_adi='merkez-satis'
   )
   print(f"Merkez Satış işlem sayısı: {merkez_satis.count()}")
   ```

4. **Kod Değişikliğini Kontrol Et**:
   - `dashboard/views.py` dosyasını aç
   - Satır ~2671'i kontrol et:
   ```python
   islemler = Transaction.objects.filter(created_by=request.user).exclude(
       kasa_adi='merkez-satis'  # Bu satır olmalı
   ).exclude(
       kasa_adi='virman'
   )
   ```

## Özet

| Kasa | Gelir/Gider Raporu | Products Sayfası |
|------|-------------------|------------------|
| Servis | ✅ Görünür | ✅ Görünür |
| Merkez Satış | ❌ Görünmez | ✅ Görünür (Merkez Ekstra) |
| Virman | ❌ Görünmez | ✅ Görünür (Merkez Ekstra) |
