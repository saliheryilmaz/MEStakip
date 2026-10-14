"""
DİA entegrasyon altyapı modelleri.

Bu app'in modelleri iş verisi içermez; sadece entegrasyon altyapısına
(session yönetimi, loglama, hata takibi, kuyruk) hizmet eder.

Modeller:
  - DiaBaglanti   : DİA sunucu/session bilgisi
  - SyncLog       : Her senkronizasyon çalıştırmasının özeti
  - SyncHataKaydi : Kayıt bazlı hata detayı
  - ApiIstekLog   : Her DİA API çağrısının logu
  - SenkronKuyrugu: Retry/yeniden deneme kuyruğu
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────────────────────
# DiaBaglanti — DİA sunucu/oturum bilgisi
# ─────────────────────────────────────────────────────────────

class DiaBaglanti(models.Model):
    """
    DİA ERP bağlantı yapılandırması ve aktif session yönetimi.

    Sistemde genellikle tek bir aktif bağlantı kaydı bulunur.
    Birden fazla firma/dönem desteği gerekirse is_aktif alanıyla
    hangi bağlantının kullanılacağı belirlenir.
    """

    ad = models.CharField(
        max_length=100,
        verbose_name=_('Bağlantı adı'),
        help_text=_('Örn: "Meslas Demo", "Meslas Production"'),
    )
    sunucu_kodu = models.CharField(
        max_length=50,
        verbose_name=_('Sunucu kodu'),
        help_text=_('DİA URL\'sindeki sunucu kodu (örn: diademo)'),
    )
    kullanici_adi = models.CharField(max_length=100, verbose_name=_('Kullanıcı adı'))
    # Şifre production'da .env'den gelir; burada yedek olarak saklanır,
    # ancak gerçek değer settings.DIA_PASSWORD'dan okunur.
    sifre_maskelenmiş = models.CharField(
        max_length=100,
        verbose_name=_('Şifre (maskelenmiş)'),
        blank=True,
        help_text=_('Görüntüleme amaçlı; gerçek şifre .env\'den okunur.'),
    )
    firma_kodu = models.CharField(max_length=20, verbose_name=_('Firma kodu'))
    donem_kodu = models.CharField(max_length=20, verbose_name=_('Dönem kodu'))

    # Aktif session bilgisi (her login'de güncellenir)
    session_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Session ID'),
    )
    session_alindi = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Session alınma zamanı'),
    )

    # Firma/dönem hiyerarşisi (sis_yetkili_firma_donem_sube_depo yanıtı)
    firma_donem_bilgisi = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Firma/dönem/şube/depo bilgisi'),
        help_text=_('sis_yetkili_firma_donem_sube_depo yanıtından önbelleğe alınan veri'),
    )
    firma_donem_guncellendi = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Firma/dönem bilgisi güncellenme zamanı'),
    )

    is_aktif = models.BooleanField(default=True, verbose_name=_('Aktif'))
    olusturuldu = models.DateTimeField(auto_now_add=True)
    guncellendi = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('DİA Bağlantı')
        verbose_name_plural = _('DİA Bağlantılar')
        ordering = ['-is_aktif', 'ad']

    def __str__(self) -> str:
        return f'{self.ad} ({self.sunucu_kodu} / firma:{self.firma_kodu})'

    def session_gecerli_mi(self, ttl_saniye: int = 3000) -> bool:
        """Session hâlâ geçerli mi? (TTL aşılmadıysa True)"""
        if not self.session_id or not self.session_alindi:
            return False
        gecen = (timezone.now() - self.session_alindi).total_seconds()
        return gecen < ttl_saniye

    def session_guncelle(self, session_id: str) -> None:
        """Yeni session ID'yi kaydet."""
        self.session_id = session_id
        self.session_alindi = timezone.now()
        self.save(update_fields=['session_id', 'session_alindi'])


# ─────────────────────────────────────────────────────────────
# SyncLog — Her senkronizasyon çalıştırmasının özeti
# ─────────────────────────────────────────────────────────────

class SyncDurum(models.TextChoices):
    CALISIYOR = 'calisiyor', _('Çalışıyor')
    BASARILI = 'basarili', _('Başarılı')
    KISMI_BASARILI = 'kismi_basarili', _('Kısmen Başarılı')
    BASARISIZ = 'basarisiz', _('Başarısız')


class SyncTetikleyen(models.TextChoices):
    OTOMATIK = 'otomatik', _('Otomatik (zamanlanmış)')
    MANUEL = 'manuel', _('Manuel (kullanıcı)')
    SISTEM = 'sistem', _('Sistem (management command)')


