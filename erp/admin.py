"""
ERP Admin paneli — Cari ve gelecek modüller için.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Cari, CariDurum, CariTip


@admin.register(Cari)
class CariAdmin(admin.ModelAdmin):
    list_display = (
        'cari_kodu', 'unvan', 'tip_badge', 'durum_badge',
        'vergi_no', 'telefon1', 'sehir',
        'bakiye_goster', 'sync_durum_badge', 'son_sync_tarihi',
    )
    list_filter = ('tip', 'durum', 'sync_durumu', 'sehir')
    search_fields = ('cari_kodu', 'unvan', 'vergi_no', 'tc_kimlik_no', 'telefon1', 'eposta')
    readonly_fields = (
        'dia_key', 'son_sync_tarihi', 'sync_durumu', 'dia_son_degisiklik',
        'bakiye', 'borc_toplam', 'alacak_toplam',
        'olusturuldu', 'guncellendi',
    )
    fieldsets = (
        (_('Temel Bilgiler'), {
            'fields': ('cari_kodu', 'unvan', 'kisa_aciklama', 'tip', 'durum', 'notlar'),
        }),
        (_('Vergi / Kimlik'), {
            'fields': ('vergi_no', 'tc_kimlik_no', 'vergi_dairesi', 'daire_kodu'),
        }),
        (_('İletişim'), {
            'fields': ('telefon1', 'telefon2', 'cep_tel', 'fax', 'eposta', 'web_url'),
        }),
        (_('Adres'), {
            'fields': ('adres1', 'adres2', 'ilce', 'sehir', 'posta_kodu', 'ulke'),
        }),
        (_('Finansal'), {
            'fields': (
                'risk_limiti', 'indirim_orani',
                'bakiye', 'borc_toplam', 'alacak_toplam',
                'efatura_senaryosu',
            ),
        }),
        (_('DİA Senkronizasyon (salt okunur)'), {
            'fields': ('dia_key', 'sync_durumu', 'son_sync_tarihi', 'dia_son_degisiklik'),
            'classes': ('collapse',),
        }),
        (_('Zaman Damgaları'), {
            'fields': ('olusturuldu', 'guncellendi'),
            'classes': ('collapse',),
        }),
    )
    actions = ['dia_ya_gonder', 'bakiye_guncelle', 'cari_sync_et']
    ordering = ['unvan']
    list_per_page = 50

    @admin.display(description=_('Tip'))
    def tip_badge(self, obj: Cari) -> str:
        renkler = {
            CariTip.ALICI: '#2196F3',
            CariTip.SATICI: '#FF9800',
            CariTip.ALICI_SATICI: '#9C27B0',
            CariTip.DIGER: '#607D8B',
        }
        renk = renkler.get(obj.tip, '#607D8B')
        return format_html(
            '<span style="color:{}; font-weight:bold">{}</span>',
            renk,
            obj.get_tip_display(),
        )

    @admin.display(description=_('Durum'))
    def durum_badge(self, obj: Cari) -> str:
        if obj.durum == CariDurum.AKTIF:
            return format_html('<span style="color:green">✓ Aktif</span>')
        return format_html('<span style="color:grey">✗ Pasif</span>')

    @admin.display(description=_('Bakiye'))
    def bakiye_goster(self, obj: Cari) -> str:
        if obj.bakiye == 0:
            return '0,00'
        renk = 'red' if obj.bakiye > 0 else 'green'
        return format_html(
            '<span style="color:{}">{:,.2f} ₺</span>',
            renk,
            obj.bakiye,
        )

    @admin.display(description=_('Sync'))
    def sync_durum_badge(self, obj: Cari) -> str:
        from dia_integration.mixins import SyncDurumSecenekleri
        renkler = {
            SyncDurumSecenekleri.SENKRON: 'green',
            SyncDurumSecenekleri.BEKLIYOR: 'orange',
            SyncDurumSecenekleri.HATALI: 'red',
            SyncDurumSecenekleri.YEREL: 'blue',
            SyncDurumSecenekleri.ISLENIYOR: 'grey',
        }
        renk = renkler.get(obj.sync_durumu, 'grey')
        return format_html(
            '<span style="color:{}">{}</span>',
            renk,
            obj.get_sync_durumu_display(),
        )

    @admin.action(description=_('Seçilenleri DİA\'ya gönder (oluştur/güncelle)'))
    def dia_ya_gonder(self, request, queryset):
        from dia_integration.services import CariService
        from dia_integration.exceptions import DiaBaseError
        basarili = hatali = 0
        for cari in queryset:
            try:
                CariService.dia_ya_gonder(cari)
                basarili += 1
            except DiaBaseError as exc:
                hatali += 1
                self.message_user(request, f'{cari.cari_kodu}: {exc}', level='error')
        if basarili:
            self.message_user(request, f'{basarili} cari DİA\'ya başarıyla gönderildi.')

    @admin.action(description=_('Seçilenlerin bakiyesini DİA\'dan güncelle'))
    def bakiye_guncelle(self, request, queryset):
        from dia_integration.services import CariService
        from dia_integration.exceptions import DiaBaseError
        basarili = 0
        for cari in queryset.filter(dia_key__isnull=False).exclude(dia_key=''):
            try:
                CariService.bakiye_guncelle(cari)
                basarili += 1
            except Exception as exc:
                self.message_user(request, f'{cari.cari_kodu}: {exc}', level='warning')
        self.message_user(request, f'{basarili} carinin bakiyesi güncellendi.')

    @admin.action(description=_('DİA\'dan cari sync et (delta)'))
    def cari_sync_et(self, request, queryset):
        from dia_integration.tasks import sync_cari_listesi
        sync_cari_listesi.delay(delta=True)
        self.message_user(request, 'Cari delta sync görevi Celery kuyruğuna gönderildi.')


# ─────────────────────────────────────────────────────────────
# Faz 3 — Stok / Depo admin
# ─────────────────────────────────────────────────────────────

from .models import Depo, StokDurum, StokKart, StokDepoMiktari


class StokDepoMiktariInline(admin.TabularInline):
    model = StokDepoMiktari
    extra = 0
    readonly_fields = ('depo', 'gercek_miktar', 'fiili_miktar', 'son_sync')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StokKart)
class StokKartAdmin(admin.ModelAdmin):
    list_display = (
        'stok_kodu', 'aciklama', 'tur', 'durum_badge',
        'ana_birim', 'marka',
        'gercek_stok_goster', 'fiili_stok_goster',
        'sync_durum_badge', 'son_sync_tarihi',
    )
    list_filter = ('tur', 'durum', 'sync_durumu', 'marka')
    search_fields = ('stok_kodu', 'aciklama', 'ana_barkod', 'marka')
    readonly_fields = (
        'dia_key', 'son_sync_tarihi', 'sync_durumu', 'dia_son_degisiklik',
        'gercek_stok', 'fiili_stok', 'olusturuldu', 'guncellendi',
    )
    inlines = [StokDepoMiktariInline]
    actions = ['dia_ya_gonder', 'stok_sync_et']
    list_per_page = 50

    fieldsets = (
        (_('Temel Bilgiler'), {
            'fields': ('stok_kodu', 'aciklama', 'tur', 'durum', 'notlar'),
        }),
        (_('Birim / Barkod'), {
            'fields': ('ana_birim', 'ana_birim_dia_key', 'ana_barkod'),
        }),
        (_('Marka / Kategori'), {
            'fields': ('marka', 'ozel_kod1', 'ozel_kod2'),
        }),
        (_('Vergi / Fiyat'), {
            'fields': ('kdv_alis', 'kdv_satis', 'fiyat1', 'fiyat2'),
        }),
        (_('Stok Miktarı (DİA — salt okunur)'), {
            'fields': ('gercek_stok', 'fiili_stok'),
        }),
        (_('DİA Senkronizasyon (salt okunur)'), {
            'fields': ('dia_key', 'sync_durumu', 'son_sync_tarihi', 'dia_son_degisiklik'),
            'classes': ('collapse',),
        }),
        (_('Zaman Damgaları'), {
            'fields': ('olusturuldu', 'guncellendi'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Durum'))
    def durum_badge(self, obj: StokKart) -> str:
        if obj.durum == StokDurum.AKTIF:
            return format_html('<span style="color:green">✓ Aktif</span>')
        return format_html('<span style="color:grey">✗ Pasif</span>')

    @admin.display(description=_('Gerçek stok'))
    def gercek_stok_goster(self, obj: StokKart) -> str:
        renk = 'red' if obj.gercek_stok <= 0 else 'green'
        return format_html(
            '<span style="color:{}">{} {}</span>',
            renk, obj.gercek_stok, obj.ana_birim,
        )

    @admin.display(description=_('Fiili stok'))
    def fiili_stok_goster(self, obj: StokKart) -> str:
        return f'{obj.fiili_stok} {obj.ana_birim}'

    @admin.display(description=_('Sync'))
    def sync_durum_badge(self, obj: StokKart) -> str:
        from dia_integration.mixins import SyncDurumSecenekleri
        renkler = {
            SyncDurumSecenekleri.SENKRON:  'green',
            SyncDurumSecenekleri.BEKLIYOR: 'orange',
            SyncDurumSecenekleri.HATALI:   'red',
            SyncDurumSecenekleri.YEREL:    'blue',
        }
        renk = renkler.get(obj.sync_durumu, 'grey')
        return format_html(
            '<span style="color:{}">{}</span>', renk, obj.get_sync_durumu_display()
        )

    @admin.action(description=_('Seçilenleri DİA\'ya gönder'))
    def dia_ya_gonder(self, request, queryset):
        from dia_integration.services import StokService
        from dia_integration.exceptions import DiaBaseError
        basarili = hatali = 0
        for stok in queryset:
            try:
                StokService.dia_ya_gonder(stok)
                basarili += 1
            except DiaBaseError as exc:
                hatali += 1
                self.message_user(request, f'{stok.stok_kodu}: {exc}', level='error')
        if basarili:
            self.message_user(request, f'{basarili} stok DİA\'ya başarıyla gönderildi.')

    @admin.action(description=_('DİA\'dan stok sync et (delta)'))
    def stok_sync_et(self, request, queryset):
        from dia_integration.tasks import sync_stok_listesi
        sync_stok_listesi.delay(delta=True)
        self.message_user(request, 'Stok delta sync görevi Celery kuyruğuna gönderildi.')


@admin.register(Depo)
class DepoAdmin(admin.ModelAdmin):
    list_display = ('ad', 'sube_adi', 'dia_key', 'sube_dia_key', 'aktif')
    list_filter = ('aktif', 'sube_adi')
    search_fields = ('ad', 'sube_adi', 'dia_key')
    readonly_fields = ('olusturuldu', 'guncellendi')
