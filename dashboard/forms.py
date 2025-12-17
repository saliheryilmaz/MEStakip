from django import forms
from django.utils import timezone
from .models import Transaction, TransactionCategory
from .models import Siparis
from .models import MalzemeHareketi


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            'hareket_tipi', 'tarih', 'kasa_adi',
            'nakit', 'kredi_karti', 'cari', 'sanal_pos',
            'mehmet_havale', 'banka_havale', 'pafgo',
            'aciklama', 'kategori1'
        ]
        widgets = {
            'tarih': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hareket_tipi': forms.Select(attrs={'class': 'form-select'}),
            'kasa_adi': forms.Select(attrs={'class': 'form-select'}),
            'nakit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'kredi_karti': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'cari': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'sanal_pos': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'mehmet_havale': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'banka_havale': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'pafgo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'aciklama': forms.TextInput(attrs={'class': 'form-control'}),
            'kategori1': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Kullanıcıyı al ve kwargs'dan çıkar
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Kategori1'i opsiyonel yap
        self.fields['kategori1'].required = False
        self.fields['kategori1'].empty_label = "Alt Kategori Seçiniz (Opsiyonel)"
        
        # Açıklama alanını opsiyonel yap
        self.fields['aciklama'].required = False
        
        # Eğer yeni form ise (instance yoksa) tarihi bugünün tarihi olarak ayarla
        try:
            # Eğer instance yoksa veya pk yoksa (yeni kayıt) bugünün tarihini ayarla
            if not hasattr(self.instance, 'pk') or self.instance.pk is None:
                self.fields['tarih'].initial = timezone.now().date()
        except AttributeError:
            # Instance yoksa direkt bugünün tarihini ayarla
            self.fields['tarih'].initial = timezone.now().date()
        
        # Kategori seçeneklerini kullanıcıya göre filtrele
        # Not: Alt kategoriler JavaScript ile dinamik olarak yüklenecek
        if user:
            # Tüm kategorileri queryset'e ekle (hem ana hem alt)
            self.fields['kategori1'].queryset = TransactionCategory.objects.filter(
                created_by=user
            ).order_by('parent__id', 'name')

    def clean(self):
        cleaned = super().clean()
        nakit = cleaned.get('nakit') or 0
        kredi = cleaned.get('kredi_karti') or 0
        cari = cleaned.get('cari') or 0
        sanal = cleaned.get('sanal_pos') or 0
        mehmet = cleaned.get('mehmet_havale') or 0
        banka = cleaned.get('banka_havale') or 0
        pafgo = cleaned.get('pafgo') or 0
        
        # En az bir ödeme alanı dolu olmalı
        if nakit + kredi + cari + sanal + mehmet + banka + pafgo <= 0:
            raise forms.ValidationError(
                'En az bir ödeme alanı (Nakit, Kredi Kartı, Sanal Pos, Cari, Mehmet Havale, Banka Havale veya Pafgo) doldurulmalıdır.'
            )
        
        # Sadece bir ödeme türü seçilmeli
        filled_fields = []
        if nakit > 0:
            filled_fields.append('Nakit')
        if kredi > 0:
            filled_fields.append('Kredi Kartı')
        if cari > 0:
            filled_fields.append('Cari')
        if sanal > 0:
            filled_fields.append('Sanal Pos')
        if mehmet > 0:
            filled_fields.append('Mehmet Havale')
        if banka > 0:
            filled_fields.append('Banka Havale')
        if pafgo > 0:
            filled_fields.append('Pafgo')
            
        if len(filled_fields) > 1:
            raise forms.ValidationError(f'Sadece bir ödeme türü seçilmelidir. Şu anda seçili: {", ".join(filled_fields)}')
        
        return cleaned

class SiparisForm(forms.ModelForm):
    """Sipariş formu"""
    
    class Meta:
        model = Siparis
        fields = [
            'cari_firma', 'marka', 'urun', 'grup', 'mevsim',
            'adet', 'birim_fiyat', 'toplam_fiyat', 'durum', 'ambar', 
            'odeme', 'sms_durum', 'aciklama', 'one_cikar', 'iptal_sebebi',
            'musteri_adi', 'musteri_telefon', 'musteri_odeme_tutari', 'musteri_aciklama'
        ]
        widgets = {
            'cari_firma': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Müşteri firma adını girin'
            }),
            'marka': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Lastik markasını girin'
            }),
            'urun': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Lastik model ve özelliklerini girin'
            }),
            'grup': forms.Select(attrs={
                'class': 'form-select'
            }),
            'mevsim': forms.Select(attrs={
                'class': 'form-select'
            }),
            'adet': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1'
            }),
            'birim_fiyat': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'value': '0'
            }),
            'toplam_fiyat': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01'
            }),
            'durum': forms.Select(attrs={
                'class': 'form-select'
            }),
            'ambar': forms.Select(attrs={
                'class': 'form-select'
            }),
            'odeme': forms.Select(attrs={
                'class': 'form-select'
            }),
            'sms_durum': forms.Select(attrs={
                'class': 'form-select'
            }),
            'aciklama': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': '3',
                'placeholder': 'Ek açıklama girin'
            }),
            'one_cikar': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'iptal_sebebi': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': '3',
                'placeholder': 'İptal sebebini girin',
                'id': 'iptal-sebebi-field'
            }),
            'musteri_adi': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Müşteri adını giriniz'
            }),
            'musteri_telefon': forms.TextInput(attrs={
                'class': 'form-control',
                
            }),
            'musteri_odeme_tutari': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'musteri_aciklama': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': '3',
                'placeholder': 'Müşteri ile ilgili ek bilgiler...'
            })
        }
        labels = {
            'cari_firma': 'CARI (FIRMA)',
            'marka': 'MARKA',
            'urun': 'ÜRÜN (LASTIK MARKA MODEL)',
            'grup': 'GRUP',
            'mevsim': 'MEVSİM',
            'adet': 'ADET',
            'birim_fiyat': 'BİRİM FİYAT',
            'toplam_fiyat': 'TOPLAM FİYAT',
            'durum': 'DURUM',
            'ambar': 'AMBAR',
            'odeme': 'ÖDEME',
            'sms_durum': 'SMS DURUMU',
            'aciklama': 'AÇIKLAMA',
            'one_cikar': 'ÖNE ÇIKAR',
            'iptal_sebebi': 'İPTAL SEBEBİ',
            'musteri_adi': 'MÜŞTERİ ADI',
            'musteri_telefon': 'TELEFON NUMARASI',
            'musteri_odeme_tutari': 'ÖDEME TUTARI',
            'musteri_aciklama': 'AÇIKLAMA'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Boş seçenekler ekle
        self.fields['grup'].empty_label = "--------"
        self.fields['mevsim'].empty_label = "--------"
        self.fields['durum'].empty_label = "--------"
        self.fields['ambar'].empty_label = "--------"
        self.fields['odeme'].empty_label = "--------"
        self.fields['sms_durum'].empty_label = "--------"

        
        # Zorunlu alanları işaretle
        self.fields['cari_firma'].required = True
        self.fields['marka'].required = True
        self.fields['urun'].required = True
        self.fields['grup'].required = True
        self.fields['mevsim'].required = True
        self.fields['adet'].required = True
        self.fields['birim_fiyat'].required = True
        self.fields['ambar'].required = True
        self.fields['odeme'].required = True
        
        # Durum iptal ise iptal_sebebi zorunlu
        if self.data.get('durum') == 'iptal':
            self.fields['iptal_sebebi'].required = True
            self.fields['iptal_sebebi'].widget.attrs['required'] = True
    
    def clean(self):
        cleaned_data = super().clean()
        durum = cleaned_data.get('durum')
        iptal_sebebi = cleaned_data.get('iptal_sebebi')
        
        # Durum iptal ise sebep zorunlu
        if durum == 'iptal' and not iptal_sebebi:
            raise forms.ValidationError({
                'iptal_sebebi': 'İptal edilecek siparişler için iptal sebebi belirtmek zorunludur.'
            })
        
        return cleaned_data

class MalzemeExcelUploadForm(forms.Form):
    file = forms.FileField(label='Excel Dosyası (*.xls, *.xlsx)', required=True)


class TransactionCategoryForm(forms.ModelForm):
    """Kategori ekleme/düzenleme formu"""
    
    class Meta:
        model = TransactionCategory
        fields = ['name', 'parent', 'order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kategori adını girin'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'value': '0'
            })
        }
        labels = {
            'name': 'Kategori Adı',
            'parent': 'Üst Kategori (Opsiyonel)',
            'order': 'Sıra'
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Parent alanını opsiyonel yap
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = "Ana Kategori (Üst Kategori Yok)"
        
        # Order alanını opsiyonel yap
        self.fields['order'].required = False
        
        # Kullanıcıya ait kategorileri göster
        if user:
            self.fields['parent'].queryset = TransactionCategory.objects.filter(
                created_by=user
            ).order_by('parent__id', 'order', 'name')
