#!/bin/zsh
# HOLDOUT 2024H2 -- run only after the freeze commit (d35c50e). Then extract with run_extracts semantics.
cd "$(dirname $0)"
for q in 2024Q3 2024Q4; do ./fetch.sh option_trades_with_nbbo_quarterly/$q.parquet && ../.venv/bin/python -I extract.py options $q; done
for m in 07 08 09 10 11 12; do ./fetch.sh intraday_nbbo_close_open_windows_monthly/2024_$m.parquet && ./fetch.sh auction_window_trades_monthly/2024_$m.parquet && ../.venv/bin/python -I extract.py equity 2024_$m; done
../.venv/bin/python -I context.py
echo HOLDOUT_DONE
