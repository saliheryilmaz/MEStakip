"""
DİA Entegrasyon — Django Admin paneli.

Bu panel üzerinden:
  - DİA bağlantı ayarları görüntülenip düzenlenebilir
  - API istek logları izlenebilir
  - Sync logları ve hata kayıtları incelenebilir
  - Senkron kuyruğu yönetilebilir (manual retry vb.)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    ApiIstekLog,
    DiaBaglanti,
    SenkronKuyrugu,
    SenkronKuyrukDurum,
    SyncDurum,
    SyncHataKaydi,
    SyncLog,
)


# ─────────────────────────────────────────────────────────────
# DiaBaglanti
# ─────────────────────────────────────────────────────────────

@admin.register(DiaBaglanti)
class DiaBaglantiAdmin(admin.ModelAdmin):
    list_display = (
        'ad', 'sunucu_kodu', 'firma_kodu', 'donem_kodu',
        'is_aktif', 'session_durum_badge', 'guncellendi',
    )
    list_filter = ('is_aktif',)
    readonly_fields = (
        'session_id', 'session_alindi',
        'firma_donem_bilgisi', 'firma_donem_guncellendi',
        'olusturuldu', 'guncellendi',
    )
    fieldsets = (
        (_('Bağlantı Bilgisi'), {
            'fields': ('ad', 'sunucu_kodu', 'kullanici_adi', 'sifre_maskelenmiş',
                       'firma_kodu', 'donem_kodu', 'is_aktif'),
        }),
        (_('Aktif Session (salt okunur)'), {
            'fields': ('session_id', 'session_alindi'),
            'classes': ('collapse',),
        }),
        (_('Firma/Dönem Önbelleği (salt okunur)'), {
            'fields': ('firma_donem_bilgisi', 'firma_donem_guncellendi'),
            'classes': ('collapse',),
        }),
        (_('Zaman Damgaları'), {
            'fields': ('olusturuldu', 'guncellendi'),
            'classes': ('collapse',),
        }),
    )
    actions = ['baglanti_test_et', 'firma_donem_guncelle']

    @admin.display(description=_('Session'), boolean=False)
    def session_durum_badge(self, obj: DiaBaglanti) -> str:
        from django.conf import settings
        ttl = getattr(settings, 'DIA_SESSION_TTL_SECONDS', 3000)
        if obj.session_gecerli_mi(ttl):
            return format_html('<span style="color:green">✓ Aktif</span>')
        return format_html('<span style="color:red">✗ Süresi Dolmuş</span>')

    @admin.action(description=_('Seçili bağlantıyı test et (DİA login/logout)'))
    def baglanti_test_et(self, request, queryset):
        from dia_integration.tasks import test_dia_baglantisi
        for _ in queryset:
            test_dia_baglantisi.delay()
        self.message_user(request, _('Bağlantı testi görevi Celery kuyruğuna gönderildi.'))

    @admin.action(description=_('Firma/dönem önbelleğini güncelle'))
    def firma_donem_guncelle(self, request, queryset):
        from dia_integration.tasks import sync_firma_donem
        sync_firma_donem.delay()
        self.message_user(request, _('Firma/dönem sync görevi Celery kuyruğuna gönderildi.'))


# ─────────────────────────────────────────────────────────────
# SyncLog + SyncHataKaydi (inline)
# ─────────────────────────────────────────────────────────────

class SyncHataKaydiInline(admin.TabularInline):
    model = SyncHataKaydi
    extra = 0
    readonly_fields = ('modul', 'yerel_model', 'yerel_id', 'dia_servis',
                       'hata_kodu', 'hata_mesaji', 'deneme_sayisi', 'olusturuldu')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = (
        'modul', 'baslangic', 'durum_badge', 'tetikleyen',
        'toplam_kayit', 'basarili_kayit', 'hatali_kayit', 'sure_goster',
    )
    list_filter = ('modul', 'durum', 'tetikleyen')
    search_fields = ('modul', 'hata_mesaji', 'celery_task_id')
    readonly_fields = (
        'modul', 'baslangic', 'bitis', 'durum', 'tetikleyen',
        'tetikleyen_kullanici', 'toplam_kayit', 'basarili_kayit',
        'hatali_kayit', 'hata_mesaji', 'celery_task_id',
    )
    inlines = [SyncHataKaydiInline]
    date_hierarchy = 'baslangic'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description=_('Durum'))
    def durum_badge(self, obj: SyncLog) -> str:
        renkler = {
            SyncDurum.BASARILI: 'green',
            SyncDurum.KISMI_BASARILI: 'orange',
            SyncDurum.BASARISIZ: 'red',
            SyncDurum.CALISIYOR: 'blue',
        }
        renk = renkler.get(obj.durum, 'grey')
        return format_html(
            '<span style="color:{}">{}</span>', renk, obj.get_durum_display()
        )

    @admin.display(description=_('Süre'))
    def sure_goster(self, obj: SyncLog) -> str:
        if obj.bitis and obj.baslangic:
            sure = (obj.bitis - obj.baslangic).total_seconds()
            return f'{sure:.1f}s'
        return '—'


# ─────────────────────────────────────────────────────────────
# ApiIstekLog
# ─────────────────────────────────────────────────────────────

@admin.register(ApiIstekLog)
class ApiIstekLogAdmin(admin.ModelAdmin):
    list_display = (
        'servis_adi', 'istek_zamani', 'basarili_badge',
        'sure_ms', 'http_durum_kodu', 'dia_durum_kodu', 'sonuc_sayisi',
    )
    list_filter = ('basarili', 'servis_adi')
    search_fields = ('servis_adi', 'hata_mesaji')
    date_hierarchy = 'istek_zamani'

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description=_('Sonuç'), boolean=True)
    def basarili_badge(self, obj: ApiIstekLog) -> bool:
        return obj.basarili


# ─────────────────────────────────────────────────────────────
# SenkronKuyrugu
# ─────────────────────────────────────────────────────────────

@admin.register(SenkronKuyrugu)
class SenkronKuyruguAdmin(admin.ModelAdmin):
    list_display = (
        'modul', 'islem_tipi', 'yerel_model', 'yerel_id',
        'durum_badge', 'deneme_sayisi', 'max_deneme',
        'sonraki_deneme', 'olusturuldu',
    )
    list_filter = ('durum', 'modul', 'islem_tipi')
    search_fields = ('yerel_model', 'yerel_id', 'dia_key', 'son_hata')
    readonly_fields = ('olusturuldu', 'guncellendi')
    actions = ['yeniden_dene', 'iptal_et']

    @admin.display(description=_('Durum'))
    def durum_badge(self, obj: SenkronKuyrugu) -> str:
        renkler = {
            SenkronKuyrukDurum.BEKLIYOR: 'orange',
            SenkronKuyrukDurum.ISLENIYOR: 'blue',
            SenkronKuyrukDurum.TAMAMLANDI: 'green',
            SenkronKuyrukDurum.BASARISIZ: 'red',
            SenkronKuyrukDurum.IPTAL: 'grey',
        }
        renk = renkler.get(obj.durum, 'grey')
        return format_html(
            '<span style="color:{}">{}</span>', renk, obj.get_durum_display()
        )

    @admin.action(description=_('Seçilenleri yeniden dene (BEKLIYOR durumuna al)'))
    def yeniden_dene(self, request, queryset):
        from django.utils import timezone as tz
        guncellenen = queryset.filter(
            durum__in=[SenkronKuyrukDurum.BASARISIZ, SenkronKuyrukDurum.ISLENIYOR]
        ).update(
            durum=SenkronKuyrukDurum.BEKLIYOR,
            sonraki_deneme=tz.now(),
        )
        self.message_user(request, f'{guncellenen} kayıt yeniden deneme kuyruğuna alındı.')

    @admin.action(description=_('Seçilenleri iptal et'))
    def iptal_et(self, request, queryset):
        guncellenen = queryset.exclude(
            durum=SenkronKuyrukDurum.TAMAMLANDI
        ).update(durum=SenkronKuyrukDurum.IPTAL)
        self.message_user(request, f'{guncellenen} görev iptal edildi.')
