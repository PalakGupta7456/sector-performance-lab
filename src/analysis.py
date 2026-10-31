"""
Sector Performance Lab — analysis engine
Builds sector portfolios (US + India), computes return / risk / risk-adjusted
metrics, rolling stats, persistence tests, a momentum outlook and portfolio backtests.
Input : data/prices_monthly.csv  (monthly adjusted closes, from parse.py)
Output: outputs/*.csv and outputs/dashboard_data.json
"""
import json, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"; OUT.mkdir(exist_ok=True)
px = pd.read_csv(ROOT / "data/prices_monthly.csv", index_col=0)
px.index = pd.PeriodIndex(px.index, freq="M")

# ----------------------------------------------------------------- sector maps
US = {  # sector -> list of tickers (Fidelity Select sector funds = total-return sector proxies)
    "Banks": ["FSRBX"], "Brokerage & Asset Mgmt": ["FSLBX"], "Insurance": ["FSPCX"],
    "Chemicals": ["FSCHX"], "Materials": ["FSDPX"], "Energy": ["FSENX"],
    "Health Care": ["FSPHX"], "Biotech": ["FBIOX"], "Technology": ["FSPTX"],
    "Software & IT Services": ["FSCSX"], "Semiconductors": ["FSELX"], "Utilities": ["FSUTX"],
    "Telecom": ["FSTCX"], "Defense & Aerospace": ["FSDAX"], "Transportation": ["FSRFX"],
    "Automotive": ["FSAVX"], "Consumer Staples": ["FDFAX"], "Retail": ["FSRPX"],
    "Leisure": ["FDLSX"], "Construction & Housing": ["FSHOX"], "Gold": ["FSAGX"],
    "Agri & Fertilizers": ["MOS", "CF", "NTR", "ADM", "DE"],
}
IN = {
    "Banks": ["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","KOTAKBANK.NS","AXISBANK.NS","BANKBARODA.NS"],
    "NBFC & Fin. Services": ["BAJFINANCE.NS","SHRIRAMFIN.NS","M&MFIN.NS","LICHSGFIN.NS","CHOLAFIN.NS"],
    "IT Services": ["INFY.NS","TCS.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"],
    "Pharma": ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","LUPIN.NS","AUROPHARMA.NS","DIVISLAB.NS"],
    "FMCG": ["HINDUNILVR.NS","ITC.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS","MARICO.NS"],
    "Auto": ["MARUTI.NS","M&M.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","EICHERMOT.NS","ASHOKLEY.NS"],
    "Metals & Mining": ["TATASTEEL.NS","HINDALCO.NS","JSWSTEEL.NS","SAIL.NS","VEDL.NS","NATIONALUM.NS"],
    "Oil & Gas": ["RELIANCE.NS","ONGC.NS","BPCL.NS","IOC.NS","GAIL.NS","HINDPETRO.NS"],
    "Chemicals": ["PIDILITIND.NS","SRF.NS","UPL.NS","TATACHEM.NS","AARTIIND.NS","DEEPAKNTR.NS","NAVINFLUOR.NS","GUJALKALI.NS"],
    "Fertilizers": ["CHAMBLFERT.NS","COROMANDEL.NS","GSFC.NS","RCF.NS","NFL.NS","DEEPAKFERT.NS","GNFC.NS","FACT.NS"],
    "Cement": ["ULTRACEMCO.NS","ACC.NS","AMBUJACEM.NS","SHREECEM.NS","RAMCOCEM.NS"],
    "Capital Goods": ["LT.NS","BHEL.NS","SIEMENS.NS","ABB.NS","CUMMINSIND.NS","THERMAX.NS"],
    "Power": ["NTPC.NS","POWERGRID.NS","TATAPOWER.NS"],
    "Consumer Durables": ["TITAN.NS","HAVELLS.NS","VOLTAS.NS","WHIRLPOOL.NS","BLUESTARCO.NS"],
    "Realty": ["DLF.NS","GODREJPROP.NS","OBEROIRLTY.NS"],
}
# Approximate annual average Indian 91-day T-bill yields (%), RBI data, rounded
IN_RF = {1995:12.0,1996:11.5,1997:7.3,1998:8.8,1999:9.1,2000:9.1,2001:7.4,2002:5.9,2003:5.0,
         2004:4.7,2005:5.4,2006:6.6,2007:7.2,2008:8.0,2009:3.6,2010:5.4,2011:8.0,2012:8.3,
         2013:8.6,2014:8.6,2015:7.5,2016:6.6,2017:6.2,2018:6.7,2019:6.0,2020:3.6,2021:3.5,
         2022:5.6,2023:6.8,2024:6.8,2025:5.8,2026:5.4}

