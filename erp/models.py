"""
ERP iş modelleri — MEStakip'e ait, DİA'dan bağımsız iş katmanı.

Faz 2: Cari (müşteri/tedarikçi kart)
Faz 3: StokKart, Depo, StokDepoMiktari
Faz 5+: Siparis, Irsaliye, Fatura, Kasa, ...
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from dia_integration.mixins import DiaSyncMixin


# ─────────────────────────────────────────────────────────────
# Seçenek sabitleri
# ─────────────────────────────────────────────────────────────

class CariTip(models.TextChoices):
    """DİA carikarttipi alanı karşılıkları."""
    ALICI = 'AL', _('Alıcı (Müşteri)')
    SATICI = 'SA', _('Satıcı (Tedarikçi)')
    ALICI_SATICI = 'AS', _('Alıcı/Satıcı')
    DIGER = 'D', _('Diğer')


class CariDurum(models.TextChoices):
    """DİA durum alanı karşılıkları."""
    AKTIF = 'A', _('Aktif')
    PASIF = 'P', _('Pasif')


# ─────────────────────────────────────────────────────────────
# Cari — müşteri/tedarikçi ana kartı
# ─────────────────────────────────────────────────────────────

class Cari(DiaSyncMixin, models.Model):
    """
    Müşteri / tedarikçi ana kartı.

    DİA karşılığı: scf_carikart
    Senkronizasyon yönü:
      - DİA → MEStakip: periyodik delta sync (_date filtresiyle)
      - MEStakip → DİA: yeni cari oluşturma / güncelleme (Faz 2 son adımı)

    DiaSyncMixin'den gelen alanlar:
      dia_key, son_sync_tarihi, sync_durumu, dia_son_degisiklik
    """

    # ── Temel kimlik ──────────────────────────────────────────
    cari_kodu = models.CharField(
        max_length=30,
        unique=True,
        verbose_name=_('Cari kodu'),
        help_text=_('DİA carikartkodu. Otomatik atanır veya DİA\'dan senkronize edilir.'),
    )
    unvan = models.CharField(max_length=200, verbose_name=_('Ünvan'))
    kisa_aciklama = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Kısa açıklama'),
    )

    # ── Tür ve durum ─────────────────────────────────────────
    tip = models.CharField(
        max_length=2,
        choices=CariTip.choices,
        default=CariTip.ALICI,
        verbose_name=_('Cari tipi'),
    )
    durum = models.CharField(
        max_length=1,
        choices=CariDurum.choices,
        default=CariDurum.AKTIF,
        verbose_name=_('Durum'),
    )

    # ── Vergi / kimlik ────────────────────────────────────────
    vergi_no = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Vergi numarası'),
    )
    tc_kimlik_no = models.CharField(
        max_length=11,
        blank=True,
        verbose_name=_('TC kimlik no'),
    )
    vergi_dairesi = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Vergi dairesi'),
    )
    daire_kodu = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Daire kodu'),
    )

    # ── İletişim ─────────────────────────────────────────────
    telefon1 = models.CharField(max_length=30, blank=True, verbose_name=_('Telefon 1'))
    telefon2 = models.CharField(max_length=30, blank=True, verbose_name=_('Telefon 2'))
    cep_tel = models.CharField(max_length=30, blank=True, verbose_name=_('Cep telefonu'))
    fax = models.CharField(max_length=30, blank=True, verbose_name=_('Faks'))
    eposta = models.EmailField(blank=True, verbose_name=_('E-posta'))
    web_url = models.URLField(
        blank=True,
        verbose_name=_('Web sitesi'),
        max_length=300,
    )

    # ── Adres (ana adres) ─────────────────────────────────────
    adres1 = models.CharField(max_length=200, blank=True, verbose_name=_('Adres 1'))
    adres2 = models.CharField(max_length=200, blank=True, verbose_name=_('Adres 2'))
    ilce = models.CharField(max_length=100, blank=True, verbose_name=_('İlçe'))
    sehir = models.CharField(max_length=100, blank=True, verbose_name=_('Şehir'))
    posta_kodu = models.CharField(max_length=10, blank=True, verbose_name=_('Posta kodu'))
    ulke = models.CharField(
        max_length=100,
        blank=True,
        default='TÜRKİYE',
        verbose_name=_('Ülke'),
    )

    # ── Finansal ─────────────────────────────────────────────
    risk_limiti = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0'),
        verbose_name=_('Risk limiti'),
    )
    indirim_orani = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=Decimal('0'),
        verbose_name=_('İndirim oranı (%)'),
    )
    # Bakiye — DİA'dan okunan önbellek (salt okunur, hesaplanmaz)
    bakiye = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0'),
        verbose_name=_('Bakiye (DİA\'dan)'),
        help_text=_('DİA\'dan senkronize edilen anlık bakiye. MEStakip hesaplamaz.'),
    )
    borc_toplam = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0'),
        verbose_name=_('Borç toplamı'),
    )
    alacak_toplam = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0'),
        verbose_name=_('Alacak toplamı'),
    )

    # ── e-Fatura ─────────────────────────────────────────────
    efatura_senaryosu = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_('e-Fatura senaryosu'),
        help_text=_('DİA efaturasenaryosu: 0=Temel, 1=Ticari vb.'),
    )

    # ── Notlar ───────────────────────────────────────────────
    notlar = models.TextField(blank=True, verbose_name=_('Notlar'))

    # ── Zaman damgaları ───────────────────────────────────────
    olusturuldu = models.DateTimeField(auto_now_add=True, verbose_name=_('Oluşturuldu'))
    guncellendi = models.DateTimeField(auto_now=True, verbose_name=_('Güncellendi'))

    class Meta:
        verbose_name = _('Cari')
        verbose_name_plural = _('Cariler')
        ordering = ['unvan']
        indexes = [
            models.Index(fields=['cari_kodu']),
            models.Index(fields=['vergi_no']),
            models.Index(fields=['tip', 'durum']),
            models.Index(fields=['unvan']),
        ]

    def __str__(self) -> str:
        return f'{self.cari_kodu} — {self.unvan}'

    @property
    def musteri_mi(self) -> bool:
        return self.tip in (CariTip.ALICI, CariTip.ALICI_SATICI)

    @property
    def tedarikci_mi(self) -> bool:
        return self.tip in (CariTip.SATICI, CariTip.ALICI_SATICI)

    @property
    def aktif_mi(self) -> bool:
        return self.durum == CariDurum.AKTIF


# ─────────────────────────────────────────────────────────────
# Faz 3 — Stok sabitleri
# ─────────────────────────────────────────────────────────────

class StokKartTur(models.TextChoices):
    """DİA stokkartturu alanı karşılıkları."""
    TICARI_MAL   = 'TCR', _('Ticari Mal')
    HAMMADDE     = 'HMM', _('Hammadde')
    YARI_MAMUL   = 'YRM', _('Yarı Mamul')
    MAMUL        = 'MAM', _('Mamul')
    HIZMET       = 'HZM', _('Hizmet')
    DIGER        = 'DIG', _('Diğer')


class StokDurum(models.TextChoices):
    AKTIF = 'A', _('Aktif')
    PASIF = 'P', _('Pasif')


# ─────────────────────────────────────────────────────────────
# Depo
# ─────────────────────────────────────────────────────────────

class Depo(models.Model):
    """
    DİA şube/depo tanımı.
    sis_yetkili_firma_donem_sube_depo yanıtından senkronize edilir.
    """

    dia_key     = models.CharField(max_length=20, unique=True, verbose_name=_('DİA Depo Key'))
    ad          = models.CharField(max_length=100, verbose_name=_('Depo adı'))
    sube_adi    = models.CharField(max_length=100, blank=True, verbose_name=_('Şube adı'))
    sube_dia_key = models.CharField(max_length=20, blank=True, verbose_name=_('DİA Şube Key'))
    aktif       = models.BooleanField(default=True, verbose_name=_('Aktif'))
    olusturuldu = models.DateTimeField(auto_now_add=True)
    guncellendi = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Depo')
        verbose_name_plural = _('Depolar')
        ordering = ['sube_adi', 'ad']

    def __str__(self) -> str:
        return f'{self.sube_adi} / {self.ad}' if self.sube_adi else self.ad


# ─────────────────────────────────────────────────────────────
# StokKart
# ─────────────────────────────────────────────────────────────

class StokKart(DiaSyncMixin, models.Model):
    """
    Ürün / lastik ana kartı.
    DİA karşılığı: scf_stokkart
    """

    stok_kodu   = models.CharField(max_length=30, unique=True, verbose_name=_('Stok kodu'))
    aciklama    = models.CharField(max_length=200, verbose_name=_('Açıklama'))
    tur         = models.CharField(
        max_length=5, choices=StokKartTur.choices,
        default=StokKartTur.TICARI_MAL, verbose_name=_('Tür'),
    )
    durum       = models.CharField(
        max_length=1, choices=StokDurum.choices,
        default=StokDurum.AKTIF, verbose_name=_('Durum'),
    )
    ana_birim   = models.CharField(max_length=20, blank=True, verbose_name=_('Ana birim'))
    ana_birim_dia_key = models.CharField(max_length=20, blank=True, verbose_name=_('Birim DİA key'))
    ana_barkod  = models.CharField(max_length=50, blank=True, verbose_name=_('Ana barkod'))
    marka       = models.CharField(max_length=100, blank=True, verbose_name=_('Marka'))
    ozel_kod1   = models.CharField(max_length=100, blank=True, verbose_name=_('Özel kod 1'))
    ozel_kod2   = models.CharField(max_length=100, blank=True, verbose_name=_('Özel kod 2'))
    kdv_alis    = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('18'), verbose_name=_('KDV alış (%)'))
    kdv_satis   = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('18'), verbose_name=_('KDV satış (%)'))
    fiyat1      = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Fiyat 1'))
    fiyat2      = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Fiyat 2'))
    gercek_stok = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal('0'),
        verbose_name=_('Gerçek stok'),
        help_text=_('DİA\'dan senkronize edilir, MEStakip hesaplamaz.'),
    )
    fiili_stok  = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Fiili stok'))
    notlar      = models.TextField(blank=True, verbose_name=_('Notlar'))
    olusturuldu = models.DateTimeField(auto_now_add=True)
    guncellendi = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Stok Kartı')
        verbose_name_plural = _('Stok Kartları')
        ordering = ['stok_kodu']
        indexes = [
            models.Index(fields=['stok_kodu']),
            models.Index(fields=['ana_barkod']),
            models.Index(fields=['marka']),
            models.Index(fields=['durum']),
        ]

    def __str__(self) -> str:
        return f'{self.stok_kodu} — {self.aciklama}'

    @property
    def aktif_mi(self) -> bool:
        return self.durum == StokDurum.AKTIF


# ─────────────────────────────────────────────────────────────
# StokDepoMiktari
# ─────────────────────────────────────────────────────────────

class StokDepoMiktari(models.Model):
    """
    Bir stok kartının bir depodaki anlık miktarı.
    DİA'dan senkronize edilir — salt okunur önbellek.
    DİA karşılığı: scf_stok_depo_miktarlari_listele
    """

    stok = models.ForeignKey(
        StokKart, on_delete=models.CASCADE,
        related_name='depo_miktarlari', verbose_name=_('Stok kartı'),
    )
    depo = models.ForeignKey(
        Depo, on_delete=models.CASCADE,
        related_name='stok_miktarlari', verbose_name=_('Depo'),
    )
    gercek_miktar = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Gerçek miktar'))
    fiili_miktar  = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Fiili miktar'))
    son_sync      = models.DateTimeField(auto_now=True, verbose_name=_('Son sync'))

    class Meta:
        verbose_name = _('Stok Depo Miktarı')
        verbose_name_plural = _('Stok Depo Miktarları')
        unique_together = [('stok', 'depo')]
        ordering = ['stok', 'depo']

    def __str__(self) -> str:
        return f'{self.stok.stok_kodu} @ {self.depo.ad}: {self.gercek_miktar}'


# ─────────────────────────────────────────────────────────────
# Depo Fişi — stok istek/talep takibi
# ─────────────────────────────────────────────────────────────

class DepoFisiDurum(models.TextChoices):
    BEKLIYOR   = 'bekliyor',   _('Bekliyor')
    ONAYLANDI  = 'onaylandi',  _('Onaylandı')
    IPTAL      = 'iptal',      _('İptal')


class DepoFisi(models.Model):
    """
    Depo stok talep/istek fişi.
    Stok listesindeki araba ikonuna tıklandığında oluşturulur.
    """
    fis_no        = models.AutoField(primary_key=True, verbose_name=_('Fiş No'))
    tarih         = models.DateField(auto_now_add=True, verbose_name=_('Tarih'))
    plaka         = models.CharField(max_length=20, blank=True, verbose_name=_('Plaka'))
    kilometre     = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Kilometre'))
    arac_marka    = models.CharField(max_length=50, blank=True, verbose_name=_('Araç Marka'))
    arac_model    = models.CharField(max_length=50, blank=True, verbose_name=_('Araç Model'))
    cari          = models.CharField(max_length=200, blank=True, verbose_name=_('Cari'))
    depo          = models.ForeignKey(
        Depo, null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Depo'),
    )
    adet          = models.PositiveIntegerField(default=1, verbose_name=_('Adet'))
    aciklama      = models.TextField(blank=True, verbose_name=_('Açıklama'))
    yazildi       = models.BooleanField(default=False, verbose_name=_('Yazıldı?'))
    onaylandi     = models.BooleanField(default=False, verbose_name=_('Onaylandı'))
    onay_veren    = models.ForeignKey(
        'auth.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='onaylanan_fisler',
        verbose_name=_('Onay Veren'),
    )
    onay_tarihi   = models.DateTimeField(null=True, blank=True, verbose_name=_('Onay Tarihi'))
    fatura_no     = models.CharField(max_length=50, blank=True, verbose_name=_('Fatura No'))
    durum         = models.CharField(
        max_length=15, choices=DepoFisiDurum.choices,
        default=DepoFisiDurum.BEKLIYOR, verbose_name=_('Durum'),
    )
    islem_yapan   = models.ForeignKey(
        'auth.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('İşlem Yapan'),
    )
    olusturuldu   = models.DateTimeField(auto_now_add=True)
    guncellendi   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Depo Fişi')
        verbose_name_plural = _('Depo Fişleri')
        ordering            = ['-olusturuldu']

    def __str__(self) -> str:
        return f'Fiş #{self.fis_no} — {self.tarih}'


class DepoFisiKalemi(models.Model):
    """Depo fişinin stok kalemi."""
    fis   = models.ForeignKey(
        DepoFisi, on_delete=models.CASCADE,
        related_name='kalemler', verbose_name=_('Fiş'),
    )
    stok  = models.ForeignKey(
        StokKart, on_delete=models.PROTECT,
        verbose_name=_('Stok Kartı'),
    )
    adet  = models.PositiveIntegerField(default=1, verbose_name=_('Adet'))
    kalem_notu = models.CharField(max_length=200, blank=True, verbose_name=_('Not'))

    class Meta:
        verbose_name        = _('Depo Fişi Kalemi')
        verbose_name_plural = _('Depo Fişi Kalemleri')

    def __str__(self) -> str:
        return f'{self.stok.stok_kodu} x{self.adet}'


# ─────────────────────────────────────────────────────────────
# Fatura — DİA'dan senkronize fatura/malzeme hareket
# ─────────────────────────────────────────────────────────────

class FaturaTur(models.TextChoices):
    SATIS  = 'S', _('Satış')
    ALIS   = 'A', _('Alış')
    IADE   = 'I', _('İade')
    DIGER  = 'D', _('Diğer')


class Fatura(DiaSyncMixin, models.Model):
    """
    DİA'dan senkronize fatura kaydı.
    DİA karşılığı: scf_fatura_listele
    """
    fis_no       = models.CharField(max_length=30, blank=True, verbose_name=_('Fiş No'))
    belge_no     = models.CharField(max_length=50, blank=True, verbose_name=_('Belge No'))
    tarih        = models.DateField(null=True, blank=True, verbose_name=_('Tarih'))
    saat         = models.CharField(max_length=10, blank=True, verbose_name=_('Saat'))
    tur          = models.CharField(
        max_length=1, choices=FaturaTur.choices,
        default=FaturaTur.SATIS, verbose_name=_('Tür'),
    )
    tur_aciklama = models.CharField(max_length=50, blank=True, verbose_name=_('Tür Açıklama'))
    # Cari
    cari_kodu    = models.CharField(max_length=30, blank=True, verbose_name=_('Cari Kodu'))
    cari_unvan   = models.CharField(max_length=200, blank=True, verbose_name=_('Cari Ünvan'))
    # Tutar
    toplam       = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Toplam'))
    net          = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Net'))
    indirim      = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('İndirim'))
    # Depo/Şube
    depo_adi     = models.CharField(max_length=100, blank=True, verbose_name=_('Depo'))
    sube_adi     = models.CharField(max_length=100, blank=True, verbose_name=_('Şube'))
    # Notlar
    aciklama     = models.TextField(blank=True, verbose_name=_('Açıklama'))
    olusturuldu  = models.DateTimeField(auto_now_add=True)
    guncellendi  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Fatura')
        verbose_name_plural = _('Faturalar')
        ordering            = ['-tarih', '-fis_no']
        indexes = [
            models.Index(fields=['tarih']),
            models.Index(fields=['tur']),
            models.Index(fields=['cari_kodu']),
        ]

    def __str__(self) -> str:
        return f'{self.fis_no} — {self.cari_unvan} ({self.tarih})'


class FaturaKalemi(models.Model):
    """Fatura satır kalemi — DİA m_kalemler'den."""
    fatura       = models.ForeignKey(Fatura, on_delete=models.CASCADE, related_name='kalemler')
    dia_key      = models.CharField(max_length=20, blank=True, db_index=True)
    sirano       = models.PositiveSmallIntegerField(default=0, verbose_name=_('Sıra No'))
    stok_kodu    = models.CharField(max_length=30, blank=True, verbose_name=_('Stok Kodu'))
    stok_adi     = models.CharField(max_length=200, blank=True, verbose_name=_('Ürün Adı'))
    miktar       = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Miktar'))
    kanal        = models.CharField(max_length=50, blank=True, verbose_name=_('Kanal'))
    birim        = models.CharField(max_length=20, blank=True, verbose_name=_('Birim'))
    prim         = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Prim'))
    maliyet      = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Maliyet'))
    birim_fiyat  = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Birim Fiyat'))
    indirim      = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'), verbose_name=_('İskonto %'))
    tutar        = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'), verbose_name=_('Tutar'))
    satisci      = models.CharField(max_length=100, blank=True, verbose_name=_('Satış Temsilcisi'))
    odeme_plani  = models.CharField(max_length=100, blank=True, verbose_name=_('Ödeme Planı'))
    depo         = models.CharField(max_length=100, blank=True, verbose_name=_('Ambar'))
    marka        = models.CharField(max_length=100, blank=True, verbose_name=_('Marka'))
    kategori     = models.CharField(max_length=100, blank=True, verbose_name=_('Kategori'))
    mevsim       = models.CharField(max_length=50, blank=True, verbose_name=_('Mevsim'))
    dot          = models.CharField(max_length=20, blank=True, verbose_name=_('DOT / Yıl'))
    bolge        = models.CharField(max_length=100, blank=True, verbose_name=_('Bölge'))

    class Meta:
        verbose_name        = _('Fatura Kalemi')
        verbose_name_plural = _('Fatura Kalemleri')
        ordering            = ['fatura', 'sirano']

    def __str__(self) -> str:
        return f'{self.stok_kodu} x{self.miktar}'
