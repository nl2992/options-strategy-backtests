"""Reduce the raw tapes to the two inputs the strategies need.

usage: python pipeline/extract.py options <QUARTER>   -> data/extracts/option_flow_<QUARTER>.parquet
       python pipeline/extract.py auction <YYYY_MM>   -> data/extracts/auction_<YYYY_MM>.csv
Raw tapes are read from data/raw/tapes/ (download with pipeline/fetch_tapes.sh).
"""
import sys, pathlib, duckdb
ROOT = pathlib.Path(__file__).resolve().parents[1]
TAPES = ROOT / "data/raw/tapes"
EX = ROOT / "data/extracts"
SINGLES = ["AAPL", "TSLA", "AMD", "AMZN", "AVGO", "CRM", "GOOGL", "JPM", "LLY", "NFLX", "UNH", "MSFT", "NVDA", "WMT", "XOM"]
# primary listing exchange per symbol (Q = Nasdaq, N = NYSE, P = NYSE Arca)
PRIMARY = {**{s: "Q" for s in ["AAPL", "AMD", "AMZN", "AVGO", "MSFT", "NFLX", "NVDA", "TSLA"]},
           **{s: "N" for s in ["CRM", "JPM", "LLY", "UNH", "WMT", "XOM"]}, "SPY": "P"}  # WMT moved to Nasdaq on 2024-12-09; its later crosses are missed
MS = lambda h, m, s=0: (h * 3600 + m * 60 + s) * 1000


def options(q):
    """Per contract-day signed option volume, regular hours, trades signed against the quote midpoint."""
    f = TAPES / f"option_trades_with_nbbo_quarterly/{q}.parquet"
    c = duckdb.connect()
    c.execute(f"""create view t as select root, date, expiration exp, strike/1000.0 k, "right" cp, ms_of_day ms,
        price, size, bid, ask from '{f}' where bid > 0 and ask >= bid""")
    c.execute(f"""copy (select root, date, exp, k, cp, sum(size) filter (price > (bid+ask)/2) buy, sum(size) filter (price < (bid+ask)/2) sell,
        count(*) n from t where root in ({",".join(f"'{r}'" for r in SINGLES)}) and ms >= {MS(9, 30)} and ms < {MS(16, 0)}
        group by all) to '{EX}/option_flow_{q}.parquet'""")
    print("option flow", q)


def auction(ym):
    """Official opening and closing cross per symbol-day: the largest O/6 print on the primary exchange.
    sym_root mixes share classes (e.g. JPM preferreds near $25), so the largest print isolates the common-stock cross."""
    a = TAPES / f"auction_window_trades_monthly/{ym}.parquet"
    c = duckdb.connect()
    prim = ",".join(f"('{s}','{e}')" for s, e in PRIMARY.items())
    c.execute(f"""copy (with p as (select sym_root sym, strftime(date::date,'%Y%m%d')::int date, ex, price, size,
          case when tr_scond like '%O%' then 'open' else 'close' end side
        from '{a}' join (values {prim}) v(s, pe) on sym_root = s and ex = pe
        where tr_corr = '00' and (tr_scond like '%O%' or tr_scond like '%6%'))
      select sym, date, side, max_by(price, size) px, max(size) sz from p group by all
      order by date, sym, side) to '{EX}/auction_{ym}.csv' (header)""")
    print("auction", ym, c.execute(f"select count(*) from '{EX}/auction_{ym}.csv'").fetchone()[0])


if __name__ == "__main__":
    EX.mkdir(parents=True, exist_ok=True)
    {"options": options, "auction": auction}[sys.argv[1]](sys.argv[2])