# ----------------------------------------------------------------- cleaning
def clean_returns(p: pd.Series, is_india: bool):
    r = p.pct_change(fill_method=None)
    log = np.log1p(r)
    bad = pd.Series(False, index=r.index)
    if is_india:
        # 1) spike-and-reversal pairs (bad split adjustment): big move undone within 2 months
        v = log.values
        for i in range(len(v)):
            if np.isnan(v[i]) or abs(v[i]) < 0.6: continue
            for k in (1, 2):
                if i + k < len(v) and not np.isnan(v[i + k]) and np.sign(v[i + k]) != np.sign(v[i]) \
                        and abs(v[i] + v[i + k]) < 0.4 * abs(v[i]):
                    bad.iloc[i:i + k + 1] = True
        # 2) implausible single months for large/mid caps
        bad |= (r < -0.70) | (r > 3.0)
        # first two months after listing on Yahoo are often unreliable
        fv = p.first_valid_index()
        if fv is not None:
            bad.loc[fv:fv + 2] = True
    flagged = r[bad & r.notna()]
    return r.mask(bad), flagged

def build_sector(tickers, is_india):
    rets, flags = {}, []
    for t in tickers:
        if t not in px: continue
        r, f = clean_returns(px[t], is_india)
        rets[t] = r
        flags += [(t, str(d), round(float(x), 3)) for d, x in f.items()]
    R = pd.DataFrame(rets)
    # equal-weight, monthly rebalanced; need >=2 stocks for a multi-stock basket (else 1)
    need = 1 if len(tickers) == 1 else min(2, len(tickers))
    port = R.mean(axis=1, skipna=True).where(R.notna().sum(axis=1) >= need)
    return port, R.notna().sum(axis=1), flags

def build_market(key):
    if key == "US":
        sectors, flags, counts = {}, [], {}
        for s, tk in US.items():
            sectors[s], counts[s], f = build_sector(tk, False); flags += f
        bench = px["^SP500TR"].pct_change(fill_method=None)
        rf = (px["^IRX"] / 100 / 12).shift(1)  # yield known at start of month
        start = pd.Period("1990-02", "M")
    else:
        sectors, flags, counts = {}, [], {}
        for s, tk in IN.items():
            sectors[s], counts[s], f = build_sector(tk, True); flags += f
        bench = px["^BSESN"].pct_change(fill_method=None)
        rf = pd.Series([IN_RF.get(p.year, np.nan) / 100 / 12 for p in px.index], index=px.index)
        start = pd.Period("1997-08", "M")
    S = pd.DataFrame(sectors)
    S = S[S.index >= start]
    # equal-weight "all sectors" portfolio
    S["All-Sector EW"] = S.mean(axis=1, skipna=True)
    return S, bench[bench.index >= start], rf[rf.index >= start].ffill(), flags, counts

# ----------------------------------------------------------------- metrics
def drawdown(r):
    w = (1 + r.fillna(0)).cumprod()
    return w / w.cummax() - 1

