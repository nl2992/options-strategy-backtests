"""Small context inputs for the C++ engines (all dates as yyyymmdd ints).

ctx_sessions.csv  date, rf_daily, spx_close
ctx_equity.csv    date, ticker, open_raw, close_raw, div_ret, share_adj  (META fund rows dropped)
ctx_earnings.csv  ticker, announce, amc    (amc=1 if announced at/after 16:00)
h4_signals.csv    date, root, flow, ivspread, smirk   (day-t information; traded t+1 open)
h6_gex.csv        date, und, gex           (EOD gamma exposure, dealer long calls / short puts assumption)
f2_eod.csv        date, exp, k, bid, ask, spot      SPXW third-Friday puts (EOD)
"""
import pathlib, duckdb
W = pathlib.Path(__file__).resolve().parent
R = W.parent / "data/raw"
N = W.parent / "data/normalized"
EX = W / "extracts"
D = lambda col: f"strftime({col}, '%Y%m%d')::int"
SINGLES = ["AAPL", "TSLA", "AMD", "AMZN", "AVGO", "CRM", "GOOGL", "JPM", "LLY", "NFLX", "UNH", "MSFT", "NVDA", "WMT", "XOM"]

c = duckdb.connect()
c.execute(f"""copy (select {D('o.date')} date, f.risk_free_rate_1m rf_daily, o.sp500_cash_level spx_close
  from '{R}/context/market_overlays_2022_2024.parquet' o join '{R}/context/factor_returns_daily_2022_2024.parquet' f using (date)
  order by 1) to '{W}/extracts/ctx_sessions.csv' (header)""")
c.execute(f"""copy (select {D('date')} date, ticker, open_raw, close_raw, total_return - price_return_ex_div div_ret, share_adj_factor share_adj
  from '{R}/context/equity_daily_2022_2024.parquet' where ticker <> 'META' or security_id = 13407 order by 1, 2) to '{EX}/ctx_equity.csv' (header)""")
c.execute(f"""copy (select distinct ticker, {D('announce_date::date')} announce, (announce_time >= '16:00:00')::int amc
  from '{R}/context/earnings_actuals_2022_2024.parquet' where ticker in ({",".join(f"'{s}'" for s in SINGLES)})
  and announce_date between '2022-01-01' and '2024-12-31' order by 2, 1) to '{EX}/ctx_earnings.csv' (header)""")

# H4 day-t signals. EOD chain gives delta/IV/OI on the same session; all are known after the close of t.
eod = " union all ".join(f"select '{s}' root, * from '{N}/quotes_{s}.parquet'" for s in SINGLES)
c.execute(f"create table q as select root, {D('date')} date, {D('exdate')} exp, strike k, cp, iv, delta, oi, spot, dte from ({eod})")
c.execute(f"""create table flow as select f.root, f.date, sum(q.delta * (coalesce(buy,0) - coalesce(sell,0))) / nullif(sum(abs(q.delta) * (coalesce(buy,0) + coalesce(sell,0))), 0) flow
  from '{EX}/h4_flow_*.parquet' f join q on q.root = f.root and q.date = f.date and q.exp = f.exp and q.k = f.k and q.cp = f.cp
  where q.delta is not null group by all""")
c.execute("""create table ivs as select c.root, c.date, sum((c.iv - p.iv) * (c.oi + p.oi)) / nullif(sum(c.oi + p.oi), 0) ivspread
  from q c join q p on p.root = c.root and p.date = c.date and p.exp = c.exp and p.k = c.k and p.cp = 'P'
  where c.cp = 'C' and c.dte between 10 and 60 and c.iv > 0 and p.iv > 0 group by all""")
c.execute("""create table smk as with b as (select * from q where dte between 10 and 60 and iv > 0),
  p as (select root, date, arg_min(iv, abs(k/spot - .95)) piv from b where cp = 'P' and k/spot between .80 and .95 group by all),
  a as (select root, date, arg_min(iv, abs(k/spot - 1)) civ from b where cp = 'C' and k/spot between .95 and 1.05 group by all)
  select root, date, piv - civ smirk from p join a using (root, date)""")
c.execute(f"""copy (select * from flow full join ivs using (root, date) full join smk using (root, date) order by date, root)
  to '{EX}/h4_signals.csv' (header)""")

# H6 GEX per ETF from raw EOD chain (gamma per 1-pt move scaled to 1% move, $ notional)
chain = " union all ".join(f"select * from '{R}/eod_option_chain/eod_option_chain_{y}.parquet'" for y in (2022, 2023, 2024))
c.execute(f"""copy (select {D('ch.date')} date, m.ticker und,
    sum(case when cp_flag = 'C' then 1 else -1 end * nullif(gamma, 'NaN') * open_interest * 100 * e.close_raw * e.close_raw * 0.01) gex
  from ({chain}) ch join '{R}/eod_option_chain/_ticker_id_mapping.parquet' m using (option_security_id)
  join '{R}/context/equity_daily_2022_2024.parquet' e on e.ticker = m.ticker and e.date = ch.date
  where m.ticker in ('SPY', 'QQQ') and contract_size = 100 group by all order by 1, 2) to '{EX}/h6_gex.csv' (header)""")

c.execute(f"""copy (select {D('date')} date, {D('exdate')} exp, strike k, bid, ask, spot from '{N}/quotes_SPX.parquet'
  where root = 'SPXW' and cp = 'P' and dayofweek(exdate) = 5 and day(exdate) between 15 and 21 order by 1, 2, 3)
  to '{EX}/f2_eod.csv' (header)""")
for f in ["ctx_sessions", "ctx_equity", "ctx_earnings", "h4_signals", "h6_gex", "f2_eod"]:
    print(f, c.execute(f"select count(*) from '{EX}/{f}.csv'").fetchone()[0])
