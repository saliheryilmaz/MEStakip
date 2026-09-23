"""Shared stock scope and filters for the used-tire list and export."""

from datetime import timedelta

from django.db.models import Q, Value
from django.db.models.functions import Coalesce, Trim
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import CikmaLastik
from .utils import create_turkish_search_variants, format_tire_size


FILTER_KEYS = (
    'id', 'marka', 'ebat', 'mevsim', 'arac_tipi', 'depo_konumu',
    'tarih', 'baslangic_tarihi', 'bitis_tarihi',
)


def inventory_scope(user, is_guest=False):
    stock = CikmaLastik.objects.filter(durum__in=('cikti', 'depolandi'))
    if not is_guest:
        stock = stock.filter(user=user)
    return stock.annotate(depot_name=Trim(Coalesce('depo_konumu', Value(''))))


def inventory_filters(params, is_guest=False):
    filters = {key: params.get(key, '').strip() for key in FILTER_KEYS}
    if is_guest:
        filters['depo_konumu'] = ''
    return filters


def filter_inventory(stock, filters, include_depot=True):
    if filters['id']:
        record_id = filters['id'].removeprefix('#').strip()
        if not (record_id.isascii() and record_id.isdigit() and len(record_id) <= 19):
            return stock.none()
        if not 1 <= int(record_id) <= 9223372036854775807:
            return stock.none()
        stock = stock.filter(pk=int(record_id))
    if filters['marka']:
        query = Q()
        for variant in create_turkish_search_variants(filters['marka']):
            query |= Q(marka__icontains=variant)
        stock = stock.filter(query)
    if filters['ebat']:
        stock = stock.filter(ebat__icontains=format_tire_size(filters['ebat']))
    for field in ('mevsim', 'arac_tipi'):
        if filters[field]:
            stock = stock.filter(**{field: filters[field]})
    if include_depot and filters['depo_konumu']:
        stock = stock.filter(depot_name=filters['depo_konumu'])

    now = timezone.now()
    period = filters['tarih']
    days = {'son-1-ay': 30, 'son-3-ay': 90, 'son-6-ay': 180}
    if period in days:
        stock = stock.filter(olusturma_tarihi__gte=now - timedelta(days=days[period]))
    elif period == 'bugun':
        stock = stock.filter(olusturma_tarihi__date=timezone.localdate())
    elif period == 'bu-hafta':
        today = timezone.localdate()
        stock = stock.filter(olusturma_tarihi__date__gte=today - timedelta(days=today.weekday()))
    elif period == 'bu-ay':
        stock = stock.filter(olusturma_tarihi__date__gte=timezone.localdate().replace(day=1))
    for key, lookup in (('baslangic_tarihi', 'gte'), ('bitis_tarihi', 'lte')):
        try:
            value = parse_date(filters[key]) if filters[key] else None
        except ValueError:
            value = None
        if value:
            stock = stock.filter(**{f'olusturma_tarihi__date__{lookup}': value})
    return stock
