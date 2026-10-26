"""Wave-3 inputs (written next to the wave-2 extracts so the shared C++ loaders find them).

w3_spxw_eod.csv    SPXW Friday expiries, DTE 1-40, |K/S-1|<=8%: date,exp,k,cp,bid,ask,iv,delta,spot   (S5 entry + daily marks)
w3_spxw_oi.csv     SPXW OI on the last record before expiry, DTE 1-4: rec_date,exp,k,cp,oi            (S7 pin strike)
w3_single_eod.csv  15 single names, 3rd-Friday monthlies, DTE 1-45, |K/S-1|<=10%: root,date,exp,k,cp,bid,ask,iv,spot (S6)
w3_flow.csv        per (date,root): numerators/denominators of three delta-weighted flow measures (S3, S4)
w3_vix.csv         date, vix_1m, vix_3m (S5)
"""
import pathlib, duckdb
W = pathlib.Path(__file__).resolve().parents[1]
N, EX, R = W / "data/normalized", W / "wave2/extracts", W / "data/raw/context"
D = lambda col: f"strftime({col}, '%Y%m%d')::int"
SINGLES = ["AAPL", "TSLA", "AMD", "AMZN", "AVGO", "CRM", "GOOGL", "JPM", "LLY", "NFLX", "UNH", "MSFT", "NVDA", "WMT", "XOM"]
c = duckdb.connect()
c.execute(f"""copy (select {D('date')} date, {D('exdate')} exp, strike k, cp, bid, ask, iv, delta, spot from '{N}/quotes_SPX.parquet'
  where root = 'SPXW' and dayofweek(exdate) = 5 and dte <= 40 and abs(strike/spot - 1) <= .08 order by 1, 2, 4, 3) to '{EX}/w3_spxw_eod.csv' (header)""")
c.execute(f"""copy (select {D('date')} rec_date, {D('exdate')} exp, strike k, cp, oi from '{N}/quotes_SPX.parquet'
  where root = 'SPXW' and dte <= 4 and abs(strike/spot - 1) <= .05 order by 2, 1, 3) to '{EX}/w3_spxw_oi.csv' (header)""")
eod = " union all ".join(f"select '{s}' root, * from '{N}/quotes_{s}.parquet'" for s in SINGLES)
c.execute(f"""copy (select root, {D('date')} date, {D('exdate')} exp, strike k, cp, bid, ask, iv, spot from ({eod})
  where dayofweek(exdate) = 5 and day(exdate) between 15 and 21 and dte <= 45 and abs(strike/spot - 1) <= .10 order by 2, 1, 3, 5, 4)
  to '{EX}/w3_single_eod.csv' (header)""")
# flow measures. OI convention (assumption, labelled in prereg): the EOD record on the next session carries OI as of
# this session's close, published by OCC before the next open -> d_oi is known before the t+1 opening auction.
c.execute(f"create table q as select root, {D('date')} date, {D('exdate')} exp, strike k, cp, delta, oi, dte from ({eod})")
c.execute("create table qn as select *, lead(oi) over (partition by root, exp, k, cp order by date) - oi d_oi from q")
c.execute(f"""copy (select f.root, f.date,
    sum(q.delta * (coalesce(buy,0) - coalesce(sell,0))) num_all, sum(abs(q.delta) * (coalesce(buy,0) + coalesce(sell,0))) den_all,
    sum(q.delta * (coalesce(buy,0) - coalesce(sell,0))) filter (where q.d_oi > 0) num_open,
    sum(abs(q.delta) * (coalesce(buy,0) + coalesce(sell,0))) filter (where q.d_oi > 0) den_open,
    sum(q.delta * (coalesce(buy,0) - coalesce(sell,0))) filter (where q.dte <= 30 and abs(q.delta) < .4) num_so,
    sum(abs(q.delta) * (coalesce(buy,0) + coalesce(sell,0))) filter (where q.dte <= 30 and abs(q.delta) < .4) den_so
  from '{EX}/h4_flow_*.parquet' f join qn q on q.root = f.root and q.date = f.date and q.exp = f.exp and q.k = f.k and q.cp = f.cp
  where q.delta is not null group by all order by 2, 1) to '{EX}/w3_flow.csv' (header)""")
c.execute(f"copy (select {D('date')} date, vix_1m, vix_3m from '{R}/market_overlays_2022_2024.parquet' order by 1) to '{EX}/w3_vix.csv' (header)")
for f in ["w3_spxw_eod", "w3_spxw_oi", "w3_single_eod", "w3_flow", "w3_vix"]:
    print(f, c.execute(f"select count(*) from '{EX}/{f}.csv'").fetchone()[0])
