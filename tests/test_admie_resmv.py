import sys, os, io, tempfile, contextlib
from datetime import date, timedelta
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
import diagnose_admie_history as H
import diagnose_admie_resmv as X
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
URL_RANGE = X.URL_RANGE
class R:
    def __init__(s, status=200, data=None, content=b""): s.status_code = status; s._d = data; s.content = content
    def json(s):
        if s._d is None: raise ValueError("no json")
        return s._d
COLS = ['ΗΜΕΡΑ', 'ΩΡΑ', 'B/A ΕΝΕΡΓΕΙΑ KWh', 'B/A ΕΓΚ ΙΣΧΥΣ KW', 'ΜΥΗΣ ΕΝΕΡΓΕΙΑ KWh', 'ΜΥΗΣ ΕΓΚ ΙΣΧΥΣ KW', 'ΣΗΘΥΑ ΕΝΕΡΓΕΙΑ KWh', 'ΣΗΘΥΑ ΕΓΚ ΙΣΧΥΣ KW', 'Φ/Β ΕΝΕΡΓΕΙΑ KWh', 'Φ/Β ΕΓΚ ΙΣΧΥΣ KW']
def resmv_bytes(blocks):
    """blocks: [(day, [ΩΡΑ labels], doubled_label|None)] — real structure: header, hour rows (the doubled hour holds the SUM of two hours), text footer rows."""
    rows = [COLS]
    for day, labels, doubled in blocks:
        for h in labels:
            k = 2.0 if h == doubled else 1.0
            rows.append([int(day.strftime("%Y%m%d")), float(h), 80000 * k, 160000, 27000.0 * k + h * 10, 250000, 30000 * k, 60000, 100.0 * k, 4.9e6])
    rows += [["Τα ανωτέρω στοιχεία έχουν προκύψει από μη πιστοποιημένες μετρήσεις"] + [None] * 9, ["και για οποιαδήποτε ζημιά ή βλάβη προκληθεί από την χρήση τους."] + [None] * 9]
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w: pd.DataFrame(rows).to_excel(w, sheet_name="Sheet1", header=False, index=False)
    return bio.getvalue()
def entry(name, f, t, pub, folder="2026/10"):
    return {"file_path": f"sites/default/files/attached-files/type-file/{folder}/{name}", "file_fromdate": f.strftime("%d.%m.%Y"), "file_todate": t.strftime("%d.%m.%Y"), "file_published": pub}
SCEN = {"single": {}, "listed": [], "files": {}, "down": False, "soft404": False}
def fake(url, params=None, tries=3, what="", use_session=True):
    if SCEN["down"]: return None
    if url == U.API_FILES:
        d = date.fromisoformat(params["dateStart"]); return R(200, SCEN["single"].get(d, []))
    if url == URL_RANGE:
        a, b = date.fromisoformat(params["dateStart"]), date.fromisoformat(params["dateEnd"]); out = []
        for e in SCEN["listed"]:
            f = pd.to_datetime(e["file_fromdate"], format="%d.%m.%Y").date(); t = pd.to_datetime(e["file_todate"], format="%d.%m.%Y").date()
            if f <= b and t >= a: out.append(e)
        return R(200, out)
    c = SCEN["files"].get(url)
    if c is None and SCEN["soft404"]: return R(200, content=("<html><body>" + "Η σελίδα δεν βρέθηκε " * 200 + "</body></html>").encode("utf-8"))      # a site that answers 200 with an error page
    return R(200, content=c) if c is not None else R(404)
U.http_get = fake
tmp = tempfile.mkdtemp(); os.chdir(tmp)
def reset(**kw):
    SCEN.update({"single": {}, "listed": [], "files": {}, "down": False, "soft404": False}); SCEN.update(kw)
