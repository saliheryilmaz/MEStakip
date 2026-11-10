# MEStakip ↔ DİA Entegrasyonu: Mentorluk Rehberi

Bu belge, repodaki `dia_integration` uygulamasının veri akışını, cari ve stok kartlarının eşlemesini ve entegrasyonu güvenli biçimde çalıştırmayı açıklar. DİA Web Servis erişimi tanımlanınca bu rehber operasyonel başlangıç noktası olarak kullanılabilir.

## 1. Önce yönü seç: hangi sistem ana kaynak?

Entegrasyon iki yönde de işlem yapabilecek kod içeriyor:

```text
DİA → MEStakip: listele → alanları eşle → yerel kaydı oluştur/güncelle
MEStakip → DİA: yerel modeli eşle → ekle veya güncelle servisini çağır
```

İlk kurulum için **DİA'yı ana kaynak kabul edip önce yalnızca DİA → MEStakip yönünde başlamak** önerilir. Çünkü cari ve ürün kartlarını DİA'ya girdiğini belirttin. MEStakip'teki `dia_key`, bir kaydı DİA'daki kartla eşler. DİA'dan gelen kayıtlar `cari_kodu` veya `stok_kodu` ile `update_or_create` edildiği için kodu aynı olan yerel kayıt güncellenir; farklı kodla varsa ayrı kayıt açılabilir.

MEStakip'ten DİA'ya gönderim kodu da var (`CariService.dia_ya_gonder`, `StokService.dia_ya_gonder`), ama bu çağrı DİA'da gerçek kayıt oluşturabilir veya değiştirebilir. İlk eşleşmeler ve alan kontrolleri yapılmadan bu yönü toplu kullanma.

## 2. Katmanlar ve sorumlulukları

```text
Management command / Django admin / Celery task
                     │ ne zaman çalışacağını belirler
                     ▼
         CariService veya StokService
          ├─ sayfalama ve iş akışı
          ├─ Django veritabanı işlemleri
          ├─ SyncLog ve kayıt hataları
          └─ DiaMapper çağrısı
                     │
            DiaMapper: alanları çevirir
                     │
               DiaClient: HTTP/API
                     │
                     ▼
                    DİA
```

- **`client/dia_client.py` — `DiaClient`:** URL oluşturur, login/session yönetir, JSON POST çağrısı yapar, DİA cevap kodlarını exception'a çevirir. İş kuralları ve Cari/Stok ORM işlemleri burada olmamalı.
- **`mappers/cari_mapper.py`, `mappers/stok_mapper.py`:** DİA JSON alanlarını MEStakip model alanlarına, gerektiğinde de ters yönde dönüştürür. Mapper mümkün olduğunca saf dönüşüm kodu olmalı; ağ ve veritabanı çağırmamalı.
- **`services/cari_service.py`, `services/stok_service.py`:** Senkronizasyonun iş akışıdır. API'den sayfa alır, her kaydı mapper'dan geçirir, veritabanına kaydeder ve sonuç/hata sayılarını tutar.
- **`models.py`:** Entegrasyon bağlantı bilgisi, senkronizasyon geçmişi ve API çağrı loglarının tabloları.
- **`mixins.py`:** Cari/Stok modeline ortak `dia_key`, sync durumu ve zaman alanlarını ekler.
- **`management/commands/`:** Terminalden bağlantı testi ve elle senkronizasyon.
- **`tasks.py`:** Aynı servisleri Celery arka plan görevlerinden çağırır.
- **`erp/views.py`, `erp/admin.py`, `templates/erp/dia_durum.html`:** Yönetim ekranı ve admin işlemleri. UI/task katmanı API payload'larını kendisi kurmamalı; service çağırmalı.
- **`migrations/`:** Django veritabanı şemasının sürümlü tanımları.

## 3. `DiaClient`: ham API katmanı

### Login ve oturum

DİA servisleri önce `sis` modülündeki `login` ile oturum açar. Login cevabındaki `msg`, sonraki isteklerde kullanılacak `session_id` olur. `with DiaClient() as client:` kullanımı login'i başlatır; blok bitince logout edip HTTP bağlantısını kapatır.

Bu repodaki login gövdesi kabaca şöyledir:

```python
{
    "login": {
        "username": "...",
        "password": "...",
        "disconnect_same_user": True,
        "params": {"apikey": "..."},  # API anahtarı varsa
    }
}
```

API anahtarı boşsa `params` gönderilmez. Anahtar, parola gibi yalnızca ortam değişkeninden okunmalı; loglara yazılmamalı.

### Ortak çağrı ve CRUD yardımcıları

`_cagir(modul, servis_adi, data)` login olmuş oturum ve firma/dönem kodunu ekleyip şu adrese POST eder:

