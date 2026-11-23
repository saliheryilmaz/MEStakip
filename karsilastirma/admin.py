from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .models import Abonelik, AramaGecmisi, Odeme, Notlar


# ── Abonelik inline — User admin içinde görünür ──────────────────────────────

class AbonelikInline(admin.StackedInline):
    model           = Abonelik
    can_delete      = False
    verbose_name    = "Abonelik Bilgisi"
    extra           = 1
    fields          = ("plan", "baslangic", "bitis", "aktif", "not_alani")


class KullaniciAdmin(UserAdmin):
    inlines         = (AbonelikInline,)
    list_display    = ("username", "email", "abonelik_durumu", "abonelik_bitis", "is_staff")
    list_filter     = ("is_active", "is_staff")

    def abonelik_durumu(self, obj):
        try:
            ab = obj.abonelik
            if ab.erisim_var_mi:
                return mark_safe('<span style="color:green;font-weight:bold">✓ Aktif</span>')
            return mark_safe('<span style="color:red;font-weight:bold">✗ Süresi Doldu</span>')
        except Abonelik.DoesNotExist:
            return mark_safe('<span style="color:gray">— Yok</span>')
    abonelik_durumu.short_description = "Abonelik"
    abonelik_durumu.allow_tags = True  # Django eski sürüm uyumluluğu

    def abonelik_bitis(self, obj):
        try:
            return obj.abonelik.bitis
        except Abonelik.DoesNotExist:
            return "—"
    abonelik_bitis.short_description = "Bitiş"


# User admin'i yeniden kaydet
admin.site.unregister(User)
admin.site.register(User, KullaniciAdmin)


# ── Abonelik ayrı admin sayfası ───────────────────────────────────────────────

@admin.register(Abonelik)
class AbonelikAdmin(admin.ModelAdmin):
    list_display  = ("kullanici", "plan", "baslangic", "bitis", "aktif", "kalan_gun")
    list_filter   = ("plan", "aktif")
    search_fields = ("kullanici__username", "kullanici__email")
    list_editable = ("aktif",)
    ordering      = ("bitis",)

    def kalan_gun(self, obj):
        kalan = (obj.bitis - timezone.localdate()).days
        if kalan < 0:
            return mark_safe(f'<span style="color:red">Süresi doldu ({abs(kalan)} gün)</span>')
        if kalan <= 7:
            return mark_safe(f'<span style="color:orange">{kalan} gün</span>')
        return mark_safe(f'<span style="color:green">{kalan} gün</span>')
    kalan_gun.short_description = "Kalan"


# ── Arama geçmişi ─────────────────────────────────────────────────────────────

@admin.register(AramaGecmisi)
class AramaGecmisiAdmin(admin.ModelAdmin):
    list_display    = ("kullanici", "ebat", "marka", "mevsim", "sonuc_sayisi", "arama_zamani")
    list_filter     = ("mevsim", "kullanici")
    search_fields   = ("ebat", "marka", "kullanici__username")
    readonly_fields = ("arama_zamani",)


@admin.register(Odeme)
class OdemeAdmin(admin.ModelAdmin):
    list_display   = ("kullanici", "tutar_tl", "tarih", "yontem", "aciklama")
    list_filter    = ("yontem", "tarih")
    search_fields  = ("kullanici__username", "aciklama")
    date_hierarchy = "tarih"
    ordering       = ("-tarih",)

    def tutar_tl(self, obj):
        return f"{obj.tutar:,.2f} ₺"
    tutar_tl.short_description = "Tutar"


@admin.register(Notlar)
class NotlarAdmin(admin.ModelAdmin):
    list_display   = ("kullanici", "ebat", "marka", "kisa_icerik", "olusturulma", "silinme")
    list_filter    = ("kullanici",)
    search_fields  = ("kullanici__username", "ebat", "marka", "icerik")
    readonly_fields = ("olusturulma", "silinme")
    ordering       = ("-olusturulma",)

    def kisa_icerik(self, obj):
        return obj.icerik[:60] + ("…" if len(obj.icerik) > 60 else "")
    kisa_icerik.short_description = "Not"
