from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.contrib.auth.models import User
import json

class UserProfile(models.Model):
    """Kullanıcı profil modeli - rol yönetimi için"""
    
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('yonetici', 'Yönetici'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Kullanıcı")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='yonetici', verbose_name="Rol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    class Meta:
        verbose_name = "Kullanıcı Profili"
        verbose_name_plural = "Kullanıcı Profilleri"
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    def is_admin(self):
        """Admin rolü kontrolü"""
        return self.role == 'admin'
    
    def is_yonetici(self):
        """Yönetici rolü kontrolü"""
        return self.role == 'yonetici'

class Siparis(models.Model):
    """Sipariş modeli - Lastik, Akü, Jant siparişleri"""
    
    GRUP_CHOICES = [
        ('ticari', 'Ticari'),
        ('binek', 'Binek'),
        ('aku', 'Akü'),
        ('jant', 'Jant'),
    ]
    
    MEVSIM_CHOICES = [
        ('kis', 'Kış'),
        ('yaz', 'Yaz'),
        ('dort-mevsim', '4 Mevsim'),
    ]
    
    DURUM_CHOICES = [
        ('yolda', 'Yolda'),
        ('islemde', 'İşleme Devam Ediyor'),
        ('teslim', 'Teslim Edildi'),
        ('kontrol', 'Kontrol Edildi'),
        ('iptal', 'İptal Edildi'),
    ]
    
    ODEME_CHOICES = [
        ('kredi-karti', 'Kredi Kartı'),
        ('havale', 'Havale'),
        ('cari-hesap', 'Cari Hesap'),
        ('banka-havale', 'Banka Havale'),
        ('sanal-pos', 'Sanal POS'),
    ]
    
    SMS_CHOICES = [
        ('gonderilmedi', 'Gönderilmedi'),
        ('gonderildi', 'Gönderildi'),
    ]
    
    AMBAR_CHOICES = [
        ('stok', 'Stok'),
        ('satis', 'Satış'),
    ]
    
    # Kullanıcı bilgisi - Her sipariş bir kullanıcıya ait
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Kullanıcı", related_name='siparisler', null=True, blank=True)
    
    # Temel Bilgiler
    cari_firma = models.CharField(max_length=200, verbose_name="CARI (FIRMA)")
    marka = models.CharField(max_length=100, verbose_name="MARKA")
    urun = models.CharField(max_length=300, verbose_name="ÜRÜN (LASTIK MARKA MODEL)")
    
    # Kategori Bilgileri
    grup = models.CharField(max_length=20, choices=GRUP_CHOICES, verbose_name="GRUP")
    mevsim = models.CharField(max_length=20, choices=MEVSIM_CHOICES, verbose_name="MEVSİM")
    
    # Miktar ve Fiyat
    adet = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], 
        verbose_name="ADET"
    )
    birim_fiyat = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0)], 
        verbose_name="BİRİM FİYAT"
    )
    toplam_fiyat = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        validators=[MinValueValidator(0)], 
        verbose_name="TOPLAM FİYAT"
    )
    
    # Durum Bilgileri
    durum = models.CharField(max_length=20, choices=DURUM_CHOICES, default='yolda', verbose_name="DURUM")
    ambar = models.CharField(max_length=20, choices=AMBAR_CHOICES, default='stok', verbose_name="AMBAR")
    
    # Ödeme ve İletişim
    odeme = models.CharField(max_length=20, choices=ODEME_CHOICES, verbose_name="ÖDEME")
    sms_durum = models.CharField(max_length=20, choices=SMS_CHOICES, default='gonderilmedi', verbose_name="SMS")
    
    # Ek Bilgiler
    aciklama = models.TextField(blank=True, null=True, verbose_name="AÇIKLAMA")
    one_cikar = models.BooleanField(default=False, verbose_name="ÖNE ÇIKAR")
    iptal_sebebi = models.TextField(blank=True, null=True, verbose_name="İPTAL SEBEBİ")
    
    # Müşteri Bilgileri
    musteri_adi = models.CharField(max_length=200, blank=True, null=True, verbose_name="MÜŞTERİ ADI")
    musteri_telefon = models.CharField(max_length=20, blank=True, null=True, verbose_name="MÜŞTERİ TELEFON")
    musteri_odeme_tutari = models.CharField(max_length=100, blank=True, null=True, verbose_name="MÜŞTERİ ÖDEME TUTARI")
    musteri_aciklama = models.TextField(blank=True, null=True, verbose_name="MÜŞTERİ AÇIKLAMA")
    
    # Zaman Damgaları
    olusturma_tarihi = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturma Tarihi")
    guncelleme_tarihi = models.DateTimeField(auto_now=True, verbose_name="Güncelleme Tarihi")
    
    class Meta:
        verbose_name = "Sipariş"
        verbose_name_plural = "Siparişler"
        ordering = ['-olusturma_tarihi']
    
    def __str__(self):
        return f"{self.cari_firma} - {self.urun} ({self.adet} adet)"
    
    def save(self, *args, **kwargs):
        # Toplam fiyatı otomatik hesapla
        self.toplam_fiyat = self.adet * self.birim_fiyat
        super().save(*args, **kwargs)
    
    def get_grup_display_color(self):
        """Grup için renk döndür"""
        colors = {
            'ticari': 'warning',
            'binek': 'success',
            'aku': 'warning',
            'jant': 'info',
        }
        return colors.get(self.grup, 'secondary')
    
    def get_durum_display_color(self):
        """Durum için renk döndür"""
        colors = {
            'yolda': 'info',
            'islemde': 'primary',
            'teslim': 'success',
            'kontrol': 'warning',
            'iptal': 'danger',
        }
        return colors.get(self.durum, 'secondary')
    
    def get_mevsim_display_color(self):
        """Mevsim için renk döndür"""
        colors = {
            'kis': 'info',
            'yaz': 'warning',
            'dort-mevsim': 'primary',
        }
        return colors.get(self.mevsim, 'secondary')
    
    def get_sms_display_color(self):
        """SMS durumu için renk döndür"""
        colors = {
            'gonderildi': 'success',
            'gonderilmedi': 'danger',
        }
        return colors.get(self.sms_durum, 'secondary')
    
    def get_ambar_display_color(self):
        """Ambar için renk döndür"""
        colors = {
            'stok': 'primary',
            'satis': 'success',
        }
        return colors.get(self.ambar, 'secondary')
    
    def get_musteri_odeme_tutari_display(self):
        """Müşteri ödeme tutarı için display değeri döndür"""
        return self.musteri_odeme_tutari if self.musteri_odeme_tutari else None

