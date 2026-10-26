"""Execution-aware EOD event-driven backtester for defined-risk option structures.

Timing contract (information_cutoff):
  * decisions on session t use ONLY snapshot/feature data of session t-1 (or earlier);
  * orders fill at session t's end-of-day quotes, same snapshot for all legs, buying at
    ask / selling at bid (times a `slip` multiplier on the half-spread);
  * stop/target thresholds observed at close t are executed at close t+1 (never intraday);
  * positions are force-closed `exit_dte` calendar days before expiry (no assignment model).
"""
from __future__ import annotations
import math, zlib
from dataclasses import dataclass, field, replace
import numpy as np, pandas as pd

MULT = 100

@dataclass(frozen=True)
class Cfg:
    strategy: str = "pcs"            # pcs | ccs | ic | dv | pdv (put debit vertical)
    delta: float = 0.20              # short-leg |delta| (dv: long-leg delta)
    dte_target: int = 30             # 30 -> [21,35]; 45 -> [35,60]
    filt: str = "none"               # none | f1 | f2
    signal: str = "legacy"           # none | ivp | vrp20 | vrp60 | trend20 | trend60 | vrp20_trend60 | skew25
    ivp_min: float = 60.0
    vrp_min: float = 0.0             # annualized IV minus realized-volatility forecast
    trend_threshold: float = 0.0     # absolute underlying return over the selected lookback
    skew_threshold: float = 0.02     # 25-delta put IV minus call IV
    entry_every: int = 5
    exit_dte: int = 5
    tp: float = 0.5                  # credit: capture 50% ; debit: +50% of debit
    stop_mult: float = 2.0           # credit: loss = 2x credit ; debit: -50% of debit
    equity0: float = 200_000.0
    risk_trade: float = 0.005
    risk_agg: float = 0.05
    risk_und: float = 0.02
    reserve: float = 0.25
    widths: tuple = (("SPY", 5.0), ("QQQ", 5.0), ("SPX", 10.0))
    fee: float = 0.65                # per contract per side (placeholder, not broker schedule)
    fee_mult: float = 1.0
    slip: float = 1.0                # 1 = cross full spread; 0.5 = optimistic; >1 adverse
    entry_delay: int = 0             # extra sessions between signal and fill
    min_credit_frac: float = 0.10
    max_rel_spread_short: float = 0.30
    max_rel_spread_long: float = 0.60
    min_oi: int = 10
    start_idx: int = 63
    end_idx: int | None = None       # truncate simulation (for isolation tests)
    force_exit_at_end: bool = False  # close fold positions at the final eligible snapshot
    shuffle_seed: int | None = None  # placebo: permute filter flag within month buckets
    universe: tuple = ("SPY", "QQQ", "SPX")

    def width(self, u): return dict(self.widths).get(u, 5.0)
    def band(self): return {30: (21, 35), 45: (35, 60), 15: (8, 14)}[self.dte_target]

def dte_days(a, b): return (b - a).days

class Day:
    """Per-session quote lookup for one underlying."""
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.idx = {k: i for i, k in enumerate(zip(df.root.values, df.exdate.values, df.cp.values, df.strike.values))}
        self.bid = df.bid.values; self.ask = df.ask.values
        self.delta = df.delta.values; self.oi = df.oi.values
    def q(self, key):
        i = self.idx.get(key)
        return None if i is None else (self.bid[i], self.ask[i], self.delta[i], self.oi[i])

class Market:
    def __init__(self, quotes: dict[str, pd.DataFrame], feats: dict[str, pd.DataFrame], rf: pd.Series, dates):
        self.dates = list(dates)
        self.feats = feats; self.rf = rf
        self.groups = {}
        for u, df in quotes.items():
            df = df.sort_values(["date", "root", "exdate", "cp", "strike"]).reset_index(drop=True)
            self.groups[u] = {d: g.reset_index(drop=True) for d, g in df.groupby("date")}
        self._day = {}
        self._sel = {}
    def day(self, u, d):
        k = (u, d)
        if k not in self._day:
            g = self.groups[u].get(d)
            self._day[k] = Day(g) if g is not None else None
            if len(self._day) > 40: self._day.pop(next(iter(self._day)))
        return self._day[k]

# ---------- selection (snapshot of signal session only) ----------
def _pick_expiry(g, d, lo, hi, target):
    e = g[["exdate"]].drop_duplicates()
    e = e.assign(dte=[dte_days(d, x) for x in e.exdate])
    e = e[(e.dte >= lo) & (e.dte <= hi)]
    if e.empty: return None
    return e.iloc[np.argsort((e.dte - target).abs().values)[:1]].exdate.iloc[0]

