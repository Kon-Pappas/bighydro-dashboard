import sys, os, io, json, math, tempfile, contextlib, shutil
from datetime import date, timedelta
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_inflow as B
import build_water_balance as W
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
def pct(v, p):
    v = sorted(v); i = (len(v) - 1) * p; lo = int(i); hi = min(lo + 1, len(v) - 1); return v[lo] + (v[hi] - v[lo]) * (i - lo)

CUR_END = date(2026, 4, 12)
class World:
    """Κόσμος γνωστής αλήθειας: εισροή I(d) και παραγωγή Q(d) (hm³/ημέρα) ορισμένες, V(d+1)=V(d)+I−Q ολοκληρώνεται, και τα αρχεία γράφονται όπως τα διαβάζει το build_inflow.
    Η σωστή εβδομαδιαία εισροή = ΣI της εβδομάδας. Το Q έχει εβδομαδιαίο ρυθμό (καθημερινές ψηλά, Σαββατοκύριακο χαμηλά) ώστε η γραμμική παρεμβολή ΟΓΚΟΥ να είναι αισθητά χειρότερη."""
    def __init__(self, rid="ladonas", y0=2016, y1=2025, cur_scale=None, drop_fill=(), drop_gen=(), dst_day=None, short_hist=None, cap=200.0):
        self.rid = rid; self.dir = tempfile.mkdtemp(); self.cap = cap
        groups = W.GROUPS[rid]; self.dams = [k for g, _a, _b in groups for k in g]; self.outs = [g[-1] for g, _a, _b in groups]
        self.unit = {"ladonas": "Ladonas", "aliakmonas": "Asomata", "arachthos": "Pournari2"}[rid]
        self.heads = {k: {"GrossHeadM": 200.0, "EtaMin": 0.9, "EtaMax": 0.9} for k in self.outs}; self.ratio = 1.1
        self.K = W.k_values(self.heads, self.outs, self.ratio)[0][self.outs[-1]]
        self.scale = lambda y: (cur_scale if (y == 2026 and cur_scale is not None) else 1 + 0.1 * (y - 2017))
        self.drop_fill, self.drop_gen = set(drop_fill), set(drop_gen)
        self.I, self.Q, self.V = {}, {}, {}
        d, v = date(2016, 1, 1), 100.0
        while d <= CUR_END + timedelta(days=1):
            sc = self.scale(d.year); i = sc * (1 + 0.2 * math.sin(2 * math.pi * d.timetuple().tm_yday / 365.25))
            q = sc * (1 + (0.35 if d.weekday() < 5 else -0.875))
            self.I[d], self.Q[d], self.V[d] = i, q, v; v += i - q; d += timedelta(days=1)
        meta = {"Schema": "1", "Rivers": [{"Id": rid, "Name": rid, "Order": self.dams, "Pump": None}],
                "Reservoirs": {k: {"CapacityHm3": (cap if k == self.dams[0] else 100.0), "Units": [self.unit if k == self.outs[-1] else "x_" + k]} for k in self.dams}}
        os.makedirs(self.dir + "/data/history"); os.makedirs(self.dir + "/data/days")
        json.dump(meta, open(self.dir + "/data/reservoirs.json", "w")); json.dump({"Plants": self.heads, "GrossToNetRatio": self.ratio}, open(self.dir + "/data/plant_heads.json", "w"))
        for y in range(y0, y1 + 1):
            if short_hist and y < short_hist: continue
            ds = []; d = date(y, 1, 1)
            while d.year == y: ds.append(d); d += timedelta(days=1)
            fill = {k: [None if x in self.drop_fill else self.pct(k, x) for x in ds] for k in self.dams}
            json.dump({"Dates": [x.isoformat() for x in ds], "Fill": fill, "Gen": {self.unit: [None if x in self.drop_gen else self.Q[x] * self.K for x in ds]}}, open(f"{self.dir}/data/history/admie_{y}.json", "w"))
        d = date(2026, 1, 1)
        while d <= CUR_END:
            rec = {"Date": d.isoformat(), "Meta": {"Status": {"scada": "missing" if d in self.drop_gen else "ok"}}}
            if d not in self.drop_fill: rec["Reservoir"] = {k: self.pct(k, d) for k in self.dams}
            if d not in self.drop_gen:
                e = self.Q[d] * self.K; n = 23 if d == dst_day else 24
                rows = [{"Hour": f"H{h+1:02d}", "SCADA_" + self.unit: (e / n if not (n == 23 and h == 3) else None)} for h in range(24)]
                rec["Hourly"] = rows
                if n == 23: rec["Meta"]["ClockChange"] = {"Hours": 23, "Hour": "H04", "Kind": "missing", "ExtraHourMWh": {}}
            json.dump(rec, open(f"{self.dir}/data/days/{d.isoformat()}.json", "w")); d += timedelta(days=1)
    def pct(self, dam, d):
        return (self.V[d] / self.cap * 100.0) if dam == self.dams[0] else 50.0
    def truth(self, monday): return sum(self.I[monday + timedelta(days=i)] for i in range(7))
    def run(self):
        os.chdir(self.dir); rc, lg = cap(B.main)
        return rc, lg, (json.load(open("data/inflow_climatology.json", encoding="utf-8")) if os.path.exists("data/inflow_climatology.json") else None)
