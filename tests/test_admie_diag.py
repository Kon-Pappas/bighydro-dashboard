import sys, os, io, tempfile, contextlib
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
EP_DEF, EP_RNG = U.API_FILES, U.BASE_URL + "/getOperationMarketFilewRange"
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
    rows = [[None, names[0]] + [50.0] * 24 for key, names, _ in U.HYDRO_UNITS[:n_units]]
    rows += [[None, "TOTAL HYDRO"] + [800.0] * 24, [None, "TOTAL PUMPING"] + [10.0] * 24]
    return xls({"System_Production": rows})
fmt = lambda d: d.strftime("%d.%m.%Y")
today = date.today()
def daily_range(pre, d0, d1, step=1):
    out, d = [], d0
    while d <= d1: out.append((d, d, f"files/{pre}_{d.isoformat()}.xlsx")); d += timedelta(days=step)
    return out
def weekly(y, pre):
    out, d = [], date(y, 1, 1)
    while d.year == y: out.append((d, min(d + timedelta(days=6), date(y, 12, 31)), f"files/{pre}_{d.isoformat()}.xlsx")); d += timedelta(days=7)
    return out
recent = (today - timedelta(days=420), today)
CAT = {"ReservoirFillingRate": daily_range("resrecent", *recent) + daily_range("res2019", date(2019, 1, 1), date(2019, 12, 31)) + weekly(2020, "res2020") + [(date(2018, 1, 1), date(2018, 1, 31), "files/res2018_jan.xlsx")],
       "SystemRealizationSCADA": daily_range("screcent", *recent) + daily_range("scada2019", date(2019, 1, 1), date(2019, 3, 31)) + [(date(2019, 7, 15), date(2019, 7, 15), "files/scada2019_2019-07-15.xlsx")] + daily_range("scada2020", date(2020, 1, 1), date(2020, 12, 31))}
FILES = {"res2019": reservoir_file(U.RESERVOIRS), "res2020": reservoir_file(U.RESERVOIRS[:9], total=None), "scada2019": scada_file(), "scada2020": scada_file(5)}
MODE = {"def": 10**6, "rng": 10**6}       # largest window (days) each endpoint answers; larger -> silently EMPTY list (as seen in the real log); None -> HTTP 404
calls = []
def fake(url, params=None, tries=3, what="", use_session=True):
    if url in (EP_DEF, EP_RNG):
        mx = MODE["def" if url == EP_DEF else "rng"]
        if mx is None: return R(404)
        a, b = date.fromisoformat(params["dateStart"]), date.fromisoformat(params["dateEnd"]); calls.append((url, a, b))
        if (b - a).days + 1 > mx: return R(200, [])
        return R(200, [{"file_path": p, "file_fromdate": fmt(f), "file_todate": fmt(t)} for f, t, p in CAT[params["FileCategory"]] if t >= a and f <= b])
    pre = url.split("/files/", 1)[-1].split("_")[0]; return R(200, content=FILES[pre]) if pre in FILES else R(404)
