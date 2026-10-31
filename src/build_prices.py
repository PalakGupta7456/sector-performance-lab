"""
Step 2 — turn the raw Yahoo JSON files in data/raw/ into one tidy monthly table:
data/prices_monthly.csv (rows = months, columns = tickers, values = dividend/split-adjusted close)
and data/names.json (ticker -> company / fund name).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

series, names = {}, {}
for f in sorted(RAW.glob("*.json")):
    j = json.loads(f.read_text())["chart"]["result"][0]
    meta, ts = j["meta"], j.get("timestamp")
    if not ts:
        continue
    ind = j["indicators"]
    px = ind["adjclose"][0]["adjclose"] if "adjclose" in ind else ind["quote"][0]["close"]
    # shift by the exchange's UTC offset so an IST month-start bar isn't filed under the previous month
    idx = pd.to_datetime(np.array(ts) + meta.get("gmtoffset", 0), unit="s").to_period("M")
    s = pd.Series(px, index=idx, dtype="float64").dropna()
    series[meta["symbol"]] = s[~s.index.duplicated(keep="last")]
    names[meta["symbol"]] = meta.get("longName") or meta.get("shortName") or meta["symbol"]

df = pd.DataFrame(series).sort_index()
df.to_csv(ROOT / "data" / "prices_monthly.csv")
(ROOT / "data" / "names.json").write_text(json.dumps(names, indent=1, ensure_ascii=False))
print(f"{df.shape[1]} tickers, {df.index.min()} → {df.index.max()}")
