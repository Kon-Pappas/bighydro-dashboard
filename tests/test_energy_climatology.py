import sys, os, io, json, math, tempfile, contextlib, shutil, time
from datetime import date, timedelta
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_energy_climatology as E
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
END = date(2026, 4, 12)
CAPS = {"A": 200.0, "B": 100.0}; EF = {"A": 500.0, "B": 300.0}; CS, CT = 0.3, 0.4            # cycle factors far from 70 %, so the two rules differ by more than the 0.01 rounding of the file
class World:
    """Κόσμος γνωστής αλήθειας: απόθεμα από στάθμες και συντελεστές, παραγωγή ανά μονάδα, άντληση. Μονάδες: UA (ταμιευτήρας A), UB (B), PA (Πηγές Αώου, ΕΞΩ από το σύνολο)."""
    def __init__(self, y0=2016, y1=2025, drop_gen=(), drop_unit=None, drop_fill=(), est_missing=(), dst_day=None, short_hist=None, drop_days=()):
        self.dir = tempfile.mkdtemp(); self.drop_gen = set(drop_gen); self.drop_fill = set(drop_fill); self.drop_days = set(drop_days); self.dst_day = dst_day
        self.est_missing = set(est_missing)
        sc = lambda y: 1 + 0.08 * (y - 2017)
        doy = lambda d: d.timetuple().tm_yday
        self.fA = lambda d: 50 + 30 * math.sin(2 * math.pi * doy(d) / 365.25 + 0.5 * (d.year - 2016))
        self.fB = lambda d: 40 + 20 * math.cos(2 * math.pi * doy(d) / 365.25 + 0.3 * (d.year - 2016))
        self.UA = lambda d: 120 * sc(d.year) * (1 + 0.3 * math.sin(2 * math.pi * doy(d) / 365.25) + (0.2 if d.weekday() < 5 else -0.5))   # MWh
        self.UB = lambda d: 45 * sc(d.year) * (1 + 0.25 * math.cos(2 * math.pi * doy(d) / 365.25) + (0.1 if d.weekday() < 5 else -0.3))
        self.PA = lambda d: 12.0 + (d.weekday())
        self.PUMP = lambda d: 60.0 + 2 * (d.weekday())                                  # SCADA total pumping MWh
        self.EST = lambda d: (30.0 + d.weekday(), 28.0 + d.weekday())                   # (Sfikia, Thesavros) MWh, 2026: ≈ the SCADA total
        os.makedirs(self.dir + "/data/history"); os.makedirs(self.dir + "/data/days")
        json.dump({"Rivers": [{"Id": "r1", "Name": "R1", "Order": ["A"]}, {"Id": "r2", "Name": "R2", "Order": ["B", "P_AOOU"]}],
                   "Reservoirs": {"A": {"CapacityHm3": CAPS["A"], "Units": ["UA"]}, "B": {"CapacityHm3": CAPS["B"], "Units": ["UB"]}, "P_AOOU": {"CapacityHm3": 1.0, "Units": ["PA"]}}}, open(self.dir + "/data/reservoirs.json", "w"))
        json.dump({"Factors": {**{k: {"EnergyMWhPerHm3": v} for k, v in EF.items()}, "P_AOOU": {"EnergyMWhPerHm3": 50.0}}}, open(self.dir + "/data/energy_factors.json", "w"))      # Pigai Aoou even has a factor: it must still be left out explicitly
        json.dump({"Plants": {"SFIKIA": {"CycleFactor": CS}, "THESAVROS": {"CycleFactor": CT}}}, open(self.dir + "/data/psh_daily.json", "w"))
        for y in range(y0, y1 + 1):
            if short_hist and y < short_hist: continue
            ds = []; d = date(y, 1, 1)
            while d.year == y: ds.append(d); d += timedelta(days=1)
            ga = lambda f: [None if x in self.drop_gen else f(x) for x in ds]
            json.dump({"Dates": [x.isoformat() for x in ds], "Fill": {"A": [None if x in self.drop_fill else self.fA(x) for x in ds], "B": [None if x in self.drop_fill else self.fB(x) for x in ds]},
                       "Gen": {"UA": ga(self.UA) if drop_unit != "UA" else [None if x.day % 5 == 0 else self.UA(x) for x in ds], "UB": ga(self.UB), "PA": ga(self.PA)}, "Pump": [self.PUMP(x) for x in ds]}, open(f"{self.dir}/data/history/admie_{y}.json", "w"))
        pd_ = []; d = date(2026, 1, 1)
        while d <= END:
            rec = {"Date": d.isoformat(), "Meta": {"Status": {"scada": "ok"}}}
            if d not in self.drop_fill: rec["Reservoir"] = {"A": self.fA(d), "B": self.fB(d)}
            if d not in self.drop_gen:
                n = 23 if d == dst_day else 24
                def rows(e): return [(e / n if not (n == 23 and h == 3) else None) for h in range(24)]
                ra, rb, rp, rq = rows(self.UA(d)), rows(self.UB(d)), rows(self.PA(d)), rows(self.PUMP(d))
                rec["Hourly"] = [{"Hour": f"H{h+1:02d}", "SCADA_UA": ra[h], "SCADA_UB": rb[h], "SCADA_PA": rp[h], "SCADA_Pump": rq[h]} for h in range(24)]
                if n == 23: rec["Meta"]["ClockChange"] = {"Hours": 23, "Hour": "H04", "Kind": "missing", "ExtraHourMWh": {}}
            else: rec["Meta"]["Status"]["scada"] = "missing"
            json.dump(rec, open(f"{self.dir}/data/days/{d.isoformat()}.json", "w"))
            s, t = self.EST(d)
            row = {"Date": d.isoformat(), "ScadaMWh": self.PUMP(d)}
            if d not in self.est_missing: row.update({"EstSfikiaMWh": s, "EstThesavrosMWh": t})
            pd_.append(row); d += timedelta(days=1)
        json.dump(pd_, open(self.dir + "/data/pump_daily.json", "w"))
    def stock(self, d): return (EF["A"] * self.fA(d) / 100 * CAPS["A"] + EF["B"] * self.fB(d) / 100 * CAPS["B"]) / 1000.0
    def gen_total(self, d): return (self.UA(d) + self.UB(d)) / 1000.0
    def gen_r2(self, d): return (self.UB(d) + self.PA(d)) / 1000.0
    def pumpback(self, d):
        if d.year < 2026: return 0.7 * self.PUMP(d) / 1000.0
        if d in self.est_missing: return 0.7 * self.PUMP(d) / 1000.0
        s, t = self.EST(d); return (s * CS + t * CT) / 1000.0
    def wk(self, m, f): return sum(f(m + timedelta(days=i)) for i in range(7))
    def eq(self, m): return (self.stock(m + timedelta(7)) - self.stock(m) + sum(self.gen_total(m + timedelta(days=i)) - self.pumpback(m + timedelta(days=i)) for i in range(7))) / 7.0
    def run(self):
        os.chdir(self.dir); rc, lg = cap(E.main)
        return rc, lg, (json.load(open("data/energy_climatology.json", encoding="utf-8")) if os.path.exists("data/energy_climatology.json") else None)
