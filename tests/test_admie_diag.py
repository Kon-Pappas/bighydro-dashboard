import sys, os, io, json, tempfile, contextlib
from datetime import date, timedelta
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
import diagnose_admie_history as D
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
D.time.sleep = lambda s: None
class R:
    def __init__(s, status=200, data=None, content=b""): s.status_code = status; s._d = data; s.content = content
    def json(s):
        if s._d is None: raise ValueError("no json")
        return s._d
def xls(sheets):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        for n, rows in sheets.items(): pd.DataFrame(rows).to_excel(w, sheet_name=n, header=False, index=False)
    return bio.getvalue()
def reservoir_file(names, total=0.61):
    rows = [[None, n, 0.5 + i / 100] for i, n in enumerate(names)]
    if total is not None: rows.append(["FILLING RATE (%) TOTAL", None, None, total, None])
    return xls({"Sheet1": rows})
def scada_file(n_units=16):
    rows = []
    for key, names, _ in U.HYDRO_UNITS[:n_units]: rows.append([None, names[0]] + [50.0] * 24)
    rows += [[None, "TOTAL HYDRO"] + [800.0] * 24, [None, "TOTAL PUMPING"] + [10.0] * 24]
    return xls({"System_Production": rows})
fmt = lambda d: d.strftime("%d.%m.%Y")
def daily(y, cat, pre, step=1, count=None):
    out, d = [], date(y, 1, 1)
    while d.year == y and (count is None or len(out) < count):
        out.append((d, d, f"files/{pre}_{d.isoformat()}.xlsx")); d += timedelta(days=step)      # every real file has its own name
    return out
def weekly(y, pre):
    out, d = [], date(y, 1, 1)
    while d.year == y: out.append((d, min(d + timedelta(days=6), date(y, 12, 31)), f"files/{pre}_{d.isoformat()}.xlsx")); d += timedelta(days=7)
    return out
CAT = {"ReservoirFillingRate": [], "SystemRealizationSCADA": []}
CAT["ReservoirFillingRate"] += daily(2019, 0, "res2019") + weekly(2020, "res2020") + [(date(2017, 8, 1), date(2017, 8, 7), "files/res2017_a.xlsx"), (date(2017, 8, 8), date(2017, 8, 14), "files/res2017_b.xlsx")]
CAT["SystemRealizationSCADA"] += daily(2019, 0, "scada2019", step=1, count=99) + [(date(2019, 7, 15), date(2019, 7, 15), "files/scada2019_2019-07-15.xlsx")] + daily(2020, 0, "scada2020")
CAT["ReservoirFillingRate"] += [(date(2018, 1, 1), date(2018, 1, 31), "files/res2018_jan.xlsx")]      # a year with files, but none on 15 July
FILES = {"res2019": reservoir_file(U.RESERVOIRS), "res2020": reservoir_file(U.RESERVOIRS[:9], total=None),
         "res2017": reservoir_file(U.RESERVOIRS), "scada2019": scada_file(), "scada2020": scada_file(5)}
calls = []; FAIL_YEARS = {2017}
def fake(url, params=None, tries=3, what="", use_session=True):
    calls.append(url)
    if url != U.API_FILES:
        pre = url.split("/files/", 1)[-1].split("_")[0]; return R(200, content=FILES[pre]) if pre in FILES else R(404)
    cat = params["FileCategory"]; a, b = date.fromisoformat(params["dateStart"]), date.fromisoformat(params["dateEnd"])
    if a.year in FAIL_YEARS and (b - a).days > 100: return R(500)       # the API refuses a whole year for these years
    return R(200, [{"file_path": p, "file_fromdate": fmt(f), "file_todate": fmt(t)} for f, t, p in CAT[cat] if t >= a and f <= b])
