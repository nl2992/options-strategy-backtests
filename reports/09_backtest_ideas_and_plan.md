# Next-wave backtest plan: implementable, fillable, pre-registered

Prepared 2026-10-25. Builds on `06_final_research_report.md` (EOD verticals/condors: all REJECT), `07_earnings_study.md` (EOD earnings: no edge), `08_rolling_research_protocol.md` (running), and the data audit in `dataset_audit/ASSESSMENT.md`.

## 1. What we have, and what changed today

| Asset | Local? | Size | What it uniquely enables |
|---|---|---|---|
| EOD option chain 2022–24 (57.6M rows) | yes | 2.4 GB | Daily selection/marks; already used |
| Context panels (equity daily, factors, fundamentals, earnings, overlays, DSPX) | yes | ~20 MB | Signals, hedges, benchmarks |
| **Option trades + attached NBBO (bid/ask *and sizes*)**, 1.81B rows | **no** | 22.5 GB (12 quarterly files, ~1.8 GB each) | Intraday fills against observed quotes with displayed size; signed order flow; effective-spread measurement |
| **Option trades + Greeks + `underlying_price`**, 2.26B rows | **no** | 57.5 GB (~4.8 GB/quarter) | Intraday underlying path (incl. SPX index) at option-trade times; trade-time IV |
| **Equity NBBO, 17 names**, 553M rows | **no** | 5.1 GB | Top-of-book quotes **09:29–09:35 and 15:55–16:01 only** (measured on 2023-06; GOOGL absent) |
| Equity auction-window trades | **no** | 1.0 GB | Rebuild official MOO/MOC prints → auction fills |

**Dropbox access, verified today:** swapping `dl=0`→`dl=1` on the manifest links downloads cleanly. One equity-NBBO month (137.6 MB) arrived in 6.5 s (~21 MB/s), and the byte count for `option_trades_with_nbbo_quarterly/2024Q4` matched the manifest exactly. Range requests return HTTP 206, but the signed redirect URLs fail under DuckDB `httpfs`. **So the workflow is download → reduce → (delete), not remote querying.** Disk has ~45 GB free, so the Greeks tape must be streamed one quarter at a time.

## 2. Why the last wave failed and what to change

1. **No power.** The selected test books had 1–34 trades on 151 sessions. For roughly i.i.d. returns, SE(annualized Sharpe) ≈ √((1+SR²/2)/years) ≈ 0.6 on 3 years. *Any* 3-year test can confirm only SR ≳ 1.2 at 5%. Sampling more often doesn't shrink that; only more **breadth** (independent bets per day) or **more years** raises the detectable signal. So: prefer high-breadth, high-Sharpe effects (intraday, many expiries, cross-sectional panels), and report minimum detectable effects (MDE) up front.
2. **Costs: buying the ask and selling the bid at EOD with no size information.** That is both pessimistic on price (index options often trade inside the spread) and silent on capacity. The NBBO tape fixes both, within limits.
3. **The exit fill was the biggest cost.** Holding cash-settled, European SPXW to PM settlement removes the exit fill entirely.

## 3. Fill-realism tiers (every backtest declares one)

| Tier | Mechanism | Fill price | Size cap | Where valid |
|---|---|---|---|---|
| **T0 Settlement** | Hold PM-settled SPXW to expiry | Official SPX close (verify `market_overlays` S&P close vs Cboe settlement) | n/a | SPXW only. Exclude AM-settled SPX: the SET value isn't in the data |
| **T1 Auction** | Equity MOO/MOC | Primary-exchange auction print rebuilt from `auction_window_trades` (condition codes, corrections) | ≤1–5% of *lagged* (t-1…t-20) auction volume | 16 names + SPY/QQQ; early-close days excluded |
| **T2 Marketable vs observed NBBO** | Decision time τ, latency L | Ask (buy) / bid (sell) from the **first tape quote strictly after τ+L**; reject if quote age > A seconds, crossed, or bid ≤ 0 | ≤ displayed size at that quote and ≤ k% of trailing contract volume; multi-leg = each leg independently, legging risk charged | Liquid roots/strikes where trades are dense (measure density first) |
| **T3 EOD** | Existing engine | EOD bid/ask | No size info, so cap by % volume/OI | Daily strategies only |
| Passive limit | Not modelled as a base case | Only as a sensitivity: fill if tape trades *through* the limit by ≥1 tick | — | Never in headline results |