```text
https://<sunucu_kodu>.ws.dia.com.tr/api/v3/<modul>/json
```

Örneğin `modul='scf'`, `servis_adi='scf_carikart_listele'` olur. `listele`, `getir`, `ekle`, `guncelle`, `sil` bu ortak çağrının etrafındaki küçük yardımcı metodlardır:

```python
with DiaClient() as client:
    cariler = client.listele(
        modul='scf',
        servis_adi='scf_carikart_listele',
        limit=5,
        offset=0,
    )
```

Bu çağrı **DİA'dan okur**, kendi başına `erp.Cari` tablosuna kayıt yapmaz. Veritabanına yazma service katmanında gerçekleşir.

`_yanit_isle`, `code == 200` kontrolü yapar; 401, 402/405, 406 ve 419 gibi hataları `exceptions.py` içindeki sınıflara dönüştürür. Böylece üst katmanlar ağ/API hatasını kayıt eşleme hatasından ayırabilir.

## 4. Cari kart akışı, metottan veritabanına

Komutun çağrı zinciri:

```text
python manage.py dia_sync_cari --tam
  → management/commands/dia_sync_cari.py
  → CariService.dia_dan_senkronize_et(delta=False)
  → DiaClient.listele('scf', 'scf_carikart_listele', ...)
  → CariMapper.dia_to_fields(dia_kayit)
  → Cari.objects.update_or_create(cari_kodu=..., defaults=...)
  → SyncLog / SyncHataKaydi
```

Önemli parçalar:

1. `SyncLog` başta oluşturulur; işlem sonunda toplam, başarılı, hatalı kayıt ve durumla tamamlanır.
2. Liste `limit`/`offset` ile sayfalanır. Her DİA kartı tek tek işlenir; bir kayıttaki hata diğer kayıtları durdurmadan `SyncHataKaydi` olarak kaydedilir.
3. `CariMapper.dia_to_fields` API alan adlarını model alanlarına dönüştürür. Örnek: `carikartkodu → cari_kodu`, `unvan → unvan`, `tckimlikno → tc_kimlik_no`, `_key → dia_key`.
4. Yerel eşleştirme `cari_kodu` üzerinden yapılır. Bulursa günceller, bulamazsa ekler. DİA anahtarı da `dia_key` olarak saklanır.
5. Delta modunda son başarılı/kısmi sync logunun bitişinden 15 dakika geriye giden `_date >= ...` filtresi gönderilir. Bu geriye pay, sınır zamanındaki kayıtları kaçırmamak içindir.

Örnek ham cevap kaydı (temsili):

```python
{
    "_key": 78123,
    "_date": "2026-10-22 12:30:00",
    "carikartkodu": "MUST-001",
    "unvan": "Örnek Müşteri",
    "carikarttipi": "AL",
    "durum": "A",
    "il": "İstanbul",
}
```

Bu, `CariMapper` ile yaklaşık şu yerel alanlara dönüşür:

```python
{
    "cari_kodu": "MUST-001",
    "unvan": "Örnek Müşteri",
    "tip": CariTip.ALICI,
    "durum": CariDurum.AKTIF,
    "sehir": "İstanbul",
    "dia_key": "78123",
}
```

Mapper ayrıca Decimal, telefon/adres, vergi kimliği, bakiye ve not alanlarını dönüştürür. Cari modelinin kabul ettiği alan/uzunluklarla DİA modelindeki alanları karşılaştırmak gerekir; API belgelerinde bulunan her alan yerel modele aktarılmıyor.

## 5. Ürün/stok kartı akışı

Ürün kartı MEStakip terminolojisinde `StokKart` olarak modellenmiş. Zincir cariyle aynı, servis ve mapper farklı:

```text
dia_sync_stok
  → StokService.dia_dan_senkronize_et
  → scf_stokkart_listele
  → StokMapper.dia_to_fields
  → StokKart.objects.update_or_create(stok_kodu=...)
```

Eşlenen başlıca alanlar: `stokkartkodu → stok_kodu`, `aciklama → aciklama`, `stokkartturu → tur`, `birimadi → ana_birim`, barkod, marka, KDV, fiyat ve `note → notlar`. `_key`, `dia_key` olur. Stok türleri DİA kodları (`TCR`, `HMM`, `YRM`, `MAM`, `HZM`) ile Django `TextChoices` seçenekleri arasında çevrilir.

Stok kartı ve **depo miktarı ayrı kavramlardır**. `scf_stokkart_listele` kart alanlarını listeler. `StokService.depo_miktarlarini_guncelle` stok başına ek servis çağrıları yapıp depo bazlı miktarları `StokDepoMiktari`'na yazar. Önce depo tanımları `Depo` modeline alınmalıdır (`--depolar`); ardından miktar sync yapılabilir (`--miktarlar`). Bu ikinci adım çok sayıda çağrı üretebilir.

