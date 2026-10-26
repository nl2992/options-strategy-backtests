// S1 pre-earnings premium | S2 earnings-announcement-return drift | S4 pre-announcement option flow.
// All: stock leg + SPY beta hedge, auction/official-close fills, marked daily (wave3/PREREGISTRATION.md).
#include "w3.hpp"

static const std::vector<std::string> NAMES = {"AAPL", "TSLA", "AMD", "AMZN", "AVGO", "CRM", "GOOGL", "JPM", "LLY", "NFLX", "UNH", "MSFT", "NVDA", "WMT", "XOM"};

int main() {
  Sessions S; cut(S); Equity E;
  std::map<std::pair<std::string, int>, std::array<double, 2>> flow;  // (root,date) -> {num_all, den_all}
  { auto f = load("w3_flow"); int a = f.c("num_all"), b = f.c("den_all");
    for (auto& r : f.rows) flow[{r[0], std::stoi(r[1])}] = {num(r[a]), num(r[b])}; }
  auto ev = load("ctx_earnings");
  Ledger L("s_events", "strategy,variant,ticker,announce,amc,signal,beta,d_in,when_in,d_out,when_out,r_stock,r_spy,r_hedged,status");
  std::map<std::string, Book*> books;
  auto book = [&](const std::string& v) { if (!books.count(v)) books[v] = new Book(E, S, L, v); return books[v]; };
  auto px = [&](const std::string& s, int d, When w) { return book("_px")->px(s, d, w); };
  for (auto& e : ev.rows) {
    std::string tk = e[0]; int A = std::stoi(e[1]); bool amc = e[2] == "1";
    if (std::find(NAMES.begin(), NAMES.end(), tk) == NAMES.end()) continue;
    int xi = -1, yi = -1;  // X = last session before the announcement, Y = first session after it
    for (size_t i = 0; i < S.d.size(); ++i) { if (amc ? S.d[i] <= A : S.d[i] < A) xi = int(i); if (yi < 0 && (amc ? S.d[i] > A : S.d[i] >= A)) yi = int(i); }
    if (xi < 61 || yi < 0) continue;
    // one trade = (strategy, variant, entry index/when, exit index/when, direction, hedged?)
    struct T { std::string st, v; int i0; When w0; int i1; When w1; double dir; bool hedge; double sig; };
    std::vector<T> ts;
    // --- S1: long into the announcement, out before it ---
    ts.push_back({"S1", "S1_hedged_5", xi - 5, CLOSE, xi, CLOSE, 1, true, NAN});
    ts.push_back({"S1", "S1_unhedged_5", xi - 5, CLOSE, xi, CLOSE, 1, false, NAN});
    if (xi >= 71) ts.push_back({"S1", "S1_hedged_10", xi - 10, CLOSE, xi, CLOSE, 1, true, NAN});
    // --- S2: sign of the announcement-window abnormal return, entered at the next open (known at Y's close) ---
    double b = beta60(E, S, tk, xi);
    double ear = cc_ret(E, tk, S.d[xi], S.d[yi]) - b * cc_ret(E, "SPY", S.d[xi], S.d[yi]);
    if (std::isfinite(ear) && ear != 0) {
      double dir = ear > 0 ? 1 : -1;
      ts.push_back({"S2", "S2_hedged_h20", yi + 1, OPEN, yi + 20, CLOSE, dir, true, ear});
      if (std::abs(ear) > 0.02) ts.push_back({"S2", "S2_big2_h20", yi + 1, OPEN, yi + 20, CLOSE, dir, true, ear});
      ts.push_back({"S2", "S2_hedged_h40", yi + 1, OPEN, yi + 40, CLOSE, dir, true, ear});
    }
    // --- S4: option flow over X-5..X-1, enter at X close, exit at the first open after the announcement ---
    double nu = 0, de = 0;
    for (int j = xi - 5; j < xi; ++j) if (auto it = flow.find({tk, S.d[j]}); it != flow.end() && std::isfinite(it->second[0])) { nu += it->second[0]; de += it->second[1]; }
    if (de > 0 && nu != 0) ts.push_back({"S4", "S4_hedged", xi, CLOSE, yi, OPEN, nu > 0 ? 1.0 : -1.0, true, nu / de});
    for (auto& t : ts) {
      if (t.i1 >= int(S.d.size()) || t.i0 < 1) continue;
      int d0 = S.d[t.i0], d1 = S.d[t.i1];
      auto row = [&](const std::string& st, double rs = NAN, double rm = NAN, double rh = NAN) {
        L.trades << t.st << "," << t.v << "," << tk << "," << A << "," << amc << "," << t.sig << "," << b << "," << d0 << "," << t.w0 << "," << d1 << "," << t.w1
                 << "," << rs << "," << rm << "," << rh << "," << st << "\n"; };
      // --- portfolio: 10% of equity at the prior close; hedge = -beta x notional in SPY ---
      auto prev = E.day.find({tk, S.d[t.i0 - 1]}), sprev = E.day.find({"SPY", S.d[t.i0 - 1]});
      if (prev == E.day.end() || sprev == E.day.end()) { row("no_price"); continue; }
      double sh = std::floor(0.10 * E0 / prev->second.close_raw) * t.dir;
      double hs = t.hedge ? -std::round(b * std::abs(sh) * prev->second.close_raw / sprev->second.close_raw) * t.dir : 0;
      // event-level return at the same fill prices the book will use (missed open -> same-day close)
      auto fp = [&](const std::string& s, int d, When w) { double p = px(s, d, w); return std::isfinite(p) || w == CLOSE ? p : px(s, d, CLOSE); };
      double rs = E.ret(tk, d0, fp(tk, d0, t.w0), d1, fp(tk, d1, t.w1)), rm = E.ret("SPY", d0, fp("SPY", d0, t.w0), d1, fp("SPY", d1, t.w1));
      if (!std::isfinite(rs) || (t.hedge && !std::isfinite(rm))) { row("no_fill"); continue; }
      Book* B = book(t.v);
      B->order(d0, t.w0, tk, sh); B->order(d1, t.w1, tk, -sh);
      if (t.hedge) { B->order(d0, t.w0, "SPY", hs); B->order(d1, t.w1, "SPY", -hs); }
      row("filled", rs, rm, t.dir * (rs - (t.hedge ? b * rm : 0)));
    }
  }
  int miss = 0;
  for (auto& [v, B] : books) if (v != "_px") miss += B->run();
  L.write_daily(S, S.d[61], S.d.back());
  std::cerr << "s_events done, unfilled orders " << miss << "\n";
}