def cur(doc, rid, monday): return next((r for r in doc["Rivers"][rid]["Current"] if r["Start"] == monday.isoformat()), None)
M = lambda y, m, d: date(y, m, d)

print("TEST 1: the weekly inflow of a full series equals the truth (definition: V(next Monday) − V(Monday) + ΣQ)")
w = World(); rc, lg, doc = w.run(); R = doc["Rivers"]["ladonas"]
check("rc 0 and one river written", rc == 0 and list(doc["Rivers"]) == ["ladonas"], lg[-200:])
mondays = [M(2026, 1, 5), M(2026, 1, 12), M(2026, 2, 16), M(2026, 3, 2), M(2026, 3, 30)]
check("current-year weeks (incl. the 23-hour-free days of March) equal the truth to 0.01 hm³", all(cur(doc, "ladonas", m) and abs(cur(doc, "ladonas", m)["Mm3"] - w.truth(m)) < 0.011 for m in mondays), [(m, cur(doc, "ladonas", m), w.truth(m)) for m in mondays[:2]])
check("the week that starts in the previous calendar year (2025-12-29 = ISO 2026-W01) is a current-year week and is correct", cur(doc, "ladonas", M(2025, 12, 29)) and abs(cur(doc, "ladonas", M(2025, 12, 29))["Mm3"] - w.truth(M(2025, 12, 29))) < 0.011)
check("a full series needs no interpolation: no week is flagged", all(not r["Interp"] for r in R["Current"]) and R["Quality"]["BaselineWeeksInterpolated"] == 0)
check("the last week is the last COMPLETE week: the data end on Sun 12 Apr, and the week of 6 Apr needs the level of 13 Apr, so the last is 30 Mar", R["Current"][-1]["Start"] == "2026-03-30", R["Current"][-1])
print("TEST 2: gaps — inside the week costs nothing, on the boundary the flow-aware fill is exact, long gaps leave the week empty")
mon = M(2026, 2, 16)
w2 = World(drop_fill={mon + timedelta(days=i) for i in range(1, 6)}); _, _, d2 = w2.run()
check("5 days of missing levels INSIDE a week (the Mondays are known): the week is exact and not flagged", abs(cur(d2, "ladonas", mon)["Mm3"] - w2.truth(mon)) < 0.011 and not cur(d2, "ladonas", mon)["Interp"], cur(d2, "ladonas", mon))
for L in (1, 2, 3):
    gap = {mon + timedelta(days=7 + i - (L // 2)) for i in range(L)}                # το κενό καλύπτει τη Δευτέρα mon+7
    w3 = World(drop_fill=gap); _, _, d3 = w3.run(); a, b = cur(d3, "ladonas", mon), cur(d3, "ladonas", mon + timedelta(days=7))
    Vlin = None
    check(f"a {L}-day gap on the Monday between two weeks: both weeks present, flagged, and within 0.05 hm³ of the truth (flow-aware fill)",
          a and b and a["Interp"] and b["Interp"] and abs(a["Mm3"] - w3.truth(mon)) < 0.05 and abs(b["Mm3"] - w3.truth(mon + timedelta(days=7))) < 0.05, (a, b, w3.truth(mon), w3.truth(mon + timedelta(days=7))))
    check(f"…and the two weeks together keep the exact total (the gap only moves inflow between them)", abs(a["Mm3"] + b["Mm3"] - w3.truth(mon) - w3.truth(mon + timedelta(days=7))) < 0.011)
# η απλή γραμμική παρεμβολή ΟΓΚΟΥ θα έκανε μεγαλύτερο λάθος: το υπολογίζω ανεξάρτητα στον κόσμο της δοκιμής
Lg = 3; gap = {mon + timedelta(days=7 + i - 1) for i in range(Lg)}; p, n = min(gap) - timedelta(days=1), max(gap) + timedelta(days=1)
V0, V1 = w.V[p], w.V[n]; vlin = V0 + (V1 - V0) * ((mon + timedelta(days=7) - p).days) / ((n - p).days); err_lin = abs(vlin - w.V[mon + timedelta(days=7)])
w3 = World(drop_fill=gap); _, _, d3 = w3.run(); err_flow = abs(cur(d3, "ladonas", mon)["Mm3"] - w3.truth(mon))
check("the flow-aware fill is at least 5× more accurate than linear interpolation of the volume in this world", err_flow * 5 < err_lin, (err_flow, err_lin))
w4 = World(drop_fill={mon + timedelta(days=7 + i - 1) for i in range(4)}); _, _, d4 = w4.run()
check("a 4-day gap on the Monday is NOT filled: neither adjacent week has a value", cur(d4, "ladonas", mon) is None and cur(d4, "ladonas", mon + timedelta(days=7)) is None)
check("…and the weeks before and after them are untouched", abs(cur(d4, "ladonas", mon - timedelta(days=7))["Mm3"] - w4.truth(mon - timedelta(days=7))) < 0.011 and abs(cur(d4, "ladonas", mon + timedelta(days=14))["Mm3"] - w4.truth(mon + timedelta(days=14))) < 0.011)
w5 = World(drop_gen={mon + timedelta(days=2), mon + timedelta(days=3)}); _, _, d5 = w5.run()
check("2 days of missing generation inside a week: the week is present and flagged as interpolated", cur(d5, "ladonas", mon) and cur(d5, "ladonas", mon)["Interp"], cur(d5, "ladonas", mon))
w6 = World(drop_gen={mon + timedelta(days=i) for i in range(1, 5)}); _, _, d6 = w6.run()
check("4 days of missing generation: the week is empty (generation is not invented beyond 3 days)", cur(d6, "ladonas", mon) is None)
w7 = World(drop_fill={mon + timedelta(days=7)}, drop_gen={mon + timedelta(days=5), mon + timedelta(days=6), mon + timedelta(days=7), mon + timedelta(days=8)}); _, _, d7 = w7.run()
check("a level gap needs the generation of the gap days: with a 4-day generation gap the level is NOT reconstructed", cur(d7, "ladonas", mon) is None and cur(d7, "ladonas", mon + timedelta(days=7)) is None)
w8 = World(dst_day=M(2026, 3, 29)); _, _, d8 = w8.run()
check("the 23-hour day (29 Mar 2026: H04 empty) is used with the energy of its 23 real hours: the week is exact", abs(cur(d8, "ladonas", M(2026, 3, 23))["Mm3"] - w8.truth(M(2026, 3, 23))) < 0.011 and not cur(d8, "ladonas", M(2026, 3, 23))["Interp"], cur(d8, "ladonas", M(2026, 3, 23)))
print("TEST 3: the baseline (2018–2025) and the alternative (2016–2025)")
base = {b["Wk"]: b for b in R["Weeks"]}; ext = {b["Wk"]: b for b in R["Extended"]}
def week_vals(world, wk, y0, y1): return [(world.truth(date.fromisocalendar(y, wk, 1)), y) for y in range(y0, y1 + 1)]
v = week_vals(w, 10, 2018, 2025); vv = [x for x, _y in v]
check("week 10: N = 8, P25 / median / P75 / min / max of the eight years", base[10]["N"] == 8 and abs(base[10]["P25"] - pct(vv, .25)) < 0.011 and abs(base[10]["Median"] - pct(vv, .5)) < 0.011 and abs(base[10]["P75"] - pct(vv, .75)) < 0.011 and abs(base[10]["Min"] - min(vv)) < 0.011 and abs(base[10]["Max"] - max(vv)) < 0.011, base[10])
check("the years of the minimum and the maximum are reported (scale grows with the year: 2018 lowest, 2025 highest)", base[10]["MinYear"] == 2018 and base[10]["MaxYear"] == 2025)
ve = [x for x, _y in week_vals(w, 10, 2016, 2025)]
check("the alternative baseline has 10 years, its own percentiles, and only the slim fields", ext[10]["N"] == 10 and abs(ext[10]["Median"] - pct(ve, .5)) < 0.011 and "Min" not in ext[10] and ext[10]["P25"] != base[10]["P25"])
check("ISO week 53 exists only in 2020 (N = 1 < 4): no band is given for it", 53 not in base and 53 not in ext)
check("the current year (2026) is NOT part of its own baseline", all(b["N"] <= 8 for b in R["Weeks"]))
fake = {date.fromisocalendar(y, 10, 1): (float(y), False) for y in range(2018, 2027)}        # 2018–2026: nine values for week 10
t_in = {b["Wk"]: b for b in B.band_table(fake, 2018, 2026, 2026)}
check("even if the baseline range is extended to include the current year, the current year is left out of its own baseline (guard checked directly)", t_in[10]["N"] == 8 and t_in[10]["Max"] == 2025.0 and t_in[10]["MaxYear"] == 2025, t_in[10])
c10 = cur(doc, "ladonas", date.fromisocalendar(2026, 10, 1))
check("a current week carries its rank (1 = highest) among the 9 values and its difference from the median", c10["Of"] == 9 and 1 <= c10["Rank"] <= 9 and abs(c10["DeltaMedian"] - (c10["Mm3"] - base[10]["Median"])) < 0.011, c10)
print("TEST 4: the regime — the two highest of nine are wet, the two lowest dry, the rest transitional")
def regime_for(scale, **kw):
    ww = World(cur_scale=scale, **kw); _, _, dd = ww.run(); return dd["Rivers"][ww.rid]["Regime"], dd, ww
scales = {y: 1 + 0.1 * (y - 2017) for y in range(2018, 2026)}                  # 1.1 … 1.8
for name, sc, want in (("far below every baseline year", 0.3, "dry"), ("between the 2nd and 3rd lowest years", 1.25, "transitional"), ("between the lowest two years", 1.15, "dry"),
                       ("between the 3rd and 2nd highest years", 1.55, "transitional"), ("between the two highest years", 1.75, "wet"), ("far above every baseline year", 3.0, "wet")):
    g, _d, _w = regime_for(sc)
    check(f"current inflow {name} -> {want}", g and g["Regime"] == want and g["Of"] == 9 and g["N"] == 8, g)
g, dd, ww = regime_for(0.3)
check("the regime lists the 4 weeks it is based on, ending at the last complete week, and the sum of their inflows", g["LastWeek"] == "2026-03-30" and g["Weeks"][-1] == "2026-03-30" and len(g["Weeks"]) == 4 and abs(g["Mm3"] - sum(ww.truth(date.fromisoformat(x)) for x in g["Weeks"])) < 0.02, g)
check("the regime carries the alternative-baseline result (10 years)", g["Extended"]["Of"] == 11 and g["Extended"]["N"] == 10 and g["Extended"]["Regime"] == "dry", g.get("Extended"))
g_top, _d, _w = regime_for(3.0); check("rank 1 = the highest inflow", g_top["Rank"] == 1 and g["Rank"] == 9)
g_few, d_few, _w = regime_for(1.0, short_hist=2022); R_few = d_few["Rivers"]["ladonas"]
check("fewer than 6 baseline years -> no regime, with the reason; the bands (N ≥ 4) are still given", g_few is None and R_few["RegimeUnavailable"] == "few_years" and len(R_few["Weeks"]) > 40, R_few["RegimeUnavailable"])
wst = World(cur_scale=1.0, drop_gen={CUR_END - timedelta(days=i) for i in range(0, 20)}); _, _, dst = wst.run()
check("the latest complete week is more than 10 days older than the last data -> no regime (stale)", dst["Rivers"]["ladonas"]["Regime"] is None and dst["Rivers"]["ladonas"]["RegimeUnavailable"] == "stale", dst["Rivers"]["ladonas"]["RegimeUnavailable"])
wgp = World(cur_scale=1.0, drop_gen={date(2026, 3, 17) + timedelta(days=i) for i in range(5)}); _, _, dgp = wgp.run()          # 5 days without generation inside the week of 16 Mar
check("one of the 4 weeks is empty while the later weeks are valid -> no regime (gap)", dgp["Rivers"]["ladonas"]["Regime"] is None and dgp["Rivers"]["ladonas"]["RegimeUnavailable"] == "gap", dgp["Rivers"]["ladonas"]["RegimeUnavailable"])
wit = World(cur_scale=1.0, drop_fill={date(2026, 3, 30)}); _, _, dit = wit.run()
check("the regime says when one of its weeks relied on interpolation", dit["Rivers"]["ladonas"]["Regime"]["Interp"] is True)
print("TEST 5: rivers with their own rules — Aliakmon (Ilarionas sensitivity, no Ilarionas before 2018-05) and Arachthos (low confidence)")
wa = World("aliakmonas", cur_scale=1.0); rca, lga, da = wa.run(); RA = da["Rivers"]["aliakmonas"]
check("Aliakmon is computed on the Ilarionas–Polyfyto–Sfikia–Asomata system with Asomata as the exit unit", rca == 0 and RA["ExitUnit"] == "Asomata" and RA["Dams"] == ["ILARIONAS", "POLYFYTO", "SFIKIA", "ASOMATA"], (RA["ExitUnit"], RA["Dams"]))
S = RA["Sensitivity"]
check("the Ilarionas sensitivity states the capacity used (412 here as in the metadata) and the alternative (305)", S and S["Used"] == 200.0 and S["IlarionasHm3"] == 305.0 and "Regime" in S, S)
g_a = RA["Regime"]; vol = lambda d: wa.V[d]
dv = sum(vol(date.fromisoformat(x) + timedelta(days=7)) - vol(date.fromisoformat(x)) for x in g_a["Weeks"])
check("with the alternative capacity only the Ilarionas volume change is rescaled: Mm3(305) = Mm3 − (1 − 305/cap)·ΔV_Ilarionas", abs(S["Mm3"] - (g_a["Mm3"] - (1 - 305.0 / 200.0) * dv)) < 0.02, (S["Mm3"], g_a["Mm3"], dv))
check("the metadata of this test uses a capacity of 200 for the Ilarionas stand-in, so « Used » follows reservoirs.json (no number is hard-coded)", S["Used"] == 200.0)
wb = World("arachthos", cur_scale=1.0); _, _, db = wb.run(); RB = db["Rivers"]["arachthos"]
check("Arachthos carries the low-confidence note (Greek and English); the other rivers do not", RB["LowConfidence"] and "El" in RB["LowConfidence"] and "En" in RB["LowConfidence"] and R["LowConfidence"] is None)
check("Arachthos uses Pournari II as the exit unit (estimated head)", RB["ExitUnit"] == "Pournari2" and RB["Dams"] == ["P_AOOU", "POYRNARI1", "POYRNARI2"])
print("TEST 6: the file, the failures, no needless rewrite")
os.chdir(w.dir); b1 = open("data/inflow_climatology.json", "rb").read(); import time; time.sleep(1.1); rc, _ = cap(B.main); b2 = open("data/inflow_climatology.json", "rb").read()
check("a second run with the same inputs leaves the file byte-for-byte unchanged (no timestamp refresh)", rc == 0 and b1 == b2)
check("the document names the baselines, the rule and the method", doc["Baseline"]["Years"] == [2018, 2025] and doc["Baseline"]["Extended"] == [2016, 2025] and doc["Rule"]["Extreme"] == 2 and doc["Rule"]["MaxGapDays"] == 3 and doc["CurrentYear"] == 2026)
os.remove("data/plant_heads.json"); rc, lg = cap(B.main); check("a missing input file -> rc 1 and a message", rc == 1 and "plant_heads" in lg)
w9 = World(); os.chdir(w9.dir); open("data/history/admie_2019.json", "w").write("{ broken"); rc, lg = cap(B.main)
check("a corrupt history file is reported and skipped; the rest is still computed", rc == 0 and "admie_2019.json" in lg)
w10 = World(); os.chdir(w10.dir); shutil.rmtree("data/history"); shutil.rmtree("data/days"); os.makedirs("data/days"); rc, lg = cap(B.main)
check("no data at all -> rc 1 and no file", rc == 1 and not os.path.exists("data/inflow_climatology.json"))
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