## 6. Senkronizasyon takibi

- **`DiaSyncMixin`:** İş modellerine `dia_key`, `son_sync_tarihi`, `dia_son_degisiklik`, `sync_durumu` alanları sağlar.
- **`SyncLog`:** Bir sync çalışmasının modül, tetikleyen, başlangıç/bitiş, toplam/başarılı/hatalı sayılarını tutar.
- **`SyncHataKaydi`:** Hangi kayıt ve serviste ne hatası olduğunu tutar.
- **`ApiIstekLog`:** DİA API isteğinin servis adını, süresini, cevap kodunu ve sonucunu takip eder. `DIA_LOG_API_REQUESTS` ayarıyla kapatılabilir.
- **`DiaBaglanti`:** Admin/durum ekranı için sunucu, firma/dönem ve yetkili firma/dönem/depo bilgisinin önbelleğini tutar. Şu an `DiaClient` esas bağlantı değerlerini Django `settings` üzerinden okuyor; `DiaBaglanti` kaydını oluşturmak tek başına parola/API anahtarı yapılandırmak anlamına gelmez.

## 7. Erişim bilgileri gelince izlenecek sıra

Bilgileri sadece uygulamanın secret/env ayarlarına koy. `.env` dosyasını Git'e ekleme; Coolify kullanılıyorsa Application → Environment Variables bölümüne gir. Gerekli adlar:

```env
DIA_SERVER_CODE=...
DIA_USERNAME=...
DIA_PASSWORD=...
DIA_API_KEY=...
DIA_FIRMA_KODU=...
DIA_DONEM_KODU=...
```

1. Sunucu/API kullanıcı/API anahtarı ve firma/dönem bilgilerini DİA'dan doğrula.
2. Kullanıcıda Web Servis çağırma ve gerekli modül yetkileri olsun. Cari okuma için Cari Kart Listeleme; stok okuma için Stok-Malzeme Listeleme gerekir.
3. `python manage.py dia_test_baglanti` ile login ve yetkili firma/dönem sorgusunu dene.
4. `python manage.py dia_sync_cari --kuru-calis --sayfa 5` ile az sayıda cari getir; `python manage.py dia_sync_stok --kuru-calis --sayfa 5` ile az sayıda stok getir.
5. Mapper alanlarını DİA Web Service Tester'dan alınan gerçek cevapla kontrol et. Örnek kayıtta boş gelen alanlarla temsilî örneğe güvenme.
6. Yedek al; sonra tam içe aktarımı yap: `python manage.py dia_sync_cari --tam --sayfa 50` ve `python manage.py dia_sync_stok --tam --sayfa 50`.
7. Django admin / DİA durum ekranında kayıt sayılarını, örnek kayıtları, `dia_key` ve sync hatalarını incele.
8. Ancak ilk sonuçlar doğrulanıp hangi sistemin ana kaynak olacağı kararlaştırıldıktan sonra otomatik görevleri aç.

`--kuru-calis`, **iş modeli kayıtlarını yazmayan** bir bağlantı/ilk sayfa denemesidir. DİA'da okuma çağrısı yaptığı için kontör tüketebilir. Ayrıca API istek logu açıksa `ApiIstekLog` tablosuna log yazabilir; dolayısıyla “hiç veritabanına yazmıyor” şeklinde yorumlanmamalı. Bu seçenek mapper'ın bütün sayfalarını ve alan doğruluğunu test etmez.

## 8. Celery otomasyonu: ilk gün açma

`dia_sync_zamanlama_kur` varsayılan olarak cari, stok ve fatura delta sync görevlerini **dakikada bir**; stok depo miktarlarını da dakikada bir; ayrıca geceleri tam sync görevlerini kuruyor. Her listeleme çağrısı kontör kullanır ve depo miktarı işi stok başına çağrı yapabilir. İlk veri eşlemesi tamamlanmadan bu komutu çalıştırma. Önce DİA kontör tüketim politikasını sor, çağrı hacmini ölç, sonra makul aralık belirle. Otomasyon için Celery worker ve beat de çalışıyor olmalı.

## 9. Yeni bir DİA modeli ekleme tarifi

Örneğin başka bir kart tipi eklenecekse:

1. DİA WS dokümanında model adını, liste/getir/ekle/güncelle servislerini, zorunlu alanları, yetki kodunu ve cevap JSON'unu bul.
2. MEStakip'te hedef Django modelini ve mevcut alanların tip/uzunluklarını belirle.
3. `mappers/<model>_mapper.py` içinde saf iki yönlü dönüşüm yaz:

