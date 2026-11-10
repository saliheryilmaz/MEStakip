# Review: aktif-is-emri akışı (commit 2f21751)

## Checked against task requirements

| Requirement | Status |
|---|---|
| depo_fisi_istek: depo_fisi_id varsa mevcut fişe kalem ekle | ✅ Implemented (erp/views.py:344-349) |
| depo_fisi_istek: yoksa yeni fiş oluştur | ✅ Implemented (erp/views.py:347-357) |
| depo_fisi_istek response'a depo_fisi_id ekle | ✅ `'depo_fisi_id': fis.fis_no` (erp/views.py:361) |
| Yeni depo_fisi_kalem_ekle view | ✅ erp/views.py:524 |
| POST /erp/depo-fisi/<id>/kalem-ekle/ URL | ✅ erp/urls.py line 38 |
| Yeni stok_ara_ajax view | ✅ erp/views.py:564 |
| GET /erp/stok/ara/ URL | ✅ erp/urls.py line 39 |
| stok_listesi.html: sessionStorage aktifIsEmriId | ✅ present at multiple points |
| stok_listesi.html: fisEkleForm div | ✅ line 168 |
| stok_listesi.html: fisEkleSonuc div | ✅ line 221 |
| stok_listesi.html: devamEtBtn | ✅ line 228 |
| stok_listesi.html: isEmriniKapatBtn | ✅ line 231 |
| depo_fisi_detay.html: kalemEklePanel div | ✅ line 62 |
| depo_fisi_detay.html: stokAra fonksiyonu | ✅ line 374 |
| depo_fisi_detay.html: kalemEkle fonksiyonu | ✅ line 438 |
| python manage.py check: 0 issues | ✅ confirmed |

## Blocker

### depo_fisi_istek does not guard fis.durum when adding to an existing fiş

**File:** `erp/views.py`, lines 344–358

**Evidence:** When `depo_fisi_id` is present, the view does:
```python
fis = get_object_or_404(DepoFisi, pk=int(depo_fisi_id))
# … no durum check …
DepoFisiKalemi.objects.create(fis=fis, stok=stok, adet=adet)
```

`sessionStorage` persists across browser tabs. If a user approves or cancels a fiş in another tab (changing its `durum` to `onaylandi` or `iptal`), the stok_listesi modal still holds that fiş ID in `sessionStorage` and the next submission will append a new `DepoFisiKalemi` row to a fiş that is no longer in `bekliyor` state, silently corrupting it.

The companion `depo_fisi_kalem_ekle` view (erp/views.py:528–529) already implements the correct guard:
```python
if fis.durum != 'bekliyor':
    return JsonResponse({'basarili': False, 'hata': 'Sadece bekliyor durumundaki fişlere kalem eklenebilir.'})
```

**User-visible consequence:** Items are silently added to approved or cancelled receipts without any error feedback, and the counts/history on those receipts become incorrect.

**Correction:** Add the same durum guard to `depo_fisi_istek` immediately after the fiş lookup:
```python
if depo_fisi_id:
    fis = get_object_or_404(DepoFisi, pk=int(depo_fisi_id))
    if fis.durum != 'bekliyor':
        return JsonResponse({'basarili': False, 'hata': 'Bu fiş artık bekliyor durumunda değil. Yeni bir fiş oluşturuluyor.'})
```
Or alternatively fall through to creating a new fiş (clearing sessionStorage on the client side when this error is returned).
