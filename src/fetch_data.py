"""
Step 1 — download monthly price history (Jan 1990 → today) for every ticker in universe.py
from Yahoo Finance's public chart endpoint, saving one raw JSON file per ticker in data/raw/.

    python src/fetch_data.py            # fetch everything (skips files already present)
    python src/fetch_data.py --refresh  # re-download all

The repo already ships the raw files pulled on 1 Nov 2026, so this step is optional.
"""
import json, sys, time, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

from universe import ALL_TICKERS

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
START = int(datetime(1990, 1, 1, tzinfo=timezone.utc).timestamp())
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1mo&events=div%2Csplit"
HEADERS = {"User-Agent": "Mozilla/5.0 (sector-performance-lab research script)"}


def raw_path(sym: str) -> Path:
    return RAW / f"{sym.replace('^', 'IDX_')}.json"


def fetch(sym: str) -> dict:
    url = URL.format(sym=urllib.parse.quote(sym), p1=START, p2=int(time.time()))
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data["chart"]["result"]:
        raise ValueError(data["chart"].get("error"))
    return data


def main(refresh: bool = False):
    for i, sym in enumerate(ALL_TICKERS, 1):
        p = raw_path(sym)
        if p.exists() and not refresh:
            continue
        try:
            p.write_text(json.dumps(fetch(sym), separators=(",", ":")))
            print(f"[{i}/{len(ALL_TICKERS)}] {sym} ok")
        except Exception as e:  # keep going; a missing ticker just drops out of its basket
            print(f"[{i}/{len(ALL_TICKERS)}] {sym} FAILED: {e}")
        time.sleep(0.4)  # be polite


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
