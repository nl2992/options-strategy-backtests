import pandas as pd, numpy as np, duckdb, pathlib
from .features import build_features
ROOT = pathlib.Path(__file__).resolve().parents[2]

def load_market(universe=("SPY", "QQQ", "SPX")):
    from .engine import Market
    c = duckdb.connect()
    eq = c.sql(f"select ticker,date::date as date,close_raw,adj_close,total_return from '{ROOT}/data/raw/context/equity_daily_2022_2024.parquet'").df()
    ov = c.sql(f"select date::date as date, sp500_cash_level, treasury_1mo from '{ROOT}/data/raw/context/market_overlays_2022_2024.parquet' where sp500_cash_level is not null").df().set_index("date")
    quotes, feats = {}, {}
    for u in universe:
        q = pd.read_parquet(f"{ROOT}/data/normalized/quotes_{u}.parquet")
        spot = ov.sp500_cash_level if u == "SPX" else eq[eq.ticker == u].set_index("date").close_raw
        signal_spot = None if u == "SPX" else eq[eq.ticker == u].set_index("date").adj_close
        spot = spot.sort_index(); spot.index = pd.to_datetime(spot.index)
        if signal_spot is not None:
            signal_spot = signal_spot.sort_index(); signal_spot.index = pd.to_datetime(signal_spot.index)
        q = q.copy(); q["date"] = pd.to_datetime(q["date"]); q["exdate"] = pd.to_datetime(q["exdate"])
        f = build_features(q, spot, signal_spot)
        f.index = [x.date() for x in f.index]
        q["date"] = q["date"].dt.date; q["exdate"] = q["exdate"].dt.date
        quotes[u] = q; feats[u] = f
    dates = sorted(set.intersection(*[set(f.index) for f in feats.values()]))
    ov.index = [pd.Timestamp(x).date() for x in ov.index]
    rf = (ov.treasury_1mo / 100.0).reindex(dates).ffill().bfill()
    return Market(quotes, feats, rf, dates), eq
