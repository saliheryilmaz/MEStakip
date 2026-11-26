from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
from math import isfinite
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render
from django.views.decorators.http import require_GET

GRAM_GOLD = "GRA"
GRAM_SILVER = "GUMUS"
GRAM_METALS = (GRAM_GOLD, GRAM_SILVER)
logger = logging.getLogger(__name__)
QUOTE_ERRORS = (requests.RequestException, KeyError, IndexError, ValueError, TypeError, OverflowError)
MARKET_STRIP_KEY = "dashboard-market-strip:v6"
INSTRUMENTS = (
    ("Euro", "EURTRY=X", "₺", "currency-euro", "primary"),
    ("Dolar", "TRY=X", "₺", "currency-dollar", "success"),
    ("BIST 100", "XU100.IS", "puan", "graph-up", "info"),
    ("Gram Altın", GRAM_GOLD, "₺ · satış", "gem", "warning"),
    ("Gram Gümüş", GRAM_SILVER, "₺/g · satış", "gem", "secondary"),
)


def _truncgil_gram(symbol):
    response = requests.get("https://finans.truncgil.com/v4/today.json", timeout=4)
    response.raise_for_status()
    payload = response.json()
    return payload[symbol]["Selling"], payload["Update_Date"]


def _gramhane_gram(symbol):
    response = requests.get("https://api.gramhane.com/v1/prices.json", timeout=4)
    response.raise_for_status()
    payload = response.json()
    if payload["meta"]["status"] != "success":
        raise ValueError("Gramhane did not return a quote")
    key = "ALTIN" if symbol == GRAM_GOLD else symbol
    return payload["kurlar"][key]["satis"], payload["meta"]["tarih"]


def _gram_quote(symbol):
    for source, fetch in (("Trunçgil Finans", _truncgil_gram), ("Gramhane", _gramhane_gram)):
        try:
            amount, updated_at = fetch(symbol)
            price = float(amount)
            if not isfinite(price) or price <= 0:
                raise ValueError("Invalid price")
            timestamp = datetime.fromisoformat(updated_at)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=ZoneInfo("Europe/Istanbul"))
        except QUOTE_ERRORS as error:
            logger.warning("%s verisi alınamadı (%s): %s", symbol, source, type(error).__name__)
            continue
        return price, timestamp, source
    raise ValueError("Gram metal sources unavailable")


def _yahoo_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}"
    response = requests.get(url, params={"range": "1d", "interval": "1d"},
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
    response.raise_for_status()
    meta = response.json()["chart"]["result"][0]["meta"]
    return float(meta["regularMarketPrice"]), datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc)


def _quote(instrument):
    name, symbol, unit, icon, color = instrument
    key = f"market-quote:v1:{symbol}"
    row = dict(name=name, unit=unit, icon=icon, color=color)
    try:
        if symbol in GRAM_METALS:
            price, timestamp, source = _gram_quote(symbol)
        else:
            price, timestamp = _yahoo_quote(symbol)
            source = ""
        if not isfinite(price) or price <= 0:
            raise ValueError("Invalid price")
        data = {"price": format(price, ",.2f").translate(str.maketrans(",.", ".,")),
                "timestamp": timestamp, "source": source}
    except QUOTE_ERRORS:
        cached = cache.get(key) or {}
        return {**row, **cached, "stale": symbol in GRAM_METALS and bool(cached)}
    cache.set(key, data, 7 * 86400)
    return {**row, **data}


@login_required
@require_GET
def market_strip(request):
    rows = cache.get(MARKET_STRIP_KEY)
    if rows is None:
        with ThreadPoolExecutor(max_workers=len(INSTRUMENTS)) as pool:
            rows = list(pool.map(_quote, INSTRUMENTS))
        retry = any(not row.get("price") or row.get("stale") for instrument, row in zip(INSTRUMENTS, rows)
                    if instrument[1] in GRAM_METALS)
        cache.set(MARKET_STRIP_KEY, rows, 30 if retry else 300)
    return render(request, "dashboard/_market_strip.html", {"quotes": rows})
