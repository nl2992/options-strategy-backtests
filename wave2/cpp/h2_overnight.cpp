// H2: short delta-hedged ATM straddle in SPY/QQQ, overnight (15:58 -> 09:33 next session) vs intraday (09:33 -> 15:58).
// Options and stock hedge both fill T2 against the first post-arrival NBBO.
// rule "orig": pre-registered contract (first expiry DTE>=7, parity strike). rule "a1": amendment A1 (see prereg).
#include "common.hpp"

constexpr long OPEN = 34380000, CLOSE = 57480000;  // 09:33, 15:58

struct Pick { int exp = 0; double k = NAN, F = NAN; };
static Pick pick_orig(const std::vector<Q>& pre, const std::string& root, int d0) {
  Pick p; for (auto& q : pre) if (q.root == root && days_between(d0, q.exp) >= 7 && (!p.exp || q.exp < p.exp)) p.exp = q.exp;
  if (p.exp) { Fwd f = forward(pre, root, p.exp); p.k = f.K; p.F = f.F; }
  return p;
}
// A1: among expiries with DTE in [7,21], the strike with both legs quoted post-arrival that is closest to its parity forward
static Pick pick_a1(const Snaps& s, const std::vector<Q>& pre, const std::string& root, int d0, long t0, int lat) {
  Pick best; double bd = 0.01; auto fl = s.get(d0, t0, lat); if (!fl) return best;
  std::map<int, Fwd> fw;
  for (auto& q : pre) if (q.root == root && days_between(d0, q.exp) >= 7 && days_between(d0, q.exp) <= 21 && !fw.count(q.exp)) fw[q.exp] = forward(pre, root, q.exp);
  for (auto& q : *fl) {
    if (q.root != root || q.cp != 'C' || !fw.count(q.exp) || !std::isfinite(fw[q.exp].F)) continue;
    if (!std::isfinite(fill_px(&q, -1)) || !std::isfinite(fill_px(s.find(d0, t0, lat, root, q.exp, q.k, 'P'), -1))) continue;
    double dd = std::abs(q.k / fw[q.exp].F - 1);
    if (dd <= bd) { bd = dd; best = {q.exp, q.k, fw[q.exp].F}; }
  }
  return best;
}