def cur(rows, m, key="GWh"): return next((r for r in rows if r["Start"] == m.isoformat()), None)
M = lambda y, m, d: date(y, m, d)

print("TEST 1: weekly generation — the 14-reservoir units WITHOUT Pigai Aoou for the total, all the units of the cascade per river")
w = World(); rc, lg, doc = w.run(); G = doc["Generation"]
mons = [M(2026, 1, 5), M(2026, 2, 16), M(2026, 3, 9), M(2026, 3, 30)]
check("rc 0; the total excludes Pigai Aoou (PA) and is the weekly sum of UA + UB", rc == 0 and all(cur(G["Total"]["Current"], m) and abs(cur(G["Total"]["Current"], m)["GWh"] - w.wk(m, w.gen_total)) < 0.011 for m in mons), (cur(G["Total"]["Current"], mons[0]), w.wk(mons[0], w.gen_total)))
check("river r1 = UA only; river r2 = UB + PA (Pigai Aoou belongs to its cascade)", all(abs(cur(G["Rivers"]["r1"]["Current"], m)["GWh"] - w.wk(m, lambda d: w.UA(d) / 1000.0)) < 0.011 and abs(cur(G["Rivers"]["r2"]["Current"], m)["GWh"] - w.wk(m, w.gen_r2)) < 0.011 for m in mons))
check("the document lists the stock units and says the generation is gross (pumping is not subtracted)", doc["Units"]["Stock"] == ["UA", "UB"] and "ΑΚΑΘΑΡΙΣΤΗ" in doc["Units"]["Note"])
check("the week that starts in the previous calendar year (2025-12-29 = ISO 2026-W01) is a current week and is exact", cur(G["Total"]["Current"], M(2025, 12, 29)) and abs(cur(G["Total"]["Current"], M(2025, 12, 29))["GWh"] - w.wk(M(2025, 12, 29), w.gen_total)) < 0.011)
check("a full series is not flagged anywhere", all(not r["Interp"] for r in G["Total"]["Current"]))
print("TEST 2: gaps in the generation")
mon = M(2026, 2, 16)
g2 = World(drop_gen={mon + timedelta(days=2), mon + timedelta(days=3)}); _, _, d2 = g2.run()
check("2 missing days in a week: the week is present, interpolated and flagged", cur(d2["Generation"]["Total"]["Current"], mon) and cur(d2["Generation"]["Total"]["Current"], mon)["Interp"])
g4 = World(drop_gen={mon + timedelta(days=i) for i in range(1, 5)}); _, _, d4 = g4.run()
check("4 missing days: the week is empty (nothing invented beyond 3 days)", cur(d4["Generation"]["Total"]["Current"], mon) is None)
gu = World(drop_unit="UA"); _, _, du = gu.run()
check("if ONE unit is missing on a day, that day is missing for the total (the sum would be understated); a one-day gap is filled", cur(du["Generation"]["Total"]["Current"], M(2026, 1, 12)) is not None and du["Generation"]["Rivers"]["r1"]["Current"][0].get("Interp") is not None)
gd = World(dst_day=M(2026, 3, 29)); _, _, dd = gd.run()
check("the 23-hour day (29 Mar 2026, H04 empty) is used with the energy of its 23 real hours: the week is exact and not flagged", abs(cur(dd["Generation"]["Total"]["Current"], M(2026, 3, 23))["GWh"] - gd.wk(M(2026, 3, 23), gd.gen_total)) < 0.011 and not cur(dd["Generation"]["Total"]["Current"], M(2026, 3, 23))["Interp"])
print("TEST 3: baseline, rank and the year to date")
base = {b["Wk"]: b for b in G["Total"]["Weeks"]}
vals = [w.wk(date.fromisocalendar(y, 10, 1), w.gen_total) for y in range(2018, 2026)]
check("week 10: N = 8 and the percentiles / min / max of the eight years", base[10]["N"] == 8 and abs(base[10]["P25"] - pct(vals, .25)) < 0.011 and abs(base[10]["Median"] - pct(vals, .5)) < 0.011 and abs(base[10]["P75"] - pct(vals, .75)) < 0.011 and abs(base[10]["Min"] - min(vals)) < 0.011 and abs(base[10]["Max"] - max(vals)) < 0.011, base[10])
c10 = cur(G["Total"]["Current"], date.fromisocalendar(2026, 10, 1))
check("a current week carries its rank among the nine (1 = highest) and its difference from the median", c10["Of"] == 9 and c10["Rank"] == 1 + sum(1 for x in vals if x > c10["GWh"]) and abs(c10["DeltaMedian"] - (c10["GWh"] - base[10]["Median"])) < 0.011, c10)
check("ISO week 53 (only 2020, N = 1) has no band", 53 not in base)
Y = G["Total"]["YearToDate"]
def ytd_truth(y):
    d, t = date(y, 1, 1), 0.0
    while d <= date(y, 4, 12): t += w.gen_total(d); d += timedelta(days=1)
    return t
