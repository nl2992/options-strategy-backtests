# Strategy registry
| Code | Structure | Entry | Exit |
|---|---|---|---|
| pcs | Sell put delta {0.15,0.20,0.30}, buy put ~W lower (W: SPY/QQQ $5, SPX $10) | weekly, DTE 30 [21-35] or 45 [35-60] | 50% credit capture, loss = 2× credit, ≤5 DTE, ITM short (SPY/QQQ) |
| ccs | Mirror with calls | same | same |
| ic | pcs + ccs same expiry | same | same |
| dv | Buy call delta {0.50,0.60,0.70}, sell call ~W higher | weekly | +50% / −50% of debit, ≤5 DTE, short strike ITM |
Filters: none; f1 = ATM-IV 126-session percentile ≥60 (lagged); f2 = f1 + trend (pcs/dv: 60d ret>0, ccs: 60d ret<0, ic: |20d ret|<3%).
Not implemented (feasibility in 01 matrix): calendars, diagonals, butterflies, earnings, collars, covered calls, CSPs, delta-hedged, dispersion.
