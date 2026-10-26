#!/bin/zsh
# extract every downloaded dev file that has no extract yet (idempotent; waits for in-flight downloads)
cd "$(dirname $0)/.."
for q in 2022Q1 2022Q2 2022Q3 2022Q4 2023Q1 2023Q2 2023Q3 2023Q4 2024Q1 2024Q2; do
  until [[ -f wave2/raw/option_trades_with_nbbo_quarterly/$q.parquet ]]; do sleep 20; done
  [[ -f wave2/extracts/f1_atlas_$q.csv ]] || .venv/bin/python -I wave2/extract.py options $q
done
for y in 2022 2023 2024; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  [[ $y == 2024 && $m > 06 ]] && continue
  until [[ -f wave2/raw/auction_window_trades_monthly/${y}_$m.parquet && -f wave2/raw/intraday_nbbo_close_open_windows_monthly/${y}_$m.parquet ]]; do sleep 10; done
  .venv/bin/python -I wave2/extract.py equity ${y}_$m
done; done
.venv/bin/python -I wave2/context.py
echo EXTRACTS_DONE
