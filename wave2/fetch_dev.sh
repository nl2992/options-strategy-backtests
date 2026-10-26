#!/bin/zsh
# dev period only: 2022-01 .. 2024-06. 2024H2 is the frozen holdout -- do NOT add it here.
cd "$(dirname $0)"
for q in 2022Q2 2022Q3 2022Q4 2023Q1 2023Q2 2023Q3 2023Q4 2024Q1 2024Q2; do ./fetch.sh option_trades_with_nbbo_quarterly/$q.parquet; done
for y in 2022 2023 2024; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  [[ $y == 2024 && $m > 06 ]] && continue
  ./fetch.sh intraday_nbbo_close_open_windows_monthly/${y}_$m.parquet; ./fetch.sh auction_window_trades_monthly/${y}_$m.parquet; done; done
echo ALLDONE
