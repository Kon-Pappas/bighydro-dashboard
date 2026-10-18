import sys, os, io, tempfile, contextlib
from datetime import date, timedelta
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
import diagnose_admie_history as H
import diagnose_admie_formats as F
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
H.time.sleep = lambda s: None; F.time.sleep = lambda s: None
URL = F.URL
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
# OLD reservoir format: Stratos is called "STRATOS I", Pournari absent, Ilarionas spelled differently
old_names = [n for n in U.RESERVOIRS if n not in ("STRATOS", "POYRNARI1", "POYRNARI2", "ILARIONAS")] + ["STRATOS I", "ILARION"]
RES_OLD = xls({"Sheet1": [[None, n, 0.5] for n in old_names] + [["FILLING RATE (%) TOTAL", None, None, 0.7, None]]})
RES_NEW = xls({"Sheet1": [[None, n, 0.5] for n in U.RESERVOIRS] + [["FILLING RATE (%) TOTAL", None, None, 0.7, None]]})
# OLD SCADA format: the total row is called "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ" and there is no pumping row
sc_rows = [[None, names[0]] + [100.0] * 24 for key, names, _ in U.HYDRO_UNITS]
SC_OLD = xls({"System_Production": sc_rows + [[None, "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ"] + [1600.0] * 24, [None, "ΑΝΑΝΕΩΣΙΜΑ"] + [0.0] * 24]})
SC_NEW = xls({"System_Production": sc_rows + [[None, "TOTAL HYDRO"] + [1600.0] * 24, [None, "TOTAL PUMPING"] + [5.0] * 24]})
fmt = lambda d: d.strftime("%d.%m.%Y")
def entries(cat, d):
    new = d.year >= 2022
    pre = ("resnew" if new else "resold") if cat == "ReservoirFillingRate" else ("scnew" if new else "scold")
    out = [{"file_path": f"files/{pre}_{d.isoformat()}.xls", "file_fromdate": fmt(d), "file_todate": fmt(d), "file_publish_date": fmt(d + timedelta(days=1))}]
    if (cat == "ReservoirFillingRate" and d == date(2018, 3, 5)) or (cat == "SystemRealizationSCADA" and d == date(2020, 3, 5)):
        out.append({"file_path": f"files/{pre}_{d.isoformat()}_rev.xls", "file_fromdate": fmt(d), "file_todate": fmt(d), "file_publish_date": fmt(d + timedelta(days=9))})
    return out
FILES = {"resnew": RES_NEW, "resold": RES_OLD, "scnew": SC_NEW, "scold": SC_OLD}
def fake(url, params=None, tries=3, what="", use_session=True):
    if url == URL:
        a, b = date.fromisoformat(params["dateStart"]), date.fromisoformat(params["dateEnd"]); out = []; d = a
        while d <= b: out += entries(params["FileCategory"], d); d += timedelta(days=1)
        return R(200, out)
    pre = url.split("/files/", 1)[-1].split("_")[0]; return R(200, content=FILES[pre]) if pre in FILES else R(404)
U.http_get = fake
tmp = tempfile.mkdtemp(); os.chdir(tmp)
print("TEST 1: reservoirs — missing and unmatched labels")
sys.argv = ['x', '2018-07-15', '2022-07-15']; r, out = cap(F.main)
res = out.split("#### SCADA ####")[0]; old_part, new_part = res.split("--- ΣΤΑΘΜΕΣ 2022-07-15 ---")
check("rc 0 and nothing written (read-only)", r == 0 and os.listdir(tmp) == [], os.listdir(tmp))
check("old file: the expected reservoirs that are MISSING are listed (STRATOS, POYRNARI1, POYRNARI2, ILARIONAS)", "ΛΕΙΠΟΥΝ από τους αναμενόμενους: ['POYRNARI1', 'POYRNARI2', 'STRATOS', 'ILARIONAS']" in old_part or all(x in old_part.split("ΛΕΙΠΟΥΝ")[1].split("\n")[0] for x in ("STRATOS", "POYRNARI1", "POYRNARI2", "ILARIONAS")), old_part[-600:])
check("old file: the labels that match nothing are shown, which reveals the renaming ('STRATOS I', 'ILARION')", "STRATOS I" in old_part.split("ΔΕΝ αντιστοιχούν")[1] and "ILARION" in old_part.split("ΔΕΝ αντιστοιχούν")[1], old_part[-400:])
check("new file (2022): nothing missing", "ΛΕΙΠΟΥΝ από τους αναμενόμενους: κανένας" in new_part, new_part[-300:])
check("the row labels of the sheet are printed (row number: label | value)", "KREMASTA" in old_part and "FILLING RATE (%) TOTAL" in old_part, old_part[:700])
print("TEST 2: SCADA — unit matching and the total/pumping labels")
sc = out.split("#### SCADA ####")[1].split("#### ΔΙΠΛΑ ΑΡΧΕΙΑ ####")[0]; sc_old, sc_new = sc.split("--- SCADA 2022-07-15 ---")
check("each of the 16 units is reported with its matched label, the kind of match and its daily GWh (100 MW × 24 h = 2.40)", "Kremasta→'ΚΡΕΜΑΣΤΑ'[exact] 2.40" in sc_old and sc_old.count("[exact]") >= 14, sc_old[:900])
check("old file: the differently named total is found by keyword (ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ → 38.40 GWh) and no TOTAL PUMPING exists", "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ" in sc_old and "38.40 GWh" in sc_old and "TOTAL PUMPING" not in sc_old, sc_old[-700:])
check("new file: TOTAL HYDRO and TOTAL PUMPING (0.12 GWh) are listed", "TOTAL HYDRO" in sc_new and "TOTAL PUMPING" in sc_new and "0.12 GWh" in sc_new, sc_new[-500:])
print("TEST 3: duplicate files")
dup = out.split("#### ΔΙΠΛΑ ΑΡΧΕΙΑ ####")[1]; d_res, d_sc = dup.split("--- ΔΙΠΛΑ ΑΡΧΕΙΑ: SystemRealizationSCADA 2020 ---")
check("2018 reservoirs: one day with two files; the record fields (incl. the publish date) and both file names are shown", "ημέρες με πάνω από ένα αρχείο: 1" in d_res and "file_publish_date" in d_res and "_rev.xls" in d_res and "05.03.2018→05.03.2018: 2 αρχεία" in d_res, d_res)
check("2020 SCADA: the same for the SCADA duplicates", "ημέρες με πάνω από ένα αρχείο: 1" in d_sc and "05.03.2020→05.03.2020: 2 αρχεία" in d_sc, d_sc)
print("TEST 4: failures never raise")
U.http_get = lambda *a, **k: None
r, out = cap(F.main); check("network down: rc 0, every section says nothing was downloaded, and it ends normally", r == 0 and "δεν κατέβηκε αρχείο" in out and "=== ΤΕΛΟΣ ===" in out and "δεν ήρθε λίστα" in out, out[-300:])
U.http_get = lambda url, params=None, **k: R(200, content=b"not an excel file") if url != URL else R(200, [{"file_path": "files/x.xls", "file_fromdate": "15.07.2018", "file_todate": "15.07.2018"}])
sys.argv = ['x', '2018-07-15']; r, out = cap(F.main); check("a file that is not Excel is reported, not raised", r == 0 and "δεν διαβάζεται ως Excel" in out, out[:400])
U.http_get = fake; sys.argv = ['x', 'not-a-date']; r, _ = cap(F.main); check("invalid date -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