def metrics(r, b, rf):
    d = pd.concat([r, b, rf], axis=1, keys=["r", "b", "rf"]).dropna()
    if len(d) < 24: return None
    n = len(d); yrs = n / 12
    ex, exb = d.r - d.rf, d.b - d.rf
    cagr = (1 + d.r).prod() ** (1 / yrs) - 1
    bcagr = (1 + d.b).prod() ** (1 / yrs) - 1
    rf_ann = (1 + d.rf).prod() ** (1 / yrs) - 1
    vol = d.r.std() * np.sqrt(12)
    down = np.sqrt((np.minimum(ex, 0) ** 2).mean()) * np.sqrt(12)
    beta = np.cov(ex, exb)[0, 1] / exb.var()
    ann_ex = ex.mean() * 12
    alpha = ann_ex - beta * exb.mean() * 12              # Jensen's alpha (annualised, arithmetic)
    te = (d.r - d.b).std() * np.sqrt(12)
    mdd = drawdown(d.r).min()
    yearly = (1 + d.r).groupby(d.index.year).prod() - 1
    full_years = d.groupby(d.index.year).size() == 12
    yearly = yearly[full_years]
    up, dn = d.b > 0, d.b < 0
    var95 = np.percentile(d.r, 5)
    return dict(
        start=str(d.index[0]), end=str(d.index[-1]), months=n,
        cagr=cagr, bench_cagr=bcagr, excess_cagr=cagr - bcagr, total_return=(1 + d.r).prod() - 1,
        vol=vol, sharpe=ann_ex / vol, sortino=ann_ex / down if down > 0 else np.nan,
        treynor=ann_ex / beta if beta != 0 else np.nan, beta=beta, alpha=alpha,
        info_ratio=((d.r - d.b).mean() * 12) / te, tracking_error=te,
        max_dd=mdd, calmar=cagr / abs(mdd) if mdd < 0 else np.nan,
        corr=d.r.corr(d.b), r2=d.r.corr(d.b) ** 2,
        best_year=yearly.max() if len(yearly) else np.nan, worst_year=yearly.min() if len(yearly) else np.nan,
        pct_pos_months=(d.r > 0).mean(), pct_years_beat=(yearly > ((1 + d.b).groupby(d.index.year).prod() - 1)[full_years]).mean() if len(yearly) else np.nan,
        up_capture=d.r[up].mean() / d.b[up].mean(), down_capture=d.r[dn].mean() / d.b[dn].mean(),
        var95=var95, cvar95=d.r[d.r <= var95].mean(), skew=d.r.skew(), kurt=d.r.kurt(), rf=rf_ann,
    )

def rolling_sharpe(r, rf, w=36):
    ex = r - rf
    return (ex.rolling(w, min_periods=w).mean() * 12) / (r.rolling(w, min_periods=w).std() * np.sqrt(12))

def persistence(S, horizon=36):
    """Does a sector's rank over the past N months predict its rank over the next N months?"""
    cols = [c for c in S if c != "All-Sector EW"]
    out = []
    for i in range(horizon, len(S) - horizon + 1, 12):
        past = (1 + S[cols].iloc[i - horizon:i]).prod() - 1
        fut = (1 + S[cols].iloc[i:i + horizon]).prod() - 1
        ok = past.notna() & fut.notna()
        if ok.sum() < 6: continue
        rho = past[ok].rank().corr(fut[ok].rank())
        top = past[ok].nlargest(3).index; bot = past[ok].nsmallest(3).index
        out.append(dict(date=str(S.index[i]), rho=rho,
                        top3_next=fut[top].mean(), bottom3_next=fut[bot].mean(), all_next=fut[ok].mean()))
    return pd.DataFrame(out)

def momentum_backtest(S, b, rf, lookback=12, skip=1, k=3):
    """Each month hold the top-k sectors by past 12-1 month return, equal weighted."""
    cols = [c for c in S if c != "All-Sector EW"]
    mom = (1 + S[cols]).rolling(lookback - skip).apply(np.prod, raw=True).shift(skip) - 1
    rets = []
    for i in range(len(S)):
        m = mom.iloc[i - 1] if i > 0 else None
        if m is None or m.notna().sum() < k + 2: rets.append(np.nan); continue
        picks = m.dropna().nlargest(k).index
        rets.append(S[cols].iloc[i][picks].mean())
    return pd.Series(rets, index=S.index)