U.http_get = fake
tmp = tempfile.mkdtemp(); os.chdir(tmp)
print("TEST 1: availability table")
sys.argv = ['x', '2016', '2020']; r, out = cap(D.main)
check("rc 0 and nothing is written to disk (read-only)", r == 0 and os.listdir(tmp) == [], os.listdir(tmp))
res, scada = out.split("--- SystemRealizationSCADA ---")
check("a year without files is reported as 0 (2016)", "2016 | 0" in res, res[:400])
check("daily files for the whole of 2019: 365 files, 100 % coverage, duration {1: 365}", "2019 | 365" in res and "365/365 (100%)" in res and "{1: 365}" in res, res)
check("weekly files (2020): duration {7: 52}-like and full coverage", "{7:" in res and "(100%)" in res.split("2020 |")[1].split("\n")[0], res.split("2020 |")[1][:200])
check("a refused whole-year request falls back to quarters and still finds the August 2017 files (2017)", "2017 | 2" in res and "2017-08-01 → 2017-08-14" in res, res.split("2017 |")[1][:160])
check("SCADA with only 100 days in 2019: partial coverage is shown (100/365)", "100/365 (27%)" in scada, scada[:500])
print("TEST 2: samples are parsed with the pipeline's own parsers")
check("complete reservoir file (2019): 14/14 reservoirs and the official total, no warning", "2019-07-15: 14/14 ταμιευτήρες" in res and "επίσημο σύνολο 61.0%" in res and "ΕΛΛΙΠΕΣ" not in res.split("2019-07-15")[1].split("\n")[0], res)
check("incomplete reservoir file (2020: 9 reservoirs, no total) is flagged ΕΛΛΙΠΕΣ", "2020-07-15: 9/14" in res and "ΕΛΛΙΠΕΣ" in res.split("2020-07-15")[1].split("\n")[0], res)
check("SCADA sample (2019): 16 units, TOTAL HYDRO in GWh (800 MW × 24 h = 19.2 GWh), pumping found", "2019-07-15: 16/" in scada and "19.2 GWh" in scada and "άντληση ναι" in scada, scada)
check("SCADA sample with only 5 units (2020) is flagged ΕΛΛΙΠΕΣ", "2020-07-15: 5/" in scada and "ΕΛΛΙΠΕΣ" in scada.split("2020-07-15")[1].split("\n")[0], scada)
check("a year with files but none on the sample date says so clearly (2018) instead of failing", "2018-07-15: δεν κατέβηκε αρχείο" in res, res.split("2018 |")[1][:300])
print("TEST 3: conclusion")
tail = out.split("=== ΣΥΜΠΕΡΑΣΜΑ ===")[1]
check("years with at least 90 % coverage per category, and the years where BOTH exist", "ReservoirFillingRate: έτη με κάλυψη ≥ 90%: [2019, 2020]" in tail and "SystemRealizationSCADA: έτη με κάλυψη ≥ 90%: [2020]" in tail and "δύο (ό,τι χρειάζεται για ιστορική εισροή ανά ταμιευτήρα): 2020" in tail, tail)
check("partial coverage is listed separately (SCADA 2019)", "μερική κάλυψη: [2019]" in tail, tail)
print("TEST 4: failures never raise and never turn the run red")
U.http_get = lambda *a, **k: None
r, out = cap(D.main); check("network down: rc 0, every year reported as 'no list', conclusion 'κανένα'", r == 0 and "δεν ήρθε λίστα" in out and "δύο (ό,τι χρειάζεται για ιστορική εισροή ανά ταμιευτήρα): κανένα" in out, out[-300:])
U.http_get = lambda url, params=None, **k: R(200, {"oops": 1}) if url == U.API_FILES else R(404)
r, out = cap(D.main); check("unexpected API structure: rc 0 and a clear reason", r == 0 and "μη αναμενόμενη δομή" in out, out[:300])
U.http_get = fake; sys.argv = ['x', 'abc']; r, _ = cap(D.main); check("invalid arguments -> rc 1", r == 1)
sys.argv = ['x', '2020', '2016']; r, _ = cap(D.main); check("years in the wrong order -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
