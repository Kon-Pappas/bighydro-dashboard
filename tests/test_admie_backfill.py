import sys, os, io, json, tempfile, contextlib
from datetime import date, timedelta
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
import backfill_admie_history as B
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
B.time.sleep = lambda s: None
class R:
    def __init__(s, status=200, data=None, content=b""): s.status_code = status; s._d = data; s.content = content
    def json(s):
        if s._d is None: raise ValueError("no json")
        return s._d
def xlsx(sheet, rows):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w: pd.DataFrame(rows).to_excel(w, sheet_name=sheet, header=False, index=False)
    return bio.getvalue()
OLD_RES = ["POLYFYTO", "SFIKIA", "ASOMATA", "KREMASTA", "KASTRAKI", "STRATOS1", "P_AOOU", "POURNARI1", "POURNARI2", "THESAVROS1", "THESAVROS2", "THESAVROS3", "PLATANOVRYSI", "LADONAS", "PLASTIRAS", "AGRAS", "EDESSAIOS"]
def res_file(kremasta=0.5, total=0.7, ilar=None):
    rows = [[None, "2019-07-15", None, "Lake Filling-Rate (as of)", None], [None, None, "Filling Rate (%)", None, None]]
    for n in OLD_RES: rows.append([None, n, (kremasta if n == "KREMASTA" else (None if n in ("AGRAS", "EDESSAIOS") else 0.37))])
    if ilar is not None: rows.append([None, "ILARIONAS", ilar])
    rows.append(["FILLING RATE (%) TOTAL", None, None, total, None])
    return xlsx("20190715ReservoirFillingRate", rows)
def sc_file():
    rows = [[None, "ΣΥΝΟΛΙΚΟ ΦΟΡΤΙΟ"] + [100.0] * 24, [None, "ΑΝΤΛΗΣΗ"] + [5.0] * 24]
    rows += [[None, names[0]] + [100.0] * 24 for key, names, _ in U.HYDRO_UNITS]
    rows += [[None, al[0]] + [10.0] * 24 for key, al in U.OTHER_HYDRO_SCADA]
    rows += [[None, "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ"] + [16 * 100.0 + 10.0 * len(U.OTHER_HYDRO_SCADA)] * 24]
    return xlsx("System_Production", rows)
fmt = lambda d: d.strftime("%d.%m.%Y")
def rec(cat, d, name, pub="01.01.2020 10:00"):
    return {"file_path": f"files/{cat}/{d.isoformat()}_{name}", "file_fromdate": fmt(d), "file_todate": fmt(d), "file_published": pub}
D = lambda n: date(2019, 7, n)
CAT = {U.CAT_RESERVOIR: [rec("res", D(14), "ReservoirFillingRate_01.xls"), rec("res", D(15), "ReservoirFillingRate_01.xls"), rec("res", D(16), "ReservoirFillingRate_01.xls"),
                         rec("res", D(17), "ReservoirFillingRate_01.xls"), rec("res", D(17), "ReservoirFillingRate_02.xls"), rec("res", D(19), "ReservoirFillingRate_01.xls")],
       U.CAT_SCADA: [rec("sc", D(14), "SystemRealizationSCADA_01.xls"), rec("sc", D(16), "SystemRealizationSCADA_01.xls", "02.08.2020 08:40"), rec("sc", D(16), "SystemRealizationSCADA_01.xls", "02.08.2020 10:35"),
                     rec("sc", D(17), "SystemRealizationSCADA_01.xls"), rec("sc", D(18), "SystemRealizationSCADA_01.xls"), rec("sc", D(19), "SystemRealizationSCADA_01.xls")]}
FILES = {}
for cat in CAT:
    for e in CAT[cat]:
        FILES[e["file_path"]] = res_file() if "/res/" in e["file_path"] else sc_file()
