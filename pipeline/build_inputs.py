"""Build the small daily inputs the C++ engines read (all dates as yyyymmdd ints) into data/extracts/.

ctx_sessions.csv    date, rf_daily, spx_close
ctx_equity.csv      date, ticker, open_raw, close_raw, div_ret, share_adj   (unrelated META fund rows dropped)
ctx_earnings.csv    ticker, announce, amc   (amc = 1 if announced at or after 16:00)
flow_measures.csv   date, root, num_all, den_all: delta-weighted signed option volume and total volume (option-flow strategy)
option_signals.csv  date, root, flow: day-t flow ratio for the earlier option-flow version

Needs data/raw/context/, data/normalized/ (pipeline/normalize.py) and data/extracts/option_flow_*.parquet (pipeline/extract.py).
"""
import pathlib, duckdb
ROOT = pathlib.Path(__file__).resolve().parents[1]
R = ROOT / "data/raw/context"
N = ROOT / "data/normalized"
EX = ROOT / "data/extracts"
D = lambda col: f"strftime({col}, '%Y%m%d')::int"
SINGLES = ["AAPL", "TSLA", "AMD", "AMZN", "AVGO", "CRM", "GOOGL", "JPM", "LLY", "NFLX", "UNH", "MSFT", "NVDA", "WMT", "XOM"]

c = duckdb.connect()
c.execute("set threads=1")  # fixed summation order, so reruns are byte-identical
c.execute(f"""copy (select {D('o.date')} date, f.risk_free_rate_1m rf_daily, o.sp500_cash_level spx_close
  from '{R}/market_overlays_2022_2024.parquet' o join '{R}/factor_returns_daily_2022_2024.parquet' f using (date)
  order by 1) to '{EX}/ctx_sessions.csv' (header)""")
c.execute(f"""copy (select {D('date')} date, ticker, open_raw, close_raw, total_return - price_return_ex_div div_ret, share_adj_factor share_adj
  from '{R}/equity_daily_2022_2024.parquet' where ticker <> 'META' or security_id = 13407 order by 1, 2) to '{EX}/ctx_equity.csv' (header)""")
c.execute(f"""copy (select distinct ticker, {D('announce_date::date')} announce, (announce_time >= '16:00:00')::int amc
  from '{R}/earnings_actuals_2022_2024.parquet' where ticker in ({",".join(f"'{s}'" for s in SINGLES)})
  and announce_date between '2022-01-01' and '2024-12-31' order by 2, 1) to '{EX}/ctx_earnings.csv' (header)""")

# end-of-day chain: delta, IV and OI are known after the close of day t
eod = " union all ".join(f"select '{s}' root, * from '{N}/quotes_{s}.parquet'" for s in SINGLES)
c.execute(f"create table q as select root, {D('date')} date, {D('exdate')} exp, strike k, cp, iv, delta, oi, spot, dte from ({eod})")
c.execute(f"create table f as select * from '{EX}/option_flow_*.parquet'")

c.execute(f"""copy (select f.root, f.date,
    sum(q.delta * (coalesce(buy,0) - coalesce(sell,0))) num_all, sum(abs(q.delta) * (coalesce(buy,0) + coalesce(sell,0))) den_all
  from f join q on q.root = f.root and q.date = f.date and q.exp = f.exp and q.k = f.k and q.cp = f.cp
  where q.delta is not null group by all order by 2, 1) to '{EX}/flow_measures.csv' (header)""")

c.execute("""create table flow as select f.root, f.date, sum(q.delta * (coalesce(buy,0) - coalesce(sell,0))) / nullif(sum(abs(q.delta) * (coalesce(buy,0) + coalesce(sell,0))), 0) flow
  from f join q on q.root = f.root and q.date = f.date and q.exp = f.exp and q.k = f.k and q.cp = f.cp
  where q.delta is not null group by all""")
c.execute(f"copy (select * from flow order by date, root) to '{EX}/option_signals.csv' (header)")

for name in ["ctx_sessions", "ctx_equity", "ctx_earnings", "flow_measures", "option_signals"]:
    print(name, c.execute(f"select count(*) from '{EX}/{name}.csv'").fetchone()[0])
