import sys, io, os, json, tempfile, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
b=io.StringIO()
with contextlib.redirect_stdout(b): ns=runpy.run_path(os.path.join(HERE,'test_v3.py'))
U=ns['U']; make_fake=ns['make_fake']; ALL=ns['ALL']; MCP_DOC=ns['MCP_DOC']
PASS=FAIL=0
def check(n,c,e=""):
    global PASS,FAIL
    if c: PASS+=1; print("  PASS",n)
    else: FAIL+=1; print("  FAIL",n,e)
def cap(fn,*a,**k):
    s=io.StringIO()
    with contextlib.redirect_stdout(s): r=fn(*a,**k)
    return r,s.getvalue()
def row(s,a,b): return {"SCADA_Pump":s,"ISP_PumpSfikia":a,"ISP_PumpThesavros":b}
print("TEST 1: pump_split logic")
r=U.pump_split([row(100,10,30),row(60,0,0),row(0,20,0),row(50,0,0),row(0,0,0)])
# hour1: ISP 40, share Sfikia 0.25 -> 25 / 75 ; hour2: no ISP, SCADA 60 -> day share 30/(30+30... compute: a_day=30,b_day=30 -> 0.5 -> 30/30 ; hour3: ISP only, scada 0 -> not realized 20 ; hour4: no ISP SCADA 50 -> day share 0.5 -> 25/25
check("SCADA / ISP totals",r["ScadaMWh"]==210 and r["IspMWh"]==60,r)
check("per-plant ISP",r["IspSfikiaMWh"]==30 and r["IspThesavrosMWh"]==30)
check("estimated split (25+30+25 / 75+30+25)",r["EstSfikiaMWh"]==80 and r["EstThesavrosMWh"]==130,(r["EstSfikiaMWh"],r["EstThesavrosMWh"]))
check("hourly vs day-share energy",r["ByHourlyShareMWh"]==100 and r["ByDayShareMWh"]==110 and r["UnallocatedMWh"]==0,r)
check("unscheduled = 110, not realized = 20",r["UnscheduledMWh"]==110 and r["NotRealizedMWh"]==20)
check("allocated energy conserves SCADA total",abs(r["EstSfikiaMWh"]+r["EstThesavrosMWh"]-r["ScadaMWh"])<0.2)
r=U.pump_split([row(40,0,0),row(60,0,0)]); check("no ISP at all that day -> unallocated, estimates 0",r["UnallocatedMWh"]==100 and r["EstSfikiaMWh"]==0 and r["EstThesavrosMWh"]==0,r)
r=U.pump_split([{"SCADA_Pump":None,"ISP_PumpSfikia":5,"ISP_PumpThesavros":5}]*3); check("no SCADA yet -> SCADA fields null, ISP kept",r["ScadaMWh"] is None and r["IspMWh"]==30 and r["EstSfikiaMWh"] is None,r)
check("no data at all -> None",U.pump_split([{"SCADA_Pump":None}]*2) is None and U.pump_split([]) is None)

print("TEST 2: pump_daily.json written by the pipeline")
tmp=tempfile.mkdtemp(); os.chdir(tmp); U.ENTSOE_TOKEN="x"
U.http_get=make_fake(ALL,MCP_DOC); sys.argv=['x','2026-10-03','2026-10-04']; rc,_=cap(U.main)
pdly=json.load(open('data/pump_daily.json'))
check("two days, ascending",rc==0 and [x["Date"] for x in pdly]==['2026-10-03','2026-10-04'],pdly)
x=pdly[1]
check("fixture: SCADA 300 MW all day = 7200 MWh; ISP 5+40 MW all day",x["ScadaMWh"]==7200 and x["IspSfikiaMWh"]==120 and x["IspThesavrosMWh"]==960,x)
check("estimate 5/45 vs 40/45 of 7200 = 800 / 6400",x["EstSfikiaMWh"]==800 and x["EstThesavrosMWh"]==6400,x)
check("nothing unscheduled / unallocated",x["UnscheduledMWh"]==0 and x["UnallocatedMWh"]==0 and x["ByHourlyShareMWh"]==7200)
print("TEST 3: file regenerated on a run that touches no day (derived data self-heals)")
os.remove('data/pump_daily.json'); sys.argv=['x','2026-10-03','2026-10-04']; rc,_=cap(U.main)
check("recreated",os.path.exists('data/pump_daily.json') and len(json.load(open('data/pump_daily.json')))==2)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
