// H3: overnight equity drift. Buy closing cross on t, sell opening cross on t+1 (T1), equal weight, 100% gross.
#include "equity.hpp"

static const std::vector<std::string> NAMES = {"AAPL", "AMD", "AMZN", "AVGO", "CRM", "JPM", "LLY", "MSFT", "NFLX", "NVDA", "TSLA", "UNH", "WMT", "XOM", "SPY", "QQQ"};
constexpr long T_CLOSE = 57540000, T_OPEN = 34260000;  // 15:59, 09:31 for the spread-crossing sensitivity

int main() {
  Sessions S; Equity E; Snaps eq("eq_snap_", true);
  Ledger L("h3", "variant,date_in,date_out,sym,w,px_in,px_out,shares,ret,fees,pnl,capped");
  std::map<std::string, std::vector<double>> on_hist;  // past overnight returns (cross-to-cross), for the momentum variant
  int first = 99999999, last = 0;
  for (size_t i = 1; i + 1 < S.d.size(); ++i) {
    int d0 = S.d[i], d1 = S.d[i + 1];
    // --- signal: eligibility needs both crosses (known after the fact only for the exit, which is a fill, not a signal) ---
    std::vector<std::string> elig;
    for (auto& s : NAMES) if (E.get(E.close, s, d0) && E.get(E.open, s, d1)) elig.push_back(s);
    if (elig.empty()) continue;
    first = std::min(first, d0); last = std::max(last, d1);
    // momentum rank on trailing 21 overnight returns (strictly before d0's close)
    std::vector<std::pair<double, std::string>> mom;
    for (auto& s : elig) { auto& h = on_hist[s]; if (h.size() >= 15) { double m = 0; size_t k = std::min<size_t>(21, h.size()); for (size_t j = h.size() - k; j < h.size(); ++j) m += h[j]; mom.push_back({m / k, s}); } }
    std::sort(mom.rbegin(), mom.rend());
    std::vector<std::string> top; for (size_t j = 0; j < mom.size() / 3; ++j) top.push_back(mom[j].second);
    for (std::string v : {"overnight", "overnight_fee2", "overnight_mom", "overnight_cross_spread", "intraday"}) {
      auto& book = v == "overnight_mom" ? top : elig;
      if (book.empty()) continue;
      double w = 1.0 / book.size(), fm = v == "overnight_fee2" ? 2 : 1;
      for (auto& s : book) {
        double a, b; int da = d0, db = d1; bool capped = false;
        if (v == "intraday") { da = db = d1; auto c = E.get(E.close, s, d1); if (!c) continue; a = E.get(E.open, s, d1)->px; b = c->px; }
        else if (v == "overnight_cross_spread") {
          auto q0 = eq.find(d0, T_CLOSE, 2000, s), q1 = eq.find(d1, T_OPEN, 2000, s);
          if (!q0 || !q1) continue; a = q0->ask; b = q1->bid;
        } else { a = E.get(E.close, s, d0)->px; b = E.get(E.open, s, d1)->px; }
        // --- portfolio + risk: equal weight, participation <= 1% of lagged median cross size ---
        double shares = std::floor(w * E0 / a);
        if (v != "overnight_cross_spread") {
          double cap = 0.01 * std::min(E.med_size(v == "intraday" ? E.open : E.close, s, S, i), E.med_size(v == "intraday" ? E.close : E.open, s, S, i + 1));
          if (std::isfinite(cap) && shares > cap) { shares = std::floor(cap); capped = true; }
          if (!std::isfinite(cap)) continue;
        }
        double r = E.ret(s, da, a, db, b); if (!std::isfinite(r)) continue;
        double fees = 2 * shares * FEE_SH * fm, pnl = shares * a * r - fees;
        L.add(v, db, pnl);
        L.trades << v << "," << da << "," << db << "," << s << "," << w << "," << a << "," << b << "," << shares << "," << r << "," << fees << "," << pnl << "," << capped << "\n";
      }
    }
    for (auto& s : elig) on_hist[s].push_back(E.ret(s, d0, E.get(E.close, s, d0)->px, d1, E.get(E.open, s, d1)->px));
  }
  L.write_daily(S, first, last);
  std::cerr << "h3 done\n";
}
