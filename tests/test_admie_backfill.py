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
print("TEST 6: cleaning rules found in the real data (empty cells, empty versions, false zeros)")
def res_vals(vals, total):
    rows = [[None, "2018-01-01", None, "Lake Filling-Rate (as of)", None], [None, None, "Filling Rate (%)", None, None]]
    for n in OLD_RES: rows.append([None, n, None if n in ("AGRAS", "EDESSAIOS") else vals.get(n, vals.get("*"))])
    rows.append(["FILLING RATE (%) TOTAL", None, None, total, None]); return xlsx("20180101ReservoirFillingRate", rows)
def sc_nan_hour():
    rows = [[None, "ΣΥΝΟΛΙΚΟ ΦΟΡΤΙΟ"] + [100.0] * 24, [None, "ΑΝΤΛΗΣΗ"] + [5.0] * 24]
    for i, (key, names, _) in enumerate(U.HYDRO_UNITS): rows.append([None, names[0]] + ([100.0] * 23 + [None] if i == 0 else [100.0] * 24))
    rows += [[None, al[0]] + [10.0] * 24 for key, al in U.OTHER_HYDRO_SCADA]
    rows += [[None, "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ"] + [16 * 100.0 + 10.0 * len(U.OTHER_HYDRO_SCADA)] * 24]
    return xlsx("System_Production", rows)
G = lambda m, dd: date(2018, m, dd)
def reg(cat, d, name, path_extra="", pub="01.01.2020 10:00", content=None):
    e = {"file_path": f"files/x{cat}/{d.isoformat()}_{name}{path_extra}", "file_fromdate": fmt(d), "file_todate": fmt(d), "file_published": pub}
    CAT[U.CAT_RESERVOIR if cat == "res" else U.CAT_SCADA].append(e); FILES[e["file_path"]] = content; return e
