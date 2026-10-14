"""
DiaSyncMixin — DİA ile senkronize edilebilen modeller için soyut mixin.

Kullanım (erp/models.py içinde):
    from dia_integration.mixins import DiaSyncMixin

    class Cari(DiaSyncMixin, models.Model):
        unvan = models.CharField(...)
        ...
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SyncDurumSecenekleri(models.TextChoices):
    SENKRON = 'senkron', _('Senkron (DİA ile uyumlu)')
    BEKLIYOR = 'bekliyor', _('Bekliyor (senkronize edilmedi)')
    ISLENIYOR = 'isleniyor', _('İşleniyor')
    HATALI = 'hatali', _('Hatalı (son sync başarısız)')
    YEREL = 'yerel', _('Yerel değişiklik var (DİA\'ya yazılmadı)')


class DiaSyncMixin(models.Model):
    """
    DİA ile senkronize edilecek tüm iş modellerine eklenecek alanlar.

    Sağladığı alanlar:
        dia_key          : DİA'daki kaydın _key değeri (unique, nullable)
        son_sync_tarihi  : Son başarılı senkronizasyon zamanı
        sync_durumu      : Mevcut senkronizasyon durumu
        dia_son_degisiklik: DİA'daki son değişiklik zamanı (_date alanından)
    """

    dia_key = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_('DİA Key'),
        help_text=_('DİA ERP\'deki kaydın _key değeri. Henüz senkronize edilmediyse boş.'),
        db_index=True,
    )
    son_sync_tarihi = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Son senkronizasyon'),
    )
    sync_durumu = models.CharField(
        max_length=20,
        choices=SyncDurumSecenekleri.choices,
        default=SyncDurumSecenekleri.BEKLIYOR,
        verbose_name=_('Sync durumu'),
        db_index=True,
    )
    dia_son_degisiklik = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('DİA\'da son değişiklik'),
        help_text=_('DİA _date alanından alınan son güncelleme zamanı (delta sync için)'),
    )

    class Meta:
        abstract = True

    def sync_basarili_isle(self, dia_key: str | None = None) -> None:
        """Başarılı senkronizasyon sonrası çağrılır."""
        if dia_key:
            self.dia_key = dia_key
        self.son_sync_tarihi = timezone.now()
        self.sync_durumu = SyncDurumSecenekleri.SENKRON
        self.save(update_fields=['dia_key', 'son_sync_tarihi', 'sync_durumu'])

    def sync_hatali_isle(self) -> None:
        """Başarısız senkronizasyon sonrası çağrılır."""
        self.sync_durumu = SyncDurumSecenekleri.HATALI
        self.save(update_fields=['sync_durumu'])

    def yerel_degisiklik_isle(self) -> None:
        """Kayıt yerel olarak değiştirildiğinde (signal ile) çağrılır."""
        self.sync_durumu = SyncDurumSecenekleri.YEREL
        self.save(update_fields=['sync_durumu'])

    @property
    def dia_da_var_mi(self) -> bool:
        """Kayıt DİA'da oluşturulmuş mu?"""
        return bool(self.dia_key)