class Event(models.Model):
    """Takvim etkinlikleri modeli"""
    
    TYPE_CHOICES = [
        ('event', 'Etkinlik'),
        ('meeting', 'Toplantı'),
        ('task', 'Görev'),
        ('reminder', 'Hatırlatıcı'),
        ('deadline', 'Son Tarih'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Düşük'),
        ('medium', 'Orta'),
        ('high', 'Yüksek'),
    ]
    
    RECURRENCE_CHOICES = [
        ('none', 'Tekrarlanmaz'),
        ('daily', 'Günlük'),
        ('weekly', 'Haftalık'),
        ('biweekly', '2 Haftada Bir'),
        ('monthly', 'Aylık'),
        ('yearly', 'Yıllık'),
    ]
    
    # Temel Bilgiler
    title = models.CharField(max_length=200, verbose_name="Başlık")
    description = models.TextField(blank=True, null=True, verbose_name="Açıklama")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='event', verbose_name="Tür")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Öncelik")
    
    # Tarih ve Zaman
    date = models.DateField(verbose_name="Tarih")
    time = models.TimeField(verbose_name="Başlangıç Saati")
    duration = models.PositiveIntegerField(default=60, verbose_name="Süre (dakika)")
    
    # Konum ve Katılımcılar
    location = models.CharField(max_length=300, blank=True, null=True, verbose_name="Konum")
    attendees = models.TextField(blank=True, null=True, verbose_name="Katılımcılar")
    
    # Tekrarlama
    recurring = models.BooleanField(default=False, verbose_name="Tekrarlanan")
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='none', verbose_name="Tekrar Deseni")
    
    # Hatırlatıcılar (JSON formatında)
    reminders = models.TextField(blank=True, null=True, verbose_name="Hatırlatıcılar")
    
    # Oluşturan kullanıcı
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Oluşturan")
    
    # Zaman Damgaları
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    class Meta:
        verbose_name = "Etkinlik"
        verbose_name_plural = "Etkinlikler"
        ordering = ['date', 'time']
    
    def __str__(self):
        return f"{self.title} - {self.date} {self.time}"
    
    def get_type_color(self):
        """Etkinlik türü için renk döndür"""
        colors = {
            'event': '#3b82f6',
            'meeting': '#10b981',
            'task': '#f59e0b',
            'reminder': '#8b5cf6',
            'deadline': '#ef4444'
        }
        return colors.get(self.type, '#6b7280')
    
    def get_priority_color(self):
        """Öncelik için renk döndür"""
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444'
        }
        return colors.get(self.priority, '#6b7280')
    
    def get_duration_display(self):
        """Süreyi okunabilir formatta döndür"""
        if self.duration == 480:
            return 'Tüm gün'
        hours = self.duration // 60
        minutes = self.duration % 60
        
        if hours == 0:
            return f'{minutes} dakika'
        elif minutes == 0:
            return f'{hours} saat'
        else:
            return f'{hours}s {minutes}d'

