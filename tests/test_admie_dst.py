import sys, os, io, tempfile, contextlib
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
def scada_file(hours, label="TOTAL HYDRO"):
    vals = [100.0] * hours + [None] * (25 - hours)          # a 25-column block: the extra columns are blank on shorter days
    return xlsx("System_Production", [[None, "ΣΥΝΟΛΙΚΟ ΦΟΡΤΙΟ"] + [1.0] * 25, [None, label] + vals])
def isp_file(hours):
    n = hours * 4; vals = [50.0] * n + [None] * (100 - n)
    return xlsx("20251026_ISP", [["ISP"] + list(range(1, 101)), [KREMASTA_ISP] + vals])
def fake(url, params=None, tries=3, what="", use_session=True):
    if url == URL:
        d = date.fromisoformat(params["dateStart"]); cat = "scada" if params["FileCategory"] == U.CAT_SCADA else "isp"; f = d.strftime("%d.%m.%Y")
        return R(200, [{"file_path": f"files/{cat}_{d.isoformat()}.xls", "file_fromdate": f, "file_todate": f}])
    kind, ds = url.split("/files/", 1)[-1].replace(".xls", "").split("_"); h = X.hours_in_day(date.fromisoformat(ds))
    return R(200, content=scada_file(h) if kind == "scada" else isp_file(h))
U.http_get = fake
tmp = tempfile.mkdtemp(); os.chdir(tmp)
print("TEST 1: the hours of a day (Europe/Athens)")
check("26 Oct 2025 and 25 Oct 2026 have 25 hours, 30 Mar 2025 and 29 Mar 2026 have 23, ordinary days have 24", [X.hours_in_day(date(2025, 10, 26)), X.hours_in_day(date(2026, 10, 25)), X.hours_in_day(date(2025, 3, 30)), X.hours_in_day(date(2026, 3, 29)), X.hours_in_day(date(2026, 10, 24))] == [25, 25, 23, 23, 24])
print("TEST 2: what the pipeline reads on each kind of day")
sys.argv = ['x', '2025-10-26', '2025-03-30', '2025-10-25']; r, out = cap(X.main)
a, rest = out.split("--- 2025-03-30")[0], out.split("--- 2025-03-30")[1]; b, c = rest.split("--- 2025-10-25")
check("rc 0 and nothing written (read-only)", r == 0 and os.listdir(tmp) == [], os.listdir(tmp))
check("25-hour day: 25 numeric hour columns; the pipeline (24 columns) loses the last hour, 100 MWh = 4.0 %", "ΑΛΛΑΓΗ ΩΡΑΣ" in a and "αριθμητικές στήλες ωρών: 25" in a and "το pipeline χάνει 100 MWh (4.0%)" in a, a)
check("25-hour day, ISP: 100 quarter-hours; the first 96 (pipeline) lose 4 quarter-hours = 50 MWh", "τεταρτόωρα με τιμή: 100 (η ημέρα έχει 100)" in a and "χάνονται 50 MWh" in a, a)
check("23-hour day: 23 numeric hour columns and 92 quarter-hours; the pipeline loses no energy, and the output says so", "αριθμητικές στήλες ωρών: 23" in b and "τεταρτόωρα με τιμή: 92 (η ημέρα έχει 92)" in b and b.count("→ ίδια") == 2, b)
check("ordinary day: 24 columns, 96 quarter-hours, 'ίδια' for both", "αριθμητικές στήλες ωρών: 24" in c and "τεταρτόωρα με τιμή: 96 (η ημέρα έχει 96)" in c and "ΑΛΛΑΓΗ ΩΡΑΣ" not in c, c)
check("the hourly values of the total are printed as a row of numbers with a dot for an empty column", "· ·" in b or "·" in b.split("TOTAL HYDRO")[1][:200], b[:600])
print("TEST 3: old label of the total and failures")
U.http_get = lambda url, params=None, **k: R(200, [{"file_path": "files/scada_2025-10-26.xls", "file_fromdate": "26.10.2025", "file_todate": "26.10.2025"}]) if url == URL else R(200, content=xlsx("System_Production", [[None, "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ"] + [100.0] * 25]))
sys.argv = ['x', '2025-10-26']; r, out = cap(X.main); check("the old label ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ is found and the row is read", "αριθμητικές στήλες ωρών: 25" in out, out[:500])
U.http_get = lambda *a, **k: None
r, out = cap(X.main); check("network down: rc 0 and 'δεν κατέβηκε αρχείο' for both files", r == 0 and out.count("δεν κατέβηκε αρχείο") == 2 and "=== ΤΕΛΟΣ ===" in out, out[-300:])
U.http_get = fake; sys.argv = ['x', 'not-a-date']; r, _ = cap(X.main); check("invalid date -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