class SyncLog(models.Model):
    """Her senkronizasyon çalıştırmasının özet kaydı."""

    modul = models.CharField(
        max_length=50,
        verbose_name=_('Modül'),
        help_text=_('Örn: cari, stok, fatura, irsaliye'),
    )
    baslangic = models.DateTimeField(default=timezone.now, verbose_name=_('Başlangıç'))
    bitis = models.DateTimeField(null=True, blank=True, verbose_name=_('Bitiş'))
    durum = models.CharField(
        max_length=20,
        choices=SyncDurum.choices,
        default=SyncDurum.CALISIYOR,
        verbose_name=_('Durum'),
    )
    tetikleyen = models.CharField(
        max_length=20,
        choices=SyncTetikleyen.choices,
        default=SyncTetikleyen.SISTEM,
        verbose_name=_('Tetikleyen'),
    )
    tetikleyen_kullanici = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Tetikleyen kullanıcı'),
    )
    toplam_kayit = models.PositiveIntegerField(default=0, verbose_name=_('Toplam kayıt'))
    basarili_kayit = models.PositiveIntegerField(default=0, verbose_name=_('Başarılı kayıt'))
    hatali_kayit = models.PositiveIntegerField(default=0, verbose_name=_('Hatalı kayıt'))
    hata_mesaji = models.TextField(blank=True, verbose_name=_('Genel hata mesajı'))
    celery_task_id = models.CharField(max_length=255, blank=True, verbose_name=_('Celery task ID'))

    class Meta:
        verbose_name = _('Senkronizasyon Logu')
        verbose_name_plural = _('Senkronizasyon Logları')
        ordering = ['-baslangic']
        indexes = [
            models.Index(fields=['modul', 'baslangic']),
            models.Index(fields=['durum']),
        ]

    def __str__(self) -> str:
        sure = ''
        if self.bitis:
            sure = f' ({(self.bitis - self.baslangic).total_seconds():.1f}s)'
        return f'[{self.modul}] {self.baslangic:%d.%m.%Y %H:%M} — {self.get_durum_display()}{sure}'

    def tamamla(self, durum: str = SyncDurum.BASARILI, hata: str = '') -> None:
        """Sync tamamlandığında çağrılır."""
        self.bitis = timezone.now()
        self.durum = durum
        self.hata_mesaji = hata
        self.save(update_fields=['bitis', 'durum', 'hata_mesaji'])


# ─────────────────────────────────────────────────────────────
# SyncHataKaydi — Kayıt bazlı hata detayı
# ─────────────────────────────────────────────────────────────

class SyncHataKaydi(models.Model):
    """Tek bir kayıt için senkronizasyon hatası detayı."""

    sync_log = models.ForeignKey(
        SyncLog,
        on_delete=models.CASCADE,
        related_name='hatalar',
        verbose_name=_('Sync logu'),
    )
    modul = models.CharField(max_length=50, verbose_name=_('Modül'))
    yerel_model = models.CharField(
        max_length=100,
        verbose_name=_('Yerel model adı'),
        help_text=_('Örn: erp.Cari'),
    )
    yerel_id = models.CharField(
        max_length=50,
        verbose_name=_('Yerel kayıt ID'),
    )
    dia_servis = models.CharField(
        max_length=100,
        verbose_name=_('DİA servis adı'),
        help_text=_('Örn: scf_carikart_ekle'),
    )
    hata_kodu = models.CharField(max_length=20, blank=True, verbose_name=_('Hata kodu'))
    hata_mesaji = models.TextField(verbose_name=_('Hata mesajı'))
    deneme_sayisi = models.PositiveSmallIntegerField(default=1, verbose_name=_('Deneme sayısı'))
    olusturuldu = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Sync Hata Kaydı')
        verbose_name_plural = _('Sync Hata Kayıtları')
        ordering = ['-olusturuldu']

    def __str__(self) -> str:
        return f'{self.yerel_model}#{self.yerel_id} → {self.dia_servis} ({self.hata_kodu})'


# ─────────────────────────────────────────────────────────────
# ApiIstekLog — Her DİA API çağrısının logu
# ─────────────────────────────────────────────────────────────

