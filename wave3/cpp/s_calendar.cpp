// S8 daytime-reversal frequency (monthly cross-section) | S9 FOMC pre-announcement | S10 turn-of-the-month.
// Stock fills at auction / official close, marked daily (wave3/PREREGISTRATION.md).
#include "w3.hpp"

static const std::vector<std::string> NAMES = {"AAPL", "TSLA", "AMD", "AMZN", "AVGO", "CRM", "GOOGL", "JPM", "LLY", "NFLX", "UNH", "MSFT", "NVDA", "WMT", "XOM"};
// FOMC statement dates 2022-2024 (Federal Reserve meeting calendar; second day of each scheduled meeting)
static const std::vector<int> FOMC = {20220126, 20220316, 20220504, 20220615, 20220727, 20220921, 20221102, 20221214,
                                      20230201, 20230322, 20230503, 20230614, 20230726, 20230920, 20231101, 20231213,
                                      20240131, 20240320, 20240501, 20240612, 20240731, 20240918, 20241107, 20241218};

int main() {
  Sessions S; cut(S); Equity E;
  Ledger L("s_calendar", "variant,date,sym,signal,shares,note");
  Book b8(E, S, L, "S8_nr"), b9(E, S, L, "S9_fomc"), b10(E, S, L, "S10_tom");
  auto shares = [&](const std::string& s, size_t i, double notional) { auto it = E.day.find({s, S.d[i - 1]}); return it == E.day.end() ? 0.0 : std::floor(notional / it->second.close_raw); };
  // ---------- S9: buy SPY at the close before the statement, sell at the statement-day close ----------
  for (int a : FOMC) { int i = S.i(a); if (i < 2) continue;
    double sh = shares("SPY", i - 1, E0); b9.order(S.d[i - 1], CLOSE, "SPY", sh); b9.order(a, CLOSE, "SPY", -sh);
    L.trades << "S9_fomc," << a << ",SPY,," << sh << ",\n"; }
  // ---------- S10: close of 2nd-to-last session -> close of 3rd session of next month ----------
  for (size_t i = 2; i + 3 < S.d.size(); ++i) {
    if (S.d[i] / 100 != S.d[i + 1] / 100 || S.d[i + 1] / 100 == S.d[i + 2] / 100) continue;  // i = second-to-last session of month
    double sh = shares("SPY", i, E0); b10.order(S.d[i], CLOSE, "SPY", sh); b10.order(S.d[i + 4], CLOSE, "SPY", -sh);
    L.trades << "S10_tom," << S.d[i] << ",SPY,," << sh << ",exit " << S.d[i + 4] << "\n";
  }
  // ---------- S8: month-end rank on NR = share of last 21 sessions with overnight>0 and intraday<0 ----------
  std::map<std::string, double> held; int last_rb = 0;
  for (size_t i = 22; i < S.d.size(); ++i) {
    bool month_end = i + 1 == S.d.size() || S.d[i] / 100 != S.d[i + 1] / 100;
    if (!month_end) continue;
    std::vector<std::pair<double, std::string>> nr;
    for (auto& s : NAMES) {
      int n = 0, hit = 0;
      for (size_t j = i - 20; j <= i; ++j) {
        auto o = E.get(E.open, s, S.d[j]); auto c0 = E.day.find({s, S.d[j - 1]}), c1 = E.day.find({s, S.d[j]});
        if (!o || c0 == E.day.end() || c1 == E.day.end()) continue;
        double on = E.ret(s, S.d[j - 1], c0->second.close_raw, S.d[j], o->px), id = c1->second.close_raw / o->px - 1;
        ++n; hit += on > 0 && id < 0;
      }
      if (n >= 15) nr.push_back({double(hit) / n, s});
    }
    std::map<std::string, double> tgt;
    if (nr.size() >= 6) {
      std::sort(nr.begin(), nr.end()); size_t t = nr.size() / 3;
      for (size_t j = 0; j < t; ++j) tgt[nr[j].second] = -0.5 / t, tgt[nr[nr.size() - 1 - j].second] = 0.5 / t;  // high NR long
      for (auto& [x, s] : nr) L.trades << "S8_nr," << S.d[i] << "," << s << "," << x << ",," << (tgt.count(s) ? tgt[s] : 0) << "\n";
    }
    std::set<std::string> nm; for (auto& [s, x] : tgt) nm.insert(s); for (auto& [s, x] : held) nm.insert(s);
    for (auto& s : nm) {
      double want = tgt.count(s) ? std::trunc(tgt[s] * E0 / E.day.at({s, S.d[i]}).close_raw) : 0, have = held.count(s) ? held[s] : 0;
      if (have != 0 && last_rb) have *= E.day.at({s, last_rb}).adj / E.day.at({s, S.d[i]}).adj;  // splits since the last rebalance
      if (want != have) b8.order(S.d[i], CLOSE, s, want - have);
      held[s] = want;
    }
    last_rb = S.d[i];
  }
  int miss = b8.run() + b9.run() + b10.run();
  L.write_daily(S, S.d[1], S.d.back());
  std::cerr << "s_calendar done, unfilled " << miss << "\n";
}