def url_of(e): return U.BASE_URL + "/" + e["file_path"]
print("TEST 1: names and addresses")
check("the file of day D is named with the publication date D+1; the candidates start in the publication month and go two months on (xls then xlsx), also across New Year", X.expected_name(date(2026, 10, 25)) == "20261026_RESMV_01" and X.candidate_urls(date(2026, 10, 25))[0].endswith("/type-file/2026/10/20261026_RESMV_01.xls") and X.candidate_urls(date(2026, 10, 25))[1].endswith("20261026_RESMV_01.xlsx") and [u.split("type-file/")[1][:7] for u in X.candidate_urls(date(2025, 12, 31))[::2]] == ["2026/01", "2026/02", "2026/03"])
print("TEST 2: the 25-hour day — the list never shows the file (as on 25 Oct 2026), the direct address does")
d = date(2026, 10, 25); ok24 = entry("20261025_RESMV_01.xls", date(2026, 10, 24), date(2026, 10, 24), "25.10.2026 10:05"); ok26 = entry("20261027_RESMV_01.xls", date(2026, 10, 26), date(2026, 10, 26), "27.10.2026 10:05")
reset(listed=[ok24, ok26], files={"https://www.admie.gr/sites/default/files/attached-files/type-file/2026/10/20261026_RESMV_01.xls": resmv_bytes([(d, list(range(1, 25)), 4)])})
sys.argv = ['x', '2026-10-25']; r, out = cap(X.main)
check("rc 0 and nothing written (read-only)", r == 0 and os.listdir(tmp) == [], os.listdir(tmp))
check("the pipeline's own query finds nothing, the one-day and the wide listings do not contain the expected name", "1) API όπως το χρησιμοποιεί το pipeline (getOperationMarketFile, μία ημέρα): 0 εγγραφές" in out and "περιέχει το αναμενόμενο όνομα: ΟΧΙ" in out, out)
check("the wide listing shows the neighbouring files with their full path (to see the folder pattern)", "20261025_RESMV_01.xls [24.10.2026→24.10.2026" in out and "διαδρομή: sites/default/files/attached-files/type-file/2026/10/20261025_RESMV_01.xls" in out, out)
check("the direct download by name finds it and says so with the address", "ΒΡΕΘΗΚΕ στη διεύθυνση https://www.admie.gr/sites/default/files/attached-files/type-file/2026/10/20261026_RESMV_01.xls" in out, out)
check("the analysis: one ΗΜΕΡΑ with 24 rows, hours 1…24, and hour 4 recognised as the SUM of two hours", "ΗΜΕΡΑ στο αρχείο: 20261025: 24 γραμμές" in out and "ΩΡΑ: 1…24" in out and "ΩΡΑ 4 (×" in out, out)
check("the conclusion says the file exists but the pipeline does not find it", "το αρχείο βρέθηκε μέσω: άμεση λήψη; το pipeline (1) ΔΕΝ το βρίσκει" in out, out)
print("TEST 3: a spring day — one file holds two days (listed with the range 28→29), the pipeline's own query is empty")
d = date(2026, 3, 29); two = entry("20260330_RESMV_01.xls", date(2026, 3, 28), date(2026, 3, 29), "30.03.2026 10:05", "2026/03")
reset(listed=[two], files={url_of(two): resmv_bytes([(date(2026, 3, 28), list(range(1, 25)), None), (d, list(range(1, 24)), None)])})
sys.argv = ['x', '2026-03-29']; r, out = cap(X.main)
check("both days of the file are counted, the rows of the wanted day are selected, and the missing hour label is named", "ΗΜΕΡΑ στο αρχείο: 20260328: 24 γραμμές, 20260329: 23 γραμμές" in out and "γραμμές της 2026-03-29: 23 (η ημέρα έχει 23 ώρες)" in out and "ΛΕΙΠΟΥΝ οι ΩΡΑ [24]" in out, out)
check("found through the range listing (not through the pipeline's one-day query)", "λήψη από API εύρους: ΕΠΙΤΥΧΗΣ" in out and "το pipeline (1) ΔΕΝ το βρίσκει" in out, out)
check("an ordinary file has no row flagged as a double hour", "μοιάζουν με ΑΘΡΟΙΣΜΑ δύο ωρών (πάνω από 1,7× των γειτονικών): καμία" in out, out)
print("TEST 4: a file published two months late sits in a later folder")
d = date(2024, 3, 31); reset(files={"https://www.admie.gr/sites/default/files/attached-files/type-file/2024/05/20240401_RESMV_01.xlsx": resmv_bytes([(d, list(range(1, 24)), None)])})
sys.argv = ['x', '2024-03-31']; r, out = cap(X.main)
check("found in the folder two candidates later, with the failed attempts listed (404)", "ΒΡΕΘΗΚΕ στη διεύθυνση https://www.admie.gr/sites/default/files/attached-files/type-file/2024/05/20240401_RESMV_01.xlsx" in out and "2024/04/20240401_RESMV_01.xls → 404" in out, out)
print("TEST 5: nothing found anywhere, an ordinary day, failures")
reset(soft404=True); sys.argv = ['x', '2026-10-25']; r, out = cap(X.main)
check("a site that answers 200 with an error page (HTML) is NOT taken for the file: every attempt is labelled and the result is 'not found'", "200 (ΔΕΝ είναι Excel: πιθανή σελίδα σφάλματος)" in out and "ΣΥΜΠΕΡΑΣΜΑ: το αρχείο ΔΕΝ βρέθηκε με κανέναν τρόπο" in out and "ΒΡΕΘΗΚΕ" not in out, out)
reset(); sys.argv = ['x', '2024-10-27']; r, out = cap(X.main)
check("not found by any means: said clearly, no invented result", "ΣΥΜΠΕΡΑΣΜΑ: το αρχείο ΔΕΝ βρέθηκε με κανέναν τρόπο" in out and "ΒΡΕΘΗΚΕ" not in out, out)
d = date(2026, 10, 24); reset(single={d: [ok24]}, listed=[ok24], files={url_of(ok24): resmv_bytes([(d, list(range(1, 25)), None)])})
sys.argv = ['x', '2026-10-24']; r, out = cap(X.main)
check("an ordinary day: the pipeline's query finds it, no double hour", "το pipeline (1) το βρίσκει" in out and "μοιάζουν με ΑΘΡΟΙΣΜΑ δύο ωρών (πάνω από 1,7× των γειτονικών): καμία" in out, out)
reset(down=True); sys.argv = ['x', '2026-10-25']; r, out = cap(X.main)
check("network down: rc 0, every step reports it, normal end", r == 0 and "δεν ήρθε (δεν απάντησε)" in out and "=== ΤΕΛΟΣ ===" in out, out[-300:])
reset(); _o = X.analyse
X.analyse = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
reset(files={"https://www.admie.gr/sites/default/files/attached-files/type-file/2026/10/20261026_RESMV_01.xls": resmv_bytes([(date(2026, 10, 25), list(range(1, 25)), 4)])})
sys.argv = ['x', '2026-10-25', '2026-10-26']; r, out = cap(X.main); X.analyse = _o
check("an unexpected error on one day is printed with the day and the next day is still processed", r == 0 and "ΣΦΑΛΜΑ στην ημέρα 2026-10-25: RuntimeError: boom" in out and "--- 2026-10-26" in out and "=== ΤΕΛΟΣ ===" in out, out[-400:])
sys.argv = ['x', 'not-a-date']; r, _ = cap(X.main); check("invalid date -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
