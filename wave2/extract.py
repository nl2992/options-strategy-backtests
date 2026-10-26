"""Reduce raw tapes to compact per-strategy extracts (CSV for the C++ engines, parquet for big intermediates).

usage: python -I wave2/extract.py options <QUARTER> | equity <YYYY_MM> | eod
All snapshot rules follow prereg/PREREGISTRATION.md:
  pre  (L=-1): last observed NBBO per contract in [tau-120s, tau)       -> information known at tau
  fill (L>=0): first observed NBBO per contract in [tau+L, tau+L+10s]   -> T2 fill quote (A=10s)
"""
import sys, pathlib, duckdb
W = pathlib.Path(__file__).resolve().parent
ROOT = W.parent
EX = W / "extracts"
EQD = ROOT / "data/raw/context/equity_daily_2022_2024.parquet"
OVL = ROOT / "data/raw/context/market_overlays_2022_2024.parquet"
LAT = [500, 2000, 10000]
CHASE = 120000  # A1 exit chase window (lat code 99999 = first quote in [tau+2s, tau+2s+120s])
SINGLES = ["AAPL", "TSLA", "AMD", "AMZN", "AVGO", "CRM", "GOOGL", "JPM", "LLY", "META", "NFLX", "UNH", "MSFT", "NVDA", "WMT", "XOM"]
PRIMARY = {**{s: "Q" for s in ["AAPL", "AMD", "AMZN", "AVGO", "MSFT", "NFLX", "NVDA", "QQQ", "TSLA", "META"]},
           **{s: "N" for s in ["CRM", "JPM", "LLY", "UNH", "WMT", "XOM"]}, "SPY": "P"}  # shortcut: WMT moved to Nasdaq 2024-12-09; holdout loses those WMT days
MS = lambda h, m, s=0: (h * 3600 + m * 60 + s) * 1000

# (name, roots, taus, dte_lo, dte_hi, |K/S-1| band)
SNAPS = [
    ("h1_spxw0dte", ["SPXW"], [MS(10, 0), MS(12, 0), MS(14, 0), MS(15, 0)], 0, 0, 0.05),
    ("h2_etf", ["SPY", "QQQ"], [MS(9, 33), MS(15, 58)], 5, 35, 0.06),
    ("h5_single", SINGLES, [MS(15, 55)], 1, 75, 0.12),
    ("f2_spxw", ["SPXW"], [MS(15, 55)], 20, 40, 0.10),  # put-write sensitivity at 15:55 instead of EOD
]


def con():
    c = duckdb.connect()
    c.execute("set threads=8; set memory_limit='10GB'")
    # prior-session close per root: used only as a wide strike filter, never as a signal
    c.execute(f"""create table ref as
      select ticker root, strftime(lead(date) over (partition by ticker order by date), '%Y%m%d')::int date, close_raw s
      from '{EQD}' where ticker <> 'META' or security_id = 13407
      union all
      select r, strftime(lead(date) over (order by date), '%Y%m%d')::int, sp500_cash_level
      from '{OVL}', (values ('SPXW'), ('SPX')) v(r) where sp500_cash_level is not null""")
    return c


