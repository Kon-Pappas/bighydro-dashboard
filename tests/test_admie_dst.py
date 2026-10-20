import sys, os, io, math, tempfile, contextlib
from datetime import date
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
import diagnose_admie_history as H
import diagnose_admie_dst as X
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
H.time.sleep = lambda s: None; X.time.sleep = lambda s: None
URL = X.URL
class R:
    def __init__(s, status=200, data=None, content=b""): s.status_code = status; s._d = data; s.content = content
    def json(s):
        if s._d is None: raise ValueError("no json")
        return s._d
def xlsx(sheet, rows):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w: pd.DataFrame(rows).to_excel(w, sheet_name=sheet, header=False, index=False)
    return bio.getvalue()
KREMASTA_ISP = [k for k in U.HYDRO_UNITS if k[0] == "Kremasta"][0][2][0]
# REAL structure seen in the files of 20 Oct 2026: label in column 1, 24 hour columns (2..25) and a DAILY TOTAL column (26).
# On 25-hour days the total includes the hidden 25th hour; on 23-hour days the last hour column is ~0.
UNITS = [u for u in U.HYDRO_UNITS if u[0] in ("Kremasta", "Kastraki", "Polyfyto", "Plastiras")]
def prof(u, h): return 100.0 * (u + 1) + 60.0 * (u + 1) * math.sin(h * 0.7 + u)           # a different, varying hourly profile per unit
def scada_file(hours, total_label="TOTAL HYDRO"):
    h = [100.0] * 24
    if hours == 23: h[-1] = 1.0
    total = sum(h) + (100.0 if hours == 25 else 0.0)
    shift = {23: -1, 24: 0, 25: 1}[hours]
    load = [4000.0] * 24; load[4 + shift] = 3000.0; load[20 + shift] = 6000.0
    rows = [[None, "HOURS"] + [f"H{i}" for i in range(1, 25)] + ["TOTAL"], [None, "ΣΥΝΟΛΙΚΟ ΦΟΡΤΙΟ"] + load + [sum(load)], [None, total_label] + h + [total]]
    for i, (key, names, _isp) in enumerate(UNITS):
        v = [prof(i, k) for k in range(24)]; rows.append([None, names[0]] + v + [sum(v)])
    return xlsx("System_Production", rows)