int main() {
  Sessions S; Snaps opt("h2_etf_"), eq("eq_snap_", true);
  Ledger L("h2", "variant,root,d0,d1,exp,k,S0,iv,delta,gamma,n,premium,opt_entry,opt_exit,hedge_sh,hedge_pnl,opt_pnl,fees,pnl,ret_on_premium,exit_size_short,status");
  int first = 99999999, last = 0;
  for (size_t i = 0; i + 1 < S.d.size(); ++i) {
    for (std::string leg : {"overnight", "intraday"}) {
      int d0 = leg == "overnight" ? S.d[i] : S.d[i + 1], d1 = S.d[i + 1];
      long t0 = leg == "overnight" ? CLOSE : OPEN, t1 = leg == "overnight" ? OPEN : CLOSE;
      bool weekend = days_between(S.d[i], S.d[i + 1]) > 1;
      double r = 252 * (std::isfinite(S.rf[i]) ? S.rf[i] : 0);
      for (std::string root : {"SPY", "QQQ"}) {
        auto pre = opt.get(d0, t0, -1); if (!pre) continue;
        first = std::min(first, d0); last = std::max(last, d1);
        for (std::string rule : {"orig", "a1"}) for (int lat : {500, 2000, 10000}) for (double fm : {1.0, 2.0}) {
          if (fm == 2 && lat != 2000) continue;
          std::string tag = (rule == "a1" ? "a1_" : "") + std::string("_L") + std::to_string(lat) + (fm == 2 ? "_fee2" : "");
          std::string v = (rule == "a1" ? "a1_" : "") + leg + "_L" + std::to_string(lat) + (fm == 2 ? "_fee2" : "");
          // --- contract selection at t0 (information known at arrival) ---
          Pick p = rule == "orig" ? pick_orig(*pre, root, d0) : pick_a1(opt, *pre, root, d0, t0, lat);
          auto out = [&](const std::string& st, std::vector<double> x = {}) {
            x.resize(15, NAN);
            L.trades << v << "," << root << "," << d0 << "," << d1 << "," << p.exp << "," << p.k;
            for (double y : x) L.trades << "," << y;
            L.trades << "," << st << "\n"; };
          if (!p.exp || !std::isfinite(p.k)) { out("no_contract"); continue; }
          auto c0 = opt.find(d0, t0, lat, root, p.exp, p.k, 'C'), p0 = opt.find(d0, t0, lat, root, p.exp, p.k, 'P');
          auto c1 = opt.find(d1, t1, lat, root, p.exp, p.k, 'C'), p1 = opt.find(d1, t1, lat, root, p.exp, p.k, 'P');
          bool chase = false;
          if (rule == "a1" && !std::isfinite(fill_px(c1, 1) + fill_px(p1, 1))) {  // A1 exit chase: up to 120 s
            if (!std::isfinite(fill_px(c1, 1))) c1 = opt.find(d1, t1, 99999, root, p.exp, p.k, 'C');
            if (!std::isfinite(fill_px(p1, 1))) p1 = opt.find(d1, t1, 99999, root, p.exp, p.k, 'P');
            chase = true;
          }
          auto e0 = eq.find(d0, t0, lat, root), e1 = eq.find(d1, t1, lat, root);
          double sc = fill_px(c0, -1), sp = fill_px(p0, -1), bc = fill_px(c1, 1), bp = fill_px(p1, 1);
          if (!std::isfinite(sc + sp)) { out("entry_unfilled"); continue; }
          if (!std::isfinite(bc + bp)) { out("exit_unfilled"); continue; }
          if (!e0 || !e1) { out("no_stock_quote"); continue; }
          // --- hedge ratio and sizing from entry mids ---
          double S0 = (e0->bid + e0->ask) / 2, T = (days_between(d0, p.exp) + (t0 == CLOSE ? 0.0 : 0.27)) / 365.0;
          double ivc = implied_vol(c0->mid(), S0, p.k, T, r, 'C'), ivp = implied_vol(p0->mid(), S0, p.k, T, r, 'P');
          double iv = std::isfinite(ivc) && std::isfinite(ivp) ? (ivc + ivp) / 2 : std::isfinite(ivc) ? ivc : ivp;
          if (!std::isfinite(iv)) { out("no_iv"); continue; }
          double delta = bs_delta(S0, p.k, T, r, iv, 'C') + bs_delta(S0, p.k, T, r, iv, 'P');  // per share, long straddle
          double gamma = 2 * bs_gamma(S0, p.k, T, r, iv);
          int n = int(0.005 * E0 / (0.5 * gamma * std::pow(0.03 * S0, 2) * 100));
          n = std::min({n, disp(c0, -1), disp(p0, -1)});
          if (n < 1) { out("size_lt1"); continue; }
          int exit_short = std::max(0, n - std::min(disp(c1, 1), disp(p1, 1)));  // diagnostic: exit size above displayed
          long sh = std::lround(n * 100 * delta);  // short straddle delta -n*100*delta -> hedge +sh shares
          double h0 = sh > 0 ? e0->ask : e0->bid, h1 = sh > 0 ? e1->bid : e1->ask;
          double hedge_pnl = sh * (h1 - h0);
          double prem = sc + sp, opt_pnl = n * 100 * (prem - (bc + bp));
          double fees = 4 * n * fee_opt(root, fm) + 2 * std::labs(sh) * FEE_SH * fm;
          double pnl = opt_pnl + hedge_pnl - fees;
          L.add(v, d1, pnl);
          if (leg == "overnight" && weekend) L.add((rule == "a1" ? "a1_" : "") + std::string("weekend") + tag.substr(rule == "a1" ? 3 : 0), d1, pnl);
          out(std::string(weekend ? "filled_weekend" : "filled") + (chase ? "_chase" : ""),
              {S0, iv, delta, gamma, double(n), prem, sc + sp, bc + bp, double(sh), hedge_pnl, opt_pnl, fees, pnl, pnl / (n * 100 * prem), double(exit_short)});
        }
      }
    }
  }
  L.write_daily(S, first, last);
  // self-check: ATM straddle delta ~ 0, IV round-trips
  assert(std::abs(bs_delta(100, 100, .1, 0, .2, 'C') + bs_delta(100, 100, .1, 0, .2, 'P') - 0.025) < 0.01);
  assert(std::abs(implied_vol(bs(100, 100, .1, .02, .25, 'P'), 100, 100, .1, .02, 'P') - .25) < 1e-6);
  std::cerr << "h2 done\n";
}
