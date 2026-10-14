import re
from decimal import Decimal, InvalidOperation


def parse_decimal_value(value, precision='0.01'):
    """
    Kullanıcıdan gelen miktarları (Excel hücreleri, string değerler vb.)
    güvenli bir şekilde Decimal'e çevirir.
    Hem Türkçe (1.234,56) hem İngilizce (1,234.56) formatlarını destekler.
    """
    if value is None:
        return Decimal('0')

    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, float)):
        result = Decimal(str(value))
    else:
        value_str = str(value).strip()
        if not value_str:
            return Decimal('0')

        # Para birimi sembollerini ve boşlukları temizle
        value_str = (
            value_str.replace('₺', '')
            .replace('TRY', '')
            .replace('TL', '')
            .replace(' ', '')
        )

        last_dot = value_str.rfind('.')
        last_comma = value_str.rfind(',')

        decimal_sep = None
        if last_dot == -1 and last_comma == -1:
            decimal_sep = None
        elif last_dot > last_comma:
            # Nokta daha sonra geliyorsa ve 1-2 hane izliyorsa ondalık kabul et
            decimals = len(value_str) - last_dot - 1
            if decimals in (1, 2):
                decimal_sep = '.'
        elif last_comma > last_dot:
            decimals = len(value_str) - last_comma - 1
            if decimals in (1, 2):
                decimal_sep = ','

        cleaned = value_str
        if decimal_sep == ',':
            cleaned = cleaned.replace('.', '')
            cleaned = cleaned.replace(',', '.')
        elif decimal_sep == '.':
            cleaned = cleaned.replace(',', '')
        else:
            # Sadece binlik ayırıcı var ya da hiç yok – hepsini kaldır
            cleaned = cleaned.replace(',', '').replace('.', '')

        cleaned = re.sub(r'[^0-9\.-]', '', cleaned)
        if cleaned in {'', '-', '.', '-.'}:
            return Decimal('0')

        try:
            result = Decimal(cleaned)
        except InvalidOperation:
            return Decimal('0')

    if precision:
        try:
            quantum = Decimal(precision)
            result = result.quantize(quantum)
        except (InvalidOperation, ValueError):
            pass
    return result


def normalize_turkish_text(text):
    """
    Türkçe karakterleri normalize eder (İ->I, Ğ->G, vb.)
    Arama işlemlerinde kullanılır.
    """
    if not text:
        return text
    
    # Türkçe karakter dönüşüm tablosu
    turkish_chars = {
        'İ': 'I', 'ı': 'i', 'Ğ': 'G', 'ğ': 'g',
        'Ü': 'U', 'ü': 'u', 'Ş': 'S', 'ş': 's',
        'Ö': 'O', 'ö': 'o', 'Ç': 'C', 'ç': 'c'
    }
    
    normalized = str(text)
    for turkish_char, latin_char in turkish_chars.items():
        normalized = normalized.replace(turkish_char, latin_char)
    
    return normalized.upper()


def create_turkish_search_variants(text):
    """
    Bir metin için Türkçe karakter varyantları oluşturur.
    Örnek: 'CONTINENTAL' -> ['CONTINENTAL', 'CONTİNENTAL']
    """
    if not text:
        return [text]
    
    # Temel metin
    base_text = str(text).strip()
    variants = [base_text]
    
    # Normalize edilmiş hali
    normalized = normalize_turkish_text(base_text)
    if normalized != base_text:
        variants.append(normalized)
    
    # Türkçe karakterli varyantlar oluştur
    # I -> İ, i -> ı dönüşümleri
    turkish_variants = []
    for variant in variants:
        # I -> İ dönüşümü
        if 'I' in variant:
            turkish_variants.append(variant.replace('I', 'İ'))
        # i -> ı dönüşümü  
        if 'i' in variant:
            turkish_variants.append(variant.replace('i', 'ı'))
        # G -> Ğ dönüşümü
        if 'G' in variant:
            turkish_variants.append(variant.replace('G', 'Ğ'))
        # g -> ğ dönüşümü
        if 'g' in variant:
            turkish_variants.append(variant.replace('g', 'ğ'))
        # U -> Ü dönüşümü
        if 'U' in variant:
            turkish_variants.append(variant.replace('U', 'Ü'))
        # u -> ü dönüşümü
        if 'u' in variant:
            turkish_variants.append(variant.replace('u', 'ü'))
        # S -> Ş dönüşümü
        if 'S' in variant:
            turkish_variants.append(variant.replace('S', 'Ş'))
        # s -> ş dönüşümü
        if 's' in variant:
            turkish_variants.append(variant.replace('s', 'ş'))
        # O -> Ö dönüşümü
        if 'O' in variant:
            turkish_variants.append(variant.replace('O', 'Ö'))
        # o -> ö dönüşümü
        if 'o' in variant:
            turkish_variants.append(variant.replace('o', 'ö'))
        # C -> Ç dönüşümü
        if 'C' in variant:
            turkish_variants.append(variant.replace('C', 'Ç'))
        # c -> ç dönüşümü
        if 'c' in variant:
            turkish_variants.append(variant.replace('c', 'ç'))
    
    # Tüm varyantları birleştir ve tekrarları kaldır
    all_variants = list(set(variants + turkish_variants))
    
    return all_variants


def format_tire_size(ebat_input):
    """
    Lastik ebat girişini otomatik formatlar.
    Örnek: '2055516' -> '205/55R16'
    """
    if not ebat_input:
        return ebat_input
    
    # Boşlukları temizle
    ebat = str(ebat_input).strip()
    
    # Eğer zaten doğru formatta ise (/ ve R içeriyorsa) olduğu gibi döndür
    if '/' in ebat and 'R' in ebat.upper():
        return ebat
    
    # Sadece rakamlardan oluşan 6-7 haneli girişleri formatla
    if ebat.isdigit() and len(ebat) in [6, 7]:
        if len(ebat) == 6:
            # 205516 -> 205/55R16
            return f"{ebat[:3]}/{ebat[3:5]}R{ebat[5:]}"
        elif len(ebat) == 7:
            # 2055516 -> 205/55R16 veya 22555R16 gibi
            # İlk 3 hane genişlik, sonraki 2 hane yükseklik oranı, kalan çap
            return f"{ebat[:3]}/{ebat[3:5]}R{ebat[5:]}"
    
    # Diğer durumlarda olduğu gibi döndür
    return ebat







