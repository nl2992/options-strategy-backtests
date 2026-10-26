"""Pre-registered rolling walk-forward grid for the first-wave options slate.

Each fold selects one configuration per structure using only the trailing
252-session training window, then evaluates it on the next 63 sessions. The
window advances 63 sessions, so the final fold may be shorter. Every fold
starts flat and liquidates open positions at its final eligible EOD snapshot.
The resulting historical OOS series is research-stage evidence, not a virgin
holdout: the underlying 2022-2024 period has been inspected in prior work.
"""
from __future__ import annotations

import dataclasses
import json
import multiprocessing as mp
import os
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from options_lab.analytics import block_boot_ci, deflated_sharpe, newey_west_t, perf, trade_stats
from options_lab.data import load_market
from options_lab.engine import Cfg, run

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "reports" / "rolling_research"
UNIVERSE = (
    "SPY", "QQQ", "SPX", "AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN",
    "AVGO", "NFLX", "AMD", "CRM", "JPM", "LLY", "UNH", "XOM", "WMT",
)  # META excluded until the audited issuer/history collision is repaired.
WIDTHS = tuple((u, 10.0 if u in ("SPX", "AVGO", "NVDA") else 5.0) for u in UNIVERSE)
STRUCTURES = ("pcs", "ccs", "ic", "dv", "pdv")
TRAIN_SESSIONS = 252
TEST_SESSIONS = 63
STEP_SESSIONS = 63
WARMUP_SESSIONS = 126
MIN_TRAIN_TRADES = 15
WORKERS = min(8, os.cpu_count() or 4)

MKT = None
RF_DAILY = None
DATES = None


def signal_specs():
    """Small, fixed grid spanning rank, VRP, trend, combined, and skew signals."""
    return [
        {"signal": "none"},
        {"signal": "ivp", "ivp_min": 50.0},
        {"signal": "ivp", "ivp_min": 70.0},
        {"signal": "vrp20", "vrp_min": 0.00},
        {"signal": "vrp20", "vrp_min": 0.02},
        {"signal": "vrp60", "vrp_min": 0.00},
        {"signal": "trend20", "trend_threshold": 0.00},
        {"signal": "trend60", "trend_threshold": 0.02},
        {"signal": "vrp20_trend60", "vrp_min": 0.02, "trend_threshold": 0.02},
        {"signal": "skew25", "skew_threshold": 0.02},
        {"signal": "skew25", "skew_threshold": 0.04},
    ]


def candidate_grid():
    rows = []
    trial = 0
    for strategy in STRUCTURES:
        deltas = (0.15, 0.25) if strategy in ("pcs", "ccs", "ic") else (0.50, 0.60)
        for delta in deltas:
            for dte in (30, 45):
                for signal in signal_specs():
                    cfg = Cfg(
                        strategy=strategy, delta=delta, dte_target=dte,
                        signal=signal["signal"], filt="none", universe=UNIVERSE,
                        widths=WIDTHS, equity0=200_000.0, start_idx=WARMUP_SESSIONS,
                        force_exit_at_end=True, **{k: v for k, v in signal.items() if k != "signal"},
                    )
                    rows.append({"trial_id": f"T{trial:04d}", **dataclasses.asdict(cfg)})
                    trial += 1
    return rows


def make_folds(n):
    folds = []
    start = WARMUP_SESSIONS
    while start + TRAIN_SESSIONS < n:
        train_end = start + TRAIN_SESSIONS
        test_start = train_end
        test_end = min(test_start + TEST_SESSIONS, n)
        if test_end - test_start < 20:
            break
        folds.append({
            "fold": len(folds) + 1,
            "train_start": start,
            "train_end": train_end,  # exclusive
            "test_start": test_start,
            "test_end": test_end,    # exclusive; final fold can be partial
        })
        start += STEP_SESSIONS
    return folds


