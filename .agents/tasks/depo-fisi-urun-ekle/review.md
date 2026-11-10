# Depo fişi detayında 'Ürün Ekle' akışı (brief uyumu)

Depo fişi detay/düzenleme ekranına, fiş 'bekliyor' durumundayken çalışan bir 'Ürün Ekle' akışı ekleniyor. Kodcu bu akışı tamamen istemci tarafında, mevcut `templates/erp/depo_fisi_detay.html` üzerinde gerçekleştirdi; backend (`erp/views.py`, `erp/urls.py`) bu commit'te değişmedi — `stok_ara_ajax` ve `depo_fisi_kalem_ekle` view'ları zaten vardı ve şablon mevcut yanıt biçimlerini tüketiyor. Yaklaşım: tek bir 'Ürün Ekle' butonu inline panel açar, stok kod/üretici kod ile arar, seçili kartta ad/marka/mevcut stok gösterir, 'Bu Fişe Ekle' mevcut kalem-ekle endpoint'ine POST atar ve başarıda tam sayfa yenileme yerine kalem tablosunu AJAX ile yeniler.

**Watch for:** 'Ara' butonu yalnızca arama ikonu, erişilebilir bir etiketi yok. 'Bu Fişe Ekle' istek sırasında devre dışı kalmıyor; panel açık kaldığı için hızlı çift tıklama aynı kalemden iki adet oluşturabilir.

**Verdict**: APPROVED

## High-level view

'Ürün Ekle' butonu ve inline panelin her ikisi de `{% if fis.durum == 'bekliyor' %}` içine alınmış; onaylı/iptal fişlerde buton ve panel hiç render edilmiyor. Eski 'Ürün Ekle' etiketi aslında stok listesi bağlantısıydı; commit bu bağlantıyı 'Stok Listesi' olarak yeniden etiketledi, böylece gerçek 'Ürün Ekle' butonu (paneli açan) tek ve net giriş noktası oldu.

Arama, mevcut `erp:stok_ara_ajax` endpoint'ini `?q=` ile çağırıyor ve dönen `sonuclar[]` dizisini liste halinde render ediyor. Seçili kart, aramadan gelen `gercek_stok` değerini `kalemSeciliYap` üzerinden yeni bir `kalemSeciliStokAdet` alanına taşıyarak ürün adı + marka + mevcut stok'u birlikte gösteriyor; bu stok değeri yalnızca bilgilendirme amaçlı, miktar kontrolü yok.

Başarıda `kalemListesiniYenile`, detay sayfasının tamamını tekrar fetch edip üç DOM bölgesini (tablo gövdesi `kalemTabloGovde`, kalem sayacı `kalemSayac`, özet kalem sayısı `fisOzetKalemSayisi`) cerrahi olarak değiştiriyor; panel açık kalıyor ve form sıfırlanıyor, böylece ardışık kalem eklenebiliyor. Fetch hatasında yedek olarak `location.reload()` devreye giriyor.

<details>
<summary>Issues (2)</summary>

1. **'Ara' butonu erişilebilir etiketsiz** — Arama butonu yalnızca `bi-search` ikonu içeriyor; görünür metin veya `aria-label` yok. İkona bir `sr-only` 'Ara' metni veya `aria-label="Ara"` ekleyin.
2. **'Bu Fişe Ekle' çift-gönderim korumasız** — İstek süresince buton devre dışı bırakılmıyor; panel açık kaldığı için hızlı çift tıklama aynı kalemden iki kayıt oluşturabilir. Fetch başlangıcında butonu `disabled` yapıp bitince açın.

</details>

<details>
<summary>Details</summary>

### Stok arama akışı ve seçili kart

`stokAra()`, `kalemAraKodu` alanındaki değeri `{% url 'erp:stok_ara_ajax' %}?q=` ile GET olarak çağırır (en az 2 karakter guard'ı istemci tarafında). Backend view `stok_ara_ajax` bu commit'te değişmedi; `uretici_kodu`/`stok_kodu`/`aciklama` üzerinde `icontains` arayıp `durum='A'` süzgeciyle ilk 15 sonucu `{sonuclar:[{pk, stok_kodu, uretici_kodu, aciklama, marka, gercek_stok}]}` biçiminde döndürür. (Not: brief'in literal JSON spec'i tek nesne ve `stok_pk`/`stok_adedi` alan adları öngörüyordu; mevcut view liste ve `pk`/`gercek_stok` adlarını kullanır. Backend bu commit'te değişmediği için bu alan adı farkı inceleme kapsamı dışıdır; şablon mevcut biçimi tüketiyor.)

Sonuçlardan birini seçince `kalemSeciliYap` gizli `kalemStokPk`'yı set eder ve seçili kartı doldurur: `kalemSeciliAdi` (ürün adı/aciklama), `kalemSeciliMarka`, `kalemSeciliKod` (üretici veya stok kodu) ve bu commit'in eklediği `kalemSeciliStokAdet` (mevcut stok). Karttaki mevcut stok yalnızca bilgilendirme amaçlıdır — 'Bu Fişe Ekle', girilen adetin mevcut stoku aşıp aşmadığını denetlemez.

### AJAX ile kalem listesi yenileme

`kalemEkle()`, `{% url 'erp:depo_fisi_kalem_ekle' fis.fis_no %}` endpoint'ine `stok_pk`, `adet`, `kalem_notu` POST eder. `DepoFisi.fis_no` bir `AutoField(primary_key=True)` olduğu için `fis.fis_no` ile `fis.pk` aynıdır; URL `<int:pk>` beklediği için bu çağrı doğru fişi bulur. Backend yalnızca `bekliyor` fişlere kalem ekler, aksi halde `basarili: False` döner.

Başarıda `kalemListesiniYenile()` tam sayfa yenileme yapmaz: `window.location.href`'i fetch eder, dönen HTML'i `DOMParser` ile parse edip `kalemTabloGovde` (tablo gövdesi), `kalemSayac` (üst kalem sayacı) ve `fisOzetKalemSayisi` (özet kalem sayısı) elementlerini sunucudaki güncel içerikle değiştirir. Bu, kullanıcıdan gelen önceki 'popup kapansın ve başka ürün ekleyebileyim' isteğine uygun olarak paneli açık tutar ve `kalemFormSifirla()` ile formu sıfırlar, böylece aynı fişe ardışık kalem eklenebilir. Ödün: sunucu tarafında tüm detay sayfası tekrar render edilir. Fetch başarısız olursa `.catch` 600 ms sonra `location.reload()` ile tam yedek yenileme yapar, böylece arızalı bir partial-update durumunda kullanıcı eski arayüzde kalmaz.

</details>

<details>
<summary>Dosya haritası</summary>

- `templates/erp/depo_fisi_detay.html` — 'Ürün Ekle' butonu/inline panel akışı: arama placeholder'ı tam metne uyarlandı, stok listesi bağlantısı 'Stok Listesi' olarak yeniden etiketlendi, seçili karta 'Mevcut Stok' alanı eklendi, kalem tablosu/sayaç/özet elementlerine id'ler kondu, başarıda tam yenileme yerine `kalemListesiniYenile()` (AJAX partial güncelleme + form sıfırlama) getirildi.

Bu commit'te yalnızca yukarıdaki şablon değişti. Backend (`erp/views.py`, `erp/urls.py`, `erp/models.py`) değişmedi; `stok_ara_ajax` ve `depo_fisi_kalem_ekle` zaten mevcuttu ve şablon mevcut yanıt biçimlerini tüketiyor. Tam diff: `git -C /Users/talha/Desktop/Projeler/MEStakip-main show HEAD`.

</details>
