from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import LastikDepo, LastikOteli, LastikOteliLastik, LastikOteliHareket, OtelKontrol, OtelKontrolFotograf, OtelPlanRaporu
from .otel_plan import KARAR, degerlendir, dot_yili, ilk_satirlar, plan, sezon
from .views import misafir_forbidden


class KontrolForm(forms.Form):
    tarih = forms.DateField(label="Kontrol tarihi", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    km = forms.IntegerField(label="Araç kilometresi", min_value=0, required=False)


class LastikForm(forms.Form):
    marka = forms.CharField(max_length=100, required=False)
    model = forms.CharField(max_length=100, required=False)
    ebat = forms.CharField(max_length=50)
    dot = forms.CharField(label="DOT (hafta/yıl veya üretim yılı)", max_length=4, required=False)
    mm = forms.DecimalField(label="Ölçülen diş (mm)", min_value=0, max_value=99, decimal_places=1, required=False)
    bulgular = forms.MultipleChoiceField(label="Fiziksel kontrol", choices=[
        ("normal", "Belirgin kusur yok"), ("hasar", "Hasar"), ("catlak", "Çatlak"),
        ("balon", "Balon"), ("duzensiz", "Düzensiz aşınma")], widget=forms.CheckboxSelectMultiple)
    fotograf = forms.ImageField(label="Lastik fotoğrafı", required=False)

    def clean_dot(self):
        value = self.cleaned_data["dot"]
        if value and not dot_yili(value):
            raise forms.ValidationError("Dört haneli hafta/yıl veya üretim yılı girin.")
        return value

    def clean_bulgular(self):
        flags = self.cleaned_data["bulgular"]
        if "normal" in flags and len(flags) > 1:
            raise forms.ValidationError("Kusur varsa yalnızca ilgili bulguları seçin.")
        return flags


@login_required
@misafir_forbidden
def panel(request):
    report_id = request.GET.get("rapor")
    if report_id and not report_id.isdecimal():
        raise Http404
    report = get_object_or_404(OtelPlanRaporu, pk=report_id) if report_id else None
    data = report.icerik if report else plan(timezone.localdate())
    return render(request, "dashboard/otel_plan.html", dict(data=data, report=report,
                  reports=OtelPlanRaporu.objects.order_by("-tarih"), sets=LastikOteli.objects.order_by("plaka", "mevsim")))


@login_required
@misafir_forbidden
@transaction.atomic
def kontrol(request, pk):
    item = get_object_or_404(LastikOteli.objects.select_for_update(), pk=pk)
    history = list(item.kontroller.prefetch_related("fotograflar"))
    for entry in history:
        entry.oneri_etiketi = KARAR.get(entry.oneri, "Kontrol verisi eksik")
        entry.karar_etiketi = KARAR.get(entry.karar, "")
        entry.talep_var = (entry.karar or entry.oneri) in ("izle", "degistir") and not entry.karsilandi
    prev = history[0] if history else None
    baseline = prev.lastikler if prev else ilk_satirlar(item)
    before_date = prev.tarih if prev else item.giris_tarihi
    before_km = prev.km if prev else item.arac_kilometre
    today = timezone.localdate()
    posted = request.method == "POST"
    form = KontrolForm(request.POST if posted else None, initial={"tarih": today})
    rows = [LastikForm(request.POST if posted else None, request.FILES if posted else None,
                       prefix=f"t{r['sira']}", initial={k: r[k] for k in ("marka", "model", "ebat", "dot")})
            for r in baseline]
    if posted:
        if not baseline:
            return HttpResponseBadRequest("Önce otel kaydına lastik adedi girin.")
        if item.durum == "degisim" or request.POST.get("previous") != str(prev.pk if prev else 0):
            return HttpResponseBadRequest("Set değişmiş. Güncel kaydı açın.")
        valid_rows = all([row.is_valid() for row in rows])
        if form.is_valid() and valid_rows:
            day, km = form.cleaned_data["tarih"], form.cleaned_data["km"]
            if day < before_date or (prev and day == before_date) or day > today:
                form.add_error("tarih", "Son kontrolden sonra ve en geç bugün olan bir tarih seçin.")
            elif km is not None and before_km is not None and km < before_km:
                form.add_error("km", "Kilometre önceki ölçümden düşük.")
            elif any((dot_yili(r.cleaned_data["dot"]) or 0) > day.year for r in rows):
                form.add_error("tarih", "Üretim yılı kontrol tarihinden sonra olamaz.")
            else:
                tires, photos = [], []
                for old, row in zip(baseline, rows):
                    data = dict(row.cleaned_data)
                    photo = data.pop("fotograf")
                    data.update(sira=old["sira"], mm=float(data["mm"]) if data["mm"] is not None else None)
                    tires.append(data)
                    if photo:
                        photos.append((old["sira"], photo))
                diff = km - before_km if None not in (km, before_km) else None
                advice, reason = degerlendir(tires, baseline, (day-before_date).days, diff, day,
                                              {"yaz": 7, "kis": 5, "dort_mevsim": 12}[item.mevsim])
                target = sezon(day, item.mevsim)
                if not prev and before_date < day:
                    OtelKontrol.objects.create(kayit=item, tarih=before_date, km=before_km,
                            lastikler=baseline, oneri="eksik", gerekce="Otel girişindeki kayıt",
                            hedef=sezon(before_date, item.mevsim), yapan=item.olusturan)
                check = OtelKontrol.objects.create(kayit=item, tarih=day, km=km, yapan=request.user,
                            lastikler=tires, oneri=advice, gerekce=reason, hedef=target,
                            bildirildi=bool(prev and prev.hedef == target and prev.bildirildi),
                            onaylandi=bool(prev and prev.hedef == target and prev.onaylandi))
                for slot, photo in photos:
                    OtelKontrolFotograf.objects.create(kontrol=check, sira=slot, resim=photo)
                for tire in tires:
                    LastikOteliLastik.objects.update_or_create(kayit=item, sira=tire["sira"], defaults={
                        "marka": tire["marka"], "desen": tire["model"], "ebat": tire["ebat"],
                        "dot": tire["dot"], "dis_derinligi": tire["mm"],
                    })
                item.marka, item.ebat = tires[0]["marka"], tires[0]["ebat"]
                if km is not None:
                    item.arac_kilometre = km
                item.save(update_fields=["marka", "ebat", "arac_kilometre"])
                return redirect("dashboard:otel_kontrol", pk=pk)
    return render(request, "dashboard/otel_kontrol.html", dict(item=item, form=form, rows=rows,
                  baseline=baseline, before_km=before_km, before_date=before_date, history=history, prev=prev,
                  depolar=LastikDepo.objects.filter(aktif=True)))


@login_required
@misafir_forbidden
@require_POST
@transaction.atomic
def karar(request, pk):
    item = get_object_or_404(LastikOteli.objects.select_for_update(), pk=pk)
    check = item.kontroller.first()
    if not check or str(check.pk) != request.POST.get("kontrol"):
        return HttpResponseBadRequest("Güncel kontrolü açın.")
    action = request.POST.get("islem")
    if action in KARAR:
        if check.karar or item.durum == "degisim":
            return HttpResponseBadRequest("Bu kontrol için karar kaydedilmiş.")
        was_returned = item.durum == "teslim_edildi" and action != "degistir"
        check.karar, check.karar_veren = action, request.user
        if action == "degistir":
            item.durum = "degisim"
            item.cikis_tarihi = timezone.localdate()
        elif item.durum == "teslim_edildi":
            depot_id = request.POST.get("depo", "")
            if not depot_id.isdecimal():
                return HttpResponseBadRequest("Depolama için bir depo ve raf seçin.")
            item.depo = get_object_or_404(LastikDepo, pk=depot_id, aktif=True)
            item.durum = "depoda"
            item.giris_tarihi = timezone.localdate()
            item.cikis_tarihi = None
        item.save()
        LastikOteliHareket.objects.create(kayit=item, hareket_tipi="giris" if was_returned else "guncelleme", yapan=request.user,
                                          aciklama=f"Fiziksel kontrol onayı · {KARAR[action]} · {item.depo or '—'}")
    elif action in {"bildirildi", "onaylandi", "karsilandi"} and (check.karar or check.oneri) in ("izle", "degistir"):
        if action == "karsilandi" and not check.onaylandi:
            return HttpResponseBadRequest("Önce müşteri onayı gereklidir.")
        if action == "onaylandi":
            check.bildirildi = True
        setattr(check, action, True)
    else:
        return HttpResponseBadRequest("Geçersiz işlem.")
    check.save()
    return redirect("dashboard:otel_kontrol", pk=pk)
