from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import quote

import requests
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render
from django.views.decorators.http import require_GET

INSTRUMENTS = (
    ("Euro", "EURTRY=X", "₺", "currency-euro", "primary"),
    ("Dolar", "TRY=X", "₺", "currency-dollar", "success"),
    ("BIST 100", "XU100.IS", "puan", "graph-up", "info"),
    ("Altın", "GC=F", "$/ons · vadeli", "gem", "warning"),
    ("Gümüş", "SI=F", "$/ons · vadeli", "gem", "secondary"),
)


def _quote(instrument):
    name, symbol, unit, icon, color = instrument
    key = f"market-quote:v1:{symbol}"
    row = dict(name=name, unit=unit, icon=icon, color=color)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}"
    try:
        response = requests.get(url, params={"range": "1d", "interval": "1d"},
                                headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
        response.raise_for_status()
        meta = response.json()["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        if not isfinite(price) or price <= 0:
            raise ValueError("Invalid price")
        data = {"price": format(price, ",.2f").translate(str.maketrans(",.", ".,")),
                "timestamp": datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc)}
    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError, OverflowError):
        return {**row, **(cache.get(key) or {})}
    cache.set(key, data, 7 * 86400)
    return {**row, **data}


@login_required
@require_GET
def market_strip(request):
    rows = cache.get("dashboard-market-strip:v2")
    if rows is None:
        with ThreadPoolExecutor(max_workers=len(INSTRUMENTS)) as pool:
            rows = list(pool.map(_quote, INSTRUMENTS))
        cache.set("dashboard-market-strip:v2", rows, 300)
    return render(request, "dashboard/_market_strip.html", {"quotes": rows})