# 2018-04-24: _01 complete, _02 (published LATER) completely empty  -> the COMPLETE one must be chosen
# 2018-04-25: every version empty -> invalid file
# 2018-05-09: two complete versions that differ -> latest chosen, 'values' conflict
# 2018-06-10: zero-filled day;  2018-06-20/21/22: Kremasta 37 -> 0 -> 38 (isolated zero glitch)
EMPTY = res_vals({"*": None}, None); GOOD = res_vals({"*": 0.37, "KREMASTA": 0.5}, 0.7)
reg("res", G(4, 24), "ReservoirFillingRate_01.xls", content=GOOD); reg("res", G(4, 24), "ReservoirFillingRate_02.xls", pub="01.01.2020 11:00", content=EMPTY)
reg("res", G(4, 25), "ReservoirFillingRate_01.xls", content=EMPTY); reg("res", G(4, 25), "ReservoirFillingRate_02.xls", content=EMPTY)
reg("res", G(5, 9), "ReservoirFillingRate_01.xls", content=GOOD); reg("res", G(5, 9), "ReservoirFillingRate_02.xls", content=res_vals({"*": 0.37, "KREMASTA": 0.55}, 0.7))
reg("res", G(6, 10), "ReservoirFillingRate_01.xls", content=res_vals({"*": 0.0}, 0.0))
for dd, v in ((20, 0.37), (21, 0.0), (22, 0.38)): reg("res", G(6, dd), "ReservoirFillingRate_01.xls", content=res_vals({"*": 0.37, "KREMASTA": v}, 0.7))
reg("scada", G(6, 20), "SystemRealizationSCADA_01.xls", content=sc_nan_hour()); reg("scada", G(4, 25), "SystemRealizationSCADA_01.xls", content=sc_file())
os.chdir(tempfile.mkdtemp()); downloads.clear(); sys.argv = ['x', '2018', '--from=2018-04-24', '--to=2018-06-22']; r, out = cap(B.main)
txt = open('data/history/admie_2018.json', encoding='utf-8').read(); d = json.loads(txt, parse_constant=lambda c: (_ for _ in ()).throw(ValueError("NaN/Infinity in JSON: " + c))); ix = {x: i for i, x in enumerate(d["Dates"])}
check("the file is STRICT JSON: no NaN token, parseable with NaN forbidden", "NaN" not in txt and r == 0)
check("2018-04-24: the version published later is EMPTY, so the COMPLETE older one (_01) is kept; the empty one is recorded as a conflict of kind 'empty_version'", d["Fill"]["KREMASTA"][ix["2018-04-24"]] == 50.0 and any(c["date"] == "2018-04-24" and c["kind"] == "empty_version" and c["chosen"].endswith("_01.xls") and any("_02.xls" in z for z in c["diff"]) for c in d["Quality"]["Conflicts"]), d["Quality"]["Conflicts"])
check("2018-04-25: all versions empty -> not stored as data, listed as invalid file and in NoReservoirData; the SCADA of that day is kept", "2018-04-25" in d["Quality"]["InvalidFiles"]["reservoir"] and "2018-04-25" in d["Quality"]["NoReservoirData"] and d["Fill"]["KREMASTA"][ix["2018-04-25"]] is None and d["TotalHydro"][ix["2018-04-25"]] == 39360.0)
check("2018-05-09: two complete versions that differ -> the latest is chosen, conflict of kind 'values' with the difference", d["Fill"]["KREMASTA"][ix["2018-05-09"]] == 55.0 and any(c["date"] == "2018-05-09" and c["kind"] == "values" and any("KREMASTA" in x for x in c["diff"]) for c in d["Quality"]["Conflicts"]), d["Quality"]["Conflicts"])
check("a day filled with zeros (all reservoirs 0.0, total 0) is INVALID, never stored as zeros", "2018-06-10" in d["Quality"]["InvalidFiles"]["reservoir"] and "2018-06-10" in d["Quality"]["NoReservoirData"] and "2018-06-10" not in d["Dates"])
check("an isolated zero (Kremasta 37 → 0 → 38) becomes null and is listed in ZeroGlitches; the neighbours keep their values", d["Fill"]["KREMASTA"][ix["2018-06-21"]] is None and d["Quality"]["ZeroGlitches"].get("KREMASTA") == ["2018-06-21"] and d["Fill"]["KREMASTA"][ix["2018-06-20"]] == 37.0 and d["Fill"]["KREMASTA"][ix["2018-06-22"]] == 38.0, d["Quality"]["ZeroGlitches"])
check("a SCADA row with one blank hour: that unit is null (not a partial sum), the others and TOTAL HYDRO are kept", d["Gen"]["Kremasta"][ix["2018-06-20"]] is None and d["Gen"]["Kastraki"][ix["2018-06-20"]] == 2400.0 and d["TotalHydro"][ix["2018-06-20"]] == 39360.0)
print("TEST 7: a second run does not re-ask files that are known to be invalid; a legacy file with NaN is repaired")
downloads.clear(); sys.argv = ['x', '2018', '--from=2018-04-24', '--to=2018-06-22']; cap(B.main)
check("the second run downloads nothing again for the invalid days (04-25 and 06-10)", not any(("2018-04-25_Reservoir" in p) or ("2018-06-10_Reservoir" in p) for p in downloads), [p for p in downloads][:6])
legacy = {"Schema": 1, "Year": 2018, "Dates": ["2018-04-25"], "FillTotal": [float("nan")], "Fill": {k: [float("nan")] for k in U.RESERVOIRS}, "Gen": {k: [100.0] for k in B.UNIT_ALL},
          "TotalHydro": [39360.0], "Pump": [120.0], "Quality": {"Failed": {}, "Conflicts": [{"date": "2018-04-25", "category": "reservoir", "files": ["a_01.xls", "a_02.xls"], "chosen": "a_02.xls", "diff": ["ASOMATA: nan → nan"]}], "Relabelled": {"reservoir": {}, "scada": {}}}}
os.chdir(tempfile.mkdtemp()); os.makedirs('data/history'); json.dump(legacy, open('data/history/admie_2018.json', 'w', encoding='utf-8'))
check("(the legacy file really contains NaN)", "NaN" in open('data/history/admie_2018.json', encoding='utf-8').read())
good25 = reg("res", G(4, 25), "ReservoirFillingRate_09.xls", content=GOOD, pub="01.02.2020 10:00")
sys.argv = ['x', '2018', '--from=2018-04-25', '--to=2018-04-25']; cap(B.main); txt2 = open('data/history/admie_2018.json', encoding='utf-8').read(); d2 = json.loads(txt2, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
check("the repaired file is strict JSON, the all-NaN day is filled from a complete version, the false 'nan → nan' conflict is gone", "NaN" not in txt2 and d2["Fill"]["KREMASTA"][0] == 50.0 and not any("nan" in json.dumps(c["diff"]).lower() for c in d2["Quality"]["Conflicts"]), d2["Quality"]["Conflicts"])
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
