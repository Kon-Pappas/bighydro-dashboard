import sys, os, io, math, contextlib
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
import clock_change as CC
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
ATH, BRU, UTC = ZoneInfo("Europe/Athens"), ZoneInfo("Europe/Brussels"), ZoneInfo("UTC")
T0 = datetime(2026, 1, 1, tzinfo=UTC)
def v(t): return 50.0 + ((int((t - T0).total_seconds() // 3600) * 37) % 400)          # TRUTH: a distinct value per real hour, a function of the UTC instant only
def inst(d, tz):
    a = datetime.combine(d, dtime(0, 0), tzinfo=tz).astimezone(UTC); b = datetime.combine(d + timedelta(days=1), dtime(0, 0), tzinfo=tz).astimezone(UTC)
    return [a + timedelta(hours=i) for i in range(int(round((b - a).total_seconds() / 3600)))]
def pump(t): return 40.0 if int(v(t)) % 3 == 0 else 0.0
UK = {key: k for k, (key, _s, _i) in enumerate(U.HYDRO_UNITS)}
f_unit = lambda k: (lambda t: (k + 1) * v(t))
f_part = lambda j: (lambda t: 0.5 * (j + 1) * v(t))
f_total = lambda t: sum((k + 1) * v(t) for k in range(len(U.HYDRO_UNITS))) + sum(0.5 * (j + 1) * v(t) for j in range(len(U.OTHER_HYDRO_SCADA)))
f_small = lambda t: 0.3 * v(t)                         # RESMV, MWh
def truth_clock(f, d, tz=ATH):
    by = {h: [] for h in range(24)}
    for t in inst(d, ATH): by[t.astimezone(ATH).hour].append(f(t))
    return [None if not by[h] else sum(by[h]) / len(by[h]) for h in range(24)]
def close(a, b, tol=0.011): return a is None and b is None or (a is not None and b is not None and abs(a - b) <= tol)
def rows_close(a, b, tol=0.011): return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
def xlsx(sheet, rows):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w: pd.DataFrame(rows).to_excel(w, sheet_name=sheet, header=False, index=False)
    return bio.getvalue()
LAYOUT = {"cols": 28}
def scada_bytes(d):
    ts = inst(d, ATH); n = len(ts); rows = [["hdr"] + ["x"] * 25]
    def add(label, f):
        vals = [f(t) for t in ts]; cols = vals[:24] + ([1.0] if n == 23 else [])
        total = sum(vals) + (1.0 if n == 23 else 0.0)
        tail = [(vals[24] if n == 25 else 0.0), total] if LAYOUT["cols"] == 28 else [total]
        rows.append(["id", label] + cols[:24] + tail)
    for key, names, _i in U.HYDRO_UNITS: add(names[0], f_unit(UK[key]))
    add("TOTAL PUMPING", pump)
    for j, (key, aliases) in enumerate(U.OTHER_HYDRO_SCADA): add(aliases[0], f_part(j))
    add("TOTAL HYDRO", f_total)
    add("ΑΥΛΑΚΙ (ΜΥΗΣ)", lambda t: 0.01 * v(t))
    return xlsx("System_Production", rows)
def isp_bytes(d):
    ts = inst(d, BRU); nq = 4 * len(ts); rows = [["ISP"] + list(range(1, nq + 2))]
    def add(label, f):
        q = []
        for t in ts: q += [f(t)] * 4
        rows.append([label] + q + [sum(q) / 4])
    for key, _s, names in U.HYDRO_UNITS:
        for j, nm in enumerate(names): add(nm, (lambda g: (lambda t: g(t) * 1.0))(f_unit(UK[key])) if j == 0 else (lambda t: 0.0))
    add("SFIKIA_PUMP", lambda t: -0.6 * pump(t)); add("THESAVROS1_PUMP", lambda t: -0.4 * pump(t)); add("THESAVROS2_PUMP", lambda t: 0.0); add("THESAVROS3_PUMP", lambda t: 0.0)
    return xlsx("20261025_ISP", rows)
RESMV_STYLE = {}
def resmv_bytes(d):
    ts = inst(d, ATH); n = len(ts); style = RESMV_STYLE.get(d) or {23: "missing4", 24: "normal", 25: "summed"}[n]
    kwh = [1000.0 * f_small(t) for t in ts]; D = int(d.strftime("%Y%m%d")); rows = [['ΗΜΕΡΑ', 'ΩΡΑ', 'B/A ΕΝΕΡΓΕΙΑ KWh', 'ΜΥΗΣ ΕΝΕΡΓΕΙΑ KWh', 'Φ/Β ΕΝΕΡΓΕΙΑ KWh']]
    if style == "normal": data = [(i + 1, x) for i, x in enumerate(kwh)]
    elif style == "chrono25": data = [(i + 1, x) for i, x in enumerate(kwh)]
    elif style == "summed": data = [(1, kwh[0]), (2, kwh[1]), (3, kwh[2]), (4, kwh[3] + kwh[4])] + [(h, kwh[h]) for h in range(5, 25)]       # 2025+: 24 clock rows, hour 4 = SUM of the two 03:00 hours
    else: data = [(h + 1 if h < 3 else h + 2, x) for h, x in enumerate(kwh)]                                                                 # 23 h: the label 4 is missing
    if ("RESMV", d) in TWO_DAY:                       # a GENUINE two-day file: the previous day first (other values), then the wanted day
        for h in range(1, 25): rows.append([int((d - timedelta(days=1)).strftime("%Y%m%d")), float(h), 1.0, 99999.0, 2.0])
    for h, x in data: rows.append([D, float(h), 1.0, x, 2.0])
    rows += [["Τα ανωτέρω στοιχεία"] + [None] * 4]
    return xlsx("Sheet1", rows)
def entsoe_xml(d):
    a = datetime.combine(d, dtime(0, 0), tzinfo=ATH).astimezone(UTC); n = CC.hours_in_day(d); b = a + timedelta(hours=n)
    pts = "".join(f"<Point><position>{i + 1}</position><price.amount>{v(a + timedelta(hours=i))}</price.amount></Point>" for i in range(n))
    return ('<?xml version="1.0"?><Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"><TimeSeries><Period><timeInterval>'
            f'<start>{a:%Y-%m-%dT%H:%MZ}</start><end>{b:%Y-%m-%dT%H:%MZ}</end></timeInterval><resolution>PT60M</resolution>{pts}</Period></TimeSeries></Publication_MarketDocument>')
class Resp:
    def __init__(s, status=200, content=b"", text="", js=None): s.status_code = status; s.content = content; s.text = text; s._js = js
    def json(s): return s._js
HIDE_SINGLE = set(); TWO_DAY = set(); UNKNOWN_NEIGHBOUR = set(); CALLS = []
def entry(cat, x, fromd=None, tod=None):
    f = (fromd or x).strftime("%d.%m.%Y"); t = (tod or x).strftime("%d.%m.%Y")
    return {"file_path": f"/files/{cat}__{x.isoformat()}.xls", "file_fromdate": f, "file_todate": t}
def fake(url, params=None, tries=3, what="", use_session=True):
    if url == U.API_FILES:
        cat = params["FileCategory"]; x = date.fromisoformat(params["dateStart"]); CALLS.append(("single", cat, x))
        if (cat, x) in HIDE_SINGLE or (cat, x) in TWO_DAY: return Resp(js=[])
        return Resp(js=[entry(cat, x)])
    if url == U.API_FILES_RANGE:
        cat = params["FileCategory"]; d0, d1 = date.fromisoformat(params["dateStart"]), date.fromisoformat(params["dateEnd"]); CALLS.append(("range", cat, d0, d1)); out = []
        x = d0
        while x <= d1:
            if (cat, x) in TWO_DAY: out.append(entry(cat, x, x - timedelta(days=1), x))
            elif (cat, x) in UNKNOWN_NEIGHBOUR: out.append({"file_path": f"/files/{cat}__{x.isoformat()}.xls", "file_fromdate": None, "file_todate": None})
            else: out.append(entry(cat, x))
            x += timedelta(days=1)
        return Resp(js=out)
    if url.startswith(U.BASE_URL) and "/files/" in url:
        cat, ds = os.path.basename(url)[:-4].split("__"); x = date.fromisoformat(ds)
        return Resp(content={"SystemRealizationSCADA": scada_bytes, "ISP2ISPResults": isp_bytes, "RESMV": resmv_bytes}[cat](x))
    if url == U.ENTSOE_URL:
        a = datetime.strptime(params["periodStart"], "%Y%m%d%H%M").replace(tzinfo=UTC); x = (a + timedelta(hours=3)).date()
        return Resp(text=entsoe_xml(x))
    raise AssertionError(url)
U.http_get = fake; U.ENTSOE_TOKEN = "x"
SRC = {"scada", "isp", "resmv", "mcp"}
def run(d, existing=None, only=SRC):
    CALLS.clear(); (rec, got), log = cap(U.process_day, d, existing, {}, only); return rec, log
D23, D23n, D25, D25n, DN = date(2026, 3, 29), date(2026, 3, 30), date(2026, 10, 25), date(2026, 10, 26), date(2026, 7, 15)
print("TEST 1: every source of the 25-hour day (25 Oct 2026) equals the truth hour by hour (28-column SCADA, summed RESMV hour, MCP)")
rec, log = run(D25); H = rec["Hourly"]; col = lambda k: [h.get(k) for h in H]
check("SCADA total hydro: 24 clock rows (H04 = mean of the two 03:00 hours, H24 = the explicit 25th hour)", rows_close(col("SCADA_TotalHydro"), truth_clock(f_total, D25)), (col("SCADA_TotalHydro")[:6], truth_clock(f_total, D25)[:6]))
check("a unit, the pump and a small plant (Stratos 2) too", all(rows_close(col(k), truth_clock(f, D25)) for k, f in (("SCADA_Kremasta", f_unit(UK['Kremasta'])), ("SCADA_Pump", pump), ("SCADA_Stratos2", f_part(0)))))
check("ISP: units and the pump split equal the truth (H01 from the last real market hour of 24 Oct)", rows_close(col("ISP_Kremasta"), truth_clock(f_unit(0), D25)) and rows_close(col("ISP_Pump"), truth_clock(pump, D25)) and rows_close(col("ISP_PumpSfikia"), truth_clock(lambda t: 0.6 * pump(t), D25)), (col("ISP_Kremasta")[:5], truth_clock(f_unit(0), D25)[:5]))
check("RESMV (2025+ convention: hour 4 = SUM of two hours): H04 is half of it, and the other rows are the clock hours", rows_close(col("SCADA_SmallHydro"), truth_clock(f_small, D25)), (col("SCADA_SmallHydro")[:6], truth_clock(f_small, D25)[:6]))
check("MCP: the 25 elapsed hours become 24 clock rows", rows_close(col("MCP_GR"), truth_clock(v, D25)), (col("MCP_GR")[:6], truth_clock(v, D25)[:6]))
cc = rec["Meta"].get("ClockChange") or {}
check("Meta.ClockChange: 25 hours, H04 repeated, and the energy outside the rows for SCADA, ISP and RESMV", cc.get("Hours") == 25 and cc.get("Kind") == "repeated" and cc.get("Hour") == "H04" and all(k in cc["ExtraHourMWh"] for k in ("SCADA_TotalHydro", "SCADA_Kremasta", "ISP_Kremasta", "SCADA_SmallHydro")), cc)
S = U.day_summary(rec); tr_all = lambda f: sum(f(t) for t in inst(D25, ATH))
check("daily energy = the energy of ALL 25 hours (file total) for SCADA total hydro, a unit and RESMV", close(S["SCADA_TotalHydro_MWh"], tr_all(f_total), 0.2) and close(S["SCADA_MWh"]["Kremasta"], tr_all(f_unit(0)), 0.2) and close(S["SmallHydro_MWh"], tr_all(f_small), 0.2), (S["SCADA_TotalHydro_MWh"], tr_all(f_total)))
check("daily ISP energy of the 25-hour local day equals the truth", close(S["ISP_MWh"]["Kremasta"], tr_all(f_unit(0)), 0.2), (S["ISP_MWh"]["Kremasta"], tr_all(f_unit(0))))
ps = U.pump_split(rec["Hourly"], cc["ExtraHourMWh"])
check("pump split: SCADA pumping energy includes the second half of the repeated hour", close(ps["ScadaMWh"], tr_all(pump), 0.2) and close(ps["IspMWh"], tr_all(pump), 0.2), (ps["ScadaMWh"], tr_all(pump)))
check("all five sources are 'ok' (no false 'partial')", all(rec["Meta"]["Status"][k] == "ok" for k in ("scada", "isp", "resmv", "mcp")), rec["Meta"]["Status"])
check("CC.energy (used by the water balance, pumped storage and unit status) equals the truth", close(CC.energy(rec, "SCADA_Kremasta"), tr_all(f_unit(0)), 0.2))
print("TEST 2: the day after (26 Oct): H01 of the ISP is the 25th hour of 25 Oct, not the 24th")
rec2, _ = run(D25n); H2 = rec2["Hourly"]
check("ISP H01 of 26 Oct equals the truth, the whole day does too, and the day has no ClockChange", rows_close([h.get("ISP_Kremasta") for h in H2], truth_clock(f_unit(0), D25n)) and "ClockChange" not in rec2["Meta"], ([h.get("ISP_Kremasta") for h in H2][:3], truth_clock(f_unit(0), D25n)[:3]))
print("TEST 3: the 23-hour day (29 Mar 2026): H04 empty, nothing 'partial', and the day after has no K04 value")
rec3, log3 = run(D23); H3 = rec3["Hourly"]; col3 = lambda k: [h.get(k) for h in H3]
check("SCADA, ISP, RESMV and MCP equal the truth, with H04 empty everywhere", all(rows_close(col3(k), truth_clock(f, D23)) and col3(k)[3] is None for k, f in (("SCADA_TotalHydro", f_total), ("ISP_Kremasta", f_unit(0)), ("SCADA_SmallHydro", f_small), ("MCP_GR", v))))
check("status: the nonexistent hour is not 'partial data' (all four sources ok) and ClockChange says 23 hours / missing", all(rec3["Meta"]["Status"][k] == "ok" for k in ("scada", "isp", "resmv", "mcp")) and rec3["Meta"]["ClockChange"]["Kind"] == "missing" and rec3["Meta"]["ClockChange"]["ExtraHourMWh"] == {}, rec3["Meta"])
check("daily energy of the 23 real hours (the stray value in the empty last column is NOT counted)", close(U.day_summary(rec3)["SCADA_TotalHydro_MWh"], sum(f_total(t) for t in inst(D23, ATH)), 0.2))
check("CC.energy works although H04 is empty (the old sum raised TypeError and the day was dropped from the water balance)", close(CC.energy(rec3, "SCADA_Kremasta"), sum(f_unit(0)(t) for t in inst(D23, ATH)), 0.2))
rec4, _ = run(D23n); H4 = rec4["Hourly"]; isp1 = H4[0].get("ISP_Kremasta"); mx = max(h.get("ISP_Kremasta") or 0 for h in H4[1:])
check("K04 fixed: H01 of 30 Mar is a real value (the old reading put the daily total there), and the whole day equals the truth", isp1 is not None and isp1 <= mx * 1.5 and rows_close([h.get("ISP_Kremasta") for h in H4], truth_clock(f_unit(0), D23n)), (isp1, mx))
print("TEST 4: replacement on clock-change days; merge unchanged on ordinary days")
stale = {"Date": D23.isoformat(), "Hourly": [{**U.blank_row(h), **{k: 999.0 for k in U.blank_row(h) if k != "Hour"}} for h in range(24)]}
r5, _ = run(D23, stale)
check("23-hour day: stale values from the old (shifted) reading are all replaced, including H04", all(h.get("SCADA_TotalHydro") != 999.0 and h.get("MCP_GR") != 999.0 for h in r5["Hourly"]) and r5["Hourly"][3]["SCADA_TotalHydro"] is None and r5["Hourly"][3]["ISP_Kremasta"] is None, r5["Hourly"][3])
stale2 = {"Date": DN.isoformat(), "Hourly": [{**U.blank_row(h), "SCADA_Kremasta": 777.0} for h in range(24)]}
r6, _ = run(DN, stale2)
check("an ordinary day is untouched by the new rules: 24 rows, no ClockChange, values written as before", len(r6["Hourly"]) == 24 and "ClockChange" not in r6["Meta"] and rows_close([h.get("SCADA_Kremasta") for h in r6["Hourly"]], truth_clock(f_unit(0), DN)))
print("TEST 5: layouts and conventions")
LAYOUT["cols"] = 27; r7, _ = run(D25, only={"scada"}); LAYOUT["cols"] = 28
check("27-column SCADA on a 25-hour day (until March 2026): the 25th hour is recovered from the total", rows_close([h.get("SCADA_TotalHydro") for h in r7["Hourly"]], truth_clock(f_total, D25)) and close(U.day_summary(r7)["SCADA_TotalHydro_MWh"], tr_all(f_total), 0.2))
RESMV_STYLE[date(2024, 10, 27)] = "chrono25"; r8, _ = run(date(2024, 10, 27), only={"resmv"}); RESMV_STYLE.clear()
check("RESMV of 2024 (25 separate rows): chronological, H04 = mean, the rest shifted, energy preserved", rows_close([h.get("SCADA_SmallHydro") for h in r8["Hourly"]], truth_clock(f_small, date(2024, 10, 27))) and close(U.day_summary(r8)["SmallHydro_MWh"], sum(f_small(t) for t in inst(date(2024, 10, 27), ATH)), 0.2))
print("TEST 6: finding the file when the one-day list is empty (K26)")
HIDE_SINGLE.add(("RESMV", D25)); r9, l9 = run(D25, only={"resmv"}); HIDE_SINGLE.clear()
check("hidden from the one-day list: found with the wide window, and the log says so", rows_close([h.get("SCADA_SmallHydro") for h in r9["Hourly"]], truth_clock(f_small, D25)) and "ευρύ εύρος" in l9 and any(c[0] == "range" for c in CALLS), l9[-300:])
TWO_DAY.add(("RESMV", D23)); r10, l10 = run(D23, only={"resmv"}); TWO_DAY.clear()
check("a two-day entry [28→29 Mar] is taken for 29 Mar (the narrowest range containing the day), and the file — which really holds BOTH days — is read by ΗΜΕΡΑ: only the rows of 29 Mar are used", rows_close([h.get("SCADA_SmallHydro") for h in r10["Hourly"]], truth_clock(f_small, D23)), l10[-300:])
HIDE_SINGLE.add(("RESMV", D25)); UNKNOWN_NEIGHBOUR.add(("RESMV", D25)); r11, l11 = run(D25, only={"resmv"}); HIDE_SINGLE.clear(); UNKNOWN_NEIGHBOUR.clear()
check("in the wide window an entry WITHOUT dates is never accepted (it could be any day): the source stays missing", r11.get("Hourly") is None or all(h.get("SCADA_SmallHydro") is None for h in r11["Hourly"]), l11[-200:])
r12, l12 = run(DN, only={"resmv"})
check("an ordinary day needs no wide request (no extra load on the API)", not any(c[0] == "range" for c in CALLS), CALLS)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
