// H1: short 0DTE SPXW iron fly / condor at fixed times, held to PM cash settlement (T2 entry, T0 exit).
#include "common.hpp"

struct Leg { double k; char cp; int side; };  // side: -1 short, +1 long
static double payoff(const std::vector<Leg>& legs, double S) {
  double x = 0; for (auto& l : legs) x += l.side * (l.cp == 'C' ? std::max(S - l.k, 0.) : std::max(l.k - S, 0.)); return x;
}
// listed strike in the snapshot nearest to target (same expiry/right)
static const Q* nearest(const std::vector<Q>& v, int exp, char cp, double target) {
  const Q* b = nullptr; for (auto& q : v) if (q.exp == exp && q.cp == cp && (!b || std::abs(q.k - target) < std::abs(b->k - target))) b = &q; return b;
}

int main() {
  Sessions S; Snaps snap("h1_spxw0dte_");
  Ledger L("h1", "date,variant,tau,lat,F,straddle,implied_move,legs,credit,max_loss,n,fees,settle,pnl,ret_on_risk,status");
  const long TAUS[] = {36000000, 43200000, 50400000, 54000000};
  std::map<long, std::vector<double>> realized;  // tau -> past realized moves (for the VRP filter, prior days only)
  int first = 99999999, last = 0;
  for (size_t si = 0; si < S.d.size(); ++si) {
    int d = S.d[si]; double settle = S.spx[si];
    for (long tau : TAUS) {
      auto pre = snap.get(d, tau, -1); if (!pre) continue;
      first = std::min(first, d); last = std::max(last, d);
      // --- signal inputs known at tau ---
      Fwd f = forward(*pre, "SPXW", d);
      if (!std::isfinite(f.F)) continue;
      double move = f.straddle / f.F;
      auto& hist = realized[tau];
      double med = NAN;
      if (hist.size() >= 10) { std::vector<double> h(hist.end() - std::min<size_t>(20, hist.size()), hist.end()); std::nth_element(h.begin(), h.begin() + h.size() / 2, h.end()); med = h[h.size() / 2]; }
      for (int lat : {500, 2000, 10000}) for (std::string kind : {"fly", "ic"}) for (int vrp : {0, 1}) for (double fm : {1.0, 2.0}) {
        bool primary_family = (tau == 43200000 && lat == 2000);
        if (kind == "ic" && !(primary_family && !vrp && fm == 1)) continue;   // condor: one secondary
        if (vrp && !(primary_family && kind == "fly" && fm == 1)) continue;    // VRP filter: one secondary
        if (fm == 2 && !(primary_family && kind == "fly" && !vrp)) continue;   // fee stress on primary only
        char vn[96]; snprintf(vn, sizeof vn, "%s_t%02ld_L%d%s%s", kind.c_str(), tau / 3600000, lat, vrp ? "_vrp" : "", fm == 2 ? "_fee2" : "");
        std::string v = vn;
        auto fl = snap.get(d, tau, lat);
        auto out = [&](const std::string& st, const std::string& legs = "", double cr = NAN, double ml = NAN, int n = 0, double fees = 0, double pnl = 0) {
          L.trades << d << "," << v << "," << tau << "," << lat << "," << f.F << "," << f.straddle << "," << move << "," << legs << "," << cr << "," << ml << ","
                   << n << "," << fees << "," << settle << "," << pnl << "," << (n ? pnl / (n * 100 * ml) : NAN) << "," << st << "\n"; };
        if (vrp && !(std::isfinite(med) && move > med)) { out("filtered"); continue; }
        if (!fl) { out("no_quotes"); continue; }
        // --- portfolio construction: strikes ---
        std::vector<Leg> legs;
        if (kind == "fly") {
          double w = std::max(5.0, 1.5 * f.straddle);
          auto cw = nearest(*fl, d, 'C', f.K + w), pw = nearest(*fl, d, 'P', f.K - w);
          if (!cw || !pw || cw->k <= f.K || pw->k >= f.K) { out("no_wing"); continue; }
          legs = {{f.K, 'C', -1}, {f.K, 'P', -1}, {cw->k, 'C', 1}, {pw->k, 'P', 1}};
        } else {
          auto sc = nearest(*fl, d, 'C', f.F + f.straddle), sp = nearest(*fl, d, 'P', f.F - f.straddle);
          auto lc = nearest(*fl, d, 'C', f.F + 2 * f.straddle), lp = nearest(*fl, d, 'P', f.F - 2 * f.straddle);
          if (!sc || !sp || !lc || !lp || lc->k <= sc->k || lp->k >= sp->k) { out("no_wing"); continue; }
          legs = {{sc->k, 'C', -1}, {sp->k, 'P', -1}, {lc->k, 'C', 1}, {lp->k, 'P', 1}};
        }
        // --- execution: every leg must fill against its first post-arrival quote ---
        double credit = 0; int cap = 1 << 30; bool ok = true; std::string ls;
        for (auto& l : legs) {
          auto q = snap.find(d, tau, lat, "SPXW", d, l.k, l.cp);
          double px = fill_px(q, l.side);
          if (!std::isfinite(px)) { ok = false; break; }
          credit -= l.side * px; cap = std::min(cap, disp(q, l.side));
          ls += (l.side < 0 ? "-" : "+") + std::string(1, l.cp) + std::to_string(int(l.k)) + ";";
        }
        if (!ok) { out("leg_unfilled", ls); continue; }
        double maxloss = std::max(legs[2].k - legs[0].k, legs[1].k - legs[3].k) - credit;
        if (!(maxloss > 0) || credit <= 0) { out("bad_price", ls, credit, maxloss); continue; }
        // --- risk: max loss <= 0.5% equity, size <= displayed size of every leg ---
        int n = std::min<int>(int(0.005 * E0 / (maxloss * 100)), cap);
        if (n < 1) { out("size_lt1", ls, credit, maxloss); continue; }
        double fees = 4 * n * fee_opt("SPXW", fm);
        double pnl = n * 100 * (credit + payoff(legs, settle)) - fees;  // payoff = signed position value at expiry (<= 0)
        L.add(v, d, pnl); out("filled", ls, credit, maxloss, n, fees, pnl);
      }
      hist.push_back(std::abs(settle - f.F) / f.F);  // realized move appended after today's decisions
    }
  }
  L.write_daily(S, first, last);
  // self-check: short fly payoff at the short strike is zero, deep ITM loses the wing width
  std::vector<Leg> t = {{100, 'C', -1}, {100, 'P', -1}, {110, 'C', 1}, {90, 'P', 1}};
  assert(payoff(t, 100) == 0 && payoff(t, 130) == -10 && payoff(t, 80) == -10);
  std::cerr << "h1 done " << first << "-" << last << "\n";
}
