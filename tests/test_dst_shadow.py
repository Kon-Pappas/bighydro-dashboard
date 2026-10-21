import sys, os, io, tempfile, contextlib
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
import diagnose_admie_history as H
import diagnose_admie_dst_fix as S
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
H.time.sleep = lambda s: None; S.time.sleep = lambda s: None
URL = S.URL
ATH, BRU, UTC = ZoneInfo("Europe/Athens"), ZoneInfo("Europe/Brussels"), ZoneInfo("UTC")
T0 = datetime(2026, 1, 1, tzinfo=UTC)
def v(t): return 50.0 + ((int((t - T0).total_seconds() // 3600) * 37) % 400)           # truth: a distinct value for every real hour
def inst(d, tz):
    a = datetime.combine(d, dtime(0, 0), tzinfo=tz).astimezone(UTC); b = datetime.combine(d + timedelta(days=1), dtime(0, 0), tzinfo=tz).astimezone(UTC)
    return [a + timedelta(hours=i) for i in range(int(round((b - a).total_seconds() / 3600)))]
class R:
    def __init__(s, status=200, data=None, content=b""): s.status_code = status; s._d = data; s.content = content
    def json(s):
        if s._d is None: raise ValueError("no json")
        return s._d
def xlsx(sheet, rows):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w: pd.DataFrame(rows).to_excel(w, sheet_name=sheet, header=False, index=False)
    return bio.getvalue()
def scada_bytes(d):                       # REAL structure: label in col 1, 24 chronological hour columns, daily total in col 26 (25th hour only in the total)
    ts = inst(d, ATH); n = len(ts); rows = []; tot_h = [0.0] * n
    for k, (key, names, _i) in enumerate(U.HYDRO_UNITS):
        vals = [(k + 1) * v(t) for t in ts]; tot_h = [a + b for a, b in zip(tot_h, vals)]
        cols = vals[:24] + ([1.0] if n == 23 else []); rows.append([None, names[0]] + cols[:24] + [sum(vals)])
    cols = tot_h[:24] + ([1.0] if n == 23 else [])
    return xlsx("System_Production", [[None, "HOURS"] + [f"H{i}" for i in range(1, 25)] + ["TOTAL"], [None, "TOTAL HYDRO"] + cols[:24] + [sum(tot_h)]] + rows)
def isp_bytes(d):                         # market (CET) day: quarter-hours (constant within the hour) + a total column (sum / 4)
    ts = inst(d, BRU); rows = [["ISP"] + list(range(1, len(ts) * 4 + 2))]
    for k, (key, _s, names) in enumerate(U.HYDRO_UNITS):
        q = []
        for t in ts: q += [(k + 1) * v(t)] * 4
        rows.append([names[0]] + q + [sum(q) / 4])
    return xlsx("20260329_ISP", rows)
def fake(url, params=None, tries=3, what="", use_session=True):
    if url == URL:
        d = date.fromisoformat(params["dateStart"]); cat = "scada" if params["FileCategory"] == U.CAT_SCADA else "isp"; f = d.strftime("%d.%m.%Y")
        return R(200, [{"file_path": f"files/{cat}_{d.isoformat()}.xls", "file_fromdate": f, "file_todate": f}])
    kind, ds = url.split("/files/", 1)[-1].replace(".xls", "").split("_"); d = date.fromisoformat(ds)
    return R(200, content=scada_bytes(d) if kind == "scada" else isp_bytes(d))
U.http_get = fake
tmp = tempfile.mkdtemp(); os.chdir(tmp)
def block(out, d): return out.split(f"--- {d} ")[1].split("\n\n")[0] if f"--- {d} " in out else ""
print("TEST 1: the shadow run on files with the REAL structure")
sys.argv = ['x', '2026-03-29', '2026-03-30', '2025-10-26', '2025-10-27', '2026-03-28']; r, out = cap(S.main)
check("rc 0 and nothing written (read-only)", r == 0 and os.listdir(tmp) == [], os.listdir(tmp))
b = block(out, "2026-03-29")
new_line = [l for l in b.split("\n") if "νέα   (ώρες ρολογιού)" in l][0]
check("23-hour day: the energy of the new rows equals the file's total, and the missing 03:00 hour (H04) is shown as '·'", "→ ΟΚ (ισούται με το σύνολο του αρχείου)" in b and new_line.split(":")[1].split("|")[0].split()[3] == "·", new_line)
check("23-hour day: the sum of the 16 units also matches the file totals", b.count("→ ΟΚ") >= 2 and "ΔΕΝ ΤΑΙΡΙΑΖΕΙ" not in b, b)
b = block(out, "2025-10-26")
check("25-hour day: the 25th hour is recovered from the total (energy outside the rows > 0) and the energy equals the file's total", "→ ΟΚ (ισούται με το σύνολο του αρχείου)" in b and "ενέργεια εκτός γραμμών: 0 MWh" not in b, b)
b = block(out, "2026-03-30")
check("K04 reproduced on the day after the 23-hour day: the OLD reading has an impossible hour (H1) and the NEW one has none", "παλιά H[1]  <-- ΣΦΑΛΜΑ (K04)" in b and "| νέα καμία" in b, b)
check("after the fix SCADA and ISP agree hour by hour on the clock-change days and the day after (correlation 1.00)", all("νέα 1.00" in block(out, d) for d in ("2026-03-29", "2026-03-30", "2025-10-26", "2025-10-27")), [l for l in out.split("\n") if "συσχέτιση" in l])
check("an ordinary day has no problem in either reading", "<-- " not in block(out, "2026-03-28"), block(out, "2026-03-28"))
print("TEST 2: failures")
U.http_get = lambda *a, **k: None
r, out = cap(S.main); check("network down: rc 0, 'δεν κατέβηκε αρχείο', normal end", r == 0 and "δεν κατέβηκε αρχείο" in out and "=== ΤΕΛΟΣ ===" in out, out[-300:])
U.http_get = fake; sys.argv = ['x', 'not-a-date']; r, _ = cap(S.main); check("invalid date -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
