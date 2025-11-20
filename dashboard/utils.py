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