U.http_get = fake
tmp = tempfile.mkdtemp(); os.chdir(tmp)
print("TEST 1: the real situation — the default address answers a long window with an EMPTY list, the range address works")
MODE.update({"def": 1, "rng": 10**6}); calls.clear(); sys.argv = ['x', '2019', '2020']; r, out = cap(D.main)
res, scada = out.split("--- SystemRealizationSCADA ---")
check("rc 0 and nothing is written to disk (read-only)", r == 0 and os.listdir(tmp) == [], os.listdir(tmp))
check("the probe shows the default address EMPTY for 366 days and the range address covering all 366", "getOperationMarketFile | 366 |" in res and "getOperationMarketFile | 366 |   0 |   0 / 366" in res and "getOperationMarketFilewRange | 366 | 366 | 366 / 366" in res, res[:900])
check("it then chooses the range address with 366-day windows", "=> χρήση: getOperationMarketFilewRange με παράθυρα 366 ημερών" in res, res[:1400])
check("2019 (365 daily files) is found completely: 365 files, 365/365 (100%), duration {1: 365}", "2019 | 365" in res and "365/365 (100%)" in res and "{1: 365}" in res, res)
check("2020 (weekly files): duration 7 days, full coverage", "{7:" in res.split("2020 |")[1].split("\n")[0] and "(100%)" in res.split("2020 |")[1].split("\n")[0], res.split("2020 |")[1][:200])
check("SCADA 2019 has only the first 90 days plus 15 July: partial coverage is shown", "91/365 (25%)" in scada.split("2019 |")[1].split("\n")[0], scada.split("2019 |")[1][:200])
check("a year was scanned with ONE request per year on the range address (not 365)", sum(1 for u, a, b in calls if u == EP_RNG and a.year == 2019 and (b - a).days >= 364) >= 2, len(calls))
print("TEST 2: samples are parsed with the pipeline's own parsers")
check("complete reservoir file (2019): 14/14 reservoirs and the official total, no warning", "2019-07-15: 14/14 ταμιευτήρες" in res and "επίσημο σύνολο 61.0%" in res and "ΕΛΛΙΠΕΣ" not in res.split("2019-07-15")[1].split("\n")[0], res)
check("incomplete reservoir file (2020: 9 reservoirs, no total) is flagged ΕΛΛΙΠΕΣ", "2020-07-15: 9/14" in res and "ΕΛΛΙΠΕΣ" in res.split("2020-07-15")[1].split("\n")[0], res)
check("SCADA sample (2019): 16 units, TOTAL HYDRO 19.2 GWh (800 MW × 24 h), pumping found", "2019-07-15: 16/" in scada and "19.2 GWh" in scada and "άντληση ναι" in scada, scada)
check("SCADA sample with only 5 units (2020) is flagged ΕΛΛΙΠΕΣ", "2020-07-15: 5/" in scada and "ΕΛΛΙΠΕΣ" in scada.split("2020-07-15")[1].split("\n")[0], scada)
print("TEST 3: other API behaviours")
MODE.update({"def": 31, "rng": 31}); calls.clear(); sys.argv = ['x', '2019', '2019']; r, out = cap(D.main)
check("both addresses limited to 31 days: windows of 31 days are used and 2019 is still found completely", "παράθυρα 31 ημερών" in out and "365/365 (100%)" in out.split("--- SystemRealizationSCADA ---")[0], out[:1500])
check("…which means 12 requests for the year, not one", sum(1 for u, a, b in calls if a.year == 2019 and b.year == 2019 and u == EP_DEF and (b - a).days <= 30 and a.month in range(1, 13)) >= 12)
MODE.update({"def": 1, "rng": None}); sys.argv = ['x', '2019', '2020']; r, out = cap(D.main); res2 = out.split("--- SystemRealizationSCADA ---")[0]
check("only single days work (range address missing, HTTP 404): sampling of the 15th of each month, 12/12 months found", "δειγματοληψία 15ης" in res2 and "δείγμα 12/12 μηνών" in res2.split("2019 |")[1].split("\n")[0], res2[:1600])
MODE.update({"def": 1, "rng": 10**6})
print("TEST 4: failures never raise and never turn the run red")
U.http_get = lambda *a, **k: None
r, out = cap(D.main); check("network down: rc 0, 'no window works', every year 0, conclusion 'κανένα'", r == 0 and "ΚΑΝΕΝΑ παράθυρο δεν δουλεύει" in out and "δύο (ό,τι χρειάζεται για ιστορική εισροή ανά ταμιευτήρα): κανένα" in out, out[-400:])
U.http_get = lambda url, params=None, **k: R(200, {"oops": 1}) if url in (EP_DEF, EP_RNG) else R(404)
r, out = cap(D.main); check("unexpected API structure: rc 0 and a clear reason", r == 0 and "μη αναμενόμενη δομή" in out, out[:400])
U.http_get = fake; sys.argv = ['x', 'abc']; r, _ = cap(D.main); check("invalid arguments -> rc 1", r == 1)
sys.argv = ['x', '2020', '2016']; r, _ = cap(D.main); check("years in the wrong order -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
