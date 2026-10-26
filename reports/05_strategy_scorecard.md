# Strategy scorecard

Decision gate: positive test excess return, 95% CI lower bound >0, positive dev and validation, beats unfiltered control, positive under fee×2 and slip×1.5, ≥30 test trades.

| Strategy | Frozen config (dev-selected) | Dev ex-ret (ann) | Val | **Test** | Test 95% block-boot CI | Test trades | Control (unfiltered) test | fee×2 | slip×1.5 | delay+1 | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Call credit spread | d=0.15 dte=30 filt=f2 | 0.48% | -1.37% | **-0.36%** | [-1.20%, 0.08%] | 1 | -2.61% | -0.36% | -0.37% | -1.16% | **REJECT** |
| Call debit vertical | d=0.5 dte=30 filt=f1 | -1.25% | 0.56% | **-4.50%** | [-12.52%, 1.69%] | 34 | -9.13% | -4.95% | -5.56% | -7.90% | **REJECT** |
| Iron condor | d=0.2 dte=30 filt=f1 | 0.91% | -2.52% | **-3.56%** | [-11.03%, 1.03%] | 33 | -6.49% | -3.89% | -4.49% | -2.63% | **REJECT** |
| Put credit spread | d=0.2 dte=30 filt=f1 | 0.33% | -0.30% | **-2.53%** | [-9.24%, 1.72%] | 19 | -2.09% | -2.60% | -2.98% | -0.73% | **REJECT** |

Deflated Sharpe (dev, 72 trials): ccs=0.006, dv=0.000, ic=0.006, pcs=0.003

Figures: `figures/equity_curves.png`, `figures/pnl_hist.png`, `figures/param_heatmap_dev.png`. Ledgers: `trade_blotter.parquet`, `daily_portfolio.parquet`.
