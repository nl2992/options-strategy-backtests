# Earnings-event study (16 single names, 2022–2024, EOD)

Rule (calendar-only, no look-ahead on prices): after-close announcers enter at announce-date close and exit next close; pre-open announcers enter prior close and exit announce-date close. Expiry = first listed with ≥5 DTE after the event. Fills buy ask / sell bid (slip 1.0; 0.5 optimistic, 1.5 adverse), $0.65/contract/side. Return = P&L / max loss per trade (size-independent). Splits are by announcement date: first 60% dev, next 20% val, last 20% test.

```
    structure  slip  events  mean_ret_on_risk   ci_lo   ci_hi    hit     dev     val    test
long_straddle   0.5     187            0.0055 -0.0555  0.0712 0.4171 -0.0192  0.0233  0.0579
long_straddle   1.0     187           -0.0115 -0.0714  0.0531 0.4011 -0.0372  0.0101  0.0405
long_straddle   1.5     187           -0.0280 -0.0871  0.0358 0.3850 -0.0546 -0.0029  0.0235
long_strangle   0.5     186            0.0036 -0.0957  0.1137 0.3925 -0.0137  0.0329  0.0255
long_strangle   1.0     186           -0.0191 -0.1164  0.0896 0.3656 -0.0374  0.0177 -0.0008
long_strangle   1.5     186           -0.0400 -0.1362  0.0670 0.3602 -0.0589  0.0028 -0.0257
 short_condor   0.5     163           -0.0129 -0.0565  0.0269 0.5460 -0.0112 -0.0345  0.0041
 short_condor   1.0     163           -0.2824 -0.8012 -0.0032 0.5092 -0.4545 -0.0494 -0.0219
 short_condor   1.5     163           -0.1592 -0.3293 -0.0321 0.4724 -0.2319 -0.0638 -0.0461
```

## Reading
- **No structure shows a positive, statistically distinguishable edge at realistic fills.** Long straddle: mean return on risk −1.2% (95% bootstrap CI −7.1% to +5.3%) at slip 1.0; only the optimistic half-spread case is marginally positive, with a CI spanning zero. Short condor is clearly negative at realistic fills.
- Mean implied move (straddle price/spot) 7.4% vs mean realised |move| 6.1%: the options priced a larger move than occurred on average (cost of crossing the spread comes on top), consistent with a risk premium that long-vol buyers pay.
- Per-ticker results (12 events each) are noise-level; do not trade on them.
- Sizing: at $200k and 0.5% risk ($1,000), ~70% of straddle events cannot be sized to ≥1 contract (single-name straddles cost $1,000+ per contract) — long straddle trading in this account would need a higher per-trade risk cap.

## Caveats
- ~190 events total, ~12 per name; test fold ≈ 37 events. Very low power.
- Announcement dates/times come from the actuals file; whether they were published ex-ante is unverified (assumed known in advance).
- Exit-day quotes are wide for single names and dominate costs; EOD fills at displayed bid/ask are assumed.
- META has 657 option days only (data gap); AVGO/NVDA splits not special-cased (moneyness filter + cfadj=1 filter used).
- Short-condor wing width (5% of spot) and 0.25-delta shorts were fixed ex-ante, not tuned.