def make_rf_daily(mkt):
    rf = mkt.rf
    return pd.Series(
        [float(rf.iloc[max(0, i - 1)]) * ((mkt.dates[i] - mkt.dates[i - 1]).days / 360.0)
         for i in range(len(mkt.dates))], index=mkt.dates, dtype=float,
    )


def eval_window(cfg_dict, start, stop, keep_returns=False):
    allowed = {f.name for f in dataclasses.fields(Cfg)}
    cfg = Cfg(**{k: v for k, v in cfg_dict.items() if k in allowed})
    cfg = dataclasses.replace(cfg, start_idx=start, end_idx=stop - 1, force_exit_at_end=True)
    daily, blotter, rejects, _ = run(MKT, cfg)
    # The period includes the prior close as the starting NAV and returns from
    # each fill session through the final fold session.
    dates = MKT.dates
    e = daily.equity.loc[dates[start - 1]:dates[stop - 1]]
    m = perf(e, RF_DAILY.reindex(e.index))
    trade_rows = blotter
    if len(trade_rows):
        trade_rows = trade_rows[
            (pd.to_datetime(trade_rows.entry_date).dt.date >= dates[start])
            & (pd.to_datetime(trade_rows.entry_date).dt.date <= dates[stop - 1])
        ]
    ts = trade_stats(trade_rows)
    out = {**m, **{f"trade_{k}": v for k, v in ts.items()},
           "rejected_entries": int(sum(rejects.values())),
           "rejections": json.dumps(rejects, sort_keys=True)}
    if keep_returns:
        r = e.pct_change().dropna()
        out["daily"] = [(str(d), float(v), float(RF_DAILY.get(d, 0.0))) for d, v in r.items()]
    return out


def _train_job(payload):
    trial_id, cfg, start, stop = payload
    return trial_id, eval_window(cfg, start, stop)


def _test_job(payload):
    label, cfg, start, stop = payload
    return label, eval_window(cfg, start, stop, keep_returns=True)


def select_train_candidate(train_rows):
    eligible = [r for r in train_rows if r.get("trade_trades", 0) >= MIN_TRAIN_TRADES
                and np.isfinite(r.get("sharpe", np.nan))]
    if not eligible:
        return None
    return sorted(eligible, key=lambda r: (r["sharpe"], r.get("ex_ann", -np.inf), r.get("trade_trades", 0)), reverse=True)[0]


def summarize_returns(rows):
    r = pd.Series([x[1] for x in rows], index=pd.to_datetime([x[0] for x in rows])).sort_index()
    rf = pd.Series([x[2] for x in rows], index=pd.to_datetime([x[0] for x in rows])).reindex(r.index).fillna(0)
    ex = r - rf
    curve = (1 + r).cumprod()
    dd = curve / curve.cummax() - 1
    ci = block_boot_ci(ex.to_numpy(), B=2000, block=10, seed=0)
    return {
        "oos_sessions": int(len(r)),
        "oos_folds": int(len({x[3] for x in rows})),
        "oos_total_return": float(curve.iloc[-1] - 1) if len(curve) else np.nan,
        "oos_excess_ann": float(ex.mean() * 252) if len(ex) else np.nan,
        "oos_vol_ann": float(r.std() * np.sqrt(252)) if len(r) > 1 else np.nan,
        "oos_sharpe": float(ex.mean() / ex.std() * np.sqrt(252)) if len(ex) > 1 and ex.std() > 0 else np.nan,
        "oos_maxdd": float(dd.min()) if len(dd) else np.nan,
        "oos_es95": float(np.sort(r.to_numpy())[:max(1, int(0.05 * len(r)))].mean()) if len(r) else np.nan,
        "oos_ci95_excess_lo": float(ci[0]), "oos_ci95_excess_hi": float(ci[1]),
        "oos_newey_west_t": float(newey_west_t(ex.to_numpy(), lags=10)) if len(ex) > 20 else np.nan,
    }


