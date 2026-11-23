"""Lastik oteli ölçüm geçmişi ve mevsim bazında stok planlaması."""
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date
import re

from django.utils import timezone
from erp.models import StokKart
from .models import LastikOteli, OtelKontrol, OtelPlanRaporu


KARAR = {"sakla": "Depolanabilir", "izle": "Son sezon olabilir", "degistir": "Değişim öneriliyor"}
EBAT = re.compile(r"(?<!\d)(\d{3})\s*[/ -]\s*(\d{2,3})\s*(?:Z?R|/)\s*(\d{2}(?:\.5)?)(?!\d)", re.I)


def ebat(text):
    match = EBAT.search(text or "")
    return f"{match[1]}/{match[2]}R{match[3]}" if match else ""


def sezon(tarih, mevsim):
    months = {"yaz": [5], "kis": [12], "dort_mevsim": [5, 12]}[mevsim]
    return next(date(y, m, 1) for y in (tarih.year, tarih.year + 1)
                for m in months if date(y, m, 1) > tarih)


def ilk_satirlar(kayit):
    tires = {t.sira: t for t in kayit.lastikler.all()}
    rows = []
    for i in range(1, kayit.adet + 1):
        t = tires.get(i)
        depth = t.dis_derinligi if t else kayit.dis_derinligi
        rows.append(dict(sira=i, marka=t.marka if t else kayit.marka, model=t.desen if t else "",
                         ebat=(t.ebat if t else "") or kayit.ebat, dot=t.dot if t else "",
                         mm=float(depth) if depth is not None else None, bulgular=[]))
    return rows


def dot_yili(dot):
    if not re.fullmatch(r"\d{4}", dot or ""):
        return None
    if 2000 <= int(dot) <= 2099:
        return int(dot)
    if 1 <= int(dot[:2]) <= 53:
        year = 2000 + int(dot[2:])
        return year - 100 if year > timezone.localdate().year + 5 else year
    return None


def degerlendir(rows, before, days, km_delta, tarih, season_months):
    reasons = set()
    rank = 0
    for row, old in zip(rows, before):
        depth = row["mm"]
        year = dot_yili(row["dot"])
        findings = set(row["bulgular"])
        if findings & {"hasar", "catlak", "balon"} or (depth is not None and depth <= 1.6):
            rank = 2
            reasons.add("Hasar bulgusu veya kritik diş derinliği")
        if year and tarih.year - year >= 10:
            rank = 2
            reasons.add("DOT yaklaşık 10 yıl veya daha eski")
        if "duzensiz" in findings or (depth is not None and depth <= 3):
            rank = max(rank, 1)
            reasons.add("Düzensiz aşınma veya düşük diş payı")
        if year and 5 <= tarih.year - year < 10:
            reasons.add("DOT nedeniyle ayrıntılı fiziksel kontrol")
        if depth is None or not findings or not year:
            reasons.add("Ölçüm, DOT veya fiziksel kontrol bilgisi eksik")
        if depth is None or old.get("mm") is None or days <= 0:
            continue
        loss = old["mm"] - depth
        if loss < 0 or any(old.get(k) and row[k] != old[k] for k in ("dot", "marka", "model", "ebat")):
            reasons.add("Karşılaştırılabilir ölçüm yok")
            continue
        # Araç kilometresi setin kullanım kilometresinden farklı olabilir.
        # Aynı setin iki kontrolü arasındaki ortalama değişim planlama göstergesidir.
        if km_delta is not None and km_delta > 0:
            per_km = loss / km_delta
            annual = km_delta * 365.25 / days
            row.update(mm_km=round(per_km, 7), mm_10000=round(per_km * 10000, 2), yillik_km=round(annual))
            if per_km > 0:
                row["plan_km"] = round(max(0, depth - 3) / per_km)
            forecast_loss = per_km * annual * season_months / 12
            row["yontem"] = "Araç km ortalaması"
        else:
            forecast_loss = loss * 365.25 / days * season_months / 12
            row["yontem"] = "Süreye dayalı, düşük güven"
        if loss > 0:
            row["plan_ay"] = round(max(0, depth - 3) * days / loss / 30.44, 1)
        row["tahmin"] = round(max(0, depth - forecast_loss), 2)
        if row["tahmin"] <= 3:
            rank = max(rank, 1)
            reasons.add("Gelecek kullanım sezonunda düşük diş payı bekleniyor")
    if not rank and (not rows or any(r["mm"] is None or not r["bulgular"] or not dot_yili(r["dot"]) for r in rows)):
        return "eksik", " · ".join(sorted(reasons))
    return ("sakla", "izle", "degistir")[rank], " · ".join(sorted(reasons)) or "Ölçüm ve fiziksel kontrol kaydedildi"


