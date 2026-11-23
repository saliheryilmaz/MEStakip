from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class AramaGecmisi(models.Model):
    kullanici     = models.ForeignKey(User, on_delete=models.CASCADE, related_name="aramalar", null=True, blank=True)
    ebat          = models.CharField(max_length=30)
    marka         = models.CharField(max_length=50, blank=True)
    mevsim        = models.CharField(max_length=20, blank=True)
    sonuc_sayisi  = models.IntegerField(default=0)
    arama_zamani  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-arama_zamani"]

    def __str__(self):
        kim = self.kullanici.username if self.kullanici else "—"
        return f"{kim} | {self.ebat} {self.marka} ({self.arama_zamani:%d.%m.%Y %H:%M})"


class Abonelik(models.Model):
    """Her kullanıcıya bir abonelik kaydı. Admin panelinden yönetilir."""

    PLAN_CHOICES = [
        ("aylik",   "Aylık"),
        ("yillik",  "Yıllık"),
        ("demo",    "Demo"),
        ("deneme",  "Deneme"),
    ]

    kullanici   = models.OneToOneField(User, on_delete=models.CASCADE, related_name="abonelik")
    plan        = models.CharField(max_length=10, choices=PLAN_CHOICES, default="demo")
    baslangic   = models.DateField(default=timezone.localdate)
    bitis       = models.DateField()
    aktif       = models.BooleanField(default=True)
    not_alani   = models.TextField(blank=True, help_text="Müşteri notları")
    session_key = models.CharField(max_length=40, blank=True, default="",
                                   help_text="Aktif session key — tek oturum kontrolü için")

    class Meta:
        verbose_name        = "Abonelik"
        verbose_name_plural = "Abonelikler"
        ordering            = ["-bitis"]

    def suresi_doldu_mu(self) -> bool:
        return timezone.localdate() > self.bitis

    @property
    def erisim_var_mi(self) -> bool:
        return self.aktif and not self.suresi_doldu_mu()

    def __str__(self):
        durum = "✓" if self.erisim_var_mi else "✗"
        return f"{durum} {self.kullanici.username} — {self.bitis} ({self.plan})"


class Odeme(models.Model):
    """Kullanıcıya ait ödeme kaydı. Admin panelinden manuel olarak eklenir."""

    YONTEM_CHOICES = [
        ("nakit",       "Nakit"),
        ("havale",      "Havale / EFT"),
        ("kredi_karti", "Kredi Kartı"),
        ("diger",       "Diğer"),
    ]

    kullanici   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="odemeler")
    tutar       = models.DecimalField(max_digits=10, decimal_places=2)
    tarih       = models.DateField()
    yontem      = models.CharField(max_length=20, choices=YONTEM_CHOICES, default="havale")
    aciklama    = models.TextField(blank=True, help_text="Dekont no, dönem vb.")
    olusturulma = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Ödeme"
        verbose_name_plural = "Ödemeler"
        ordering            = ["-tarih"]

    def __str__(self):
        return f"{self.kullanici.username} — {self.tutar} ₺ ({self.tarih})"


class Notlar(models.Model):
    """Kullanıcının fiyat verirken aldığı kısa notlar. 7 gün sonra otomatik silinir."""
    kullanici   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notlar")
    ebat        = models.CharField(max_length=30, blank=True)
    marka       = models.CharField(max_length=80, blank=True)
    musteri     = models.CharField(max_length=100, blank=True)
    icerik      = models.TextField()
    olusturulma = models.DateTimeField(auto_now_add=True)
    silinme     = models.DateTimeField()

    class Meta:
        verbose_name        = "Not"
        verbose_name_plural = "Notlar"
        ordering            = ["-olusturulma"]

    def save(self, *args, **kwargs):
        if not self.pk:
            self.silinme = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def kalan_gun(self) -> int:
        delta = self.silinme - timezone.now()
        return max(0, delta.days)

    def __str__(self):
        return f"{self.kullanici.username} | {self.ebat} | {self.icerik[:40]}"


class ToptanciIskonto(models.Model):
    """Her kullanıcının her toptancı için kendi iskonto/özel fiyat notu."""
    kullanici    = models.ForeignKey(User, on_delete=models.CASCADE,
                                     related_name="iskontolar", null=True, blank=True)
    toptanci_adi = models.CharField(max_length=60,
                                    help_text="Toptancı adı (B2B_LINKLER ile eşleşmeli)")
    iskonto_metni = models.TextField(blank=True,
                                     help_text="Tooltip'te gösterilecek iskonto/not metni.")
    guncelleme   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Toptancı İskonto"
        verbose_name_plural = "Toptancı İskontolar"
        ordering            = ["toptanci_adi"]
        unique_together     = [("kullanici", "toptanci_adi")]

    def __str__(self):
        kim = self.kullanici.username if self.kullanici else "global"
        return f"{kim} / {self.toptanci_adi}: {self.iskonto_metni[:40]}"