FILES[f"files/res/{D(17).isoformat()}_ReservoirFillingRate_02.xls"] = res_file(kremasta=0.55, ilar=0.28)       # a LATER version that differs
downloads, FAILING = [], {f"files/res/{D(19).isoformat()}_ReservoirFillingRate_01.xls"}
def fake(url, params=None, tries=3, what="", use_session=True):
    if url == B.RANGE_URL:
        a, b = date.fromisoformat(params["dateStart"]), date.fromisoformat(params["dateEnd"])
        return R(200, [e for e in CAT[params["FileCategory"]] if a <= U.parse_admie_date(e["file_fromdate"]) <= b])
    p = url.split(U.BASE_URL + "/", 1)[-1]; downloads.append(p)
    return R(500) if p in FAILING else R(200, content=FILES[p])
U.http_get = fake
tmp = tempfile.mkdtemp(); os.chdir(tmp)
A = ['2019', '--from=2019-07-14', '--to=2019-07-19']
def load(): return json.load(open('data/history/admie_2019.json', encoding='utf-8'))
print("TEST 1: relabelling, parsing, daily values")
sys.argv = ['x'] + A; r, out = cap(B.main); d = load(); ix = {x: i for i, x in enumerate(d["Dates"])}
check("rc 0; one yearly file under data/history/, nothing in data/days/, no .tmp left", r == 0 and os.listdir('data') == ['history'] and sorted(os.listdir('data/history')) == ['admie_2019.json'], os.listdir('data'))
check("days with any data are stored in ascending order (14–19 July)", d["Dates"] == [f"2019-07-{n}" for n in range(14, 20)], d["Dates"])
i14 = ix["2019-07-14"]
check("old reservoir names are mapped: STRATOS1 → STRATOS, POURNARI1/2 → POYRNARI1/2 (37 %), the official total 70 %, Kremasta 50 %", d["Fill"]["STRATOS"][i14] == 37.0 and d["Fill"]["POYRNARI1"][i14] == 37.0 and d["Fill"]["POYRNARI2"][i14] == 37.0 and d["FillTotal"][i14] == 70.0 and d["Fill"]["KREMASTA"][i14] == 50.0, {k: d["Fill"][k][i14] for k in ("STRATOS", "POYRNARI1", "KREMASTA")})
check("Ilarionas is absent from the old file (14 July): null, never zero; its first published day (17 July) is recorded", d["Fill"]["ILARIONAS"][i14] is None and d["Quality"]["ReservoirFirstDay"]["ILARIONAS"] == "2019-07-17" and d["Fill"]["ILARIONAS"][ix["2019-07-17"]] == 28.0)
check("SCADA: 100 MW × 24 h = 2400 MWh per unit; the 4 small plants 240; TOTAL HYDRO 1640 MW × 24 = 39360; pumping 5 MW × 24 = 120", d["Gen"]["Kremasta"][i14] == 2400.0 and d["Gen"]["Stratos2"][i14] == 240.0 and d["TotalHydro"][i14] == 39360.0 and d["Pump"][i14] == 120.0 and len(d["Gen"]) == 20, {k: d["Gen"][k][i14] for k in ("Kremasta", "Stratos2")})
check("the mapping is recorded: reservoir {STRATOS1, POURNARI1, POURNARI2}, SCADA {ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ, ΑΝΤΛΗΣΗ}", set(d["Quality"]["Relabelled"]["reservoir"]) == {"STRATOS1", "POURNARI1", "POURNARI2"} and set(d["Quality"]["Relabelled"]["scada"]) == {"ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ", "ΑΝΤΛΗΣΗ"}, d["Quality"]["Relabelled"])
check("the message about reservoirs that appear later is relative to the FIRST STORED DAY (14 July): only Ilarionas (17 July) is named, not the reservoirs present from the start", "ΜΕΤΑ την πρώτη αποθηκευμένη ημέρα (2019-07-14): {'ILARIONAS': '2019-07-17'}" in out and "'KREMASTA': '2019" not in out.split("ΜΕΤΑ την πρώτη")[1].split("\n")[0], out[:900])
check("the warnings of the parsers are summarised, not printed day by day (Ilarionas missing)", any("λείπουν" in k for k in d["Quality"]["WarningsLastRun"]) and out.count("λείπουν") == 1 and "×4" in out, d["Quality"]["WarningsLastRun"])
print("TEST 2: gaps, duplicates, failures")
check("a day without a SCADA file (15 July) has null generation and is listed in NoScadaData; a day without a reservoir file (18 July) in NoReservoirData", d["Gen"]["Kremasta"][ix["2019-07-15"]] is None and "2019-07-15" in d["Quality"]["NoScadaData"] and d["Fill"]["KREMASTA"][ix["2019-07-18"]] is None and "2019-07-18" in d["Quality"]["NoReservoirData"])
check("the same file listed twice (16 July SCADA, two records with the same path) is downloaded ONCE", sum(1 for p in downloads if p == f"files/sc/{D(16).isoformat()}_SystemRealizationSCADA_01.xls") == 1, downloads)
c = [x for x in d["Quality"]["Conflicts"] if x["date"] == "2019-07-17"]
check("two versions of one day (_01, _02) that DIFFER: both downloaded, the latest (_02) chosen, the conflict recorded with the difference", len(c) == 1 and c[0]["chosen"].endswith("_02.xls") and any("KREMASTA" in x for x in c[0]["diff"]) and d["Fill"]["KREMASTA"][ix["2019-07-17"]] == 55.0, c)
check("a failed download is recorded for retry (19 July reservoir) while the SCADA of that day is kept", d["Quality"]["Failed"] == {"2019-07-19": ["reservoir"]} and d["TotalHydro"][ix["2019-07-19"]] == 39360.0, d["Quality"]["Failed"])
check("DST days are flagged (31 March and 27 October 2019)", d["Quality"]["DstDays"] == ["2019-03-31", "2019-10-27"])
print("TEST 3: resume and refresh")
downloads.clear(); FAILING.clear(); r, out = cap(B.main); d = load()
check("a second run downloads ONLY the previously failed file and clears the failure", downloads == [f"files/res/{D(19).isoformat()}_ReservoirFillingRate_01.xls"] and d["Quality"]["Failed"] == {} and d["Fill"]["KREMASTA"][ix["2019-07-19"]] == 50.0, (downloads, d["Quality"]["Failed"]))
downloads.clear(); sys.argv = ['x'] + A + ['--refresh']; cap(B.main)
check("--refresh downloads everything again", len(downloads) >= 10, len(downloads))
print("TEST 4: options")
os.chdir(tempfile.mkdtemp()); downloads.clear(); sys.argv = ['x', '2019', '--from=2019-07-14', '--to=2019-07-14', '--only=scada']; cap(B.main); d = load()
check("--only=scada fetches no reservoir file and leaves the reservoir columns null", all(v is None for v in d["Fill"]["KREMASTA"]) and d["Gen"]["Kremasta"] == [2400.0] and all('/res/' not in p for p in downloads), downloads)
os.chdir(tempfile.mkdtemp()); sys.argv = ['x', '2019', '--max-minutes=0']; r, out = cap(B.main)
check("an exhausted time budget stops cleanly before the first day and writes nothing", r == 0 and "ΔΙΑΚΟΠΗ" in out and not os.path.exists('data/history/admie_2019.json'), out[-300:])
for bad in (['x'], ['x', 'abc'], ['x', '2019', '--only=foo'], ['x', '2019', '--from=not-a-date'], ['x', '2020', '2019']):
    sys.argv = bad; r, _ = cap(B.main); check(f"invalid arguments {bad[1:]} -> rc 1", r == 1)
print("TEST 5: helpers")
e1 = {"file_path": "p/a_01.xls", "file_fromdate": "05.03.2018", "file_todate": "05.03.2018", "file_published": "13.03.2020 16:54"}
e2 = dict(e1, file_path="p/a_02.xls"); e3 = dict(e1, file_path="p/a_03.xls", file_published="13.03.2020 16:53")
g, sk = B.group_days([e1, e2, e3, {"file_path": "p/w.xls", "file_fromdate": "05.03.2018", "file_todate": "11.03.2018"}])
check("versions are ordered oldest → newest by publication time, then by _NN; multi-day files are skipped and counted", [os.path.basename(x["file_path"]) for x in g[date(2018, 3, 5)]] == ["a_03.xls", "a_01.xls", "a_02.xls"] and sk == 1, g)
check("a day with an incomplete SCADA row (a missing hour) gives null, never a partial sum", B.day_sum([1.0] * 23 + [None]) is None and B.day_sum([1.0] * 24) == 24.0 and B.day_sum(None) is None)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
