"""Cari ekstrelerinden açıklanabilir ödeme profilleri ve aylık takip listeleri."""
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from statistics import median

from django.utils import timezone

from .models import Cari, CariTip, TahsilatAylikRapor


ODEMELER = {
    "tahsilat", "nakit tahsilat", "kasa tahsilat", "tahsilat makbuzu", "gelen havale",
    "gelen eft", "kredi kartı tahsilatı", "banka tahsilat", "cari tahsilat", "tahsil fişi",
}
SATISLAR = {"perakende satış", "toptan satış", "satış faturası", "hizmet satış faturası"}
YETERSIZ = "Yetersiz geçmiş"
KAPATAN = "Bakiye kapatan"
DUZENLI = "Döngüsel ödeme"
DUZENSIZ = "Düzensiz kısmi ödeme"


def tutar(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            amount = Decimal(str(value).replace(",", "."))
            return amount if amount.is_finite() else None
        except InvalidOperation:
            return None
    return None


def _monthly_days(recent):
    months = defaultdict(list)
    for day, _, _ in recent:
        months[day.year, day.month].append(day.day)
    # Compare complete interior months; outer months may be only partially visible.
    complete = list(months.values())[1:-1]
    if len(complete) < 2 or len({len(days) for days in complete}) != 1:
        return []
    slots = list(zip(*complete))
    if any(max(slot) - min(slot) > 4 for slot in slots):
        return []
    return [round(median(slot)) for slot in slots]


def _model(payments):
    recent = payments[-6:]
    if len(recent) < 3:
        return YETERSIZ
    balances = [p[2] for p in recent if p[2] is not None]
    if len(balances) < 3:
        return YETERSIZ
    if sum(b <= 0 for b in balances) * 3 >= len(balances) * 2:
        return KAPATAN
    gaps = [(b[0] - a[0]).days for a, b in zip(recent, recent[1:])]
    typical = median(gaps)
    if _monthly_days(payments[-12:]) or all(abs(gap - typical) <= max(3, typical * .25) for gap in gaps):
        return DUZENLI
    return DUZENSIZ


def analiz(cari, today):
    days = defaultdict(list)
    monthly = Decimal(0)
    monthly_sales = Decimal(0)
    for row in cari.rapor_ekstresi or []:
        try:
            day = date.fromisoformat(str(row.get("tarih", ""))[:10])
        except ValueError:
            continue
        if day <= today:
            days[day].append(row)

    payments, closure_days, changes = [], [], []
    opened = previous_balance = None
    profile = candidate = YETERSIZ
    confirmations = 0
    for day in sorted(days):
        paid = Decimal(0)
        payment_balance = None
        for row in sorted(days[day], key=lambda r: str(r.get("saat") or "")):
            kind = str(row.get("turu_txt") or row.get("turu") or "").replace("İ", "i").replace("I", "ı").lower().strip()
            balance = tutar(row, "yerelborcalacakbakiye", "borcalacakbakiye")
            debit = tutar(row, "yerelborc", "borc")
            if kind in SATISLAR and debit and debit > 0:
                if day >= today.replace(day=1):
                    monthly_sales += debit
                if opened is None and ((previous_balance is not None and previous_balance <= 0) or balance == debit):
                    opened = day
            credit = tutar(row, "yerelalacak", "alacak")
            if kind in ODEMELER and credit and credit > 0:
                paid += credit
                payment_balance = balance
                if balance is not None and balance <= 0 and opened is not None:
                    closure_days.append((day - opened).days)
            if balance is not None and balance <= 0:
                opened = None
            previous_balance = balance
        if paid:
            payments.append((day, paid, payment_balance))
            if day >= today.replace(day=1):
                monthly += paid
            observed = _model(payments)
            confirmations = confirmations + 1 if candidate == observed else 1
            candidate = observed
            if observed != YETERSIZ and observed != profile and (profile == YETERSIZ or confirmations >= 3):
                profile = observed
                changes.append(f"{day:%d.%m.%Y} · {profile}")

    expected = None
    if profile == KAPATAN and opened and closure_days:
        expected = opened + timedelta(days=round(median(closure_days[-6:])))
    elif profile == DUZENLI:
        recent = payments[-6:]
        gaps = [(b[0] - a[0]).days for a, b in zip(recent, recent[1:])]
        expected = recent[-1][0] + timedelta(days=round(median(gaps)))
        slots = _monthly_days(payments[-12:])
        if slots:
            last = recent[-1][0]
            slot = min(slots, key=lambda d: abs(d - last.day))
            later = [d for d in slots if d > slot]
            month = last if later else last.replace(day=28) + timedelta(days=4)
            expected = month.replace(day=min((later or slots)[0], monthrange(month.year, month.month)[1]))
    reason = "Takipte"
    if profile in (YETERSIZ, DUZENSIZ) or expected is None:
        reason = "Manuel inceleme"
    if expected and today > expected + timedelta(days=3):
        reason = "Ödeme aralığı aşıldı"
    elif expected and expected <= today:
        reason = "Ödeme bekleniyor"
    source_date = timezone.localdate(cari.son_sync_tarihi) if cari.son_sync_tarihi else None
    if expected and expected <= today and (source_date is None or source_date < expected):
        reason = "Güncel ekstre gerekli"
    mismatch = previous_balance is not None and abs(cari.bakiye - previous_balance) > Decimal("0.01")
    if mismatch:
        reason = "Bakiye mutabakatı gerekli"
    over_limit = cari.risk_limiti > 0 and cari.bakiye > cari.risk_limiti
    return dict(pk=cari.pk, unvan=cari.unvan, kod=cari.cari_kodu, bakiye=str(cari.bakiye),
                model=profile, durum=reason, limit_asildi=over_limit,
                beklenti=expected.isoformat() if expected else "", gecmis=changes,
                son_odeme=payments[-1][0].isoformat() if payments else "",
                ortalama_odeme=str(sum((p[1] for p in payments), Decimal(0)) / len(payments)) if payments else None,
                mutabakat_farki=mismatch,
                aylik_satis=str(monthly_sales) if cari.rapor_ekstresi is not None else None,
                kapatma_gunu=round(median(closure_days[-6:])) if closure_days else None,
                odeme_gunu=len(payments), aylik_tahsilat=str(monthly) if cari.rapor_ekstresi is not None else None,
                kaynak_tarihi=cari.son_sync_tarihi.isoformat()[:10] if cari.son_sync_tarihi else "")


def takip_listesi(today):
    cariler = Cari.objects.filter(tip__in=(CariTip.ALICI, CariTip.ALICI_SATICI), bakiye__gt=0)
    return [analiz(cari, today) for cari in cariler.order_by("-bakiye", "pk").iterator()]


def aylik_rapor_kaydet():
    today = timezone.localdate()
    return TahsilatAylikRapor.objects.update_or_create(
        ay=today.replace(day=1), defaults={"satirlar": takip_listesi(today)})[0]