```python
class OrnekMapper:
    @staticmethod
    def dia_to_fields(d: dict) -> dict:
        return {
            'yerel_kod': str(d.get('dia_kodu') or '').strip(),
            'ad': str(d.get('dia_adi') or '').strip(),
            'dia_key': str(d.get('_key') or ''),
        }

    @staticmethod
    def model_to_dia(obj) -> dict:
        kart = {'dia_kodu': obj.yerel_kod, 'dia_adi': obj.ad}
        if obj.dia_key:
            kart['_key'] = obj.dia_key
        return kart
```

4. `services/<model>_service.py` içinde `DiaClient.listele` + sayfalama + `update_or_create` akışını kur; aynı zamanda SyncLog ve kayıt hata kayıtlarını ekle.
5. `management/commands/dia_sync_<model>.py` ile manuel ve sınırlı çalıştırma ekle. Önce DİA'dan okuyan tek yönü kur; dışa yazmayı ayrı, açıkça tetiklenen bir işlem yap.
6. İhtiyaç varsa Celery task, admin aksiyonu/durum ekranı ve periyodik zamanlamayı ekle. Sırf yeni model geldi diye yüksek sıklıkta otomasyon açma.
7. DİA Tester'dan gerçek bir JSON cevapla mapper doğrula; canlı ekle/güncelleyi önce demo veya kontrollü tek kayıtla dene.

## 10. Şu an dikkat gerektiren kod noktaları

1. **DİA'dan içe alma, “kuru çalışma” sanıldığı kadar kapsamlı değil:** Cari/Stok `--kuru-calis` sadece ilk API sayfasını yazmadan çeker. `CariMapper`/`StokMapper` ve model kaydını denemiyor. Tam güvenli prova için mapper doğrulaması veya gerçek test veritabanı ayrıca gerekir.
2. **Cari satıcı kodu:** DİA'nın `ScfCarikartModel` belgesinde satıcı kodu `ST`. İçe alma `ST`'yi tanıyor ve MEStakip'ten dışa gönderimde kod artık `ST` üretiyor. Gerçek yazma çağrısından önce DİA Web Service Tester veya demo firmayla doğrula.
3. **Stok alan eşlemesi canlı cevapla doğrulanmalı:** `anabirimkey`, `markaack`, `gercek_stok` gibi alan adları ve liste servisinin gerçekten döndürdüğü alan kümesi DİA Tester cevabına göre teyit edilmeli. API modelinde alanın bulunması, liste görünümünde kesin döndüğü anlamına gelmeyebilir.
4. **Servis hata kodu ile HTTP durum kodu ayrımı:** `DiaClient._yanit_isle` DİA'nın JSON `code` değerini exception seçimi için kullanıyor; DİA bazı lisans/servis hatalarını HTTP 200 içinde JSON koduyla döndürebilir. Resmî hata tablosuna göre gerçek cevaplarla exception eşlemesini doğrula.
5. **`DiaBaglanti` parola/API key saklama yeri değil:** Maskeli şifre alanı var, fakat istemci settings kullanıyor. Gerçek sırları DB modeline, admin'e, loga veya komut satırı argümanına yazma.
6. **DİA → MEStakip senkronu yerel alanları ezebilir:** `update_or_create(defaults=...)` eşlenen alanları her çalışmada DİA değerleriyle günceller. Hangi alanların DİA'ya ait olduğunu belirle; MEStakip'e özel alanları mapper'ın `defaults` sözlüğüne ekleme.
7. **Müşterilere SaaS olarak sunma:** Mevcut `DiaClient` kimlik bilgilerini global Django settings/env'den okuyor; bu tek DİA bağlantısı/tek kurulum varsayımıdır. Her müşterinin ayrı DIA'sı olacaksa tenant başına bağlantı seçimi, sırların güvenli saklanması, her Celery işinde tenant kimliği ve tenant bazlı sync logları eklenmeli. Global `DIA_*` env ayarları tüm müşterileri birbirinden ayırmaya yetmez.

## İlgili dosyalar

- `dia_integration/client/dia_client.py`
- `dia_integration/mappers/cari_mapper.py`
- `dia_integration/mappers/stok_mapper.py`
- `dia_integration/services/cari_service.py`
- `dia_integration/services/stok_service.py`
- `dia_integration/mixins.py`
- `dia_integration/models.py`
- `dia_integration/management/commands/dia_test_baglanti.py`
- `dia_integration/management/commands/dia_sync_cari.py`
- `dia_integration/management/commands/dia_sync_stok.py`
- `dia_integration/tasks.py`
- `dia_integration/management/commands/dia_sync_zamanlama_kur.py`
- `erp/models.py` (`Cari`, `StokKart`, `Depo`, `StokDepoMiktari`)