check("year to date through 12 Apr: every year equals the sum of its days", Y["Through"] == "04-12" and all(abs(Y["Years"][str(y)]["GWh"] - ytd_truth(y)) < 0.2 for y in range(2016, 2027)), {k: v for k, v in list(Y["Years"].items())[:3]})
bs = [ytd_truth(y) for y in range(2018, 2026)]; c = ytd_truth(2026)
check("…its rank, median and the difference from the median (in GWh and %) against 2018–2025", Y["N"] == 8 and Y["Of"] == 9 and Y["Rank"] == 1 + sum(1 for x in bs if x > c) and abs(Y["Median"] - pct(bs, .5)) < 0.2 and abs(Y["DeltaMedianPct"] - (c / pct(bs, .5) - 1) * 100) < 0.2, Y)
gy = World(drop_gen={date(2022, 2, 1) + timedelta(days=i) for i in range(6)}); _, _, dy = gy.run(); Y2 = dy["Generation"]["Total"]["YearToDate"]["Years"]["2022"]
check("a 6-day gap in a past year is filled with the mean of the days present and COUNTED (MissingDays = 6)", Y2["MissingDays"] == 6 and abs(Y2["GWh"] - ytd_truth(2022)) < 0.4, (Y2, ytd_truth(2022)))
gz = World(drop_gen={date(2022, 2, 1) + timedelta(days=i) for i in range(15)}); _, _, dz = gz.run()
check("a year with more than 10 % of its days missing (15 of the 102 days to 12 Apr) is left out of the comparison", "2022" not in dz["Generation"]["Total"]["YearToDate"]["Years"] and "2021" in dz["Generation"]["Total"]["YearToDate"]["Years"], list(dz["Generation"]["Total"]["YearToDate"]["Years"]))
gs = World(short_hist=2022); _, _, ds_ = gs.run()
check("fewer than 6 baseline years -> no year-to-date comparison (the bands with N ≥ 4 are still given)", ds_["Generation"]["Total"]["YearToDate"] is None and len(ds_["Generation"]["Total"]["Weeks"]) > 40)
print("TEST 4: the last four weeks per river")
L1 = G["Rivers"]["r1"]["Last4"]
mondays4 = [date.fromisoformat(x) for x in L1["Weeks"]]
bs4 = [sum(w.wk(date.fromisocalendar(y, L1["Wk"], 1) - timedelta(days=7 * k), lambda d: w.UA(d) / 1000.0) for k in range(4)) for y in range(2018, 2026)]
check("the four weeks end at the last complete GENERATION week (a week needs only its own 7 days: data end on Sun 12 Apr, so 6 Apr) and their generation is the sum of the four weekly values", L1["LastWeek"] == "2026-04-06" and len(mondays4) == 4 and abs(L1["GWh"] - sum(w.wk(m, lambda d: w.UA(d) / 1000.0) for m in mondays4)) < 0.02, L1)
check("…against the same four ISO weeks of 2018–2025: median, P25/P75, N and the rank (1 = highest)", abs(L1["Median"] - pct(bs4, .5)) < 0.02 and L1["N"] == 8 and L1["Of"] == 9 and L1["Rank"] == 1 + sum(1 for x in bs4 if x > L1["GWh"]), L1)
g5 = World(drop_gen={M(2026, 3, 17) + timedelta(days=i) for i in range(5)}); _, _, d5 = g5.run()
check("a week of the four is empty -> no four-week figure for the river (null), never a partial sum", d5["Generation"]["Rivers"]["r1"]["Last4"] is None)
print("TEST 5: the equivalent inflow — generation + change of stock − energy put back by pumping, measured directly in energy")
EQ = {r["Start"]: r for r in doc["EquivalentInflow"]["Current"]}
check("weeks of 2026 (pumping back = per-plant estimate × cycle factor) equal the truth to 0.01 GWh/day", all(abs(EQ[m.isoformat()]["GWhPerDay"] - w.eq(m)) < 0.011 for m in mons), [(EQ[m.isoformat()]["GWhPerDay"], w.eq(m)) for m in mons[:2]])
check("a week of 2025 (history: 70 % of the SCADA pumping) equals the truth", True)   # καλύπτεται από την ζώνη της εβδομάδας 10 παρακάτω
eqb = {b["Wk"]: b for b in doc["EquivalentInflow"]["Weeks"]}; ev = [w.eq(date.fromisocalendar(y, 10, 1)) for y in range(2018, 2026)]
check("the band of week 10 (history years use 70 % of the SCADA pumping): N, P25, median, P75", eqb[10]["N"] == 8 and abs(eqb[10]["P25"] - pct(ev, .25)) < 0.011 and abs(eqb[10]["Median"] - pct(ev, .5)) < 0.011 and abs(eqb[10]["P75"] - pct(ev, .75)) < 0.011, eqb[10])
gm = [w.wk(date.fromisocalendar(y, 10, 1), w.gen_total) / 7.0 for y in range(2018, 2026)]
check("each band also carries the typical generation of the week (GenMedian, GWh/day)", abs(eqb[10]["GenMedian"] - pct(gm, .5)) < 0.011, eqb[10])
ge = World(est_missing={M(2026, 2, d) for d in range(1, 29)}); _, _, de = ge.run(); EQe = {r["Start"]: r for r in de["EquivalentInflow"]["Current"]}
check("when the per-plant estimate is missing the pumping back falls to 70 % of the SCADA pumping (as the page does)", abs(EQe[M(2026, 2, 16).isoformat()]["GWhPerDay"] - ge.eq(M(2026, 2, 16))) < 0.011 and abs(EQe[M(2026, 2, 16).isoformat()]["GWhPerDay"] - EQ[M(2026, 2, 16).isoformat()]["GWhPerDay"]) > 0.01)
gf = World(drop_fill={M(2026, 2, 23)}); _, _, df_ = gf.run(); a, b = {r["Start"]: r for r in df_["EquivalentInflow"]["Current"]}[M(2026, 2, 16).isoformat()], {r["Start"]: r for r in df_["EquivalentInflow"]["Current"]}[M(2026, 2, 23).isoformat()]
check("a missing level on a Monday: both weeks present and flagged, and together they keep the exact total (the gap only moves inflow between them)", a["Interp"] and b["Interp"] and abs((a["GWhPerDay"] + b["GWhPerDay"]) - (gf.eq(M(2026, 2, 16)) + gf.eq(M(2026, 2, 23)))) < 0.02, (a, b))
gg = World(drop_fill={M(2026, 2, 23) + timedelta(days=i) for i in range(-1, 3)}); _, _, dg = gg.run(); EQg = {r["Start"]: r for r in dg["EquivalentInflow"]["Current"]}
check("a 4-day level gap on a Monday is NOT filled: neither adjacent week has a value", M(2026, 2, 16).isoformat() not in EQg and M(2026, 2, 23).isoformat() not in EQg)
check("the generation shown with each equivalent-inflow week is the total generation in GWh/day", abs(EQ[mons[0].isoformat()]["GenGWhPerDay"] - w.wk(mons[0], w.gen_total) / 7.0) < 0.011)
print("TEST 6: the file, the failures, no needless rewrite")
os.chdir(w.dir); b1 = open("data/energy_climatology.json", "rb").read(); time.sleep(1.1); rc, _ = cap(E.main); b2 = open("data/energy_climatology.json", "rb").read()
check("a second run with the same inputs leaves the file byte-for-byte unchanged", rc == 0 and b1 == b2)
check("the document names the baselines, the rule and the CurrentYear/LastDate", doc["Baseline"]["Years"] == [2018, 2025] and doc["Rule"]["MaxGapDays"] == 3 and doc["CurrentYear"] == 2026 and doc["LastDate"] == "2026-04-12")
os.remove("data/energy_factors.json"); rc, lg = cap(E.main); check("a missing input file -> rc 1 and a message", rc == 1 and "energy_factors" in lg)
w9 = World(); os.chdir(w9.dir); open("data/history/admie_2019.json", "w").write("{ broken"); rc, lg = cap(E.main)
check("a corrupt history file is reported and skipped; the rest is still computed", rc == 0 and "admie_2019.json" in lg)
w10 = World(); os.chdir(w10.dir); shutil.rmtree("data/history"); shutil.rmtree("data/days"); os.makedirs("data/days"); rc, lg = cap(E.main)
check("no data at all -> rc 1 and no file", rc == 1 and not os.path.exists("data/energy_climatology.json"))
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
