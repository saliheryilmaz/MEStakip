# MEStakip × DİA ERP Entegrasyonu — Analiz Raporu ve Entegrasyon Planı

**Hazırlanma amacı:** MEStakip'i basit bir sipariş/stok takip panelinden, DİA ERP ile senkron çalışan kapsamlı bir ön muhasebe ve lastik yönetim sistemine dönüştürmek.

**Kapsam:** (1) DİA Web Servis API'nin tam analizi, (2) MEStakip'in mevcut Django mimarisinin analizi, (3) entegrasyon stratejisi ve mimari öneri, (4) adım adım entegrasyon planı.

**Not:** Bu doküman yalnızca analiz ve plandır — talebiniz doğrultusunda henüz hiç kod yazılmadı. Kod aşamasına geçmeden önce bu planı birlikte gözden geçireceğiz.

---

## İçindekiler

1. [MEStakip'in Mevcut Mimarisi](#1-mestakipin-mevcut-mimarisi)
2. [DİA API'nin Sunduğu İmkanlar](#2-dia-apinin-sunduğu-imkanlar)
3. [Birebir Entegre Edilebilecek Modüller](#3-birebir-entegre-edilebilecek-modüller)
4. [Yeni Oluşturulması Gereken Modeller](#4-yeni-oluşturulması-gereken-modeller)
5. [Mevcut Modellerin Kullanılabileceği Alanlar](#5-mevcut-modellerin-kullanılabileceği-alanlar)
6. [Django Servis Mimarisi Önerisi](#6-django-servis-mimarisi-önerisi)
7. [Benim Tasarım Tercihim](#7-benim-tasarım-tercihim)
8. [Temiz ve Sürdürülebilir Mimari](#8-temiz-ve-sürdürülebilir-mimari)
9. [Riskler ve Dikkat Edilmesi Gerekenler](#9-riskler-ve-dikkat-edilmesi-gerekenler)
10. [Adım Adım Entegrasyon Planı](#10-adım-adım-entegrasyon-planı)
11. [Sıradaki Adım](#11-sıradaki-adım)

---

## 1. MEStakip'in Mevcut Mimarisi

### 1.1. Genel yapı

MEStakip, tek bir Django app'i (`dashboard`) üzerine kurulu, monolitik bir yapı. Proje düzeni:

```
metis_admin/          → Django proje ayarları (settings, urls, wsgi/asgi)
dashboard/            → Tek app: models, views, forms, admin, urls, utils
templates/dashboard/  → ~45 HTML şablonu
static/                → Derlenmiş frontend varlıkları (Vite çıktısı)
src-modern/            → Frontend kaynak (statik HTML/CSS/JS şablon seti)
```

`INSTALLED_APPS` içinde Django'nun kendi app'leri dışında sadece `dashboard` var. Bu, projenin büyüklüğüne göre (7.475 satırlık `views.py`, 923 satırlık `models.py`, 63 migration) artık **app-bölünmesi gereken bir olgunluğa** ulaştığının işareti.

### 1.2. Mevcut modeller (tespit edilen 15 model)

| Model | Amaç | Cari/Stok ile ilişkisi |
|---|---|---|
| `UserProfile` | Rol yönetimi (admin/yönetici/misafir) | — |
| `Siparis` | Lastik/Akü/Jant siparişi | `cari_firma` **CharField** (serbest metin) |
| `Event` / `Notification` | Takvim ve bildirim | — |
| `TransactionCategory` / `Transaction` | Gelir-gider / kasa hareketi (nakit, kredi kartı, cari, sanal pos, havale...) | `cari` **DecimalField** (tutar alanı, cari kart değil) |
| `CikmaLastik` | Müşteriden çıkan lastik takibi | `musteri_adi` serbest metin |
| `MalzemeDosya` / `MalzemeHareketi` | Excel'den içe aktarılan servis fiş hareketleri | `musteri` serbest metin |
| `JokerSatisDosya` / `JokerSatisHareketi` | Excel'den içe aktarılan toptan satış hareketleri (kâr hesaplı) | `cari` serbest metin |
| `Quotation` / `QuotationItem` | Teklif ve teklif kalemleri | `cari` serbest metin |
| `GarantiBelgesi` / `GarantiBelgesiLastik` | Satış garanti belgesi | `musteri_adi` serbest metin |
| `LastikModelBilgisi` | Lastik model adı → mevsim eşleştirme (AI destekli, self-learning) | — |

### 1.3. Kritik tespit: Cari ve Stok, gerçek anlamda modellenmemiş

Proje adı "stok takip" olsa da, incelemede **ilişkisel bir Cari (müşteri/tedarikçi) kartı ya da Stok (ürün/lastik) kartı modeli bulunmuyor**:

- Her yerde cari bilgisi `CharField` olarak serbest metin tutuluyor (`Siparis.cari_firma`, `Quotation.cari`, `CikmaLastik.musteri_adi`, `JokerSatisHareketi.cari`, `MalzemeHareketi.musteri`). Aynı müşteri farklı yazımlarla birden fazla kez var olabiliyor, bakiye/cari hesap kavramı yok.
- Stok/ürün tarafında da kalıcı bir "şu an depoda X adet Y lastiği var" tablosu yok. Envanter benzeri veriler (`JokerSatisHareketi`, `MalzemeHareketi`) aslında Excel'den içe aktarılmış **geçmiş hareket kayıtları**; çalışan bir stok bakiyesi/ledger değil.
- Bu, hem mevcut sistemin bir eksiği hem de DİA entegrasyonu için **iyi haber**: Cari ve Stok modellerini sıfırdan, DİA'nın veri modeliyle uyumlu şekilde tasarlama fırsatınız var — eski/çelişkili bir yapıyı DİA'ya zorla uydurmak zorunda değilsiniz.

`Siparis` modeli ise DİA'daki Sipariş/Fatura kavramına en yakın olan, ilişkisel olmayan (ürün kalemi yok, tek satırlık) basit bir kayıt.

### 1.4. Views katmanı: iş mantığı view'larda

`dashboard/views.py` **7.475 satır**, hepsi fonksiyon tabanlı view (class-based view veya DRF yok). Servis katmanı, serializer, repository gibi ayrımlar mevcut değil — sorgular, agregasyonlar (`Sum`, `Case/When`), Excel export, PDF üretimi, e-posta gönderimi gibi iş mantığının tamamı view fonksiyonlarının içinde. Örneğin `products` view'ı tek başına ~150+ satır sorgu/hesaplama içeriyor.

Bu, küçük ölçekte çalışsa da DİA entegrasyonu gibi **çok adımlı, hataya açık, dış sisteme bağımlı** bir iş için sürdürülemez: yeniden deneme (retry), loglama, senkronizasyon durumu gibi kaygılar view içine sızarsa kod hızla yönetilemez hale gelir. Bölüm 6-8'de önerdiğim mimari tam olarak bu sorunu çözmeyi hedefliyor.

### 1.5. URL yapısı

Tek `urls.py` dosyasında ~90 route, düz liste halinde (namespace/prefix gruplaması yok). `api/` öneki bazı JSON endpoint'lerinde var ama tutarlı bir REST tasarımı (versiyonlama, kaynak bazlı gruplama) yok. DİA entegrasyonu için yeni bir app (`dia_integration` veya tercih ettiğiniz isim) ile ayrı, kendi `urls.py`'si olan bir yapı kurmak, mevcut `dashboard` app'ini bozmadan ilerlemenizi sağlar.

### 1.6. Bağımlılıklar (`requirements.txt`)

Django 5.1.4, gunicorn, whitenoise, crispy-forms, django-import-export, django-jazzmin, pandas/openpyxl (Excel), xhtml2pdf, python-dotenv, requests. **Celery, Django-Q, DRF, redis yok** — otomatik/periyodik senkronizasyon ve kuyruk sistemi için bunlardan en az birini ekleyeceğiz (bkz. Bölüm 6).

Mevcut dış servis entegrasyon örneği `dashboard/groq_client.py` (Groq AI API'si için) — `urllib` ile yazılmış, session/retry/loglama olmayan minimal bir fonksiyon. DİA client'ını tasarlarken bunu bir başlangıç noktası değil, **kaçınılması gereken bir örüntü** olarak ele alacağız (session yeniden kullanımı, retry, yapılandırılmış hata sınıfları olmadan).

### 1.7. Deployment ve ortam

PythonAnywhere üzerinde, geliştirmede SQLite / production'da MySQL. `DEBUG` ortam değişkeni yoksa varsayılan olarak `True` — production'a yanlışlıkla debug modunda deploy riski var. Ayrıca `settings.py` içinde **MySQL production şifresi düz metin olarak koda gömülü** ve `SECRET_KEY` için de bir fallback değer tanımlı. Bunlar DİA entegrasyonundan bağımsız, ama DİA API kullanıcı adı/şifresi gibi yeni bir hassas bilgi setini sisteme eklerken **öncelikle çözülmesi gereken** güvenlik konuları: tüm sırlar `.env` üzerinden okunmalı, kod içinde fallback/gömülü değer olmamalı, mevcut açığa çıkmış MySQL şifresi de fırsat bu fırsatken değiştirilmeli.

### 1.8. Kodlama standartları — genel değerlendirme

**İyi yönler:** Modeller genelde açıklayıcı `verbose_name` ve docstring içeriyor; `utils.py` içindeki yardımcı fonksiyonlar (örn. `parse_decimal_value` — TR/EN ondalık ayracı normalizasyonu) temiz ve tek sorumluluklu; `ModelAdmin`/`ModelForm` kullanımı standart Django pratiklerine uygun.

**İyileştirilmesi gereken yönler:** Dev boyutlu `views.py`; servis katmanı yok; tip belirteci (type hint) neredeyse hiç kullanılmamış; iş mantığı ile sunum mantığı (HTML render, Excel export) aynı fonksiyonda iç içe; bazı model alanları (`Transaction.kasa_adi`, `musteri_odeme_tutari` gibi) `CharField` olarak tutarken aslında sayısal veya ilişkisel olmalı. Bu tespitler, sizin talep ettiğiniz "Clean Architecture, SOLID, servis katmanı, tip hint, küçük fonksiyonlar" prensiplerinin **DİA entegrasyon kod tabanında baştan doğru kurulmasının** neden önemli olduğunu doğruluyor — mevcut `views.py` alışkanlığını yeni modüle taşımayacağız.

---

## 2. DİA API'nin Sunduğu İmkanlar

*(Kaynak: yüklediğiniz `DİA WS API Kılavuzu`, 415 sayfa)*

### 2.1. Genel mimari

- **Protokol:** JSON tabanlı REST Web Servis. Her modül kendi kaynak URL'sine sahip: `https://SUNUCUKODU.ws.dia.com.tr/api/v3/{modul}/json` (örn. `.../scf/json`, `.../bcs/json`).
- **Kimlik doğrulama:** Önce `login` servisi çağrılır (`username`, `password`, `disconnect_same_user`), başarılı olursa `session_id` döner. Sonraki **tüm** çağrılarda `session_id`, `firma_kodu`, `donem_kodu` zorunlu parametrelerdir. Oturumun **timeout süresi 1 saat**, her çağrı bu süreyi sıfırlar. Session bittiğinde `419 LOGIN_TIMEOUT` döner — yeniden login gerekir.
- **Yetkilendirme modeli:** Web servis üzerinden yapılan her işlem, o DİA kullanıcısının masaüstü istemcideki ekran yetkisiyle birebir sınırlı. Yani entegrasyon için kullanılacak DİA kullanıcısına ilgili modüllerde (Cari, Stok, Fatura, İrsaliye, Kasa, Sipariş...) yetki tanımlanmış olmalı.
- **Firma/Dönem/Şube/Depo kavramı:** Neredeyse tüm servisler `firma_kodu` ve `donem_kodu` ister. Bu gerçek (numerik) kodlar `sis_yetkili_firma_donem_sube_depo` servisiyle sorgulanır; yanıt firma → dönem(ler) → şube(ler) → depo(lar) hiyerarşisini ve kullanıcıya tanımlı varsayılan `_key` değerlerini (`ontanimli__key_scf_carikart` gibi) döner. **Bu servis, entegrasyonun ilk adımında bir kez çağrılıp yerelde önbelleğe alınmalı.**
- **Kontör sistemi:** Her servis çağrısı **0,5 kontör** düşer (login/logout hariç). Bu, senkronizasyon sıklığı ve toplu işlem tasarımı için doğrudan **maliyet ve performans etkisi** olan bir kısıt — Bölüm 9'da detaylandırıyorum.
- **Webhook desteği yok.** Dokümanda push/webhook mekanizmasına dair hiçbir servis bulunmuyor. Yani "DİA'da bir şey değiştiğinde bize haber versin" mümkün değil; **DİA → MEStakip yönü polling (periyodik çekme) ile** kurulmalı. Bu, istediğiniz "otomatik belirli aralıklarla senkronizasyon" özelliğini opsiyonel değil, **zorunlu** kılıyor.

### 2.2. Servis türleri (her modülde tekrar eden ortak desen)

DİA'da servis isimlendirmesi modele göre standart bir sonek kullanır — bu, entegrasyon kodunuzda genel bir `DiaClient` + jenerik CRUD metodlarıyla büyük oranda tekrar kullanılabilir bir yapı kurmanıza imkân verir:

| Sonek | Anlamı | Zorunlu parametreler | Dönüş |
|---|---|---|---|
| `_listele` | Liste getirir (ilgili DİA ekranındaki veriyi) | `filters`, `sorts`, `params`, `limit`, `offset` (hepsi opsiyonel) | `result`: liste |
| `_getir` | Tek kayıt getirir | `key` | `result`: tekil obje (bağlı alt modeller ve foreign-key referanslar da otomatik gelir) |
| `_ekle` | Yeni kayıt oluşturur | `kart` (obje) | `key`: oluşan kaydın `_key`'i, `msg` |
| `_guncelle` | Var olan kaydı günceller | `kart` içinde `_key` | `key`, `msg` |
| `_sil` | Kayıt siler | `key` | `msg` |

Önemli detaylar:
- **Filtreleme:** `{"field": ..., "operator": ..., "value": ...}` yapısı; operatörler `<, >, <=, >=, !, =, IN, NOT IN`. Operatör verilmezse "içinde geçen" mantığıyla çalışır.
- **Delta senkronizasyon için altın alan:** `_date` alanı, kaydın son ekleme/güncelleme zamanını tutar. `filters: [{"field": "_date", "operator": ">=", "value": "<son_sync_zamani>"}]` ile **sadece değişen kayıtları** çekmek mümkün — periyodik senkronizasyonu kontör-verimli hale getirmenin anahtarı budur.
- **Bağlantılı (`_key_` önekli) alanlar:** Foreign key alanlarıdır. Ya doğrudan DİA `_key` numarası verilir, ya da `{"kod": "..."} ` gibi bir filtre objesiyle DİA'nın kendisinin ilgili kaydı bulup key'i doldurması sağlanır. Bu, örneğin cari eklerken vergi dairesi veya şehir gibi referans tabloların key'ini bilmenizi gerektirmez.
- **Alt modeller (`m_` önekli):** Örn. stok kartında `m_birimler`, `m_barkodlar`; cari kartta `m_adresler`, `m_yetkililer`; faturada `m_kalemler`. Ekleme/güncellemede sadece değişen alt kayıt gönderilir; güncellemede alt kayıtta `_key` varsa günceller, yoksa yeni satır açar. Silinecek alt kayıtlar `m_silinecek_<alanadı>` listesiyle belirtilir.
- **Combo (seçimli) alanlar:** Örn. stok kartı türü (`TCR` = Ticari Mal gibi) kısa kodlarla gönderilir; geçersiz değerde `400` hatası döner.
- **Hata kodları:**

| Kod | Anlam |
|---|---|
| 200 | Başarılı |
| 400 | Geçersiz parametre (`msg` detay içerir) |
| 401 | Yetki hatası / hatalı kullanıcı-şifre |
| 402 / 405 | Lisans hatası |
| 406 | Yetersiz kontör |
| 419 | Session timeout |
| 500 / 501 | Sunucu/işlem hatası |

- **Rapor servisi (bonus):** `rpr_raporsonuc_getir` ile DİA'daki hazır/özel raporlar `pdf/html/excel/json` formatında base64 olarak alınabilir (örn. cari hesap ekstresi scf1110a). İleride "müşteriye otomatik ekstre gönderimi" gibi bir özellik isterseniz kullanılabilir.

### 2.3. Talep ettiğiniz işlemlere karşılık gelen servis modülleri

Dokümanı tarayarak, istediğiniz her işlem grubu için ilgili DİA modülünü ve servis ailesini çıkardım:

| İstediğiniz işlem | DİA modülü | İlgili servis ailesi (örnek) |
|---|---|---|
| Cari oluşturma/güncelleme/listeleme | **SCF - Cari** | `scf_carikart_ekle/guncelle/listele/getir/sil` |
| Cari bakiye sorgulama | **SCF - Cari** | `scf_carikart_hesapdurumu_getir`, `scf_carikart_hareket_listele` (liste `params` içinde bakiyeye irsaliye dahil edilsin mi gibi seçenekler var) |
| Cari adres/yetkili/banka bilgisi | **SCF - Cari** | `scf_carikart_adresleri_*`, `scf_carikart_yetkili_*`, `scf_carikart_banka_*` |
| Stok kartı oluşturma/güncelleme/listeleme | **SCF - Stok-Hizmet** | `scf_stokkart_ekle/guncelle/listele/getir/sil` |
| Stok birimleri, alternatif/ek malzeme | **SCF - Stok-Hizmet** | `scf_stokkart_birimleri_*` (alt model) |
| Lastik stoklarının depo bazlı senkronu | **SCF - Stok-Hizmet** | `scf_stok_depo_miktarlari_listele`, `scf_stok_varyant_miktarlari_listele` |
| Barkod üretme/okutma | **SCF - Stok-Hizmet / Fatura** | `scf_stokkart_barkod_uret`, `scf_barkod_okut`, `scf_karebarkod_listele` |
| Seri/Lot takibi (lastik DOT/seri no için değerlendirilebilir) | **SCF - Stok-Hizmet** | `scf_serilot_ekle/guncelle/listele`, `scf_lot_listele`, `scf_seri_listele` |
| Depo sayımı | **SCF - Stok-Hizmet** | `scf_sayimfisi_ekle/kapat/listele`, `scf_sayimfisi_kalemi_*` |
| Marka tanımları | **SCF - Stok-Hizmet** | `scf_marka_ekle/guncelle/listele` |
| Teklif | **SCF - Teklif/Sipariş/İrsaliye/Fatura** | `scf_teklif_ekle/guncelle/listele/onayla` |
| Siparişler | **SCF - Teklif/Sipariş/İrsaliye/Fatura** | `scf_siparis_ekle/guncelle/listele/getir/sil` |
| İrsaliye | **SCF - Teklif/Sipariş/İrsaliye/Fatura** | `scf_irsaliye_ekle/guncelle/listele/getir/sil` |
| Alış/Satış faturaları | **SCF - Teklif/Sipariş/İrsaliye/Fatura** | `scf_fatura_ekle/guncelle/listele/getir/sil`, `scf_fatura_odeme_hareket_listele` |
| Kasa işlemleri (tahsilat/ödeme dahil) | **SCF - Kasa** | `scf_kasakart_*` (kasa tanımı), `scf_kasaislemleri_ekle/guncelle/listele` (fiş bazlı giriş/çıkış) |
| Taksit / kredi kartı tahsilatı | **SCF - Cari** | `scf_taksit_*`, `scf_kk_tahsilat_*` |
| Depo/Şube bilgisi | **SIS (Sistem)** | `sis_yetkili_firma_donem_sube_depo`, `sis_depo_grubu_listele` |
| Banka hesapları, çek-senet, banka kredisi | **BCS (Banka Çek-Senet)** | `bcs_bankahesabi_listele`, `bcs_ceksenet_*`, `bcs_banka_kredi_*` |
| Genel muhasebe hesap kartı/hareketi | **MUH (Muhasebe)** | `muh_hesapkarti_*`, `muh_hesapkarti_hareket_listele` |

**Önemli not — "Depolar arası transfer":** Dokümanda ayrı, özel bir "transfer fişi" servisi görülmedi. DİA'da depolar arası stok transferi tipik olarak **İrsaliye** (`scf_irsaliye_ekle`) üzerinden, kaynak/hedef depo bilgisiyle bir "dahili sevkiyat" fişi türü açılarak yapılır; ayrıca **Sayım Fişi** (`scf_sayimfisi_*`) modülü de depo bazlı düzeltmeler için kullanılabilir. Kesin fiş türü kodlarını (`fisturu`/tip alanları), uygulama fazında DİA Web Service Tester aracıyla demo ortamda (`diademo`, kullanıcı `ws`/`ws`, firma `34`, dönem `1` — zaten test scriptleriniz hazır) deneyerek netleştireceğiz; bu, kod yazmadan tahmin yürütmek yerine gerçek veriyle doğrulanması gereken bir noktadır.

**Önemli not — "Banka hareketleri":** Dokümanda doğrudan bir "banka hesap ekstresi/hareketi listele" servisi tespit edilemedi; BCS modülü esas olarak çek-senet ve banka kredisi/taksit takibi sunuyor, gerçek banka hesap hareketleri muhasebe (MUH) tarafındaki hesap kartı hareketleriyle (`muh_hesapkarti_hareket_listele`, ilgili banka hesap kartının `_key`'i filtrelenerek) ya da rapor servisiyle alınabilir. Bu nedenle "Banka hareketleri" özelliğini planın **"mümkünse" kısmına uygun şekilde düşük öncelikli ve doğrulama gerektiren** bir madde olarak işaretledim.

---

## 3. Birebir Entegre Edilebilecek Modüller

Aşağıdaki alanlar, DİA tarafında zaten birebir karşılığı olan, "yeni bir iş kuralı icat etmeden, sadece veri eşleme (mapping) yaparak" entegre edilebilecek alanlardır:

- **Cari kart** — DİA `scf_carikart` modeli, MEStakip'e eklenecek yeni `Cari` modeliyle 1:1 eşlenir (ünvan, kod, tip, vergi no/TC no, adres, bakiye).
- **Stok kartı** — DİA `scf_stokkart` modeli, yeni `StokKart` modeliyle 1:1 eşlenir (kod, ad, birim, barkod, marka).
- **Sipariş** — DİA `scf_siparis`, mevcut `Siparis` modelinin köklü biçimde genişletilmiş/kalem bazlı bir hâliyle veya yeni bir modelle eşlenir.
- **İrsaliye / Fatura** — DİA `scf_irsaliye`, `scf_fatura`, yeni modellerle 1:1.
- **Kasa fişi / tahsilat / ödeme** — DİA `scf_kasaislemleri`, yeni `KasaFisi` modeliyle.
- **Depo** — DİA'daki şube/depo hiyerarşisi, yeni `Depo` modeliyle.
- **Barkod okutma** — doğrudan `scf_barkod_okut` çağrısı; yerel model gerektirmeyebilir (arayüz katmanında kullanılır).

Bu alanlarda tasarım kararı azdır; asıl iş DİA'nın beklediği alan adlarını ve zorunlu alanları doğru eşlemektir.

---

## 4. Yeni Oluşturulması Gereken Modeller

Bölüm 1.3'te belirtildiği gibi Cari ve Stok kavramları MEStakip'te hiç yok; bunları ve senkronizasyon altyapısını sıfırdan tasarlamamız gerekiyor:

### 4.1. Çekirdek iş modelleri (yeni `erp` app'i içinde önerilir)

- **`Cari`** — müşteri/tedarikçi ana kartı (unvan, cari kodu, tipi AL/SA, vergi no/TC no, telefon, e-posta, risk limiti, adresler için ayrı `CariAdres` modeli).
- **`StokKart`** — ürün/lastik ana kartı (stok kodu, adı, marka, ebat, mevsim, birim, KDV oranı; barkodlar için ayrı `StokBarkod` modeli).
- **`Depo`** — şube + depo hiyerarşisi (DİA `_key`, ad, şube ilişkisi).
- **`StokDepoMiktari`** — stok × depo bazında güncel miktar (DİA'dan senkronize edilen, salt-okunur önbellek niteliğinde).
- **`Siparis` (v2)`** / **`SiparisKalemi`** — mevcut `Siparis` modelinin kalem bazlı, `Cari` ve `StokKart`'a FK ile bağlanan yeni nesli (mevcut modelle ilişkisi Bölüm 5'te).
- **`Irsaliye`** / **`IrsaliyeKalemi`**
- **`Fatura`** / **`FaturaKalemi`** (alış/satış ayrımı `tur` alanıyla)
- **`KasaFisi`** (tahsilat/ödeme fişleri; kasa hesabı `Kasa` modeliyle ilişkili)
- **`Kasa`** / **`BankaHesabi`** — DİA `scf_kasakart` ve `bcs_bankahesabi` karşılıkları

### 4.2. Entegrasyon altyapısı modelleri (yeni `dia_integration` app'i içinde)

- **`DiaBaglanti`** — sunucu kodu, kullanıcı adı/şifre (şifreli/`.env`'den), firma/dönem kodu, aktif `session_id` ve son alınma zamanı (1 saatlik timeout yönetimi için).
- **`DiaSyncMixin`** *(abstract model, iş modellerine miras verilecek)* — `dia_key` (nullable, unique), `son_sync_tarihi`, `sync_durumu` (senkron/bekliyor/hatalı/yerel-değişiklik) alanları. Böylece her yeni modele (Cari, StokKart, Fatura...) tek tip senkron alanı eklenir.
- **`SyncLog`** — her senkronizasyon çalıştırması (hangi modül, başlangıç/bitiş, kaç kayıt, başarı/hata sayısı, tetikleyen: manuel/otomatik/kullanıcı).
- **`SyncHataKaydi`** — kayıt bazlı hata detayı (hangi yerel kayıt, hangi DİA servisi, hata kodu/mesajı, kaç kez denendi).
- **`ApiIstekLog`** — her DİA çağrısının özet logu (servis adı, süre, HTTP/DİA kod, kontör maliyeti tahmini). Kişisel veri/şifre gibi hassas alanlar maskelenerek saklanır.
- **`SenkronKuyrugu`** — retry/queue mekanizması için bekleyen iş kaydı (model adı, kayıt id, işlem tipi, deneme sayısı, sıradaki deneme zamanı — Celery ile birlikte kullanılacak, bkz. Bölüm 6).

---

## 5. Mevcut Modellerin Kullanılabileceği Alanlar

Mevcut modellerin tamamını çöpe atmıyoruz — bir kısmı doğrudan kullanılabilir, bir kısmı kaynak veri/geçiş verisi olarak değerli:

- **`Siparis`** — DİA `scf_siparis`/`scf_fatura` ile eşlenecek yeni yapıya **kavramsal olarak** en yakın model. Doğrudan genişletmek (kalem modeli eklemek, `Cari`/`StokKart`'a FK bağlamak) yerine yeni `SiparisKalemi` ilişkili yapı kurup, mevcut `Siparis` kayıtlarını **tek seferlik bir migration/data-import script'iyle** yeni yapıya taşımak (veya bir geçiş dönemi boyunca ikisini paralel tutmak) daha güvenli olur.
- **`Transaction`** — DİA kasa fişi (`scf_kasaislemleri`) ile **kavramsal olarak örtüşüyor** ama yapısal olarak uymuyor (DİA'da kasa+ödeme yöntemi ayrı modellenir, burada tek satırda 8 ayrı ödeme yöntemi sütunu var — "wide table" tasarımı). Doğrudan eşlenemez; yeni `KasaFisi` modeline **veri dönüştürme (mapping/transformation) katmanıyla** aktarılabilir, `Transaction` kısa/orta vadede yerel raporlama için paralel yaşamaya devam edebilir.
- **`Quotation`/`QuotationItem`** — yapısal olarak zaten kalem bazlı ve DİA `scf_teklif`'e en hazır model. Teklif modülünü entegre ederken bunu genişletmek (üzerine `dia_key` eklemek), sıfırdan yeni model yazmaktan daha mantıklı.
- **`CikmaLastik`, `JokerSatisHareketi`, `MalzemeHareketi`** — bunlar DİA ile birebir senkron olmayacak, MEStakip'e özgü iş süreçleri (müşteriden çıkan lastik, toptan satış marj takibi, servis fişi excel arşivi). DİA entegrasyonundan **etkilenmemeli**; yalnızca ileride "bu hareketin faturası DİA'da hangi fatura" gibi bir çapraz referans istenirse üzerlerine opsiyonel bir `ilgili_fatura` FK'sı eklenebilir.
- **`UserProfile`** — DİA kullanıcı/yetki kavramıyla karıştırılmamalı; MEStakip kendi rol sistemini korur, DİA credential'ları ayrı bir `DiaBaglanti` modelinde (kullanıcıya değil, firmaya/ortama bağlı) tutulur.

---

## 6. Django Servis Mimarisi Önerisi

Amaç: DİA'yla konuşan kod, mevcut `dashboard` app'ini hiç bozmadan, kendi başına test edilebilir ve genişletilebilir bir katman olarak yaşasın.

### 6.1. Yeni app'ler

```
dia_integration/        ← DİA API ile HAM iletişim + senkron altyapısı
  client/                 (HTTP/oturum yönetimi — DİA'ya özel, iş kuralı içermez)
  services/                (her DİA modülü için bir servis: cari, stok, fatura, irsaliye, siparis, kasa, banka)
  mappers/                 (DİA JSON ⇄ Django model dönüştürücüler)
  exceptions.py            (DiaApiError, DiaAuthError, DiaTimeoutError, DiaValidationError ...)
  models.py                (DiaBaglanti, SyncLog, SyncHataKaydi, ApiIstekLog, SenkronKuyrugu)
  tasks.py                 (Celery görevleri)
  admin.py                 (log/queue izleme paneli)
  management/commands/     (manuel senkron komutları: dia_sync_cari, dia_sync_stok ...)

erp/                     ← MEStakip'in kendi iş modelleri (Cari, StokKart, Depo, Fatura, İrsaliye, Sipariş v2, Kasa)
  models.py                (DiaSyncMixin'den türeyen modeller)
  services/                (yerel iş kuralları: bakiye hesapla, stok rezerve et, vb. — DİA'yı bilmez)
  views.py / urls.py       (mevcut dashboard'dan bağımsız, ama dashboard içinden linklenebilir)
```

`dashboard` app'i böylece **değişmeden kalır**; yeni özellikler ayrı app'lerde büyür, dashboard sadece bunlara bağlantı/menü ekler.

### 6.2. Katmanlar ve sorumluluklar

| Katman | Sorumluluk | Bağımlılık |
|---|---|---|
| `DiaClient` | Login, session yenileme, HTTP çağrısı, kontör/limit farkındalığı, generic `list/get/create/update/delete` metodları | Hiçbir Django modeline bağımlı değil |
| `*Service` (örn. `CariService`) | "Cari senkronize et", "DİA'da cari oluştur" gibi **use-case**'ler; `DiaClient`'ı kullanır, `Mapper`'ı kullanır | `DiaClient` + `Mapper` + ilgili Django modeli |
| `Mapper` | DİA JSON'ını Django modeline, Django modelini DİA `kart` formatına çevirir | Sadece veri dönüşümü, yan etkisi yok — kolay test edilir |
| `tasks.py` (Celery) | Servisleri zamanlanmış/arka planda çağırır, hata durumunda `SenkronKuyrugu`'na yazar | `*Service` |
| View / Management Command / Admin action | Kullanıcının "şimdi senkronize et" butonuna bastığında `*Service`'i (senkron değilse `tasks.py` üzerinden Celery'e) çağırır | `*Service` veya Celery task |

### 6.3. Otomasyon altyapısı için teknoloji seçimi

İstediğiniz (manuel buton, periyodik otomatik çalışma, kuyruk, retry, loglar) için **Celery + django-celery-beat + Redis** önerim; alternatif olarak daha hafif kurulum isterseniz **Django-Q2** de aynı işlevleri (periyodik görev, kuyruk, retry) tek bağımlılıkla (broker olarak doğrudan veritabanı kullanabilir, Redis şart değil) sağlıyor. PythonAnywhere'de Redis/Celery worker'ının **sürekli çalışması** hesap planınıza göre kısıtlı olabilir — bu yüzden Faz 11'de (Bölüm 10) somut bir karar vermeden önce PythonAnywhere planınızın "always-on task" desteğini birlikte teyit edeceğiz.

Retry mekanizması: Celery'nin kendi `retry` + `exponential backoff` desteği kullanılabilir; kalıcı başarısızlıklar `SenkronKuyrugu`/`SyncHataKaydi`'na düşer ve admin panelinden görülüp manuel tetiklenebilir.

### 6.4. Kod kalitesi ilkeleri (talebiniz doğrultusunda)

- Her servis metodu **tek bir iş** yapar (örn. `CariService.senkronize_et(cari: Cari) -> SyncResult`), 30-40 satırı geçen metodlar alt fonksiyonlara bölünür.
- **Type hint zorunlu** (`def carikart_getir(self, key: int) -> CariDTO:`).
- Docstring: her public metodda "ne yapar, hangi DİA servisini çağırır, hangi hataları fırlatabilir".
- DİA'ya özel hatalar için özel `Exception` sınıfları (`DiaAuthError`, `DiaValidationError`, `DiaTimeoutError`, `DiaCreditError`) — view/task katmanı bunları yakalayıp kullanıcıya anlamlı mesaj gösterir.
- Testler: `DiaClient` gerçek HTTP yapmadan `responses`/`unittest.mock` ile mock'lanır; `Mapper`'lar saf fonksiyon oldukları için kolayca birim testle doğrulanır.

---

## 7. Benim Tasarım Tercihim

Sorduğunuz için açıkça belirteyim — ben olsam şu kararları alırdım:

1. **İki ayrı app:** `dia_integration` (DİA'yla konuşan, DİA'ya özel her şey) ve `erp` (MEStakip'in kendi iş modelleri/kuralları). DİA'yı bir gün değiştirmeniz gerekirse (başka bir muhasebe programına geçiş gibi) sadece `dia_integration` değişir, `erp` ve `dashboard` etkilenmez. Bu, **Dependency Inversion**'ın somut hali.
2. **DTO/dataclass kullanımı:** DİA'dan gelen ham `dict`'i doğrudan view'a veya iş mantığına sızdırmam; `Mapper` katmanında `CariDTO`, `StokKartDTO` gibi `@dataclass`'lara çeviririm. Bu hem tip güvenliği sağlar hem de DİA'nın alan adlarını (`carikartkodu`, `unvan` gibi Türkçe/DİA-özel isimler) sistemin geri kalanından izole eder.
3. **Tek yönlü senkron önce, çift yönlü sonra:** İlk fazlarda **DİA → MEStakip** (okuma/senkron) ve **MEStakip → DİA** (yazma, örn. yeni sipariş oluşturunca DİA'da da oluştur) yönlerini **ayrı ayrı, net sınırlarla** kurar, "çift yönlü senkronizasyon" başlığını (ki en riskli kısımdır — çakışma/conflict yönetimi gerektirir) en son, tek yönlü akışlar sağlamlaştıktan sonra ele alırım. Bunu Bölüm 10'daki fazlamada da böyle sıraladım.
4. **"Source of truth" kararını en başta netleştiririm:** Örneğin stok miktarı için DİA mi, yoksa MEStakip mi asıl doğru kaynak? Benim önerim: **stok miktarı ve muhasebesel veriler için DİA asıl kaynak**, MEStakip bunları önbelleğe alıp gösterir; **sipariş/teklif gibi MEStakip'te başlayan iş süreçleri için MEStakip asıl kaynak**, DİA'ya "yazılır". Bu ayrım çakışma yönetimini büyük ölçüde basitleştirir.
5. **Idempotency ilk günden kurallı:** Her `_ekle` çağrısından önce yerel `dia_key` kontrol edilir; varsa `_guncelle`'ye düşülür. Bu, retry sırasında "aynı cariyi 3 kere oluşturma" riskini ortadan kaldırır.
6. **Loglama iş modelinin bir parçası, sonradan eklenen bir özellik değil:** `SyncLog`/`ApiIstekLog` modelleri Faz 1'de, ilk `DiaClient` ile birlikte kurulur — "önce entegrasyonu yaz, sonra loglamayı ekle" yaklaşımı yerine.

---

## 8. Temiz ve Sürdürülebilir Mimari

Clean Architecture'ın dört katmanını MEStakip bağlamına uyarlarsam:

```
┌─────────────────────────────────────────────────────────┐
│  ARAYÜZ (Interface)                                       │
│  Django views, admin actions, management commands,        │
│  Celery task giriş noktaları                               │
└───────────────────────┬───────────────────────────────────┘
                         │  yalnızca çağırır, iş kuralı içermez
┌────────────────────────▼──────────────────────────────────┐
│  UYGULAMA / SERVİS (Application)                           │
│  CariService, StokService, FaturaService, SyncOrchestrator │
│  "Bir cariyi DİA ile senkronize et" gibi use-case'ler       │
└───────────────────────┬───────────────────────────────────┘
                         │  DTO'lar üzerinden konuşur
┌────────────────────────▼──────────────────────────────────┐
│  DOMAIN (saf iş kuralları, framework'ten bağımsız)          │
│  "Bir carinin bakiyesi nasıl hesaplanır", "hangi durumda    │
│  fatura kesilebilir" gibi kurallar — Django'yu bilmez        │
└───────────────────────┬───────────────────────────────────┘
                         │  interface/protocol ile tersine döner
┌────────────────────────▼──────────────────────────────────┐
│  ALTYAPI (Infrastructure)                                   │
│  DiaClient (HTTP), Django ORM repository implementasyonları,│
│  Celery/Redis, e-posta, dosya sistemi                       │
└─────────────────────────────────────────────────────────────┘
```

**Bağımlılık yönü kuralı:** Üst katmanlar alt katmanları *arayüz (protocol/ABC)* üzerinden bilir, somut implementasyonu bilmez. Örneğin `CariService`, `DiaClient` somut sınıfına değil, `CariKaynagi` adlı bir arayüze bağımlı olur; gerçek implementasyon `DiaCariKaynagi` altyapı katmanında yaşar. Bu sayede:

- Domain ve Application katmanları **Django'suz, DİA'sız** birim testlerle doğrulanabilir.
- Yarın DİA yerine başka bir ERP'ye geçilirse (ya da test için sahte bir kaynak kullanılırsa) sadece Infrastructure katmanı değişir.
- SOLID'in **Dependency Inversion** ve **Interface Segregation** ilkeleri doğal olarak uygulanmış olur; her modül (Cari, Stok, Fatura...) kendi dar arayüzüne sahip olur, dev bir "DiaService tanrı sınıfı" oluşmaz.

Bu, ilk fazda "aşırı mühendislik" gibi görünebilir ama sizin taleplerinizin (çift yönlü sync, retry, queue, log, webhook-benzeri otomasyon) doğal olarak büyüyeceği bir alan olduğu için, katmanları en baştan ayırmak orta vadede size zaman kazandırır.

---

## 9. Riskler ve Dikkat Edilmesi Gerekenler

- **Kontör maliyeti:** Her çağrı 0,5 kontör. Örneğin 500 stok kartını her 5 dakikada bir tam listelemek yerine, `_date >= son_sync` filtresiyle **delta senkron** yapmak, kontör tüketimini kritik ölçüde azaltır. Senkron sıklığı ve kapsamı bu kısıta göre tasarlanmalı.
- **Session/timeout yönetimi:** 1 saatlik session ömrü; Celery worker'ların her çalıştırmada login olup olmayacağı ya da session'ı `DiaBaglanti` üzerinden paylaşıp yenileyeceği net kararlaştırılmalı (öneri: paylaşılan, süresi kontrol edilen, gerektiğinde otomatik yenilenen tek session).
- **Yetki eşleşmesi:** Entegrasyon için kullanılacak DİA kullanıcısının masaüstünde de aynı yetkilere sahip olması gerekiyor — DİA tarafında bu kullanıcı/yetki kurulumu proje başlamadan netleşmeli.
- **Veri tutarlılığı / çakışma yönetimi:** Çift yönlü senkron başladığında "aynı kayıt hem MEStakip'te hem DİA'da değiştiyse ne olur" sorusuna net bir politika gerekir (örn. "DİA her zaman kazanır" ya da "en son değişen kazanır" + çakışma log'u).
- **"Depolar arası transfer" ve "banka hareketleri" için doğrulama gerekiyor:** Bölüm 2.3'te belirttiğim gibi bu iki özellik dokümanda net, ayrı bir servisle karşılanmıyor; demo ortamda pratik doğrulama gerektirir.
- **Güvenlik:** DİA kullanıcı adı/şifresi gibi yeni hassas veriler eklenmeden önce mevcut `settings.py`'deki gömülü MySQL şifresi ve `SECRET_KEY` fallback'i temizlenmeli; tüm sırlar `.env`'de olmalı.
- **Test ortamı hazır:** `diademo` sunucusu (kullanıcı `ws`/`ws`, firma kodu `34`, dönem kodu `1`) ve sizin hazırladığınız test scriptleri, Faz 1'den itibaren gerçek API'ye karşı doğrulama yapmamızı sağlayacak — bu büyük bir avantaj.

---

## 10. Adım Adım Entegrasyon Planı

Her faz kendi başına çalışır durumda teslim edilecek şekilde sıralandı; küçük onaylanabilir adımlar halinde ilerleyeceğiz (talebiniz doğrultusunda, her adımda önce ne yapacağımı anlatıp onayınızı alacağım).

| Faz | İçerik | Çıktı |
|---|---|---|
| **0** | Ortam hazırlığı: `.env` yapısı, mevcut gömülü sırların temizlenmesi, `dia_integration` ve `erp` app iskeletlerinin oluşturulması | Boş ama çalışan app'ler, ayarlar |
| **1** | `DiaClient`: login/logout, session yönetimi (1 saat TTL), generic `listele/getir/ekle/guncelle/sil`, hata sınıfları, `ApiIstekLog` | Demo ortamına karşı çalışan, test edilmiş temel client |
| **2** | Cari modülü: `Cari` modeli + `CariService` (DİA→MEStakip senkron + MEStakip→DİA oluşturma/güncelleme) + admin/manuel buton | Cari oluşturma/güncelleme/listeleme/bakiye uçtan uca çalışır |
| **3** | Stok modülü: `StokKart`, `StokBarkod`, `Depo`, `StokDepoMiktari` + `StokService` | Stok kartı CRUD + depo bazlı miktar senkronu |
| **4** | Barkod işlemleri: `scf_barkod_okut` entegrasyonu, barkod üretimi | Barkod okutunca ilgili stok/miktar arayüzde görünür |
| **5** | Sipariş/Teklif: `Quotation` genişletmesi veya yeni `Siparis` v2 + `SiparisService` | Teklif/sipariş DİA ile iki yönlü |
| **6** | İrsaliye | İrsaliye oluşturma/listeleme, depo transferi (demo ortamda doğrulanmış şekliyle) |
| **7** | Fatura (alış/satış) | Fatura oluşturma/listeleme, sipariş/irsaliyeden fatura akışı |
| **8** | Kasa/Tahsilat/Ödeme | `Kasa`, `KasaFisi` — tahsilat ve ödeme fişleri |
| **9** | Banka ve çek-senet (mümkün olduğunca) | BCS modülü entegrasyonu, banka hareketleri için demo ortamda netleştirilen çözüm |
| **10** | Otomasyon: Celery/Django-Q kurulumu, periyodik senkron görevleri, manuel senkron butonu, `SenkronKuyrugu`, retry/backoff | Zamanlanmış + manuel + kuyruklu senkron çalışır |
| **11** | Gözlemlenebilirlik: `SyncLog`/`SyncHataKaydi` için admin/dashboard ekranı, senkron geçmişi arayüzü | Hataları ve geçmişi görebileceğiniz panel |
| **12** | Çift yönlü senkron sertleştirme: çakışma politikası, idempotency testleri, uçtan uca test senaryoları | Üretime hazır, test edilmiş entegrasyon |

Alış/satış faturaları ve irsaliye gibi muhasebesel etkisi yüksek modülleri (Faz 6-7), Cari/Stok temelleri (Faz 2-3) sağlamlaştıktan sonra ele almak, hataların mali kayıtlara sızma riskini azaltıyor — bu yüzden bu sırayı öneriyorum.

---

## 11. Sıradaki Adım

Bu rapor ve plan onayınızı bekliyor. Onayladıktan sonra **Faz 0**'dan başlayıp, her adımda ne yapacağımı önce anlatıp onayınızı aldıktan sonra kodlamaya geçeceğim; mevcut `dashboard` app'ine dokunmadan, ayrı app'lerde ilerleyeceğiz.

Üzerinde konuşmak isteyebileceğiniz açık kararlar:
- **Celery + Redis mi, yoksa Django-Q2 mi?** (PythonAnywhere planınıza bağlı — birlikte teyit edelim.)
- **Yeni Cari/Stok modellerine mevcut `Siparis`/`Quotation` verilerini taşıyacak mıyız, yoksa paralel mi yaşatacağız?**
- **"Depolar arası transfer" ve "banka hareketleri" için demo ortamda birlikte mi keşif yapalım, yoksa siz DİA tarafındaki bir yetkiliyle mi netleştireceksiniz?**

Hazır olduğunuzda Faz 0 ile başlayabiliriz.
