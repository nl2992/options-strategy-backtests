// H4: option-implied information (day t) -> stock return open(t+1) -> open(t+2). Dollar-neutral rank portfolio, T1 fills.
#include "equity.hpp"

int main() {
  Sessions S; Equity E;
  auto sig = load("h4_signals");
  int cr = sig.c("root"), cd = sig.c("date"), cf = sig.c("flow"), ci = sig.c("ivspread"), cs = sig.c("smirk");
  std::map<int, std::map<std::string, std::array<double, 3>>> X;  // date -> root -> {flow, ivspread, -smirk}
  for (auto& r : sig.rows) X[std::stoi(r[cd])][r[cr]] = {num(r[cf]), num(r[ci]), -num(r[cs])};
  Ledger L("h4", "date,root,flow,ivspread,neg_smirk,z_flow,z_ivspread,z_neg_smirk,z_comp,r_next,tradeable");
  const std::vector<std::string> V = {"flow", "ivspread", "neg_smirk", "composite", "flow_fee2"};
  std::map<std::string, std::map<std::string, double>> prev_w;
  int first = 99999999, last = 0;
  for (size_t i = 0; i + 2 < S.d.size(); ++i) {
    int d = S.d[i], d1 = S.d[i + 1], d2 = S.d[i + 2];
    auto it = X.find(d); if (it == X.end()) continue;
    // --- signal: cross-sectional z-scores of each raw signal on day t ---
    std::map<std::string, std::array<double, 4>> z;
    for (int k = 0; k < 3; ++k) {
      double m = 0, s2 = 0; int n = 0;
      for (auto& [r, x] : it->second) if (std::isfinite(x[k])) { m += x[k]; s2 += x[k] * x[k]; ++n; }
      if (n < 5) continue;
      m /= n; double sd = std::sqrt(std::max(1e-18, s2 / n - m * m));
      for (auto& [r, x] : it->second) if (std::isfinite(x[k])) z[r][k] = (x[k] - m) / sd; else z[r][k] = NAN;
    }
    for (auto& [r, zz] : z) { double s = 0; int n = 0; for (int k = 0; k < 3; ++k) if (std::isfinite(zz[k])) { s += zz[k]; ++n; } zz[3] = n == 3 ? s / 3 : NAN; }
    // tradeable: both opening crosses exist (GOOGL has no equity auction or NBBO data -> never tradeable)
    std::map<std::string, double> rnext;
    for (auto& [r, zz] : z) {
      auto a = E.get(E.open, r, d1), b = E.get(E.open, r, d2);
      rnext[r] = a && b ? E.ret(r, d1, a->px, d2, b->px) : NAN;
      auto& x = it->second[r];
      L.trades << d << "," << r << "," << x[0] << "," << x[1] << "," << x[2] << "," << zz[0] << "," << zz[1] << "," << zz[2] << "," << zz[3] << "," << rnext[r] << "," << std::isfinite(rnext[r]) << "\n";
    }
    first = std::min(first, d2); last = std::max(last, d2);
    for (auto& v : V) {
      int k = v == "flow" || v == "flow_fee2" ? 0 : v == "ivspread" ? 1 : v == "neg_smirk" ? 2 : 3;
      // --- portfolio construction: demeaned ranks -> 100% gross, dollar neutral ---
      std::vector<std::pair<double, std::string>> book;
      for (auto& [r, zz] : z) if (std::isfinite(zz[k]) && std::isfinite(rnext[r])) book.push_back({zz[k], r});
      if (book.size() < 5) continue;
      std::sort(book.begin(), book.end());
      double mr = (book.size() - 1) / 2.0, g = 0; std::map<std::string, double> w;
      for (size_t j = 0; j < book.size(); ++j) g += std::abs(j - mr);
      for (size_t j = 0; j < book.size(); ++j) w[book[j].second] = (j - mr) / g;
      // --- execution (T1 opening crosses), costs: per-share fee on turnover + 30 bp/yr borrow on shorts ---
      double gross = 0, fees = 0, borrow = 0, fm = v == "flow_fee2" ? 2 : 1;
      auto& pw = prev_w[v];
      std::set<std::string> names; for (auto& [r, x] : w) names.insert(r); for (auto& [r, x] : pw) names.insert(r);
      for (auto& r : names) {
        double wn = w.count(r) ? w[r] : 0, wo = pw.count(r) ? pw[r] : 0;
        auto a = E.get(E.open, r, d1); double px = a ? a->px : NAN;
        if (std::isfinite(px)) fees += std::abs(wn - wo) * E0 / px * FEE_SH * fm;
        if (wn != 0) gross += wn * E0 * rnext[r];
        if (wn < 0) borrow += -wn * E0 * 0.003 / 252;
      }
      pw = w;
      L.add(v, d2, gross - fees - borrow);
    }
  }
  L.write_daily(S, first, last);
  std::cerr << "h4 done\n";
}