def main():
    global MKT, RF_DAILY, DATES
    OUT.mkdir(parents=True, exist_ok=True)
    MKT, _ = load_market(universe=UNIVERSE)
    DATES = MKT.dates
    RF_DAILY = make_rf_daily(MKT)
    folds = make_folds(len(DATES))
    if not folds:
        raise RuntimeError(f"Not enough common sessions for rolling folds: {len(DATES)}")

    grid = candidate_grid()
    registry = pd.DataFrame([{k: v for k, v in row.items() if k != "widths" and k != "universe"}
                             | {"universe": ",".join(row["universe"]), "widths": json.dumps(row["widths"]),
                                "registered_at": pd.Timestamp.now().isoformat()} for row in grid])
    registry.to_csv(OUT / "candidate_registry.csv", index=False)
    pd.DataFrame([
        {**f, "train_start_date": str(DATES[f["train_start"]]),
         "train_end_date": str(DATES[f["train_end"] - 1]),
         "test_start_date": str(DATES[f["test_start"]]),
         "test_end_date": str(DATES[f["test_end"] - 1])}
        for f in folds
    ]).to_csv(OUT / "rolling_folds.csv", index=False)
    (OUT / "protocol.md").write_text(
        "# Rolling research protocol\n\n"
        "This is a pre-registered grid across defined-risk credit spreads/condors and call/put debit verticals. "
        "For each fold, the best configuration by training Sharpe is selected from the preceding 252-session "
        "window (minimum 15 closed trades), then evaluated on the next 63 sessions. Folds advance 63 sessions; "
        "the final partial window is retained if it has at least 20 sessions. A 126-session feature warm-up is "
        "available before the first training window. Every fold starts flat and closes positions at its final "
        "eligible EOD snapshot.\n\n"
        "Signals use the prior session close. Costs use the existing conservative bid/ask fills and $0.65 per "
        "contract-side placeholder fee; fee x2 and 1.5x spread costs are run on selected fold configurations. "
        "Returns are reported from a $1 normalized NAV, with integer sizing under the separate $200,000 reference "
        "account. The universe excludes META pending identity/history repair. This 2022-2024 walk-forward is "
        "research-stage historical OOS, not a virgin holdout.\n"
    )

    print(f"Loaded {len(UNIVERSE)} underlyings on {len(DATES)} common sessions; {len(grid)} configs; {len(folds)} folds", flush=True)
    ctx = mp.get_context("fork")
    resume_oos = "--resume-oos" in sys.argv
    score_path = OUT / "fold_candidate_scores.csv"
    selection_path = OUT / "fold_selections.json"
    if resume_oos and score_path.exists():
        all_train = pd.read_csv(score_path).to_dict("records")
    else:
        all_train = []
    fold_selections = json.loads(selection_path.read_text()) if resume_oos and selection_path.exists() else []
    oos_rows, daily_rows = [], []
    t0 = time.time()
    for fold in folds:
        train_start, train_end = fold["train_start"], fold["train_end"]
        by_strategy = {s: [] for s in STRUCTURES}
        if resume_oos:
            for row in all_train:
                if int(row["fold"]) == fold["fold"]:
                    by_strategy[row["strategy"]].append(row)
        else:
            jobs = [(row["trial_id"], row, train_start, train_end) for row in grid]
            with ProcessPoolExecutor(max_workers=WORKERS, mp_context=ctx) as ex:
                train = list(ex.map(_train_job, jobs, chunksize=1))
            for trial_id, score in train:
                cfg = next(r for r in grid if r["trial_id"] == trial_id)
                row = {"fold": fold["fold"], "trial_id": trial_id, "strategy": cfg["strategy"],
                       "delta": cfg["delta"], "dte_target": cfg["dte_target"], "signal": cfg["signal"],
                       "ivp_min": cfg["ivp_min"], "vrp_min": cfg["vrp_min"],
                       "trend_threshold": cfg["trend_threshold"], "skew_threshold": cfg["skew_threshold"],
                       **score}
                all_train.append(row); by_strategy[cfg["strategy"]].append(row)
        selected = {}
        for strategy, rows in by_strategy.items():
            best = select_train_candidate(rows)
            if best is not None:
                candidate_scores = [r["sharpe"] for r in rows if np.isfinite(r.get("sharpe", np.nan))]
                best["train_dsr"] = float(deflated_sharpe(best["sharpe"] / np.sqrt(252),
                                                            np.asarray(candidate_scores) / np.sqrt(252),
                                                            TRAIN_SESSIONS)) if len(candidate_scores) > 1 else np.nan
                selected[strategy] = best
        frozen = {s: {k: v for k, v in row.items() if k not in ("rejections",)}
                  for s, row in selected.items()}
        selection_record = {"fold": fold["fold"], "dates": {
            "train_start": str(DATES[train_start]), "train_end": str(DATES[train_end - 1]),
            "test_start": str(DATES[fold["test_start"]]), "test_end": str(DATES[fold["test_end"] - 1])},
            "selected": frozen}
        if resume_oos:
            fold_selections = [x for x in fold_selections if x["fold"] != fold["fold"]]
        fold_selections.append(selection_record)
        fold_selections.sort(key=lambda x: x["fold"])
        selection_path.write_text(json.dumps(fold_selections, indent=2, default=str))
        pd.DataFrame(all_train).to_csv(score_path, index=False)

        test_start, test_end = fold["test_start"], fold["test_end"]
        test_jobs = []
        for strategy, choice in selected.items():
            config = next(r for r in grid if r["trial_id"] == choice["trial_id"])
            test_jobs.append((f"{strategy}:selected", config, test_start, test_end))
            control = dict(config, signal="none", filt="none")
            test_jobs.append((f"{strategy}:control", control, test_start, test_end))
            test_jobs.append((f"{strategy}:fee2x", dict(config, fee_mult=2.0), test_start, test_end))
            test_jobs.append((f"{strategy}:slip1.5", dict(config, slip=1.5), test_start, test_end))
        with ProcessPoolExecutor(max_workers=WORKERS, mp_context=ctx) as ex:
            test_results = list(ex.map(_test_job, test_jobs, chunksize=1))
        for label, result in test_results:
            strategy, variant = label.split(":", 1)
            choice = selected[strategy]
            oos_rows.append({"fold": fold["fold"], "strategy": strategy, "variant": variant,
                             "selected_trial_id": choice["trial_id"], "selected_signal": choice["signal"],
                             "selected_delta": choice["delta"], "selected_dte": choice["dte_target"],
                             "train_sharpe": choice["sharpe"], "train_trades": choice.get("trade_trades", 0),
                             "train_dsr": choice.get("train_dsr"),
                             **{k: v for k, v in result.items() if k != "daily"}})
            if variant == "selected":
                daily_rows.extend([(d, r, rf, strategy, fold["fold"]) for d, r, rf in result["daily"]])
        pd.DataFrame(oos_rows).to_csv(OUT / "fold_oos_results.csv", index=False)
        partial_daily = pd.DataFrame(daily_rows, columns=["date", "return", "rf_daily", "strategy", "fold"])
        if len(partial_daily):
            partial_daily["normalized_equity"] = partial_daily.sort_values(["strategy", "date"]).groupby("strategy")["return"].transform(lambda x: (1 + x).cumprod())
        partial_daily.to_csv(OUT / "oos_daily_returns.csv", index=False)
        print(f"Fold {fold['fold']}/{len(folds)} complete ({len(selected)} selected); elapsed {time.time()-t0:.0f}s", flush=True)

    pd.DataFrame(all_train).to_csv(OUT / "fold_candidate_scores.csv", index=False)
    pd.DataFrame(oos_rows).to_csv(OUT / "fold_oos_results.csv", index=False)
    daily_frame = pd.DataFrame(daily_rows, columns=["date", "return", "rf_daily", "strategy", "fold"])
    if len(daily_frame):
        daily_frame["normalized_equity"] = daily_frame.sort_values(["strategy", "date"]).groupby("strategy")["return"].transform(lambda x: (1 + x).cumprod())
    daily_frame.to_csv(OUT / "oos_daily_returns.csv", index=False)
    summary = []
    for strategy in STRUCTURES:
        rows = [(d, r, rf, f) for d, r, rf, s, f in daily_rows if s == strategy]
        metrics = summarize_returns(rows)
        picked = pd.DataFrame([x for x in oos_rows if x["strategy"] == strategy and x["variant"] == "selected"])
        controls = pd.DataFrame([x for x in oos_rows if x["strategy"] == strategy and x["variant"] == "control"])
        fee = pd.DataFrame([x for x in oos_rows if x["strategy"] == strategy and x["variant"] == "fee2x"])
        slip = pd.DataFrame([x for x in oos_rows if x["strategy"] == strategy and x["variant"] == "slip1.5"])
        metrics.update({"strategy": strategy, "selected_folds": len(picked),
                        "positive_oos_folds": int((picked.ex_ann > 0).sum()) if len(picked) else 0,
                        "control_ex_ann_mean": float(controls.ex_ann.mean()) if len(controls) else np.nan,
                        "fee2x_ex_ann_mean": float(fee.ex_ann.mean()) if len(fee) else np.nan,
                        "slip1_5_ex_ann_mean": float(slip.ex_ann.mean()) if len(slip) else np.nan,
                        "oos_trades": int(picked.trade_trades.fillna(0).sum()) if len(picked) else 0})
        summary.append(metrics)
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(OUT / "oos_scorecard.csv", index=False)
    make_decision_memo(summary_df, pd.DataFrame(oos_rows), len(grid), folds)
    print(summary_df.to_string(index=False), flush=True)


