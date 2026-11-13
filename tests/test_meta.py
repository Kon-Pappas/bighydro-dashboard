import sys, os, io, json, tempfile, contextlib, importlib
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import write_meta as M
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
U = lambda *a: datetime(*a, tzinfo=timezone.utc)
def nxt(*a): return M.iso_z(M.next_update_utc(U(*a)))

print("TEST 1: next_update — the first scheduled run STRICTLY after now (Athens 07:15, 09:15, 10:15, 13:30)")
check("before the first run of the day (05:00 Athens, winter) -> 07:15 Athens = 05:15Z", nxt(2026, 11, 9, 3, 0) == "2026-11-09T05:15:00Z", nxt(2026, 11, 9, 3, 0))
check("between runs (09:30 Athens) -> 10:15 Athens = 08:15Z", nxt(2026, 11, 9, 7, 30) == "2026-11-09T08:15:00Z")
check("between the 10:15 and the 13:30 runs (11:00 Athens) -> 13:30 Athens = 11:30Z", nxt(2026, 11, 9, 9, 0) == "2026-11-09T11:30:00Z")
check("exactly at a run time the NEXT one is returned (13:30 Athens -> tomorrow 07:15), never the same instant", nxt(2026, 11, 9, 11, 30) == "2026-11-10T05:15:00Z", nxt(2026, 11, 9, 11, 30))
check("one second before a run time it is that run (07:14:59 Athens)", nxt(2026, 11, 9, 5, 14, 59) == "2026-11-09T05:15:00Z")
check("after the last run of the day -> tomorrow 07:15 Athens", nxt(2026, 11, 9, 12, 0) == "2026-11-10T05:15:00Z")
check("across a month end (31 Dec 14:00 Athens) -> 1 Jan 07:15 Athens", nxt(2026, 12, 31, 12, 0) == "2027-01-01T05:15:00Z")
print("TEST 2: the clock changes — the run is at 07:15 ATHENS TIME, not at a fixed UTC hour")
check("summer (+03:00): 06:00 Athens -> 07:15 Athens = 04:15Z (one hour earlier in UTC than in winter)", nxt(2026, 7, 9, 3, 0) == "2026-07-09T04:15:00Z", nxt(2026, 7, 9, 3, 0))
check("the day before the autumn change (24 Oct 2026, 14:00 Athens, +03:00) -> 25 Oct 07:15 Athens is +02:00 = 05:15Z, not 04:15Z", nxt(2026, 10, 24, 11, 0) == "2026-10-25T05:15:00Z", nxt(2026, 10, 24, 11, 0))
check("on the 25-hour day itself (25 Oct 2026, 02:00Z = 04:00 Athens) -> 07:15 Athens = 05:15Z", nxt(2026, 10, 25, 2, 0) == "2026-10-25T05:15:00Z")
check("the day before the spring change (27 Mar 2027, 14:00 Athens, +02:00) -> 28 Mar 07:15 Athens is +03:00 = 04:15Z", nxt(2027, 3, 27, 12, 0) == "2027-03-28T04:15:00Z", nxt(2027, 3, 27, 12, 0))
check("on the 23-hour day (28 Mar 2027, 03:00Z = 06:00 Athens) -> 07:15 Athens = 04:15Z", nxt(2027, 3, 28, 3, 0) == "2027-03-28T04:15:00Z")
print("TEST 3: the file — format, atomic write, one writer")
d = tempfile.mkdtemp(); p = os.path.join(d, "data", "meta.json")
m = M.write_meta(p, U(2026, 11, 9, 5, 4, 53, 123456))
check("keys are exactly fetched and next_update, UTC with Z and no microseconds", m == {"fetched": "2026-11-09T05:04:53Z", "next_update": "2026-11-09T05:15:00Z"} and json.load(open(p, encoding="utf-8")) == m, m)
check("the directory is created and no temporary file is left behind", os.listdir(os.path.dirname(p)) == ["meta.json"])
check("the file ends with a newline (clean diffs)", open(p, "rb").read().endswith(b"\n"))
m2 = M.write_meta(p, U(2026, 11, 9, 7, 16, 1))
check("it is rewritten on every run: the next run gives a new fetched and a LATER next_update (exception to D98, Option A)", m2["fetched"] == "2026-11-09T07:16:01Z" and m2["next_update"] == "2026-11-09T08:15:00Z" and json.load(open(p, encoding="utf-8")) == m2, m2)
open(p + ".tmp", "w").write("{ broken")
m3 = M.write_meta(p, U(2026, 11, 9, 9, 0)); check("a leftover temporary file from a crashed run is overwritten, never read", json.load(open(p, encoding="utf-8")) == m3 and not os.path.exists(p + ".tmp"))
print("TEST 4: main() — diagnose runs write nothing")
def run_main(env):
    old = {k: os.environ.get(k) for k in env}; [os.environ.__setitem__(k, v) for k, v in env.items()]
    cwd = os.getcwd(); os.chdir(tempfile.mkdtemp())
    try:
        s = io.StringIO()
        with contextlib.redirect_stdout(s): rc = M.main()
        return rc, s.getvalue(), os.path.exists(os.path.join("data", "meta.json"))
    finally:
        os.chdir(cwd); [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in old.items()]
rc, out, ex = run_main({"DIAGNOSE": "true"}); check("DIAGNOSE=true: rc 0, nothing written, a message says why", rc == 0 and not ex and "διάγνωσης" in out)
rc, out, ex = run_main({"DIAGNOSE": "false"}); check("DIAGNOSE=false: the file is written", rc == 0 and ex and "meta.json: fetched=" in out)
rc, out, ex = run_main({"DIAGNOSE": ""}); check("DIAGNOSE empty (a normal scheduled run): the file is written", rc == 0 and ex)
print("TEST 5: the schedule is one constant")
check("the four run times of the cron-job.org jobs are 07:15, 09:15, 10:15 and 13:30", tuple(M.UPDATE_TIMES_ATHENS) == ((7, 15), (9, 15), (10, 15), (13, 30)))
check("an empty list of times gives next_update null instead of crashing", (lambda: (setattr(M, "UPDATE_TIMES_ATHENS", ()), M.build_meta(U(2026, 11, 9, 5, 0)))[1])()["next_update"] is None); importlib.reload(M)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