def _short_leg(g, exd, cp, tgt_delta, cfg: Cfg):
    s = g[(g.exdate == exd) & (g.cp == cp) & g.delta.notna() & (g.bid > 0) & (g.oi >= cfg.min_oi)]
    s = s[(s.ask > s.bid) & ((s.ask - s.bid) / ((s.ask + s.bid) / 2) <= cfg.max_rel_spread_short)]
    if s.empty: return None
    j = (s.delta.abs() - tgt_delta).abs().idxmin()
    if abs(abs(s.delta[j]) - tgt_delta) > 0.07: return None
    return s.loc[j]

def _wing(g, root, exd, cp, strike, cfg: Cfg, W=None):
    """Nearest listed strike to the target wing strike with width in [0.5W, 2W]; liquid enough."""
    w = g[(g.root == root) & (g.exdate == exd) & (g.cp == cp) & (g.ask > 0) & (g.oi >= cfg.min_oi)]
    w = w[(w.ask >= w.bid) & ((w.ask - w.bid) / ((w.ask + w.bid) / 2) <= cfg.max_rel_spread_long)]
    if w.empty: return None
    j = (w.strike - strike).abs().idxmin(); r = w.loc[j]
    return r

def select(mkt: Market, u, d, cfg: Cfg):
    """Return list of leg tuples [(root, exdate, cp, strike, qty)] or None. Reads snapshot d only."""
    key = (u, d, cfg.strategy, cfg.delta, cfg.dte_target, cfg.width(u), cfg.min_oi, cfg.max_rel_spread_short, cfg.max_rel_spread_long)
    if key in mkt._sel: return mkt._sel[key]
    g = mkt.groups[u].get(d); out = None
    if g is not None:
        lo, hi = cfg.band(); exd = _pick_expiry(g, d, lo, hi, cfg.dte_target); W = cfg.width(u)
        if exd is not None:
            def spread(cp, short_delta):
                s = _short_leg(g, exd, cp, short_delta, cfg)
                if s is None: return None
                k2 = s.strike - W if cp == "P" else s.strike + W
                w = _wing(g, s.root, exd, cp, k2, cfg)
                if w is None or not (0.5 * W <= abs(w.strike - s.strike) <= 2 * W): return None
                return [(s.root, exd, cp, float(s.strike), -1), (s.root, exd, cp, float(w.strike), +1)]
            if cfg.strategy == "pcs": out = spread("P", cfg.delta)
            elif cfg.strategy == "ccs": out = spread("C", cfg.delta)
            elif cfg.strategy == "ic":
                a, b = spread("P", cfg.delta), spread("C", cfg.delta)
                out = a + b if a and b else None
            elif cfg.strategy == "dv":
                c = g[(g.exdate == exd) & (g.cp == "C") & g.delta.notna() & (g.ask > 0) & (g.oi >= cfg.min_oi)]
                c = c[(c.ask >= c.bid) & ((c.ask - c.bid) / ((c.ask + c.bid) / 2) <= cfg.max_rel_spread_long)]
                if not c.empty:
                    j = (c.delta - cfg.delta).abs().idxmin(); L = c.loc[j]
                    sh = _wing(g, L.root, exd, "C", L.strike + W, cfg)
                    if sh is not None and sh.bid > 0 and 0.5 * W <= sh.strike - L.strike <= 2 * W:
                        out = [(L.root, exd, "C", float(L.strike), +1), (L.root, exd, "C", float(sh.strike), -1)]
            elif cfg.strategy == "pdv":
                p = g[(g.exdate == exd) & (g.cp == "P") & g.delta.notna() & (g.ask > 0) & (g.oi >= cfg.min_oi)]
                p = p[(p.ask >= p.bid) & ((p.ask - p.bid) / ((p.ask + p.bid) / 2) <= cfg.max_rel_spread_long)]
                if not p.empty:
                    j = (p.delta.abs() - cfg.delta).abs().idxmin(); L = p.loc[j]
                    sh = _wing(g, L.root, exd, "P", L.strike - W, cfg)
                    if sh is not None and sh.bid > 0 and 0.5 * W <= L.strike - sh.strike <= 2 * W:
                        out = [(L.root, exd, "P", float(L.strike), +1), (L.root, exd, "P", float(sh.strike), -1)]
    mkt._sel[key] = out
    return out