Each T2 result is reported at L ∈ {0.5 s, 2 s, 10 s} and A ∈ {2 s, 10 s}, plus slip ×1.5. Displayed size is not reused across simulated orders within the same second.

## 4. Ideas, ranked by data fit × fillability × statistical power

### Foundations (do first; no alpha claim)

**F1. Option execution-cost atlas.** Measure effective/quoted spread, quote age between trades, and displayed size by root × moneyness × DTE × time of day × year from the NBBO tape (Muravyev & Pearson 2020, *RFS*, "Options Trading Costs Are Lower than You Think"). Also reconcile EOD chain quotes against tape quotes at 15:59/16:00/16:15: when exactly is the EOD snapshot? Output: a calibrated, size-aware cost model plus capacity tables. Re-running the rejected wave under this model is allowed **only as one pre-declared sensitivity**, not as a rescue.

**F2. Engine validation against a public index.** Replicate Cboe's put-write and buy-write indices over 2022–24 using SPXW PM monthlies, then report tracking error. If the engine can't replicate a published benchmark, no strategy result is credible. (Needs a free external download of the index history.)

### First-wave hypotheses

**H1. Short-dated SPXW premium held to PM settlement (0DTE/1DTE).** Sell defined-risk iron flies or condors at fixed decision times (10:00, 12:00, 14:00, 15:00), choosing strikes from the SPX level known at τ (the Greeks tape's `underlying_price`). Entry fill is T2; exit is T0, so there is no exit spread. Literature: Bandi, Fusari & Renò (2023) "0DTE Option Pricing"; Vilkov (2023) "0DTE Trading Rules"; Beckmeyer, Branger & Gayda (2023) "Retail Traders Love 0DTE Options… But Should They?". **Breadth:** daily expiries since May 2022 → ~650 days × 4 times. **Kill if** net mean ≤ 0 at L = 2 s, or if the result depends on a single crash day (report ES and the worst 5 days). *Best data fit in the folder.*

**H2. Overnight and weekend option premium.** Muravyev & Ni (2020, *JFE*), "Why Do Option Returns Change Sign from Day to Night?"; Jones & Shemesh (2018, *JF*), "Option Mispricing Around Nontrading Periods". Short a delta-hedged SPY/QQQ straddle (defined-risk version: iron fly) from 15:58 to 09:35+. Option legs are T2. **The stock hedge uses the equity NBBO, which exists exactly in the open and close windows**, so the hedge is fillable too. The weekend variant (Friday close → Monday open, ~150 weekends) has a quarter of the turnover. The likely answer is "premium exists, costs eat it". Measuring that net of observed spreads is a publishable-quality result either way.

**H3. Overnight equity drift with auction fills.** Lou, Polk & Skouras (2019, *JFE*), "A Tug of War"; Cliff, Cooper & Gulen (2008). Go long MOC and exit MOO in SPY, QQQ, and 16 names (T1). It's simple, with near-zero spread cost, and it doubles as the testbed for the auction-rebuild code that H4 needs.

**H4. Option order flow → next-day stock returns.** Easley, O'Hara & Srinivas (1998, *JF*); Pan & Poteshman (2006, *RFS*); Johnson & So (2012, *JFE*, O/S ratio); Cremers & Weinbaum (2010, *JFQA*, IV spread); Xing, Zhang & Zhao (2010, *JFQA*, smirk). Sign every option trade with the quote rule against its attached NBBO, aggregate delta-weighted imbalance per underlying-day, and trade the stock at the next MOO (T1). **Caveat:** there are no open/close or customer flags, so this is a weaker version of Pan–Poteshman. Treat all option-information signals as **one family** for multiple-testing control. 16 names is thin breadth, so use panel regressions with date-clustered SEs before any portfolio.

### Second wave

**H5. Pre-earnings IV run-up.** Gao, Xing & Zhang (2018, *JFQA*), "Anticipating Uncertainty". Buy a straddle about 5 sessions before the announcement and sell it *before* the event, so the event itself is never held. Both fills are T2 at 15:50. This differs from the rejected EOD study, which held through the event. Only ~190 events, so pre-register **one** spec. An optional comparison is an event-variance calendar (Dubinsky, Johannes, Kaeck & Seeger 2019, *RFS*).

**H6. End-of-day hedging-demand momentum, partial.** Gao, Han, Li & Zhou (2018, *JFE*); Baltussen, Da, Lammers & Martens (2021, *JFE*). The signal is the 09:30→15:55 SPY return from the Greeks tape. Execute at the 15:55 NBBO and exit at MOC. That captures only the last 5 minutes of the documented last-30-minute effect, because there are no equity quotes earlier in the afternoon. The dealer-gamma sign from OI is an **assumption** and is labelled as such.

### Deprioritized (not fillable with this data)
- **Dispersion / correlation risk premium** (Driessen, Maenhout & Vilkov 2009). The 16 names are roughly a third of SPX weight, there are many legs, and leg quotes aren't synchronous.
- **Intraday gamma scalping.** There are no equity quotes outside the open/close windows.
- **Anything depending on passive fills or L2 depth.**
- **More EOD VRP filter grids.** This is the family we have already over-mined; its deflated Sharpe was ~0.

## 5. Rigor protocol

1. **Physical holdout.** The intraday tapes haven't been used yet. **Do not download 2024Q3–Q4 of the option tapes** until H1–H4 specs, code, and parameters are frozen and committed (git SHA recorded). 2022Q1–2024Q2 is development (rolling/walk-forward inside it); 2024H2 is the single confirmatory run. Ideal next step: buy 2025 data as a true out-of-sample test.
2. **Pre-registration per hypothesis:** one primary spec plus at most ~10 secondaries, the decision rule, MDE, and kill criteria, written before running.
3. **Inference:** stationary block bootstrap and Newey–West for time series; date-clustered SEs for panels; events clustered by date. Multiple testing: Romano–Wolf stepdown within each family, Hansen (2005) SPA against a zero benchmark, deflated Sharpe (Bailey & López de Prado 2014) across *all* trials ever run, and a Harvey–Liu–Zhu (2016) t > 3 hurdle for headline claims.
4. **Placebos:** randomized decision times, signals shifted one day forward and backward (the backward shift checks look-ahead), and shuffled-date signals.
5. **Reporting:** gross / net at T2 base / net at T2 stress / capacity at $50k–$1M; tail metrics (worst day, ES 97.5%); fraction of P&L from the top 5 days.
6. **Data gates** (from the audit): exclude META until the identity is repaired; standard contracts only (`contract_size=100`, `cfadj=1`); quote eligibility rules; **verify the tape timezone** (SPY option trade clustering at 09:30 ET and 16:00/16:15 ET); reconcile SPX close with PM settlement; exclude early-close days from auction tests.

## 6. How to run it

**Pipeline** (new `src/options_lab/ingest.py`, manifest-driven):
1. `curl -L` with `dl=1` → check bytes against `file_manifest.csv` → reduce with DuckDB → write `data/derived/…` → delete the raw file (Greeks tape always; NBBO tape optional).
2. Reductions:
   - NBBO tape → (a) SPX/SPXW/SPY/QQQ, DTE ≤ 7, full resolution (for H1/H2); (b) per-contract per-minute last-quote snapshots for all roots (F1, H5); (c) daily signed-flow aggregates per root (H4).
   - Greeks tape → per-second/minute `underlying_price` bars per root, plus minute IV for the near-ATM strikes.
   - Equity NBBO and auction trades → keep whole (6 GB).
3. New `intraday_fill.py`: T1/T2 fills via DuckDB `ASOF JOIN` (strictly-after semantics), staleness/size rejection, no-fill outcome. New tests: as-of look-ahead, stale-quote rejection, displayed-size depletion, settlement payoff, auction-print selection.

**Budget at the measured ~21 MB/s:** NBBO tape ~20 min, Greeks tape ~50 min (stream-reduce per quarter), equity ~5 min. Dev-only (through 2024Q2) is about 75% of that. CPU: DuckDB on this Mac is enough. Avoid running alongside `run_rolling_research.py`, which is currently active.

**Order:** Phase 0 ingest and data gates (timezone, settlement, EOD snapshot time) → Phase 1 F1 + F2 → Phase 2 H1, H2, H3+H4 (pre-registered, dev only) → freeze → 2024H2 confirmatory run → Phase 3 H5, H6.