class ApiIstekLog(models.Model):
    """
    Her DİA API isteğinin özet kaydı.

    Hassas veriler (şifre, session_id) bu tabloya yazılmaz.
    """

    servis_adi = models.CharField(
        max_length=100,
        verbose_name=_('Servis adı'),
        help_text=_('Örn: scf_carikart_listele'),
    )
    http_metod = models.CharField(max_length=10, default='POST', verbose_name=_('HTTP metod'))
    istek_zamani = models.DateTimeField(default=timezone.now, verbose_name=_('İstek zamanı'))
    sure_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Süre (ms)'),
    )
    http_durum_kodu = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('HTTP durum kodu'),
    )
    dia_durum_kodu = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('DİA durum kodu'),
        help_text=_('Yanıttaki status/code alanı'),
    )
    basarili = models.BooleanField(default=True, verbose_name=_('Başarılı'))
    hata_mesaji = models.TextField(blank=True, verbose_name=_('Hata mesajı'))
    # İstek/yanıt özeti — tam JSON değil, boyut kontrolü için
    istek_ozeti = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('İstek özeti'),
        help_text=_('Filtreler, limit/offset gibi meta bilgiler; hassas veri içermemeli'),
    )
    sonuc_sayisi = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Dönen kayıt sayısı'),
    )

    class Meta:
        verbose_name = _('API İstek Logu')
        verbose_name_plural = _('API İstek Logları')
        ordering = ['-istek_zamani']
        indexes = [
            models.Index(fields=['servis_adi', 'istek_zamani']),
            models.Index(fields=['basarili']),
        ]

    def __str__(self) -> str:
        durum = '✓' if self.basarili else '✗'
        sure = f'{self.sure_ms}ms' if self.sure_ms else '?'
        return f'{durum} {self.servis_adi} [{sure}] {self.istek_zamani:%d.%m %H:%M:%S}'


# ─────────────────────────────────────────────────────────────
# SenkronKuyrugu — Retry/yeniden deneme kuyruğu
# ─────────────────────────────────────────────────────────────

class SenkronIslemTipi(models.TextChoices):
    DIA_DAN_CEK = 'dia_dan_cek', _('DİA\'dan çek (okuma)')
    DIA_YA_YAZ = 'dia_ya_yaz', _('DİA\'ya yaz (oluştur/güncelle)')
    DIA_DAN_SIL = 'dia_dan_sil', _('DİA\'dan sil')


class SenkronKuyrukDurum(models.TextChoices):
    BEKLIYOR = 'bekliyor', _('Bekliyor')
    ISLENIYOR = 'isleniyor', _('İşleniyor')
    TAMAMLANDI = 'tamamlandi', _('Tamamlandı')
    BASARISIZ = 'basarisiz', _('Başarısız (max deneme aşıldı)')
    IPTAL = 'iptal', _('İptal edildi')


class SenkronKuyrugu(models.Model):
    """
    Başarısız senkronizasyonlar ve yeniden deneme kuyruğu.

    Celery görevi başarısız olduğunda veya manuel retry
    istendiğinde buraya kayıt düşülür.
    """

    modul = models.CharField(max_length=50, verbose_name=_('Modül'))
    islem_tipi = models.CharField(
        max_length=20,
        choices=SenkronIslemTipi.choices,
        verbose_name=_('İşlem tipi'),
    )
    yerel_model = models.CharField(max_length=100, verbose_name=_('Yerel model adı'))
    yerel_id = models.CharField(max_length=50, verbose_name=_('Yerel kayıt ID'))
    dia_key = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('DİA key'),
        help_text=_('Güncelleme/silme işlemlerinde dolu olur'),
    )
    durum = models.CharField(
        max_length=20,
        choices=SenkronKuyrukDurum.choices,
        default=SenkronKuyrukDurum.BEKLIYOR,
        verbose_name=_('Durum'),
    )
    deneme_sayisi = models.PositiveSmallIntegerField(default=0, verbose_name=_('Deneme sayısı'))
    max_deneme = models.PositiveSmallIntegerField(default=3, verbose_name=_('Maksimum deneme'))
    sonraki_deneme = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Sıradaki deneme zamanı'),
    )
    son_hata = models.TextField(blank=True, verbose_name=_('Son hata mesajı'))
    ek_veri = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Ek veri'),
        help_text=_('Görevin ihtiyaç duyduğu ek parametreler'),
    )
    olusturuldu = models.DateTimeField(auto_now_add=True)
    guncellendi = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Senkron Kuyruğu')
        verbose_name_plural = _('Senkron Kuyrukları')
        ordering = ['sonraki_deneme', 'olusturuldu']
        indexes = [
            models.Index(fields=['durum', 'sonraki_deneme']),
            models.Index(fields=['modul', 'durum']),
        ]

    def __str__(self) -> str:
        return (
            f'{self.modul}/{self.yerel_model}#{self.yerel_id} '
            f'[{self.get_durum_display()}] deneme:{self.deneme_sayisi}/{self.max_deneme}'
        )

    def max_deneme_asildi_mi(self) -> bool:
        return self.deneme_sayisi >= self.max_deneme
