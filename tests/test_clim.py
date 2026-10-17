import sys, os, json, tempfile, io, contextlib
from datetime import date, timedelta
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_climatology as C
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
tmp = tempfile.mkdtemp(); os.chdir(tmp); os.makedirs('data')
def week(d, mwh):
    y, wk, _ = d.isocalendar()
    return {"Start": d.isoformat() + "T00:00Z", "End": (d + timedelta(7)).isoformat() + "T00:00Z", "StartLocal": d.isoformat(), "IsoWeek": f"{y}-W{wk:02d}", "MWh": float(mwh)}
def year_weeks(y, f, only=None):
    d = date.fromisocalendar(y, 1, 1); out = []
    while d.isocalendar()[0] == y:
        wk = d.isocalendar()[1]
        if only is None or wk in only: out.append(week(d, f(y, wk)))
        d += timedelta(7)
    return out
val = lambda y, wk: 1_000_000 * (y - 2019) + 10_000 * wk              # MWh: strictly increasing in year, and in week
def write(name, weeks): json.dump({"Weeks": weeks}, open(f'data/{name}', 'w'))
print("TEST 1: baseline, percentiles, rank")
hist = year_weeks(2019, val, only=range(1, 11)) + year_weeks(2020, val) + year_weeks(2021, val) + year_weeks(2022, val)      # 2019 partial (10 weeks); 2020 has 53 weeks
live = year_weeks(2023, lambda y, wk: 1_000_000 * 3 + 10_000 * wk + 5_000, only=range(1, 13))
write('entsoe_history.json', hist); write('entsoe_reservoir.json', live)
r, lg = cap(C.main); d = json.load(open('data/climatology.json', encoding='utf-8'))
check("rc 0; baseline = the three full years before the current one; the partial 2019 is excluded and reported", r == 0 and d["BaselineYears"] == [2020, 2021, 2022] and d["ExcludedPartialYears"] == {"2019": 10} and d["CurrentYear"] == 2023, (d["BaselineYears"], d["ExcludedPartialYears"]))
w5 = next(x for x in d["Weeks"] if x["Wk"] == 5)
vals5 = sorted(val(y, 5) / 1000 for y in (2020, 2021, 2022))
check("week 5: min / median / max and the years they come from", w5["Min"] == vals5[0] and w5["Median"] == vals5[1] and w5["Max"] == vals5[2] and w5["MinYear"] == 2020 and w5["MaxYear"] == 2022 and w5["N"] == 3, w5)
check("P25 and P75 use linear interpolation (like numpy)", abs(w5["P25"] - (vals5[0] + 0.5 * (vals5[1] - vals5[0]))) < 0.11 and abs(w5["P75"] - (vals5[1] + 0.5 * (vals5[2] - vals5[1]))) < 0.11, w5)
c5 = next(x for x in d["Current"] if x["Wk"] == 5)
check("current week 5 is the highest of the 4 years -> rank 1 of 4; difference from the median", c5["Rank"] == 1 and c5["Of"] == 4 and abs(c5["DeltaMedian"] - (3_000_000 + 50_000 + 5_000 - val(2021, 5)) / 1000) < 0.11, c5)
check("the current year is NOT part of its own baseline (N = 3 for week 5)", w5["N"] == 3)
print("TEST 2: week 53, overlap, missing weeks, peaks")
w53 = next(x for x in d["Weeks"] if x["Wk"] == 53)
check("week 53 exists only in 2020: N = 1, and the current-year rows for such weeks carry no rank", w53["N"] == 1 and w53["MinYear"] == 2020)
live2 = [x for x in live if x["IsoWeek"] != "2023-W07"]
write('entsoe_reservoir.json', live2); cap(C.main); d = json.load(open('data/climatology.json', encoding='utf-8'))
check("a week missing from the live series is listed and NOT filled", d["MissingWeeks"] == ["2023-W07"] and all(x["Wk"] != 7 for x in d["Current"]), d["MissingWeeks"])
over = dict(live[0]); over["Start"] = hist[-1]["Start"]; over["IsoWeek"] = hist[-1]["IsoWeek"]; over["StartLocal"] = hist[-1]["StartLocal"]; over["MWh"] = 123456.0
hist2 = hist[:-1] + [dict(hist[-1])]; write('entsoe_history.json', hist2); write('entsoe_reservoir.json', live + [over]); cap(C.main)
d = json.load(open('data/climatology.json', encoding='utf-8'))
w52 = next(x for x in d["Weeks"] if x["Wk"] == 52)
check("on overlap the live series wins over the history (2022-W52 becomes 123.5 GWh, the new minimum)", w52["Min"] == 123.5 and w52["MinYear"] == 2022, w52)
write('entsoe_history.json', hist); write('entsoe_reservoir.json', live); cap(C.main); d = json.load(open('data/climatology.json', encoding='utf-8'))
pk = d["Peaks"]
check("annual peaks of the baseline years and the rank of the current peak", set(pk["Baseline"]) == {"2020", "2021", "2022"} and pk["Current"]["Wk"] == 12 and pk["Current"]["Of"] == 4 and pk["Current"]["Rank"] == 2 and pk["Baseline"]["2022"] == 3520.0, pk)
print("TEST 3: failures never write")
os.remove('data/climatology.json')
write('entsoe_history.json', year_weeks(2021, val) + year_weeks(2022, val)); r, lg = cap(C.main)
check("fewer than 3 full years -> rc 1 and no file", r == 1 and not os.path.exists('data/climatology.json') and "αρκετά" in lg)
os.remove('data/entsoe_history.json'); r, lg = cap(C.main); check("missing history file -> rc 1", r == 1 and not os.path.exists('data/climatology.json'))
open('data/entsoe_history.json', 'w').write('{ broken'); r, lg = cap(C.main); check("corrupt history file -> rc 1", r == 1 and not os.path.exists('data/climatology.json') and "δεν διαβάζεται" in lg)
write('entsoe_history.json', hist); open('data/entsoe_reservoir.json', 'w').write('{ broken'); r, _ = cap(C.main); check("corrupt live file -> rc 1 (nothing half-written)", r == 1 and not os.path.exists('data/climatology.json'))
os.remove('data/entsoe_reservoir.json'); write('entsoe_history.json', year_weeks(2019, val) + year_weeks(2020, val) + year_weeks(2021, val) + year_weeks(2022, val))
r, _ = cap(C.main); check("no live file at all: the latest history year is treated as current and the three before it are the baseline", r == 0 and json.load(open('data/climatology.json'))["CurrentYear"] == 2022 and json.load(open('data/climatology.json'))["BaselineYears"] == [2019, 2020, 2021])
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
