"""Reviewed application knowledge; never load source files or secrets into prompts."""

from django.urls import reverse


# Keep descriptions aligned with the linked views, not planned features.
MODULES = [
    ("siparis", "Siparişler", "dashboard:orders",
     "Lastik siparişlerini marka, ürün, adet, cari firma ve işlem durumuyla takip eder. "
     "Yeni Lastik ekranından kayıt açılır; sipariş detayından kontrol ve teslim işlemleri yapılır. "
     "Sipariş toplamı tahsilat veya kesinleşmiş fatura cirosu değildir."),
    ("finans", "Finans ve Kasalar", "dashboard:finance",
     "Gelir/gider işlemleri, ödeme kanalları ve kasalar burada izlenir. Gelir Gider Raporu dönem karşılaştırması içindir. "
     "Asistanın finans hesabı mevcut raporun ödeme kanalına göre KDV ayırma yöntemini kullanır; "
     "net gelir-gider farkı muhasebesel net kâr olarak yorumlanmamalıdır."),
    ("stok", "DİA Stok Kartları", "erp:stok_listesi",
     "DİA'dan aktarılan ürün kodu, açıklama, marka ve gerçek/fiili stok miktarlarını gösterir. "
     "Kartın son senkronizasyon zamanı kontrol edilmelidir. Siparişlerin stok ambarı ayrı bir veri kaynağıdır; "
     "iki kaynaktaki adetler toplanmaz. Çıkma lastikler de ayrı takip edilir."),
    ("cari", "DİA Cariler", "erp:cari_listesi",
     "DİA müşteri ve tedarikçi kartlarıdır. Kod veya ünvanla aranır, detayına girilir. "
     "Varsayılan aktif filtresi pasif carileri gizleyebilir. Eksik kayıt için DİA Senkronizasyon ekranındaki "
     "Tam Cari Sync ve ardından senkronizasyon logları kontrol edilir. Cari kartı borç/alacak ekstresi değildir."),
    ("fatura", "DİA Faturalar / Malzeme Hareketleri", "erp:fatura_listesi",
     "DİA'dan aktarılan alış, satış ve iade faturaları ile ürün satırları tarih ve diğer filtrelerle incelenir. "
     "Bu ekranın mevcut görevi fatura listeleme ve senkronizasyondur; asistan fatura kesmez veya e-fatura göndermez. "
     "Fatura tutarı tahsil edildi demek değildir. Farklı türlerin toplamını net satış diye sunma."),
    ("dia", "DİA Senkronizasyon", "erp:dia_durum",
     "Cari, stok, fatura ve depo miktarlarının senkronizasyonunu ve sonuçlarını gösterir. "
     "Aktarım zamanlanmış Celery görevlerine bağlıdır; gerçek zamanlı bağlantı garantisi yoktur. "
     "Eksik veri için ilgili modülün son çalışmasını, hatalı kayıt sayısını ve firma/dönem seçimini kontrol et. "
     "Asistan yerel kopyayı okur; DİA bağlantısını test ettiğini veya sync başlattığını iddia etmez."),
    ("depo", "Depolar ve Depo Fişleri", "erp:depo_fisi_listesi",
     "Depolar stokların konumlarını, depo miktarları DİA'dan gelen miktarları gösterir. "
     "Depo fişleri stok isteklerini ve onay/iptal sürecini takip eder. Asistan fiş onaylamaz."),
    ("cikma", "Çıkma Lastikler", "dashboard:cikma_lastikler",
     "Marka, model, ebat, mevsim, kalite, depo konumu ve satış durumuyla ikinci el lastikleri takip eder. "
     "Satılan Çıkma Lastikler ekranı satış kayıtlarını gösterir. DİA sıfır lastik stoğuyla karıştırılmamalıdır."),
    ("teklif", "Teklifler", "dashboard:quotations",
     "Cari, ürün/hizmet kalemleri, KDV, geçerlilik tarihi ve açık/onaylı/reddedildi durumlarıyla teklif hazırlanır. "
     "Teklif görüntüleme, düzenleme, PDF ve e-posta işlemleri vardır. Onaylı teklif fatura veya tahsilat değildir."),
    ("garanti", "Garanti Belgeleri", "dashboard:garanti_belgeleri",
     "Müşteri, araç plakası, montaj tarihi ve takılan lastikleri kaydeder. Belge detayları buradan incelenir."),
    ("malzeme", "Excel Malzeme Hareketleri", "dashboard:malzeme_excel_upload",
     "Excel'den yüklenen malzeme hareketleri DİA fatura satırlarından bağımsızdır. "
     "Aynı satış iki kaynakta bulunabilir; toplamları birleştirmek çift sayım yaratabilir."),
    ("joker", "Joker Satış", "dashboard:joker_satis",
     "Excel satış satırlarını ürün, marka, miktar, alış, satış ve kâr alanlarıyla inceler."),
    ("takvim", "Takvim", "dashboard:calendar", "Etkinlikleri takvim üzerinde takip eder."),
    ("rapor", "Raporlar", "dashboard:income_expense_report", "Tarih aralığına göre gelir/gider raporu ve Excel çıktısı sağlar."),
    ("ayar", "Ayarlar", "dashboard:settings", "Hesap ayarları; güvenlik işlemleri Güvenlik sayfasında bulunur."),
]


def get_project_guide(topic=""):
    topic = topic.casefold().strip()
    selected = [row for row in MODULES if not topic or topic in " ".join(row).casefold()]
    return {"moduller": [
        {"modul": key, "baslik": title, "url": reverse(route), "aciklama": description}
        for key, title, route, description in selected
    ], "sinir": "Asistan salt okunurdur; kayıt oluşturmaz, değiştirmez veya silmez."}