def stoklar():
    result = Counter()
    for kart in StokKart.objects.filter(durum="A", gercek_stok__gt=0).values(
            "aciklama", "mevsim", "gercek_stok", "ana_birim"):
        season = kart["mevsim"].lower().strip()
        key = {"yazlık": "yaz", "yaz": "yaz", "kışlık": "kis", "kış": "kis",
               "kis": "kis", "4 mevsim": "dort_mevsim", "dört mevsim": "dort_mevsim"}.get(season)
        size = ebat(kart["aciklama"])
        if size and key and kart["ana_birim"].lower().strip() in ("adet", "ad"):
            result[key, size] += int(kart["gercek_stok"])
    return result


def plan(tarih, bitis=None):
    available = stoklar()
    needs = []
    customers = set()
    grouped = defaultdict(list)
    unchecked = 0
    sets = LastikOteli.objects.prefetch_related("kontroller", "lastikler").order_by("pk")
    for item in sets:
        check = next(iter(item.kontroller.all()), None)
        if check:
            if check.karsilandi or (check.karar or check.oneri) not in ("izle", "degistir"):
                continue
            rows, due = check.lastikler, check.hedef
        else:
            unchecked += 1
            rows = ilk_satirlar(item)
            suggestion, _ = degerlendir(rows, rows, 0, None, tarih, 6)
            if suggestion not in ("izle", "degistir"):
                continue
            due = sezon(tarih, item.mevsim)
        if bitis and not tarih <= due <= bitis:
            continue
        customer = (item.musteri_adi.strip().casefold(), item.musteri_telefon.strip())
        customers.add(customer)
        sizes = defaultdict(list)
        for row in rows:
            sizes[ebat(row["ebat"]) or row["ebat"] or "Ebat doğrulanmalı"].append(row)
        for size, tires in sizes.items():
            estimates = [row["tahmin"] for row in tires if row.get("tahmin") is not None]
            entry = dict(id=item.pk, ad=item.musteri_adi, plaka=item.plaka, mevsim=item.get_mevsim_display(),
                         ebat=size, adet=len(tires), hedef=due.isoformat(),
                         tahmin=min(estimates) if estimates else None, olculen=len(estimates),
                         bildirildi=bool(check and check.bildirildi),
                         onay=bool(check and check.onaylandi), kontrol=check.pk if check else None)
            needs.append(entry)
            grouped[due, item.mevsim, size].append((entry, customer))
    purchases = []
    for (due, season_key, size), group in sorted(grouped.items()):
        count = sum(entry["adet"] for entry, _ in group)
        stock = available[season_key, size]
        confirmed = sum(entry["adet"] for entry, _ in group if entry["onay"])
        purchases.append(dict(hedef=due.isoformat(), mevsim=dict(LastikOteli.MEVSIM_CHOICES)[season_key],
                              ebat=size, tahmini=count-confirmed, onayli=confirmed, adet=count,
                              musteri=len({c for _, c in group}), stok=stock if ebat(size) else None,
                              eksik=max(0, count-stock) if ebat(size) else None))
        available[season_key, size] = max(0, stock-count)
    return dict(ihtiyac=sorted(needs, key=lambda x: x["hedef"]), alim=purchases,
                musteri=len(customers), kontrolsuz=unchecked)


def rapor_kaydet(tarih=None):
    today = tarih or timezone.localdate()
    year, month = divmod(today.year * 12 + today.month - 1 + 6, 12)
    end = date(year, month + 1, min(today.day, monthrange(year, month + 1)[1]))
    report, _ = OtelPlanRaporu.objects.get_or_create(tarih=today, defaults={"icerik": plan(today, end)})
    return report.pk
