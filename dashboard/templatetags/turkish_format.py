from django import template
from decimal import Decimal
from dashboard.utils import parse_decimal_value

register = template.Library()

@register.filter(name='turkish_format')
def turkish_format(value):
    """
    Sayıyı Türkçe formatta gösterir: 18.400,00
    Binlik ayırıcı: nokta (.)
    Ondalık ayırıcı: virgül (,)
    """
    if value is None:
        return '0,00'

    try:
        num = parse_decimal_value(value, precision='0.01')
    except Exception:
        try:
            num = Decimal(str(value))
        except Exception:
            return str(value) if value else '0,00'

    is_negative = num < 0
    num = abs(num)

    num_str = f"{num:.2f}"
    integer_part, decimal_part = num_str.split('.')

    if len(integer_part) > 3:
        formatted_parts = []
        for i in range(len(integer_part), 0, -3):
            start = max(0, i - 3)
            formatted_parts.insert(0, integer_part[start:i])
        integer_part = '.'.join(formatted_parts)

    result = f"{integer_part},{decimal_part}"
    return f"-{result}" if is_negative else result


@register.filter(name='turkish_lira')
def turkish_lira(value):
    """
    Sayıyı Türk Lirası formatında gösterir: 20.000 TL
    Binlik ayırıcı: nokta (.)
    Kuruş gösterilmez (tam sayı)
    """
    if value is None:
        return '0 TL'

    try:
        num = parse_decimal_value(value, precision='1')
    except Exception:
        try:
            num = Decimal(str(value))
        except Exception:
            return str(value) if value else '0 TL'

    is_negative = num < 0
    num = abs(num)

    # Tam sayıya yuvarla (kuruş göstermiyoruz)
    num = num.quantize(Decimal('1'))
    integer_part = str(int(num))

    if len(integer_part) > 3:
        formatted_parts = []
        for i in range(len(integer_part), 0, -3):
            start = max(0, i - 3)
            formatted_parts.insert(0, integer_part[start:i])
        integer_part = '.'.join(formatted_parts)

    result = f"{integer_part} TL"
    return f"-{result}" if is_negative else result