class Notification(models.Model):
    """Bildirim modeli - Etkinlik hatırlatıcıları ve sistem bildirimleri"""
    
    TYPE_CHOICES = [
        ('event_reminder', 'Etkinlik Hatırlatıcısı'),
        ('event_start', 'Etkinlik Başlangıcı'),
        ('event_created', 'Etkinlik Oluşturuldu'),
        ('system', 'Sistem Bildirimi'),
        ('info', 'Bilgi'),
        ('warning', 'Uyarı'),
        ('error', 'Hata'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Bekliyor'),
        ('sent', 'Gönderildi'),
        ('read', 'Okundu'),
        ('dismissed', 'Kapatıldı'),
    ]
    
    # Temel Bilgiler
    title = models.CharField(max_length=200, verbose_name="Başlık")
    message = models.TextField(verbose_name="Mesaj")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info', verbose_name="Tür")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Durum")
    
    # İlişkili Etkinlik (opsiyonel) - Geçici olarak devre dışı
    # event = models.ForeignKey(Event, on_delete=models.CASCADE, blank=True, null=True, verbose_name="İlişkili Etkinlik")
    
    # Hedef Kullanıcı
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Kullanıcı")
    
    # Zamanlar
    scheduled_time = models.DateTimeField(verbose_name="Planlanmış Zaman")
    sent_time = models.DateTimeField(blank=True, null=True, verbose_name="Gönderilme Zamanı")
    read_time = models.DateTimeField(blank=True, null=True, verbose_name="Okunma Zamanı")
    
    # Ek Veriler (JSON formatında)
    extra_data = models.TextField(blank=True, null=True, verbose_name="Ek Veriler")
    
    # Zaman Damgaları
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    class Meta:
        verbose_name = "Bildirim"
        verbose_name_plural = "Bildirimler"
        ordering = ['-scheduled_time']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def get_type_icon(self):
        """Bildirim türü için ikon döndür"""
        icons = {
            'event_reminder': 'bi-bell',
            'event_start': 'bi-calendar-event',
            'event_created': 'bi-calendar-check',
            'system': 'bi-gear',
            'info': 'bi-info-circle',
            'warning': 'bi-exclamation-triangle',
            'error': 'bi-x-circle',
        }
        return icons.get(self.type, 'bi-bell')
    
    def get_type_color(self):
        """Bildirim türü için renk döndür"""
        colors = {
            'event_reminder': '#3b82f6',
            'event_start': '#10b981',
            'event_created': '#8b5cf6',
            'system': '#6b7280',
            'info': '#06b6d4',
            'warning': '#f59e0b',
            'error': '#ef4444',
        }
        return colors.get(self.type, '#6b7280')
    
    def mark_as_read(self):
        """Bildirimi okundu olarak işaretle"""
        if self.status != 'read':
            self.status = 'read'
            self.read_time = timezone.now()
            self.save()
    
    def mark_as_sent(self):
        """Bildirimi gönderildi olarak işaretle"""
        if self.status == 'pending':
            self.status = 'sent'
            self.sent_time = timezone.now()
            self.save()
    
    def is_overdue(self):
        """Bildirimin zamanı geçmiş mi kontrol et"""
        return timezone.now() > self.scheduled_time and self.status == 'pending'
    
    def get_extra_data_dict(self):
        """Ek verileri dict olarak döndür"""
        if self.extra_data:
            try:
                return json.loads(self.extra_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_extra_data(self, data_dict):
        """Ek verileri dict'ten JSON'a çevir"""
        self.extra_data = json.dumps(data_dict) if data_dict else None


class TransactionCategory(models.Model):
    """Gelir/Gider kategori modeli (çok seviyeli hiyerarşi destekler)"""
    name = models.CharField(max_length=100, verbose_name="Kategori Adı")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children', verbose_name="Üst Kategori")
    order = models.PositiveIntegerField(default=0, verbose_name="Sıra")
    
    # Kullanıcı ve zaman bilgileri
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Oluşturan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategoriler"
        ordering = ['parent__id', 'order', 'name']

    def __str__(self):
        if self.parent:
            return f"{self.parent} / {self.name}"
        return self.name
    
    def get_created_by_display(self):
        """Oluşturan kullanıcının adını döndür"""
        if self.created_by:
            return self.created_by.get_full_name() or self.created_by.username
        return "Sistem"


class Transaction(models.Model):
    """Gelir/Gider işlemleri"""
    TYPE_CHOICES = [
        ('gelir', 'Gelir'),
        ('gider', 'Gider'),
    ]
    KASA_CHOICES = [
        ('servis', 'Servis'),
        ('merkez-satis', 'Merkez Satış'),
        ('virman', 'Virman'),
    ]

    hareket_tipi = models.CharField(max_length=10, choices=TYPE_CHOICES, default='gelir', verbose_name="Hareket Tipi")
    tarih = models.DateField(default=timezone.now, verbose_name="Tarih")

    kasa_adi = models.CharField(max_length=20, choices=KASA_CHOICES, default='servis', verbose_name="Kasa Adı")
    nakit = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="Nakit")
    kredi_karti = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="Kredi Kartı")
    cari = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="Cari")
    sanal_pos = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="Sanal Pos")
    mehmet_havale = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="Mehmet Havale")
    banka_havale = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="Banka Havale")
    aciklama = models.CharField(max_length=255, blank=True, null=True, verbose_name="Açıklama")

    kategori1 = models.ForeignKey(TransactionCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='level1_transactions', verbose_name="1. Kategori")
    kategori2 = models.ForeignKey(TransactionCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='level2_transactions', verbose_name="2. Kategori")
    kategori3 = models.ForeignKey(TransactionCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='level3_transactions', verbose_name="3. Kategori")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Oluşturan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")

    class Meta:
        verbose_name = "İşlem"
        verbose_name_plural = "İşlemler"
        ordering = ['-tarih', '-id']

    def __str__(self):
        return f"{self.get_hareket_tipi_display()} - {self.tarih}"

    @property
    def toplam(self):
        return (
            (self.nakit or 0)
            + (self.kredi_karti or 0)
            + (self.sanal_pos or 0)
            + (self.cari or 0)
            + (self.mehmet_havale or 0)
            + (self.banka_havale or 0)
        )

class MalzemeDosya(models.Model):
    dosya_adi = models.CharField(max_length=200)
    yukleme_tarihi = models.DateTimeField(auto_now_add=True)
    kullanici = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    def __str__(self):
        return f"{self.dosya_adi} - {self.yukleme_tarihi}" 

class MalzemeHareketi(models.Model):
    dosya = models.ForeignKey('MalzemeDosya', on_delete=models.CASCADE, related_name='satirlar', null=True, blank=True)
    tarih = models.DateField()
    faturano = models.CharField(max_length=100)
    musteri = models.CharField(max_length=255)
    urun = models.CharField(max_length=255)
    tutar = models.DecimalField(max_digits=14, decimal_places=2)
    odeme_sekli = models.CharField(max_length=100)
    kullanici = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    eklenme_zamani = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.tarih} - {self.urun} - {self.tutar}'