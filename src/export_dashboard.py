"""Turn outputs/dashboard_data.json into tidy row-files the live dashboard reads (docs/data/*.json)."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = json.load(open(ROOT / "outputs/dashboard_data.json"))
OUTD = ROOT / "docs/data"; OUTD.mkdir(parents=True, exist_ok=True)
slug = lambda s: re.sub(r"[^A-Za-z0-9]+", "", s)
pct = lambda x, n=1: None if x is None else round(x * 100, n)
num = lambda x, n=2: None if x is None else round(x, n)
MK = {"US": "US", "IN": "India"}
import calendar
lab = lambda p: f"{calendar.month_abbr[int(p[5:7])]} {p[:4]}"
ym = lambda p: int(p[:4]) + (int(p[5:7]) - 1) / 12

def save(name, rows):
    p = OUTD / f"{name}.json"
    json.dump({"rows": rows}, open(p, "w"), separators=(",", ":"), ensure_ascii=False)
    print(f"{name:12s} {len(rows):6d} rows  {p.stat().st_size/1024:7.0f} KB")

# ---- metrics: every sector x window, plus benchmark row
metrics, headlines = [], []
for m in ("US", "IN"):
    bench = D[m]["bench_name"]
    for w, blk in D[m]["metrics"].items():
        def row(name, kind, v):
            return dict(key=f"{m}-{w}-{slug(name)}", market=MK[m], window=w, sector=name, kind=kind,
                        start=v.get("start"), end=v.get("end"),
                        cagr=pct(v.get("cagr")), bench_cagr=pct(v.get("bench_cagr")), excess=pct(v.get("excess_cagr")),
                        vol=pct(v.get("vol")), sharpe=num(v.get("sharpe")), sortino=num(v.get("sortino")),
                        treynor=pct(v.get("treynor")), beta=num(v.get("beta")), alpha=pct(v.get("alpha")),
                        info_ratio=num(v.get("info_ratio")), max_dd=pct(v.get("max_dd")), calmar=num(v.get("calmar")),
                        best_year=pct(v.get("best_year")), worst_year=pct(v.get("worst_year")),
                        pct_pos=pct(v.get("pct_pos_months"), 0), up_cap=pct(v.get("up_capture"), 0),
                        down_cap=pct(v.get("down_capture"), 0), var95=pct(v.get("var95")), cvar95=pct(v.get("cvar95")))
        rows = [row(s, "portfolio" if s == "All-Sector EW" else "sector", v) for s, v in blk["sectors"].items()]
        bv = blk.get("bench") or None
        if bv is None:  # 1Y: build simple benchmark row from any sector's bench_cagr
            any_ = next(iter(blk["sectors"].values()))
            bv = dict(cagr=any_["bench_cagr"], start=any_.get("start"), end=any_.get("end"))
        rows.append(row(bench, "benchmark", bv))
        metrics += rows
        secs = [r for r in rows if r["kind"] == "sector" and r["sharpe"] is not None]
        if secs:
            ts = max(secs, key=lambda r: r["sharpe"]); tc = max(secs, key=lambda r: r["cagr"])
            md = max(secs, key=lambda r: r["max_dd"]); wc = min(secs, key=lambda r: r["cagr"])
            beat = sum(1 for r in secs if r["cagr"] > (bv.get("cagr") or 0) * 100)
            b = [r for r in rows if r["kind"] == "benchmark"][0]
            headlines.append(dict(key=f"{m}-{w}", market=MK[m], window=w, bench=bench,
                                  start=b["start"] or ts["start"], end=b["end"] or ts["end"],
                                  top_sharpe_sector=ts["sector"], top_sharpe=ts["sharpe"],
                                  top_cagr_sector=tc["sector"], top_cagr=tc["cagr"],
                                  worst_cagr_sector=wc["sector"], worst_cagr=wc["cagr"],
                                  min_dd_sector=md["sector"], min_dd=md["max_dd"],
                                  bench_cagr=b["cagr"], bench_sharpe=b["sharpe"],
                                  n_sectors=len(secs), n_beat=beat,
                                  market_label=("US stocks" if m == "US" else "Indian stocks"),
                                  period=f"{lab(b['start'] or ts['start'])} – {lab(b['end'] or ts['end'])}",
                                  years=round(ym(b['end'] or ts['end']) - ym(b['start'] or ts['start']) + 1/12, 1),
                                  top_sharpe_cagr=ts["cagr"], top_sharpe_dd=ts["max_dd"]))
save("metrics", metrics); save("headlines", headlines)

# ---- monthly series: growth, drawdown, rolling sharpe, rolling 3y excess
series = []
for m in ("US", "IN"):
    dd, bench = D[m]["dates"], D[m]["bench_name"]
    for s in D[m]["sectors"]:
        g, d_, rs, rr = D[m]["growth"][s], D[m]["drawdown"][s], D[m]["rolling_sharpe"][s], D[m]["rolling_rel"][s]
        for i, t in enumerate(dd):
            if g[i] is None: continue
            series.append(dict(market=MK[m], date=t, sector=s, growth=g[i], drawdown=pct(d_[i]),
                               rsharpe=rs[i], rel3y=pct(rr[i])))
    for i, t in enumerate(dd):
        series.append(dict(market=MK[m], date=t, sector=bench, growth=D[m]["bench_growth"][i],
                           drawdown=pct(D[m]["bench_drawdown"][i]), rsharpe=None, rel3y=None))
save("series", series)

# ---- calendar years
years = []
for m in ("US", "IN"):
    ys = D[m]["years"]; last = ys[-1]
    for s, vals in D[m]["year_returns"].items():
        for y, v in zip(ys, vals):
            if v is not None:
                years.append(dict(key=f"{m}-{y}-{slug(s)}", market=MK[m], year=y, ytd=(y == last), sector=s, ret=pct(v)))
    for y, v in zip(ys, D[m]["bench_years"]):
        if v is not None:
            years.append(dict(key=f"{m}-{y}-bench", market=MK[m], year=y, ytd=(y == last), sector=D[m]["bench_name"], ret=pct(v)))
save("years", years)

# ---- eras (decade CAGR)
eras = []
for m in ("US", "IN"):
    for e, blk in D[m]["eras"].items():
        for s, v in blk.items():
            if v is None: continue
            name = D[m]["bench_name"] if s == "__bench" else s
            eras.append(dict(key=f"{m}-{e}-{slug(name)}", market=MK[m], era=e, sector=name, cagr=pct(v)))
save("eras", eras)

# ---- correlations (last 10 years)
corr = []
for m in ("US", "IN"):
    L, M = D[m]["corr"]["labels"], D[m]["corr"]["matrix"]
    for i, a in enumerate(L):
        for j, b in enumerate(L):
            corr.append(dict(market=MK[m], a=a, b=b, rho=M[i][j]))
save("corr", corr)

# ---- persistence test
pers = []
for m in ("US", "IN"):
    for r in D[m]["persistence"]["rows"]:
        pers.append(dict(market=MK[m], date=r["date"], rho=num(r["rho"]), top3=pct(r["top3_next"]),
                         bottom3=pct(r["bottom3_next"]), all=pct(r["all_next"])))
save("persistence", pers)
psum = []
for m in ("US", "IN"):
    P = D[m]["persistence"]
    psum.append(dict(market=MK[m], avg_rho=num(P["avg_rho"]), top3=pct(P["top3_avg"]), bottom3=pct(P["bottom3_avg"]),
                     all=pct(P["all_avg"]), pct_top_beat=pct(P["pct_top_beat_bottom"], 0), n=len(P["rows"])))
save("persist_sum", psum)

# ---- strategies
strat, smet = [], []
for m in ("US", "IN"):
    S = D[m]["strategies"]
    for name, g in S["growth"].items():
        for t, v in zip(S["dates"], g):
            strat.append(dict(market=MK[m], date=t, strategy=name, growth=v))
    for name, v in S["metrics"].items():
        smet.append(dict(key=f"{m}-{slug(name)}", market=MK[m], strategy=name, start=v["start"], end=v["end"],
                         cagr=pct(v["cagr"]), vol=pct(v["vol"]), sharpe=num(v["sharpe"]), sortino=num(v["sortino"]),
                         max_dd=pct(v["max_dd"]), beta=num(v["beta"]), alpha=pct(v["alpha"])))
save("strategies", strat); save("strat_metrics", smet)

# ---- outlook
outl = []
for m in ("US", "IN"):
    for r in D[m]["outlook"]["rows"]:
        outl.append(dict(key=f"{m}-{slug(r['sector'])}", market=MK[m], asof=D[m]["outlook"]["asof"], sector=r["sector"],
                         score=num(r["score"]), signal=r["signal"], mom=pct(r["mom_12_1"]),
                         trend=pct(r["trend_vs_10m"]), sharpe3y=num(r["sharpe_3y"]), dd3y=pct(r["dd_from_3y_peak"])))
save("outlook", outl)

# ---- official NSE indices vs baskets (India)
O = D["IN"]["official"]
nse = []
basket_map = {"Banks": "Banks", "IT Services": "IT Services", "Pharma": "Pharma", "FMCG": "FMCG", "Auto": "Auto",
              "Metals & Mining": "Metals & Mining", "Energy (Oil, Gas, Power)": "Oil & Gas", "Infrastructure": "Capital Goods",
              "Realty": "Realty", "PSU Banks": None}
for k, v in O["metrics"].items():
    b = O["basket_same_window"].get(basket_map[k]) if basket_map[k] else None
    nse.append(dict(key=slug(k), index=k, start=v["start"], end=v["end"], cagr=pct(v["cagr"]), vol=pct(v["vol"]),
                    sharpe=num(v["sharpe"]), treynor=pct(v["treynor"]), beta=num(v["beta"]), max_dd=pct(v["max_dd"]),
                    basket=basket_map[k] or "—", basket_cagr=pct(b["cagr"]) if b else None,
                    gap=pct(b["cagr"] - v["cagr"]) if b else None))
nb = O["bench"]
nse.append(dict(key="Nifty50", index="Nifty 50 (benchmark)", start=nb["start"], end=nb["end"], cagr=pct(nb["cagr"]), vol=pct(nb["vol"]),
                sharpe=num(nb["sharpe"]), treynor=pct(nb["treynor"]), beta=num(nb["beta"]), max_dd=pct(nb["max_dd"]),
                basket="—", basket_cagr=None, gap=None))
save("nse", nse)
nseg = []
for k, g in O["growth"].items():
    for t, v in zip(O["dates"], g):
        nseg.append(dict(date=t, index=k, growth=v))
for t, v in zip(O["dates"], O["bench_growth"]):
    nseg.append(dict(date=t, index="Nifty 50 (benchmark)", growth=v))
save("nse_growth", nseg)

# ---- constituents
names = D["names"]
stocks = []
for m in ("US", "IN"):
    cons = D[m]["constituents"]
    for s, tks in cons.items():
        perf = {r["ticker"]: r for r in D[m]["stocks"].get(s, [])}
        for t in tks:
            r = perf.get(t, {})
            stocks.append(dict(key=f"{m}-{t}", market=MK[m], sector=s, ticker=t.replace(".NS", ""),
                               name=names.get(t, t), since=r.get("since"), cagr=pct(r.get("cagr")),
                               vol=pct(r.get("vol")), last1y=pct(r.get("last1y"))))
save("stocks", stocks)

# ---- cleaned data points
flags = [dict(key=f"{t}-{d}", ticker=t.replace(".NS", ""), month=d, raw_return=pct(x)) for t, d, x in D["IN"]["flags"]]
save("flags", flags)