def options(q):
    f = W / f"raw/option_trades_with_nbbo_quarterly/{q}.parquet"
    c = con()
    c.execute(f"""create view t as select root, date, expiration exp, strike/1000.0 k, "right" cp, ms_of_day ms,
        price, size, bid, ask, bid_size bsz, ask_size asz,
        date_diff('day', strptime(date::varchar,'%Y%m%d'), strptime(exp::varchar,'%Y%m%d')) dte
      from '{f}' where bid > 0 and ask >= bid""")
    cols = "root, date, exp, k, cp"
    for name, roots, taus, lo, hi, band in SNAPS:
        rl = ",".join(f"'{r}'" for r in roots)
        base = f"""select t.* from t join ref using (root, date) where t.root in ({rl}) and dte between {lo} and {hi}
                   and abs(k / ref.s - 1) <= {band}"""
        parts = []
        for tau in taus:
            parts.append(f"""select {tau} tau, -1 lat, {cols}, max_by(bid, ms) bid, max_by(ask, ms) ask, max_by(bsz, ms) bsz,
                max_by(asz, ms) asz, max(ms) ms from b where ms >= {tau - 120000} and ms < {tau} group by all""")
            for L in LAT:
                parts.append(f"""select {tau} tau, {L} lat, {cols}, min_by(bid, ms) bid, min_by(ask, ms) ask, min_by(bsz, ms) bsz,
                    min_by(asz, ms) asz, min(ms) ms from b where ms >= {tau + L} and ms <= {tau + L + 10000} group by all""")
            parts.append(f"""select {tau} tau, 99999 lat, {cols}, min_by(bid, ms) bid, min_by(ask, ms) ask, min_by(bsz, ms) bsz,
                min_by(asz, ms) asz, min(ms) ms from b where ms >= {tau + 2000} and ms <= {tau + 2000 + CHASE} group by all""")
        out = EX / f"{name}_{q}.csv"
        c.execute(f"copy (with b as ({base}) {' union all '.join(parts)} order by date, tau, lat, root, exp, cp, k) to '{out}' (header)")
        print(name, q, c.execute(f"select count(*) from '{out}'").fetchone()[0])

    # H4 flow: per contract-day signed size, regular hours, quote rule vs mid (delta joined later in `eod`)
    c.execute(f"""copy (select {cols}, sum(size) filter (price > (bid+ask)/2) buy, sum(size) filter (price < (bid+ask)/2) sell,
        count(*) n from t where root in ({",".join(f"'{r}'" for r in SINGLES)}) and ms >= {MS(9, 30)} and ms < {MS(16, 0)}
        group by all) to '{EX}/h4_flow_{q}.parquet'""")

    # F1 cost atlas: effective vs quoted spread by bucket (means are additive across quarters via n)
    c.execute(f"""copy (select t.root, '{q}' q,
        case when dte = 0 then '0' when dte <= 7 then '1-7' when dte <= 30 then '8-30' when dte <= 90 then '31-90' else '>90' end dte_b,
        case when abs(k/ref.s-1) < .01 then '<1%' when abs(k/ref.s-1) < .03 then '1-3%' when abs(k/ref.s-1) < .07 then '3-7%' else '>7%' end mny_b,
        (ms // 1800000) * 30 / 60.0 halfhour, count(*) n, sum(size) contracts,
        avg(abs(price - (bid+ask)/2) / nullif((ask-bid)/2, 0)) eff_ratio,
        avg((ask-bid) / ((ask+bid)/2)) rel_qspread, avg(2*abs(price-(bid+ask)/2) / ((ask+bid)/2)) rel_espread,
        avg(ask - bid) qspread, median(least(bsz, asz)) med_min_size,
        avg((price >= ask)::int) at_or_above_ask, avg((price <= bid)::int) at_or_below_bid
      from t join ref using (root, date) where ms >= {MS(9, 30)} and ms < {MS(16, 15)} group by all) to '{EX}/f1_atlas_{q}.csv' (header)""")

    # F1 EOD snapshot timing: last tape NBBO before 16:00 / 16:15 for SPY, SPXW, AAPL
    c.execute(f"""copy (select {cols}, max_by(bid, ms) filter (ms < {MS(16, 0)}) bid1600, max_by(ask, ms) filter (ms < {MS(16, 0)}) ask1600,
        max_by(bid, ms) filter (ms < {MS(16, 15)}) bid1615, max_by(ask, ms) filter (ms < {MS(16, 15)}) ask1615
        from t where root in ('SPY','SPXW','AAPL') and dte between 1 and 60 group by all) to '{EX}/f1_eodtiming_{q}.parquet'""")


def equity(ym):
    c = con()
    q = W / f"raw/intraday_nbbo_close_open_windows_monthly/{ym}.parquet"
    a = W / f"raw/auction_window_trades_monthly/{ym}.parquet"
    c.execute(f"""create view e as select sym_root sym, strftime(date::date, '%Y%m%d')::int date,
        ((substr(time_m,1,2)::int*3600 + substr(time_m,4,2)::int*60) * 1000 + (substr(time_m,7)::double * 1000))::bigint ms,
        best_bid bid, best_ask ask, best_bid_sz bsz, best_ask_sz asz from '{q}' where best_bid > 0 and best_ask > best_bid""")
    # sym_root mixes share classes (JPM preferreds ~$20 in the JPM stream): keep quotes within 20% of the prior close
    c.execute("create view e2 as select e.* from e join ref on ref.root = e.sym and ref.date = e.date where abs((bid+ask)/2 / ref.s - 1) < 0.2")
    parts = []
    for tau in [MS(9, 31), MS(9, 33), MS(15, 55), MS(15, 58), MS(15, 59)]:
        parts.append(f"select {tau} tau, -1 lat, sym, date, max_by(bid,ms) bid, max_by(ask,ms) ask, max_by(bsz,ms) bsz, max_by(asz,ms) asz, max(ms) ms from e2 where ms >= {tau-120000} and ms < {tau} group by all")
        for L in LAT:
            parts.append(f"select {tau} tau, {L} lat, sym, date, min_by(bid,ms) bid, min_by(ask,ms) ask, min_by(bsz,ms) bsz, min_by(asz,ms) asz, min(ms) ms from e2 where ms >= {tau+L} and ms <= {tau+L+10000} group by all")
    c.execute(f"copy ({' union all '.join(parts)} order by date, sym, tau, lat) to '{EX}/eq_snap_{ym}.csv' (header)")
    # official cross = largest single O/6 print on the primary listing exchange.
    # sym_root mixes share classes (e.g. JPM preferreds ~$25), so the largest print isolates the common cross.
    prim = ",".join(f"('{s}','{e}')" for s, e in PRIMARY.items())
    c.execute(f"""copy (with p as (select sym_root sym, strftime(date::date,'%Y%m%d')::int date, ex, price, size,
          case when tr_scond like '%O%' then 'open' else 'close' end side
        from '{a}' join (values {prim}) v(s, pe) on sym_root = s and ex = pe
        where tr_corr = '00' and (tr_scond like '%O%' or tr_scond like '%6%'))
      select sym, date, side, max_by(price, size) px, max(size) sz from p group by all
      order by date, sym, side) to '{EX}/auction_{ym}.csv' (header)""")
    print(ym, c.execute(f"select count(*) from '{EX}/eq_snap_{ym}.csv'").fetchone(), c.execute(f"select count(*) from '{EX}/auction_{ym}.csv'").fetchone())


if __name__ == "__main__":
    EX.mkdir(exist_ok=True)
    {"options": options, "equity": equity}[sys.argv[1]](sys.argv[2])