def isp_file(hours, half, ahead=0):
    per = 2 if half else 4; n = hours * per; vals = [50.0] * n; tot = sum(vals) / per
    rows = [["ISP"] + list(range(1, n + 2)), [KREMASTA_ISP] + vals + [tot]]
    for i, (key, _s, names) in enumerate(UNITS):
        if key == "Kremasta": rows.pop(1)
        v = [prof(i, min(k // per + ahead, 23) % 24) for k in range(n)]; rows.append([names[0]] + v + [sum(v) / per])
    return xlsx("20251026_ISP", rows)
def fake(url, params=None, tries=3, what="", use_session=True):
    if url == URL:
        d = date.fromisoformat(params["dateStart"]); cat = "scada" if params["FileCategory"] == U.CAT_SCADA else "isp"; f = d.strftime("%d.%m.%Y")
        return R(200, [{"file_path": f"files/{cat}_{d.isoformat()}.xls", "file_fromdate": f, "file_todate": f}])
    kind, ds = url.split("/files/", 1)[-1].replace(".xls", "").split("_"); d = date.fromisoformat(ds); h = X.hours_in_day(d)
    return R(200, content=scada_file(h) if kind == "scada" else isp_file(h, half=d < date(2025, 10, 1), ahead=1 if d == date(2026, 3, 30) else 0))
U.http_get = fake
tmp = tempfile.mkdtemp(); os.chdir(tmp)
print("TEST 1: the hours of a day (Europe/Athens)")
check("26 Oct 2025 and 25 Oct 2026 have 25 hours, 30 Mar 2025 and 29 Mar 2026 have 23, ordinary days have 24", [X.hours_in_day(date(2025, 10, 26)), X.hours_in_day(date(2026, 10, 25)), X.hours_in_day(date(2025, 3, 30)), X.hours_in_day(date(2026, 3, 29)), X.hours_in_day(date(2026, 10, 24))] == [25, 25, 23, 23, 24])
print("TEST 2: an ORDINARY day never reports a loss (the bug of the first version counted the total column as an hour: '50 %')")
sys.argv = ['x', '2025-10-25']; r, out = cap(X.main)
check("rc 0, nothing written (read-only)", r == 0 and os.listdir(tmp) == [], os.listdir(tmp))
check("ordinary day: the daily total equals the sum of the 24 columns; no 'ΥΠΕΡΒΑΙΝΕΙ', no 'χάνει', no percentage loss anywhere", "το ΣΥΝΟΛΟ ημέρας = άθροισμα των 24 στηλών" in out and "ΥΠΕΡΒΑΙΝΕΙ" not in out and "χάνει" not in out and "50%" not in out and "χάνει" not in out, out)
check("ordinary day, ISP: 96 intervals, the last column recognised as the TOTAL (sum ÷ 4), read by the pipeline as 96 intervals and NOT touching the total", "96 διαστήματα (τεταρτόωρα)" in out and "ΣΥΝΟΛΟ (άθροισμα MW ÷ 4)" in out and "διαβάζει 96 διαστήματα" in out and "(K04)" not in out, out)
print("TEST 3: a 25-hour day")
sys.argv = ['x', '2025-10-26']; r, out = cap(X.main)
check("25 h: the daily TOTAL exceeds the sum of the 24 columns by the hidden hour (100 MWh = 4.0 % of the day)", "ΑΛΛΑΓΗ ΩΡΑΣ" in out and "ΥΠΕΡΒΑΙΝΕΙ" in out and "κατά 100 MWh (4.0% της ημέρας)" in out, out)
check("25 h: the load minimum and the evening peak move one column later (5 and 21 instead of 4 and 20)", "στη στήλη 5" in out and "μέγιστο στη στήλη 21" in out, out)
check("25 h, ISP: 100 intervals; the pipeline reads 96 and loses the last 4; the total column is outside its range", "100 διαστήματα (τεταρτόωρα)" in out and "χάνει τα τελευταία 4" in out and "(K04)" not in out, out)
print("TEST 4: a 23-hour day")
sys.argv = ['x', '2026-03-29']; r, out = cap(X.main)
check("23 h: total = sum, and the last hour column is ~0 (1 MW) — the day has no 24th hour", "ΑΛΛΑΓΗ ΩΡΑΣ" in out and "το ΣΥΝΟΛΟ ημέρας = άθροισμα των 24 στηλών" in out and "τελευταία στήλη ώρας = 1 MW" in out, out)
check("23 h: the load minimum and the evening peak move one column earlier (3 and 19)", "στη στήλη 3" in out and "μέγιστο στη στήλη 19" in out, out)
check("23 h, ISP: 92 intervals, and the pipeline READS THE TOTAL COLUMN AS AN INTERVAL (K04)", "92 διαστήματα (τεταρτόωρα)" in out and "διαβάζει τη ΣΤΗΛΗ ΣΥΝΟΛΟΥ ως διάστημα (K04)" in out, out)
print("TEST 4b: ISP versus SCADA, hour by hour, as the pipeline reads them (K04)")
sys.argv = ['x', '2025-10-25']; r, out = cap(X.main)
check("ordinary day: the two sources agree without any shift (correlation 1.00, shift +0), no warning", "χωρίς μετατόπιση 1.00" in out and "κατά +0 ώρες" in out and "ΜΕΤΑΤΟΠΙΣΗ" not in out, out)
sys.argv = ['x', '2026-03-30']; r, out = cap(X.main)
check("the day after the clock change with the ISP one hour ahead of SCADA: the shift is found (+1) and flagged", "καλύτερη 1.00 όταν το ISP μετατοπίζεται κατά +1 ώρες" in out and "<-- ΜΕΤΑΤΟΠΙΣΗ" in out and "χωρίς μετατόπιση 1.00" not in out, out)
check("the default list now contains the day after every change (K04 is about 30 Mar 2026)", all(x in X.DEFAULT_DATES for x in ("2024-04-01", "2024-10-28", "2025-03-31", "2025-10-27", "2026-03-30")))
print("TEST 5: the old half-hour ISP format, the old label, headers, failures")
sys.argv = ['x', '2025-03-30']; r, out = cap(X.main)
check("before 1 Oct 2025 the ISP has half-hour intervals (46 on a 23-hour day) and the output says so", "46 διαστήματα (ημίωρα" in out and "ΣΥΝΟΛΟ (άθροισμα MW ÷ 2)" in out, out)
check("the header row of the sheet is printed (to see hour labels)", "κεφαλίδα γραμμή 0: " in out and "H1" in out, out)
U.http_get = lambda url, params=None, **k: R(200, [{"file_path": "files/scada_2025-10-26.xls", "file_fromdate": "26.10.2025", "file_todate": "26.10.2025"}]) if url == URL else R(200, content=scada_file(25, total_label="ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ"))
sys.argv = ['x', '2025-10-26']; r, out = cap(X.main); check("the old label ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ is found and the row is read", "ΥΠΕΡΒΑΙΝΕΙ" in out, out[:600])
U.http_get = lambda *a, **k: None
r, out = cap(X.main); check("network down: rc 0 and 'δεν κατέβηκε αρχείο' for both files", r == 0 and out.count("δεν κατέβηκε αρχείο") == 2 and "=== ΤΕΛΟΣ ===" in out, out[-300:])
U.http_get = fake; sys.argv = ['x', 'not-a-date']; r, _ = cap(X.main); check("invalid date -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