def make_decision_memo(summary, fold_results, n_candidates, folds):
    lines = [
        "# Rolling strategy research: decision memo", "",
        "This memo summarizes the first-wave parameter search. These are historical walk-forward results on 2022-2024 data; the period has been inspected previously and is not a virgin holdout.", "",
        f"- Candidate configurations registered before the search: {n_candidates}.",
        f"- Rolling folds: {len(folds)}; each uses 252 trailing training sessions and up to 63 next-session evaluation days, stepped 63 sessions.",
        f"- Universe: {', '.join(UNIVERSE)}. META excluded pending audited identity/history repair.",
        "- Training selection: maximum Sharpe with at least 15 closed trades. Each fold starts flat and closes positions at its final eligible EOD snapshot.",
        "- Main selection results are $1-NAV normalized; $200,000 integer sizing is used inside the existing risk/cash constraints.",
        "- Fee x2 and 1.5x spread-cost stress are reported for selected configurations.", "",
        "## Aggregate rolling OOS scorecard", "",
        "```text", summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"), "```", "",
        "## Interpretation", "",
        "A positive point estimate is a research lead, not evidence of a deployable edge. Require stable results across folds, realistic cost stress, adequate closed-trade counts, and uncertainty intervals that account for serial dependence and the grid search. The grid is deliberately coarse; any refinement must be pre-registered as a new iteration and evaluated in later rolling windows, not chosen from the same OOS results.", "",
        "## Files", "",
        "- `candidate_registry.csv`: full parameter grid registered before computation.",
        "- `rolling_folds.csv`: exact chronological fold boundaries.",
        "- `fold_candidate_scores.csv`: training-only candidate metrics per fold.",
        "- `fold_selections.json`: selected parameters frozen before that fold's OOS run.",
        "- `fold_oos_results.csv`: selected, matched no-signal control, and cost-stress results.",
        "- `oos_daily_returns.csv`: normalized daily returns for reproducible aggregate metrics.",
    ]
    (OUT / "decision_memo.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