def min_var_backtest(S, window=60):
    """Walk-forward long-only minimum-variance sector portfolio (rebalanced yearly)."""
    cols = [c for c in S if c != "All-Sector EW"]
    w = None; rets = []
    for i in range(len(S)):
        if i >= window and (w is None or S.index[i].month == 1):
            hist = S[cols].iloc[i - window:i].dropna(axis=1)
            if hist.shape[1] >= 4:
                C = hist.cov().values; n = C.shape[0]
                x = np.ones(n) / n
                for _ in range(500):  # projected gradient descent on the simplex
                    g = C @ x; x = x - 0.5 * g / (np.abs(g).max() + 1e-12) * 0.02
                    x = np.clip(x, 0, None); x = x / x.sum()
                w = pd.Series(x, index=hist.columns)
        rets.append(np.nan if w is None else (S[cols].iloc[i][w.index].fillna(0) * w).sum())
    return pd.Series(rets, index=S.index), w

def outlook(S, rf):
    """Transparent composite signal — NOT a forecast. Higher = stronger recent evidence."""
    cols = [c for c in S if c != "All-Sector EW"]
    last = S.index[-1]
    mom = (1 + S[cols].iloc[-12:-1]).prod() - 1                 # 12-1 momentum
    wealth = (1 + S[cols].fillna(0)).cumprod()
    trend = wealth.iloc[-1] / wealth.iloc[-10:].mean() - 1        # vs 10-month average (trend filter)
    sh3 = pd.Series({c: rolling_sharpe(S[c], rf.reindex(S.index)).iloc[-1] for c in cols})
    dd = pd.Series({c: drawdown(S[c].iloc[-36:]).iloc[-1] for c in cols})
    z = lambda s: (s - s.mean()) / s.std()
    score = 0.5 * z(mom) + 0.25 * z(trend) + 0.25 * z(sh3)
    df = pd.DataFrame(dict(mom_12_1=mom, trend_vs_10m=trend, sharpe_3y=sh3, dd_from_3y_peak=dd, score=score))
    df["signal"] = np.where(df.score > 0.5, "Positive", np.where(df.score < -0.5, "Negative", "Neutral"))
    df["above_trend"] = df.trend_vs_10m > 0
    return df.sort_values("score", ascending=False), str(last)

# ----------------------------------------------------------------- run
def clean(x):
    if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if (np.isnan(x) or np.isinf(x)) else round(float(x), 5)
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, (np.bool_,)): return bool(x)
    return x

