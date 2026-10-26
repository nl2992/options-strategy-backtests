"""Earnings-event option study (EOD). One trade per (ticker, announcement).

Timing: announce timestamp from earnings_actuals. After-close (>=16:00) -> enter at close of announce
date, exit at close of next session. Pre-open (<09:30) -> enter at close of previous session, exit at
close of announce date. Entry decision is a pure calendar rule known in advance (announce date is the
file's value; whether it was published ex-ante is NOT verified -> flagged).
Structures (all defined risk): long_straddle (debit; max loss = debit), short_condor
(sell ~0.25-delta strangle, buy wings W% of spot further out), long_strangle.
Fills: buy ask / sell bid at entry and exit snapshots, fee per contract per side.
Expiry: first listed expiry with DTE>=5 after the event (exit occurs before expiry; no assignment).
"""
import numpy as np, pandas as pd, duckdb, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
NAMES = ["AAPL","TSLA","AMD","AMZN","AVGO","CRM","GOOGL","JPM","LLY","META","NFLX","UNH","MSFT","NVDA","WMT","XOM"]

def events():
    c = duckdb.connect()
    e = c.sql(f"select ticker, announce_date::date d, announce_time t from '{ROOT}/data/raw/context/earnings_actuals_2022_2024.parquet' "
              f"where announce_date between '2022-01-01' and '2024-12-31'").df()
    e = e[e.ticker.isin(NAMES)].drop_duplicates(["ticker", "d"]); e["d"] = [x.date() for x in pd.to_datetime(e.d)]
    return e

def load(u):
    q = pd.read_parquet(f"{ROOT}/data/normalized/quotes_{u}.parquet")
    q["date"] = pd.to_datetime(q["date"]).dt.date; q["exdate"] = pd.to_datetime(q["exdate"]).dt.date
    return q

def _leg(day, exd, cp, strike):
    r = day[(day.exdate == exd) & (day.cp == cp) & np.isclose(day.strike, strike)]
    return None if r.empty else r.iloc[0]

def run(structure="long_straddle", fee=0.65, slip=1.0, equity0=200_000, risk_trade=0.005, wing=0.05, names=NAMES):
    ev = events(); out = []
    for u in names:
        q = load(u); days = sorted(q.date.unique()); g = {d: x for d, x in q.groupby("date")}
        for _, r in ev[ev.ticker == u].iterrows():
            after = int(str(r.t)[:2]) >= 16
            if r.d not in g and r.d not in days: continue
            import bisect
            i = bisect.bisect_left(days, r.d)
            if i >= len(days) or days[i] != r.d: continue
            ie, ix = (i, i + 1) if after else (i - 1, i)
            if ie < 0 or ix >= len(days): continue
            de, dx = days[ie], days[ix]
            if (dx - de).days > 5: continue
            ge, gx = g[de], g[dx]; S0 = ge.spot.iloc[0]; S1 = gx.spot.iloc[0]
            ex = sorted(x for x in ge.exdate.unique() if (x - dx).days >= 5)
            if not ex: continue
            exd = ex[0]; ch = ge[ge.exdate == exd]
            def px(row, side, sl): 
                mid, h = (row.bid + row.ask) / 2, (row.ask - row.bid) / 2
                return max(0.0, mid + side * sl * h)
            legs = []   # (cp, strike, qty)
            atm = ch.iloc[(ch.strike - S0).abs().argsort()[:1]].strike.iloc[0]
            if structure == "long_straddle": legs = [("C", atm, 1), ("P", atm, 1)]
            elif structure == "long_strangle":
                kc = ch[(ch.cp == "C") & (ch.strike >= S0 * 1.03)].strike.min(); kp = ch[(ch.cp == "P") & (ch.strike <= S0 * 0.97)].strike.max()
                legs = [("C", kc, 1), ("P", kp, 1)]
            elif structure == "short_condor":
                sc = ch[(ch.cp == "C") & (ch.delta.between(0.2, 0.3))]; sp = ch[(ch.cp == "P") & (ch.delta.between(-0.3, -0.2))]
                if sc.empty or sp.empty: continue
                kc, kp = sc.iloc[(sc.delta - 0.25).abs().argsort()[:1]].strike.iloc[0], sp.iloc[(sp.delta + 0.25).abs().argsort()[:1]].strike.iloc[0]
                wc = ch[(ch.cp == "C") & (ch.strike >= kc + wing * S0)].strike.min(); wp = ch[(ch.cp == "P") & (ch.strike <= kp - wing * S0)].strike.max()
                if np.isnan(wc) or np.isnan(wp): continue
                legs = [("C", kc, -1), ("P", kp, -1), ("C", wc, 1), ("P", wp, 1)]
            if any(np.isnan(l[1]) for l in legs): continue
            ent = [_leg(ge, exd, cp, k) for cp, k, _ in legs]; xit = [_leg(gx, exd, cp, k) for cp, k, _ in legs]
            if any(e is None for e in ent) or any(x is None for x in xit): continue
            if any((e.ask <= e.bid) or e.ask <= 0 or (qy < 0 and e.bid <= 0) for e, (_, _, qy) in zip(ent, legs)): continue
            if any(x.ask < x.bid for x in xit): continue
            # entry: buy ask / sell bid
            o = sum((-1 if qy > 0 else 1) * px(e, +1 if qy > 0 else -1, slip) for e, (_, _, qy) in zip(ent, legs))   # +credit / -debit per share
            c = sum((1 if qy > 0 else -1) * px(x, -1 if qy > 0 else +1, slip) for x, (_, _, qy) in zip(xit, legs))     # +proceeds / -cost at exit
            width = max(abs(legs[0][1] - legs[2][1]), abs(legs[1][1] - legs[3][1])) if structure == "short_condor" else None
            max_loss = (-o) if o < 0 else (width - o)
            if max_loss <= 0: continue
            ml = max_loss * 100 + 2 * fee * len(legs)
            n = int(risk_trade * equity0 // ml)
            pnl_ps = o + c
            implied = (-o / S0) if structure == "long_straddle" else np.nan
            out.append(dict(ticker=u, announce=r.d, entry=de, exit=dx, structure=structure, S0=S0, S1=S1, move=abs(S1 / S0 - 1),
                            implied_move=implied, open_px=o, close_px=c, pnl_ps=pnl_ps, max_loss_ps=max_loss,
                            ret_on_risk=(pnl_ps * 100 - 2 * fee * len(legs)) / ml, n=n, pnl=n * (pnl_ps * 100 - 2 * fee * len(legs)),
                            n_zero=(n < 1)))
    return pd.DataFrame(out)
