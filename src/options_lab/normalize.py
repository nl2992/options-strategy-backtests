"""Normalize raw EOD option chains (OptionMetrics-style) to a compact research panel.

Output: data/normalized/quotes_<UND>.parquet, one row per (date, contract) with bid/ask,
IV, delta, OI, volume, DTE and the underlying close on the same session.
SPX = SPX (AM monthly) + SPXW (PM weekly) rows, distinguished by `root`.
Filters (documented, counted in normalize_report.csv): contract_size==100, cfadj==1,
DTE in [1,75], 0.75<=K/S<=1.25, ask>0, ask>=bid (locked/crossed dropped). Zero bids KEPT
(needed for conservative marking) but flagged by bid==0.
"""
import duckdb, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
OUT = ROOT / "data/normalized"
UNDERLYINGS = {"SPY": 109820, "QQQ": 107899, "SPX": 108105}
SINGLE_NAMES = {"AAPL": 101594, "TSLA": 143439, "AMD": 101121, "AMZN": 101310, "AVGO": 139322, "CRM": 121592, "GOOGL": 121812,
                "JPM": 102936, "LLY": 106967, "META": 154402, "NFLX": 115422, "UNH": 111469, "MSFT": 107525, "NVDA": 108321,
                "WMT": 111860, "XOM": 104533}

def run(universe=None):
    OUT.mkdir(exist_ok=True)
    c = duckdb.connect()
    eq = f"{RAW}/context/equity_daily_2022_2024.parquet"
    ov = f"{RAW}/context/market_overlays_2022_2024.parquet"
    rep = []
    for u, sid in (universe or UNDERLYINGS).items():
        spot = (f"select date, close_raw as spot from '{eq}' where ticker='{u}'" if u != "SPX"
                else f"select date, sp500_cash_level as spot from '{ov}' where sp500_cash_level is not null")
        chain = " union all ".join(f"select * from '{RAW}/eod_option_chain/eod_option_chain_{y}.parquet' where option_security_id={sid}" for y in (2022, 2023, 2024))
        q = f"""
        copy (
          with s as ({spot}), ch as ({chain})
          select ch.date::date as date, ch.exdate::date as exdate, ch.cp_flag as cp,
                 ch.strike_price/1000.0 as strike, ch.best_bid as bid, ch.best_offer as ask,
                 ch.volume, ch.open_interest as oi, nullif(ch.impl_volatility,'NaN') as iv,
                 nullif(ch.delta,'NaN') as delta, ch.am_settlement as am,
                 case when ch.symbol like 'SPXW%' then 'SPXW' else '{u}' end as root,
                 s.spot, date_diff('day', ch.date::date, ch.exdate::date) as dte
          from ch join s on s.date = ch.date
          where ch.contract_size=100 and ch.cfadj=1 and ch.best_offer>0 and ch.best_offer>=ch.best_bid
            and ch.best_bid>=0 and date_diff('day', ch.date::date, ch.exdate::date) between 1 and 75
            and ch.strike_price/1000.0 between 0.75*s.spot and 1.25*s.spot
        ) to '{OUT}/quotes_{u}.parquet' (format parquet, compression zstd)"""
        c.execute(q)
        n = c.sql(f"select count(*), count(distinct date), min(date), max(date) from '{OUT}/quotes_{u}.parquet'").fetchone()
        rep.append((u, *n)); print(u, n, flush=True)
    return rep

if __name__ == "__main__":
    run(SINGLE_NAMES if "--single" in sys.argv else None)
