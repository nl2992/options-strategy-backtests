// S7 (exploratory): 0DTE SPXW iron fly centered on the max-OI strike (pin) vs the ATM control, held to settlement.
// Same construction and fills as wave-2 H1 (T2 entry, T0 exit); realistic fees.
#include "w3.hpp"

struct Leg { double k; char cp; int side; };
static double payoff(const std::vector<Leg>& legs, double S) {
  double x = 0; for (auto& l : legs) x += l.side * (l.cp == 'C' ? std::max(S - l.k, 0.) : std::max(l.k - S, 0.)); return x;
}
static const Q* nearest(const std::vector<Q>& v, int exp, char cp, double t) {
  const Q* b = nullptr; for (auto& q : v) if (q.exp == exp && q.cp == cp && (!b || std::abs(q.k - t) < std::abs(b->k - t))) b = &q; return b;
}

int main() {
  Sessions S; cut(S); Snaps snap("h1_spxw0dte_");
  std::map<int, std::map<double, double>> oi;  // expiry -> strike -> C+P OI from the last record before expiry
  { auto t = load("w3_spxw_oi"); std::map<int, int> last;
    for (auto& r : t.rows) { int rd = std::stoi(r[0]), e = std::stoi(r[1]); if (rd < e) last[e] = std::max(last[e], rd); }
    for (auto& r : t.rows) { int rd = std::stoi(r[0]), e = std::stoi(r[1]); if (rd == last[e]) oi[e][num(r[2])] += num(r[4]); } }
  Ledger L("s7", "date,variant,F,straddle,center,dist_atm,credit,max_loss,n,fees,settle,pnl,ret_on_risk,status");
  for (size_t si = 0; si < S.d.size(); ++si) {
    int d = S.d[si]; double settle = S.spx[si];
    for (long tau : {50400000L, 54000000L}) {
      auto pre = snap.get(d, tau, -1), fl = snap.get(d, tau, 2000); if (!pre) continue;
      Fwd f = forward(*pre, "SPXW", d); if (!std::isfinite(f.F)) continue;
      // --- signal: max-OI strike within +-1 straddle of F (known from the prior EOD record) ---
      double pin = NAN, mx = -1;
      if (oi.count(d)) for (auto& [k, o] : oi[d]) if (std::abs(k - f.F) <= f.straddle && o > mx) { mx = o; pin = k; }
      for (std::string kind : {"pin", "atm"}) {
        std::string v = "S7_" + kind + "_t" + std::to_string(tau / 3600000);
        double c = kind == "pin" ? pin : f.K;
        auto row = [&](const std::string& st, double cr = NAN, double ml = NAN, int n = 0, double fees = 0, double pnl = 0) {
          L.trades << d << "," << v << "," << f.F << "," << f.straddle << "," << c << "," << c - f.K << "," << cr << "," << ml << "," << n << "," << fees << "," << settle << "," << pnl << "," << (n ? pnl / (n * 100 * ml) : NAN) << "," << st << "\n"; };
        if (!std::isfinite(c)) { row("no_pin"); continue; }
        if (!fl) { row("no_quotes"); continue; }
        double w = std::max(5.0, 1.5 * f.straddle);
        auto cw = nearest(*fl, d, 'C', c + w), pw = nearest(*fl, d, 'P', c - w);
        if (!cw || !pw || cw->k <= c || pw->k >= c) { row("no_wing"); continue; }
        std::vector<Leg> legs = {{c, 'C', -1}, {c, 'P', -1}, {cw->k, 'C', 1}, {pw->k, 'P', 1}};
        double credit = 0; int cap = 1 << 30; bool ok = true;
        for (auto& l : legs) { auto q = snap.find(d, tau, 2000, "SPXW", d, l.k, l.cp); double p = fill_px(q, l.side); if (!std::isfinite(p)) { ok = false; break; } credit -= l.side * p; cap = std::min(cap, disp(q, l.side)); }
        if (!ok) { row("leg_unfilled"); continue; }
        double ml = std::max(legs[2].k - c, c - legs[3].k) - credit;
        if (credit <= 0 || ml <= 0) { row("bad_price", credit, ml); continue; }
        int n = std::min<int>(int(0.005 * E0 / (ml * 100)), cap);
        if (n < 1) { row("size_lt1", credit, ml); continue; }
        double fees = 4 * n * opt_fee("SPXW"), pnl = n * 100 * (credit + payoff(legs, settle)) - fees;
        L.add(v, d, pnl); row("filled", credit, ml, n, fees, pnl);
      }
    }
  }
  L.write_daily(S, S.d.front(), S.d.back());
  std::cerr << "s7 done\n";
}
