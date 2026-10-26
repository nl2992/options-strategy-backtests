// Option-flow stock selection: rank book on delta-weighted option flow, realistic fees, 1- and 5-day holds.
// Signal day t -> trade at the t+1 opening cross; 5-day hold = average of the last 5 daily weight vectors.
#include "costs.hpp"

int main() {
  Sessions S; cut(S); Equity E;
  auto f = load("flow_measures");
  const std::vector<std::string> SIG = {"all"};
  std::map<int, std::map<std::string, std::array<double, 1>>> X;
  for (auto& r : f.rows) {
    auto& x = X[std::stoi(r[1])][r[0]];
    for (int k = 0; k < 1; ++k) { double a = num(r[f.c("num_" + SIG[k])]), b = num(r[f.c("den_" + SIG[k])]); x[k] = b > 0 ? a / b : NAN; }
  }
  Ledger L("option_flow", "date,variant,names,gross,fees,borrow,turnover");
  for (int k = 0; k < 1; ++k) for (int hold : {1, 5}) {
    std::string v = "S3_" + SIG[k] + "_h" + std::to_string(hold);
    std::deque<std::map<std::string, double>> hist; std::map<std::string, double> prev;
    for (size_t i = 0; i + 2 < S.d.size(); ++i) {
      int d = S.d[i], d1 = S.d[i + 1], d2 = S.d[i + 2];
      // --- signal: rank names with an opening cross on t+1 and t+2 ---
      std::vector<std::pair<double, std::string>> b;
      if (X.count(d)) for (auto& [r, x] : X[d]) if (std::isfinite(x[k]) && E.get(E.open, r, d1) && E.get(E.open, r, d2)) b.push_back({x[k], r});
      std::map<std::string, double> w;
      if (b.size() >= 5) {
        std::sort(b.begin(), b.end()); double mr = (b.size() - 1) / 2.0, g = 0;
        for (size_t j = 0; j < b.size(); ++j) g += std::abs(j - mr);
        for (size_t j = 0; j < b.size(); ++j) w[b[j].second] = (j - mr) / g;
      }
      hist.push_back(w); if (int(hist.size()) > hold) hist.pop_front();
      // --- portfolio: average of the last `hold` books (overlapping sub-portfolios) ---
      std::map<std::string, double> tw;
      for (auto& h : hist) for (auto& [r, x] : h) tw[r] += x / hold;
      // --- execution: opening-cross fills, realistic per-share fees on turnover, borrow on shorts ---
      double gross = 0, fees = 0, borrow = 0, to = 0; std::set<std::string> nm;
      for (auto& [r, x] : tw) nm.insert(r); for (auto& [r, x] : prev) nm.insert(r);
      for (auto& r : nm) {
        double wn = tw.count(r) ? tw[r] : 0, wo = prev.count(r) ? prev[r] : 0;
        auto a = E.get(E.open, r, d1), c = E.get(E.open, r, d2);
        if (!a) { tw[r] = wo; continue; }  // cannot trade today: keep the old weight
        fees += stock_fee((wn - wo) * E0 / a->px, a->px, true); to += std::abs(wn - wo);
        if (wn != 0 && c) gross += wn * E0 * E.ret(r, d1, a->px, d2, c->px);
        if (wn < 0) borrow += -wn * E0 * BORROW / 252;
      }
      prev = tw;
      if (!tw.empty()) { L.add(v, d2, gross - fees - borrow); L.trades << d2 << "," << v << "," << tw.size() << "," << gross << "," << fees << "," << borrow << "," << to << "\n"; }
    }
  }
  L.write_daily(S, S.d[2], S.d.back());
  std::cerr << "option_flow done\n";
}