result = {}
WINDOWS = {"Full": None, "20Y": 240, "10Y": 120, "5Y": 60, "3Y": 36, "1Y": 12}
for key in ("US", "IN"):
    S, b, rf, flags, counts = build_market(key)
    S.to_csv(OUT / f"{key}_sector_monthly_returns.csv")
    mkt = {"sectors": list(S.columns), "bench_name": "S&P 500 TR" if key == "US" else "BSE Sensex",
           "currency": "USD" if key == "US" else "INR", "flags": flags,
           "constituents": US if key == "US" else IN}
    # metrics by window
    mt = {}
    for wname, wn in WINDOWS.items():
        Sw = S if wn is None else S.iloc[-wn:]
        rows = {}
        for c in S.columns:
            m = metrics(Sw[c], b.reindex(Sw.index), rf.reindex(Sw.index)) if wn is None or wn >= 24 else None
            if wn == 12:  # 1-year: simple stats only
                d = pd.concat([Sw[c], b.reindex(Sw.index), rf.reindex(Sw.index)], axis=1).dropna()
                if len(d) == 12:
                    r_ = d.iloc[:, 0]; ex = r_ - d.iloc[:, 2]
                    m = dict(cagr=(1 + r_).prod() - 1, bench_cagr=(1 + d.iloc[:, 1]).prod() - 1,
                             vol=r_.std() * np.sqrt(12), sharpe=ex.mean() * 12 / (r_.std() * np.sqrt(12)),
                             max_dd=drawdown(r_).min(), start=str(d.index[0]), end=str(d.index[-1]))
                    m["excess_cagr"] = m["cagr"] - m["bench_cagr"]
            if m: rows[c] = m
        bm = metrics(b.reindex(Sw.index), b.reindex(Sw.index), rf.reindex(Sw.index)) if (wn or 999) >= 24 else None
        mt[wname] = {"sectors": rows, "bench": bm}
        if wname == "Full":
            pd.DataFrame(rows).T.to_csv(OUT / f"{key}_metrics_full_period.csv")
    mkt["metrics"] = mt
    # growth of 1 (log-friendly), drawdowns
    W = (1 + S.fillna(0)).cumprod()
    first = S.apply(lambda s: s.first_valid_index())
    for c in S: W.loc[: first[c] - 1, c] = np.nan  # blank before inception
    bw = (1 + b.fillna(0)).cumprod()
    mkt["dates"] = [str(p) for p in S.index]
    mkt["growth"] = {c: W[c].round(4).tolist() for c in S}
    mkt["bench_growth"] = bw.round(4).tolist()
    mkt["drawdown"] = {c: drawdown(S[c]).where(W[c].notna()).round(4).tolist() for c in S}
    mkt["bench_drawdown"] = drawdown(b).round(4).tolist()
    mkt["rolling_sharpe"] = {c: rolling_sharpe(S[c], rf).round(3).tolist() for c in S}
    mkt["rolling_rel"] = {c: (((1 + S[c]).rolling(36).apply(np.prod, raw=True)) ** (1/3)
                              - ((1 + b).rolling(36).apply(np.prod, raw=True)) ** (1/3)).round(4).tolist() for c in S}
    # calendar years
    full = S.groupby(S.index.year).count() == 12
    yr = (1 + S).groupby(S.index.year).prod() - 1
    yr = yr.where(full)
    last_year = S.index[-1].year
    ytd = (1 + S[S.index.year == last_year]).prod() - 1
    yr.loc[last_year] = ytd.where(S[S.index.year == last_year].notna().sum() > 0)
    bfull = b.groupby(b.index.year).count() == 12
    byr = (1 + b).groupby(b.index.year).prod() - 1
    byr = byr.where(bfull | (byr.index == last_year))  # drop partial first year; keep YTD
    mkt["years"] = [int(y) for y in yr.index]
    mkt["year_returns"] = {c: yr[c].round(4).tolist() for c in S}
    mkt["bench_years"] = byr.reindex(yr.index).round(4).tolist()
    mkt["ytd_label"] = f"{last_year} YTD (to {S.index[-1]})"
    # decades / eras
    eras = {"1990s": ("1990", "1999"), "2000s": ("2000", "2009"), "2010s": ("2010", "2019"), "2020s": ("2020", "2026")}
    era_tab = {}
    for e, (a, z_) in eras.items():
        sub = S.loc[a:z_]
        if len(sub) < 60: continue  # need at least 5 years of a decade to annualise meaningfully
        era_tab[e] = {c: ((1 + sub[c].dropna()).prod() ** (12 / max(sub[c].notna().sum(), 1)) - 1) if sub[c].notna().sum() >= 60 else None for c in S}
        bb = b.loc[a:z_]; era_tab[e]["__bench"] = (1 + bb).prod() ** (12 / len(bb)) - 1
    mkt["eras"] = era_tab
    # correlations (last 10y, monthly)
    C = S.iloc[-120:].drop(columns=["All-Sector EW"]).corr()
    mkt["corr"] = {"labels": list(C.columns), "matrix": C.round(3).values.tolist()}
    # persistence
    P = persistence(S)
    P.to_csv(OUT / f"{key}_persistence_test.csv", index=False)
    mkt["persistence"] = {"rows": P.to_dict("records"), "avg_rho": P.rho.mean(),
                          "top3_avg": P.top3_next.mean(), "bottom3_avg": P.bottom3_next.mean(),
                          "all_avg": P.all_next.mean(), "pct_top_beat_bottom": (P.top3_next > P.bottom3_next).mean()}
    # strategies
    mom = momentum_backtest(S, b, rf)
    mv, mvw = min_var_backtest(S)
    strat = pd.DataFrame({"Top-3 Momentum Rotation": mom, "Min-Variance (walk-fwd)": mv,
                          "All-Sector EW": S["All-Sector EW"], mkt["bench_name"]: b})
    common = strat.dropna().index
    strat = strat.loc[common]
    mkt["strategies"] = {"dates": [str(p) for p in common],
                         "growth": {c: (1 + strat[c]).cumprod().round(4).tolist() for c in strat},
                         "metrics": {c: metrics(strat[c], b.reindex(common), rf.reindex(common)) for c in strat},
                         "minvar_weights": mvw.sort_values(ascending=False).round(4).to_dict() if mvw is not None else {}}
    strat.to_csv(OUT / f"{key}_strategy_returns.csv")
    # outlook
    O, asof = outlook(S, rf)
    O.to_csv(OUT / f"{key}_outlook_signals.csv")
    mkt["outlook"] = {"asof": asof, "rows": O.reset_index().rename(columns={"index": "sector"}).to_dict("records")}
    # stock-level contribution inside each sector (CAGR of each constituent, cleaned)
    cons = {}
    for s, tk in (US if key == "US" else IN).items():
        if len(tk) < 2: continue
        lst = []
        for t in tk:
            if t not in px: continue
            r, _ = clean_returns(px[t], key == "IN")
            r = r[r.index >= S.index[0]].dropna()
            if len(r) < 24: continue
            lst.append(dict(ticker=t, since=str(r.index[0]), cagr=(1 + r).prod() ** (12 / len(r)) - 1,
                            vol=r.std() * np.sqrt(12), last1y=(1 + r.iloc[-12:]).prod() - 1))
        cons[s] = lst
    mkt["stocks"] = cons
    result[key] = mkt
    print(key, "sectors:", len(S.columns), "range", S.index[0], "-", S.index[-1], "flags:", len(flags))


