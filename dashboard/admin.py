from django.contrib import admin
from .models import Siparis, UserProfile, Notification, Transaction, TransactionCategory, Event, MalzemeHareketi, MalzemeDosya, CikmaLastik

@admin.register(Siparis)
class SiparisAdmin(admin.ModelAdmin):
    """Sipariş admin paneli"""
    
    list_display = [
        'id', 'cari_firma', 'marka', 'urun', 'grup', 
        'mevsim', 'adet', 'birim_fiyat', 'toplam_fiyat', 
        'durum', 'ambar', 'odeme', 'sms_durum', 'one_cikar', 
        'olusturma_tarihi'
    ]
    
    list_filter = [
        'grup', 'mevsim', 'durum', 'odeme', 'sms_durum', 
        'one_cikar', 'olusturma_tarihi'
    ]
    
    search_fields = [
        'cari_firma', 'marka', 'urun', 'ambar', 'aciklama'
    ]
    
    list_editable = [
        'durum', 'ambar', 'sms_durum', 'one_cikar'
    ]
    
    readonly_fields = [
        'toplam_fiyat', 'olusturma_tarihi', 'guncelleme_tarihi'
    ]
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('cari_firma', 'marka', 'urun')
        }),
        ('Kategori', {
            'fields': ('grup', 'mevsim')
        }),
        ('Miktar ve Fiyat', {
            'fields': ('adet', 'birim_fiyat', 'toplam_fiyat')
        }),
        ('Durum', {
            'fields': ('durum', 'ambar', 'odeme', 'sms_durum')
        }),
        ('Ek Bilgiler', {
            'fields': ('aciklama', 'one_cikar'),
            'classes': ('collapse',)
        }),
        ('Zaman Damgaları', {
            'fields': ('olusturma_tarihi', 'guncelleme_tarihi'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-olusturma_tarihi']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Etkinlik admin paneli"""
    
    list_display = [
        'id', 'title', 'type', 'date', 'time', 'priority', 
        'location', 'created_by', 'created_at'
    ]
    
    list_filter = [
        'type', 'priority', 'date', 'recurring', 'created_at'
    ]
    
    search_fields = [
        'title', 'description', 'location', 'attendees'
    ]
    
    list_editable = [
        'type', 'priority'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('title', 'description', 'type', 'priority')
        }),
        ('Tarih ve Zaman', {
            'fields': ('date', 'time', 'duration')
        }),
        ('Konum ve Katılımcılar', {
            'fields': ('location', 'attendees')
        }),
        ('Tekrarlama', {
            'fields': ('recurring', 'recurrence'),
            'classes': ('collapse',)
        }),
        ('Hatırlatıcılar', {
            'fields': ('reminders',),
            'classes': ('collapse',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-created_at']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Yeni kayıt ise
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Kullanıcı Profili admin paneli"""
    
    list_display = [
        'user', 'role', 'created_at', 'updated_at'
    ]
    
    list_filter = [
        'role', 'created_at'
    ]
    
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name', 'user__email'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at'
    ]

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Bildirim admin paneli"""
    
    list_display = [
        'id', 'title', 'type', 'status', 'user',
        'scheduled_time', 'sent_time', 'read_time', 'created_at'
    ]
    
    list_filter = [
        'type', 'status', 'scheduled_time', 'created_at'
    ]
    
    search_fields = [
        'title', 'message', 'user__username', 'user__first_name', 'user__last_name'
    ]
    
    list_editable = [
        'status'
    ]
    
    readonly_fields = [
        'sent_time', 'read_time', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('title', 'message', 'type', 'status')
        }),
        ('İlişkiler', {
            'fields': ('user',)
        }),
        ('Zamanlar', {
            'fields': ('scheduled_time', 'sent_time', 'read_time')
        }),
        ('Ek Veriler', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-scheduled_time']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    actions = ['mark_as_sent', 'mark_as_read', 'mark_as_dismissed']
    
    def mark_as_sent(self, request, queryset):
        """Seçili bildirimleri gönderildi olarak işaretle"""
        count = 0
        for notification in queryset:
            if notification.status == 'pending':
                notification.mark_as_sent()
                count += 1
        
        self.message_user(request, f'{count} bildirim gönderildi olarak işaretlendi.')
    mark_as_sent.short_description = "Seçili bildirimleri gönderildi olarak işaretle"
    
    def mark_as_read(self, request, queryset):
        """Seçili bildirimleri okundu olarak işaretle"""
        count = 0
        for notification in queryset:
            if notification.status in ['pending', 'sent']:
                notification.mark_as_read()
                count += 1
        
        self.message_user(request, f'{count} bildirim okundu olarak işaretlendi.')
    mark_as_read.short_description = "Seçili bildirimleri okundu olarak işaretle"
    
    def mark_as_dismissed(self, request, queryset):
        """Seçili bildirimleri kapatıldı olarak işaretle"""
        count = queryset.update(status='dismissed')
        self.message_user(request, f'{count} bildirim kapatıldı olarak işaretlendi.')
    mark_as_dismissed.short_description = "Seçili bildirimleri kapatıldı olarak işaretle"


@admin.register(TransactionCategory)
class TransactionCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'parent', 'order']
    list_filter = ['parent']
    search_fields = ['name']
    ordering = ['parent__id', 'order', 'name']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'hareket_tipi', 'tarih', 'kasa_adi', 'nakit', 'kredi_karti', 'sanal_pos', 'cari', 'toplam', 'kategori1', 'kategori2', 'kategori3', 'created_by']
    list_filter = ['hareket_tipi', 'tarih', 'kategori1', 'kategori2', 'kategori3']
    search_fields = ['aciklama', 'kasa_adi']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-tarih', '-id']

@admin.register(CikmaLastik)
class CikmaLastikAdmin(admin.ModelAdmin):
    """Çıkma Lastik admin paneli"""
    
    list_display = [
        'id', 'marka', 'model', 'ebat', 
        'mevsim', 'arac_tipi', 'adet', 'durum', 
        'kalite_notu', 'tahmini_deger', 'cikis_tarihi', 
        'user', 'olusturma_tarihi'
    ]
    
    list_filter = [
        'durum', 'mevsim', 'arac_tipi', 'cikis_tarihi', 
        'olusturma_tarihi', 'user'
    ]
    
    search_fields = [
        'marka', 'model', 'ebat', 'aciklama'
    ]
    
    list_editable = [
        'durum', 'kalite_notu', 'tahmini_deger'
    ]
    
    readonly_fields = [
        'olusturma_tarihi', 'guncelleme_tarihi'
    ]
    
    fieldsets = (
        ('Lastik Bilgileri', {
            'fields': ('marka', 'model', 'ebat', 'mevsim', 'arac_tipi', 'adet')
        }),
        ('Durum ve Kalite', {
            'fields': ('durum', 'diş_derinligi', 'kalite_notu', 'hasar_durumu')
        }),
        ('Fiyat ve Konum', {
            'fields': ('tahmini_deger', 'satis_fiyati', 'depo_konumu')
        }),
        ('Tarihler', {
            'fields': ('cikis_tarihi', 'satis_tarihi')
        }),
        ('Ek Bilgiler', {
            'fields': ('aciklama',),
            'classes': ('collapse',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('user', 'olusturma_tarihi', 'guncelleme_tarihi'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-cikis_tarihi', '-olusturma_tarihi']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def save_model(self, request, obj, form, change):
        if not change:  # Yeni kayıt ise
            obj.user = request.user
        super().save_model(request, obj, form, change)


admin.site.register(MalzemeHareketi)
admin.site.register(MalzemeDosya)