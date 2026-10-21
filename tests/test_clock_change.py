import sys, os, random
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
import clock_change as C
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
ATH, BRU, UTC = ZoneInfo("Europe/Athens"), ZoneInfo("Europe/Brussels"), ZoneInfo("UTC")
T0 = datetime(2026, 1, 1, tzinfo=UTC)
def v(t):                                   # the TRUTH: a distinct value for every real hour, a function of the UTC instant only
    return 50.0 + ((int((t - T0).total_seconds() // 3600) * 37) % 400)
def day_instants(d, tz):
    a = datetime.combine(d, dtime(0, 0), tzinfo=tz).astimezone(UTC); b = datetime.combine(d + timedelta(days=1), dtime(0, 0), tzinfo=tz).astimezone(UTC)
    return [a + timedelta(hours=i) for i in range(int(round((b - a).total_seconds() / 3600)))]
def truth_clock(d):                         # what the dashboard should show: the value of each CLOCK hour of the Greek day
    by = {h: [] for h in range(24)}
    for t in day_instants(d, ATH): by[t.astimezone(ATH).hour].append(v(t))
    return [None if not by[h] else sum(by[h]) / len(by[h]) for h in range(24)]
def scada_file(d):                          # REAL structure: chronological hour columns + daily total; 23 h: last column ~0; 25 h: the 25th hour only in the total
    ins = day_instants(d, ATH); vals = [v(t) for t in ins]; n = len(vals)
    cols = vals[:24] + ([1.0] if n == 23 else [])
    return cols[:24], sum(vals)
def isp_file(d):                            # market (CET) day: quarter-hours (each hour constant) + the total column (sum / 4)
    ins = day_instants(d, BRU); q = []
    for t in ins: q += [v(t)] * 4
    return q + [sum(q) / 4]
def old_isp_hourly(vals):                   # the pipeline today: the first 96 columns, mean of 4
    arr = U.to_numeric_array(vals, 96); return list(np.nanmean(np.array(arr, float).reshape(24, 4), axis=1))
print("TEST 1: hours in a day")
check("23 on 29 Mar 2026 and 30 Mar 2025, 25 on 25 Oct 2026 and 26 Oct 2025, 24 otherwise", [C.hours_in_day(date(2026, 3, 29)), C.hours_in_day(date(2025, 3, 30)), C.hours_in_day(date(2026, 10, 25)), C.hours_in_day(date(2025, 10, 26)), C.hours_in_day(date(2026, 3, 30)), C.hours_in_day(date(2026, 7, 1))] == [23, 23, 25, 25, 24, 24])
check("the CET (Brussels) market day has the same number of hours as the Greek day on every date of 2025 and 2026", all(len(day_instants(date(2025, 1, 1) + timedelta(days=i), BRU)) == C.hours_in_day(date(2025, 1, 1) + timedelta(days=i)) for i in range(730)))
print("TEST 2: SCADA — the clock hours recovered from the chronological file")
for d in (date(2026, 3, 28), date(2026, 3, 29), date(2025, 3, 30), date(2025, 10, 26), date(2026, 10, 25)):
    cols, tot = scada_file(d); rows, extra = C.scada_clock(cols, tot, d); tr = truth_clock(d); n = C.hours_in_day(d)
    check(f"{d} ({n} h): the 24 clock rows equal the truth hour by hour (None for the missing 03:00, the mean of the two for the repeated 03:00)", all((a is None and b is None) or (a is not None and b is not None and abs(a - b) < 1e-9) for a, b in zip(rows, tr)), (rows[:6], tr[:6]))
    allv = [v(t) for t in day_instants(d, ATH)]
    check(f"{d}: the day's energy is preserved: sum of the rows + the energy outside the 24 rows = sum of all {n} real hours = the file's total", abs(sum(x for x in rows if x is not None) + extra - sum(allv)) < 1e-6 and abs(sum(allv) - tot) < 1e-6, (sum(x for x in rows if x is not None), extra, sum(allv), tot))
    if n != 24:
        old = [x for x in cols[:24]]
        check(f"{d}: the CURRENT reading (24 columns labelled H01–H24) is wrong after 03:00 — this is the bug", old != tr, old[:6])
print("TEST 3: ISP — the K04 bug and its fix")
for d in (date(2026, 3, 29), date(2026, 3, 30), date(2025, 10, 26), date(2025, 10, 27), date(2026, 10, 25), date(2026, 10, 26), date(2026, 3, 28)):
    cur, prev = isp_file(d), isp_file(d - timedelta(days=1)); rows, extra = C.isp_clock(cur, prev, d); tr = truth_clock(d)
    check(f"{d}: the ISP in clock hours equals the truth hour by hour, including H01 (from the last REAL hour of the previous day)", all((a is None and b is None) or (a is not None and b is not None and abs(a - b) < 1e-9) for a, b in zip(rows, tr)), (rows[:4], tr[:4]))
d = date(2026, 3, 30); old_cur, old_prev = old_isp_hourly(isp_file(d)), old_isp_hourly(isp_file(d - timedelta(days=1)))
old = U.isp_to_local(old_cur, old_prev)
check("K04 reproduced with the CURRENT code: H01 of 30 Mar = the 23-hour day's total read as MW (more than 3 times any real value)", old[0] > 3 * max(v(t) for t in day_instants(d, ATH)) and abs(old[0] - truth_clock(d)[0]) > 100, old[0])
check("…and the NEW code gives the real value for that hour", abs(C.isp_clock(isp_file(d), isp_file(d - timedelta(days=1)), d)[0][0] - truth_clock(d)[0]) < 1e-9)
d = date(2026, 10, 26); old = U.isp_to_local(old_isp_hourly(isp_file(d)), old_isp_hourly(isp_file(d - timedelta(days=1))))
check("25 Oct → 26 Oct with the CURRENT code: H01 of 26 Oct takes the 24th hour of the 25-hour day instead of the 25th (wrong), the NEW code takes the 25th", abs(old[0] - truth_clock(d)[0]) > 1e-9 and abs(C.isp_clock(isp_file(d), isp_file(d - timedelta(days=1)), d)[0][0] - truth_clock(d)[0]) < 1e-9, (old[0], truth_clock(d)[0]))
print("TEST 4: edges")
d = date(2026, 3, 30); r, _ = C.isp_clock(isp_file(d), None, d)
check("the previous day's file missing: H01 is None and nothing else is invented", r[0] is None and r[1] == truth_clock(d)[1])
cols, tot = scada_file(date(2025, 10, 26)); r, extra = C.scada_clock(cols, None, date(2025, 10, 26))
check("25-hour SCADA without a total: the 25th hour is unknown (None), not invented; the 24 columns are still mapped", C.scada_chrono(cols, None, date(2025, 10, 26))[-1] is None and len(C.scada_chrono(cols, None, date(2025, 10, 26))) == 25)
check("25-hour SCADA whose total is smaller than the sum of the hours: no negative energy is invented", C.scada_chrono(cols, sum(cols) - 500, date(2025, 10, 26))[-1] is None)
nan = float("nan"); r = C.isp_chrono([nan] * 96 + [5.0], date(2026, 7, 1))
check("empty (NaN) quarter-hours give None for the hour, and the total column after the 96th is never read", r == [None] * 24 and C.isp_chrono([10.0] * 96 + [99999.0], date(2026, 7, 1)) == [10.0] * 24)
check("a 23-hour ISP day reads exactly 92 quarter-hours: the 93rd value (the total) is not used", C.isp_chrono([10.0] * 92 + [99999.0, nan, nan, nan], date(2026, 3, 29)) == [10.0] * 23)
rng = random.Random(7); ok = True
for dd in (date(2026, 3, 29), date(2026, 10, 25), date(2026, 5, 5)):
    n = C.hours_in_day(dd); ch = [rng.uniform(0, 1000) for _ in range(n)]; rows, extra = C.chrono_to_clock(ch, dd); ok &= abs(sum(x for x in rows if x is not None) + extra - sum(ch)) < 1e-6 and len(rows) == 24
check("property: for random series the energy is preserved on 23-, 24- and 25-hour days and there are always 24 rows", ok)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
