// H5: long ATM straddle bought 5 sessions before the last pre-announcement session, sold at 15:55 before the event (T2).
// Secondary: held through the event. rule "orig" = pre-registered strike; "a1" = amendment A1 (quoted strike, exit chase).
#include "common.hpp"

constexpr long TAU = 57300000;  // 15:55

int main() {
  Sessions S; Snaps opt("h5_single_"), eq("eq_snap_", true);
  auto ev = load("ctx_earnings");
  Ledger L("h5", "variant,ticker,announce,amc,d_in,d_out,exp,k,F,n,premium,exit_value,fees,pnl,ret_on_premium,status");
  int first = 99999999, last = 0;
  for (auto& e : ev.rows) {
    std::string tk = e[0]; int A = std::stoi(e[1]); bool amc = e[2] == "1";
    // --- signal (calendar): X = last session before the announcement, entry = X-5, through-exit Y = first session after it ---
    int xi = -1, yi = -1;
    for (size_t i = 0; i < S.d.size(); ++i) { if (amc ? S.d[i] <= A : S.d[i] < A) xi = int(i); if (yi < 0 && (amc ? S.d[i] > A : S.d[i] >= A)) yi = int(i); }
    if (xi < 5 || yi < 0) continue;
    int din = S.d[xi - 5];
    auto pre = opt.get(din, TAU, -1); if (!pre) continue;
    first = std::min(first, din); last = std::max(last, S.d[yi]);
    int exp = 0; for (auto& q : *pre) if (q.root == tk && q.exp > A && (!exp || q.exp < exp)) exp = q.exp;
    Fwd f = exp ? forward(*pre, tk, exp) : Fwd{};
    if (exp && !std::isfinite(f.F)) if (auto e = eq.find(din, TAU, 500, tk)) {  // A3: stock mid as ATM reference when parity is unavailable
      f.F = e->mid(); double kb = NAN; for (auto& q : *pre) if (q.root == tk && q.exp == exp && (!std::isfinite(kb) || std::abs(q.k - f.F) < std::abs(kb - f.F))) kb = q.k; f.K = kb; }
    for (std::string rule : {"orig", "a1", "a4"}) for (std::string hold : {"pre", "through"}) for (int lat : {500, 2000, 10000, 99999}) for (double fm : {1.0, 2.0}) {
      if ((rule == "a4") != (lat == 99999)) continue;  // A4 = A1 with entry also in the 120 s window
      if ((hold == "through" || fm == 2) && lat != 2000 && lat != 99999) continue;
      if (hold == "through" && fm == 2) continue;
      std::string v = (rule == "orig" ? "" : rule + "_") + hold + (lat == 99999 ? std::string("_chase") : "_L" + std::to_string(lat)) + (fm == 2 ? "_fee2" : "");
      int dout = hold == "pre" ? S.d[xi] : S.d[yi];
      double k = f.K;
      auto out = [&](const std::string& st, double n = 0, double prem = NAN, double xv = NAN, double fees = 0, double pnl = 0) {
        L.trades << v << "," << tk << "," << A << "," << amc << "," << din << "," << dout << "," << exp << "," << k << "," << f.F << "," << n << "," << prem << ","
                 << xv << "," << fees << "," << pnl << "," << (n ? pnl / (n * 100 * prem) : NAN) << "," << st << "\n"; };
      if (!exp || !std::isfinite(f.F)) { out("no_contract"); continue; }
      if (rule != "orig") {  // closest-to-forward strike with both legs quoted post-arrival, within 2.5%
        double bd = 0.025; k = NAN; auto fl = opt.get(din, TAU, lat);
        if (fl) for (auto& q : *fl) if (q.root == tk && q.exp == exp && q.cp == 'C' && std::isfinite(fill_px(&q, 1)) &&
                                        std::isfinite(fill_px(opt.find(din, TAU, lat, tk, exp, q.k, 'P'), 1)) && std::abs(q.k / f.F - 1) <= bd) { bd = std::abs(q.k / f.F - 1); k = q.k; }
        if (!std::isfinite(k)) { out("entry_unfilled"); continue; }
      }
      auto c0 = opt.find(din, TAU, lat, tk, exp, k, 'C'), p0 = opt.find(din, TAU, lat, tk, exp, k, 'P');
      auto c1 = opt.find(dout, TAU, lat, tk, exp, k, 'C'), p1 = opt.find(dout, TAU, lat, tk, exp, k, 'P');
      bool chase = false;
      if (rule != "orig" && !std::isfinite(fill_px(c1, -1) + fill_px(p1, -1))) {
        if (!std::isfinite(fill_px(c1, -1))) c1 = opt.find(dout, TAU, 99999, tk, exp, k, 'C');
        if (!std::isfinite(fill_px(p1, -1))) p1 = opt.find(dout, TAU, 99999, tk, exp, k, 'P');
        chase = true;
      }
      double prem = fill_px(c0, 1) + fill_px(p0, 1), xv = fill_px(c1, -1) + fill_px(p1, -1);
      if (!std::isfinite(prem)) { out("entry_unfilled"); continue; }
      if (!std::isfinite(xv)) { out("exit_unfilled", 0, prem); continue; }
      // --- portfolio/risk: premium at risk <= 0.5% of equity, size <= displayed ---
      int n = std::min({int(0.005 * E0 / (prem * 100)), disp(c0, 1), disp(p0, 1)});
      if (n < 1) { out("size_lt1", 0, prem); continue; }
      double fees = 4 * n * fee_opt(tk, fm), pnl = n * 100 * (xv - prem) - fees;
      L.add(v, dout, pnl); out(chase ? "filled_chase" : "filled", n, prem, xv, fees, pnl);
    }
  }
  L.write_daily(S, first, last);
  std::cerr << "h5 done\n";
}