# ---------- pricing ----------
def fill_px(bid, ask, side, slip):
    """side +1 buy / -1 sell. slip=1 -> ask/bid. Floors at 0."""
    mid, h = (bid + ask) / 2, (ask - bid) / 2
    return max(0.0, mid + side * slip * h)

def intrinsic_cost(legs, spot):
    """Cost-to-close per share at expiry (liquidation intrinsic): short intrinsic - long intrinsic."""
    c = 0.0
    for _, _, cp, k, q in legs:
        iv = max(0.0, spot - k) if cp == "C" else max(0.0, k - spot)
        c += -q * iv
    return c

@dataclass
class Pos:
    id: int; und: str; legs: list; n: int; entry_date: object; signal_date: object
    open_px: float                 # +credit received / -debit paid, per share
    kind: str; width: float; max_loss_pc: float; entry_fees: float
    entry_spread_cost: float
    exp: object = None
    pending: str | None = None
    last_cost: float | None = None  # last valid cost-to-close per share
    stale: int = 0
    mark_hist: list = field(default_factory=list)
    realized: float = 0.0

def run(mkt: Market, cfg: Cfg):
    dates = mkt.dates
    end = cfg.end_idx if cfg.end_idx is not None else len(dates) - 1
    cash = cfg.equity0; positions: list[Pos] = []; blotter = []; rejects = {}
    daily = []; nid = 0
    spot_of = {u: mkt.feats[u].spot for u in cfg.universe}
    flag = {}
    for u in cfg.universe:
        f = mkt.feats[u]
        # All these fields describe the close of the feature date. Entries read
        # only the previous session's flag below, preserving the information cutoff.
        trend_col = "ret20" if cfg.signal == "trend20" else "ret60"
        trend = f[trend_col]
        if cfg.strategy in ("pcs", "dv"):
            directional = trend > cfg.trend_threshold
        elif cfg.strategy in ("ccs", "pdv"):
            directional = trend < -cfg.trend_threshold
        else:
            directional = trend.abs() <= cfg.trend_threshold

        if cfg.signal == "legacy":
            if cfg.filt == "none": s = pd.Series(True, index=f.index)
            elif cfg.filt == "f1": s = f.ivp >= cfg.ivp_min
            else:
                old_trend = {"pcs": f.ret60 > 0, "ccs": f.ret60 < 0, "ic": f.ret20.abs() < 0.03,
                             "dv": f.ret60 > 0, "pdv": f.ret60 < 0}[cfg.strategy]
                s = (f.ivp >= cfg.ivp_min) & old_trend
        elif cfg.signal == "none":
            s = pd.Series(True, index=f.index)
        elif cfg.signal == "ivp":
            s = f.ivp >= cfg.ivp_min
        elif cfg.signal in ("vrp20", "vrp60"):
            vrp = f[cfg.signal]
            s = vrp >= cfg.vrp_min if cfg.strategy in ("pcs", "ccs", "ic") else vrp <= -cfg.vrp_min
        elif cfg.signal in ("trend20", "trend60"):
            s = directional
        elif cfg.signal == "vrp20_trend60":
            vrp = f.vrp20
            vol_ok = vrp >= cfg.vrp_min if cfg.strategy in ("pcs", "ccs", "ic") else vrp <= -cfg.vrp_min
            s = vol_ok & directional
        elif cfg.signal == "skew25":
            if cfg.strategy in ("pcs", "dv"):
                s = f.skew25 >= cfg.skew_threshold
            elif cfg.strategy in ("ccs", "pdv"):
                s = f.skew25 <= -cfg.skew_threshold
            else:
                s = f.skew25.abs() <= cfg.skew_threshold
        else:
            raise ValueError(f"Unsupported signal: {cfg.signal}")
        s = s.fillna(False)
        if cfg.shuffle_seed is not None and cfg.filt != "none":
            rng = np.random.default_rng(cfg.shuffle_seed + zlib.crc32(u.encode()) % 1000)
            v = s.to_numpy().copy(); months = pd.Series(pd.DatetimeIndex(s.index).to_period("M"))
            for m in months.unique():
                ix = np.where(months.values == m)[0]; v[ix] = rng.permutation(v[ix])
            s = pd.Series(v, index=s.index)
        flag[u] = s
    def rej(r): rejects[r] = rejects.get(r, 0) + 1
    pending_entries = []   # (fill_idx, und, legs, signal_date)

    def mark_pos(p: Pos, d, spot):
        day = mkt.day(p.und, d); cost = None
        if day is not None:
            c = 0.0; ok = True
            for r, e, cp, k, q in p.legs:
                qq = day.q((r, e, cp, k))
                if qq is None: ok = False; break
                b, a = qq[0], qq[1]
                c += a if q < 0 else -b           # short: buy back at ask; long: sell at bid
            if ok: cost = c
        if cost is None:
            cost = p.last_cost if p.last_cost is not None else -p.open_px; p.stale += 1
        # theoretical bounds on cost-to-close per share (conservative clip)
        if p.kind in ("cs", "ic"): cost = min(max(cost, intrinsic_cost(p.legs, spot)), p.width)
        else: cost = min(max(cost, -p.width), 0.0)
        p.last_cost = cost
        return cost

    def delta_of(p, d):
        day = mkt.day(p.und, d)
        if day is None: return 0.0
        t = 0.0
        for r, e, cp, k, q in p.legs:
            qq = day.q((r, e, cp, k))
            if qq is not None and qq[2] == qq[2]: t += q * qq[2] * MULT * p.n
        return t

    for i in range(1, end + 1):
        d = dates[i]; dprev = dates[i - 1]
        # rf accrual on cash (prev-day 1m T-bill, ACT/360)
        r_f = mkt.rf.get(dprev, 0.0)
        cash *= 1 + r_f * (d - dprev).days / 360.0
        # ---- exits ----
        for p in list(positions):
            spot = spot_of[p.und].get(d, np.nan)
            reason = p.pending
            if reason is None and dte_days(d, p.exp) <= cfg.exit_dte: reason = "time"
            if reason is None and p.und in ("SPY", "QQQ"):
                # short leg ITM at prior close -> early-assignment risk control
                sp = spot_of[p.und].get(dprev, np.nan)
                for r, e, cp, k, q in p.legs:
                    if q < 0 and ((cp == "C" and sp > k) or (cp == "P" and sp < k)): reason = "itm_short"
            if reason is None and p.exp <= d: reason = "expiry"
            if reason is None and cfg.force_exit_at_end and i == end: reason = "fold_end"
            if reason is None: continue
            day = mkt.day(p.und, d)
            if p.exp <= d:   # unmanaged expiry: intrinsic settlement
                cost = intrinsic_cost(p.legs, spot); fees = 0.0; sc = 0.0; reason = "expiry_intrinsic"
            else:
                px = []; ok = day is not None
                if ok:
                    c = 0.0; sc = 0.0
                    for r, e, cp, k, q in p.legs:
                        qq = day.q((r, e, cp, k))
                        if qq is None: ok = False; break
                        b, a = qq[0], qq[1]
                        c += fill_px(b, a, +1, cfg.slip) if q < 0 else -fill_px(b, a, -1, cfg.slip)
                        sc += abs(fill_px(b, a, +1 if q < 0 else -1, cfg.slip) - (a + b) / 2)
                if not ok: rej("exit_missing_leg_retry"); p.pending = reason; continue
                cost = c; fees = cfg.fee * cfg.fee_mult * len(p.legs) * p.n
            pnl_cash = (-cost) * MULT * p.n - (fees if p.exp > d else 0.0)
            cash += pnl_cash
            total = (p.open_px - cost) * MULT * p.n - p.entry_fees - (fees if p.exp > d else 0.0)
            blotter.append(dict(id=p.id, und=p.und, strategy=cfg.strategy, signal_date=p.signal_date, entry_date=p.entry_date,
                                exit_date=d, expiry=p.exp, n=p.n, open_px=p.open_px, close_cost=cost, width=p.width,
                                max_loss=p.max_loss_pc * p.n, fees=p.entry_fees + (fees if p.exp > d else 0.0),
                                spread_cost=p.entry_spread_cost + sc * MULT * p.n, pnl=total, reason=reason,
                                stale_marks=p.stale, hold_days=(d - p.entry_date).days))
            positions.remove(p)
        # ---- entries (signal from i-1-delay snapshot) ----
        if i < end and i >= cfg.start_idx and (i - cfg.start_idx) % cfg.entry_every == 0 and i - cfg.entry_delay >= 1:
            sig_i = i - 1 - cfg.entry_delay; sig_d = dates[sig_i]
            eq = cash + sum(-(p.last_cost if p.last_cost is not None else -p.open_px) * MULT * p.n for p in positions)
            order = list(cfg.universe); k = (i // cfg.entry_every) % len(order); order = order[k:] + order[:k]
            for u in order:
                if not flag[u].get(sig_d, False): rej("filter_off"); continue
                legs = select(mkt, u, sig_d, cfg)
                if legs is None: rej("no_candidate"); continue
                day = mkt.day(u, d)
                if day is None: rej("no_snapshot_t"); continue
                qs = [day.q((r, e, cp, kk)) for r, e, cp, kk, q in legs]
                if any(x is None for x in qs): rej("missing_leg_t"); continue
                if any(x[1] <= x[0] and x[1] > 0 and x[0] > 0 or x[1] < x[0] or x[1] <= 0 for x in qs): rej("bad_quote_t"); continue
                if any(q < 0 and x[0] <= 0 for (r, e, cp, kk, q), x in zip(legs, qs)): rej("zero_bid_short_t"); continue
                px = 0.0; sc = 0.0
                for (r, e, cp, kk, q), (b, a, _, _) in zip(legs, qs):
                    f = fill_px(b, a, +1 if q > 0 else -1, cfg.slip)
                    px += -f if q > 0 else f
                    sc += abs(f - (a + b) / 2)
                W = max(abs(legs[j][3] - legs[j + 1][3]) for j in range(0, len(legs), 2)); kind = "dv" if cfg.strategy in ("dv", "pdv") else ("ic" if cfg.strategy == "ic" else "cs")
                if kind == "dv":
                    debit = -px
                    if debit <= 0 or debit >= W: rej("bad_debit"); continue
                    max_loss = debit * MULT
                else:
                    if px < cfg.min_credit_frac * W * (2 if kind == "ic" else 1) : rej("credit_too_small"); continue
                    max_loss = (W - px) * MULT if kind == "cs" else (W - px) * MULT  # ic: one side only; credit total offsets
                fee_pc = cfg.fee * cfg.fee_mult * len(legs)
                max_loss += fee_pc * 2
                # limits
                by_und = sum(p.max_loss_pc * p.n for p in positions if p.und == u)
                agg = sum(p.max_loss_pc * p.n for p in positions)
                cap = min(cfg.risk_trade * eq, cfg.risk_und * eq - by_und, cfg.risk_agg * eq - agg)
                n = int(math.floor(cap / max_loss)) if cap > 0 else 0
                if n < 1: rej("risk_cap_or_size_lt_1"); continue
                # cash / reserve (all-cash defined risk)
                coll = sum(p.width * MULT * p.n for p in positions if p.kind != "dv")
                need = (W * MULT * n if kind != "dv" else debit * MULT * n)
                free = cash - coll - (need if kind == "dv" else 0.0)
                if kind != "dv" and cash - coll - W * MULT * n + px * MULT * n < cfg.reserve * eq: rej("reserve_breach"); continue
                if kind == "dv" and free < cfg.reserve * eq: rej("reserve_breach"); continue
                fees = fee_pc * n
                cash += px * MULT * n - fees
                nid += 1
                p = Pos(nid, u, legs, n, d, sig_d, px, kind, W, max_loss, fees, sc * MULT * n, exp=legs[0][1])
                p.last_cost = -px
                positions.append(p)
        # ---- mark + thresholds ----
        gross = 0.0; risk = 0.0; nd = 0.0; liq = 0.0
        for p in positions:
            spot = spot_of[p.und].get(d, np.nan)
            cost = mark_pos(p, d, spot)
            liq += -cost * MULT * p.n
            gross += p.width * MULT * p.n; risk += p.max_loss_pc * p.n
            nd += delta_of(p, d)
            pnl_ps = p.open_px - cost
            if p.kind == "dv":
                debit = -p.open_px
                if -cost >= debit * (1 + cfg.tp): p.pending = "take_profit"
                elif -cost <= debit * (1 - cfg.tp): p.pending = "stop"
            else:
                credit = p.open_px
                if pnl_ps >= cfg.tp * credit: p.pending = "take_profit"
                elif pnl_ps <= -cfg.stop_mult * credit: p.pending = "stop"
        equity = cash + liq
        daily.append(dict(date=d, cash=cash, liq_value=liq, equity=equity, gross_exposure=gross,
                          risk_at_entry=risk, open_pos=len(positions), net_delta_shares=nd))
    daily = pd.DataFrame(daily).set_index("date")
    # final open positions are left unliquidated on the last day (reported, not force-closed)
    return daily, pd.DataFrame(blotter), rejects, positions