# ----------------------------------------------------------------- official NSE sector indices (survivorship-free check)
IDX = {"Banks": "^NSEBANK", "PSU Banks": "^CNXPSUBANK", "IT Services": "^CNXIT", "Pharma": "^CNXPHARMA",
       "FMCG": "^CNXFMCG", "Auto": "^CNXAUTO", "Metals & Mining": "^CNXMETAL", "Energy (Oil, Gas, Power)": "^CNXENERGY",
       "Infrastructure": "^CNXINFRA", "Realty": "^CNXREALTY"}
start = pd.Period("2011-08", "M")
nb = px["^NSEI"].pct_change(fill_method=None); nb = nb[nb.index >= start]
rf_in = pd.Series([IN_RF.get(p.year, np.nan) / 100 / 12 for p in px.index], index=px.index)
I = pd.DataFrame({k: px[t].pct_change(fill_method=None) for k, t in IDX.items()})
I = I[I.index >= start]
idx_rows = {k: metrics(I[k], nb, rf_in) for k in I}
SB = pd.read_csv(OUT / "IN_sector_monthly_returns.csv", index_col=0); SB.index = pd.PeriodIndex(SB.index, freq="M")
SB = SB[SB.index >= start]
basket_rows = {k: metrics(SB[k], nb, rf_in) for k in SB if k != "All-Sector EW"}
W = (1 + I.fillna(0)).cumprod()
result["IN"]["official"] = {
    "start": str(start), "end": str(I.index[-1]), "bench_name": "Nifty 50",
    "metrics": idx_rows, "bench": metrics(nb, nb, rf_in), "basket_same_window": basket_rows,
    "dates": [str(p) for p in I.index], "growth": {k: W[k].round(4).tolist() for k in I},
    "bench_growth": (1 + nb.fillna(0)).cumprod().round(4).tolist(),
}
pd.DataFrame(idx_rows).T.to_csv(OUT / "IN_official_nse_indices_metrics.csv")

names = json.load(open(ROOT / "data/names.json"))
result["names"] = names
result["generated"] = "2026-11-01"
json.dump(clean(result), open(OUT / "dashboard_data.json", "w"), separators=(",", ":"))
print("json KB:", round((OUT / "dashboard_data.json").stat().st_size / 1024))
